"""
LangGraph tool-calling agent for the PAN Card Services end-to-end flow.

Deterministic safety gates (PII detection, confidence-based escalation) stay
as plain code, not LLM decisions -- consistent with how mas_engine.ask()
already keeps HITL/PII gating outside the model. Once those gates clear, the
LLM drives an open-ended "which tool do I need next" loop -- a standard
LangGraph ReAct-style agent (agent <-> tools), using the existing
backend/llm/ manager for generation. Tool selection is done via a prompted
JSON decision rather than native OpenAI function-calling, because the shared
LLM layer fans out across providers (Groq/Gemini/OpenRouter/HF/Grok) that
don't uniformly support native tool-calling, and this keeps that shared,
tested module untouched.
"""

from __future__ import annotations

import json
import re
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from . import pan_tracking
from .adaptive_response import detect_service_key, _term_matches
from .core_knowledge_pack import CORE_SERVICE_RECORDS, CORE_SERVICE_PROFILE_CONTEXTS
from .llm import default_manager as _llm_manager, AllProvidersFailedError
from .pii_patterns import has_personal_data

PAN_SERVICE_KEYS = ("new_pan", "pan_correction", "pan_reprint", "instant_epan")
RECORDS_BY_KEY = {r["key"]: r for r in CORE_SERVICE_RECORDS if r["key"] in PAN_SERVICE_KEYS}

MAX_AGENT_ITERATIONS = 4
CONFIDENCE_ESCALATION_THRESHOLD = 0.5


class PANState(TypedDict, total=False):
    query: str
    service_type: str
    applicant_label: str
    cloud_consent: bool
    confidence: float
    pii_blocked: bool
    escalated: bool
    escalation_reason: str
    confirmed_complaint: bool
    messages: list
    tool_calls_made: list
    iterations: int
    tracking_id: Optional[int]
    final_answer: str


# ---------------------------------------------------------------------------
# Tools -- real, independently callable Python functions. The agent picks
# among these; DB/HITL writes always read service_type/applicant_label from
# state (ground truth), never trust those specific fields from the LLM.
# ---------------------------------------------------------------------------

def _tool_lookup_guidance(state, args):
    service_type = state.get("service_type") or "new_pan"
    return CORE_SERVICE_PROFILE_CONTEXTS.get(service_type, "") or "No structured guidance found for this service."


def _tool_check_documents(state, args):
    record = RECORDS_BY_KEY.get(state.get("service_type"))
    if not record:
        return "Service type not recognized."
    lines = ["Prerequisites:"] + [f"- {item}" for item in record["prerequisites"]]
    lines += ["Documents:"] + [f"- {item}" for item in record["documents"]]
    return "\n".join(lines)


def _tool_check_eligibility(state, args):
    record = RECORDS_BY_KEY.get(state.get("service_type"))
    if not record:
        return "Service type not recognized."
    return f"Who can use: {record['who_can_use']}\nEligibility: {record['eligibility']}"


def _tool_create_tracking_record(state, args):
    guidance = (args or {}).get("guidance_summary") or state.get("query", "")
    tracking_id = pan_tracking.create_application(
        service_type=state.get("service_type") or "new_pan",
        applicant_label=state.get("applicant_label") or "citizen",
        guidance_shown=guidance,
        confidence=state.get("confidence", 0.0),
    )
    state["tracking_id"] = tracking_id
    if tracking_id is None:
        return "Could not create a tracking record (storage error)."
    return f"Tracking record created. Reference ID: PAN-{tracking_id}."


def _tool_escalate_to_officer(state, args):
    reason = (args or {}).get("reason") or "Agent requested human review"
    state["escalated"] = True
    state["escalation_reason"] = reason

    tracking_id = pan_tracking.escalate(
        app_id=state.get("tracking_id"),
        service_type=state.get("service_type") or "new_pan",
        applicant_label=state.get("applicant_label") or "citizen",
        query=state.get("query", ""),
        confidence=state.get("confidence", 0.0),
        reason=reason,
    )
    if tracking_id is None:
        return "Could not escalate (storage error)."
    state["tracking_id"] = tracking_id
    return f"Escalated to officer review. Reference: PAN-{tracking_id}."


def _tool_get_application_status(state, args):
    raw_id = (args or {}).get("tracking_id")
    if not raw_id:
        return "No tracking ID provided."
    try:
        app_id = int(str(raw_id).replace("PAN-", "").strip())
    except (ValueError, TypeError):
        return "Invalid tracking ID."
    record = pan_tracking.get_application(app_id)
    if not record:
        return "No application found with that tracking ID."
    return f"Status: {record['status']} (service: {record['service_type']}, last updated: {record['updated_at']})."


TOOLS = {
    "lookup_pan_guidance": {
        "fn": _tool_lookup_guidance,
        "description": "Get the full official step-by-step guidance for the citizen's PAN service.",
        "args": {},
    },
    "check_required_documents": {
        "fn": _tool_check_documents,
        "description": "List prerequisites and documents required for the PAN service.",
        "args": {},
    },
    "check_eligibility": {
        "fn": _tool_check_eligibility,
        "description": "Check who can use this PAN service and eligibility rules.",
        "args": {},
    },
    "create_tracking_record": {
        "fn": _tool_create_tracking_record,
        "description": "Create a local tracking record once real guidance has been given. Call once, near the end.",
        "args": {"guidance_summary": "short summary of the guidance given (string, no PII)"},
    },
    "escalate_to_officer": {
        "fn": _tool_escalate_to_officer,
        "description": "Escalate to a human officer when the request is ambiguous, out of scope, or too uncertain to guide safely.",
        "args": {"reason": "why this needs human review (string)"},
    },
    "get_application_status": {
        "fn": _tool_get_application_status,
        "description": "Look up the status of a previously created tracking record by its reference ID.",
        "args": {"tracking_id": "the tracking reference, e.g. 'PAN-12' or 12"},
    },
}


def _tools_prompt():
    lines = ["Available tools:"]
    for name, spec in TOOLS.items():
        args_desc = ", ".join(f"{k} ({v})" for k, v in spec["args"].items()) or "no arguments"
        lines.append(f"- {name}({args_desc}): {spec['description']}")
    return "\n".join(lines)


_DECISION_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_decision(content):
    if not content:
        return {"final_answer": ""}
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    match = _DECISION_RE.search(content)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            pass
    return {"final_answer": content.strip()}


# ---------------------------------------------------------------------------
# Deterministic pre-agent gates (PII + confidence) -- not LLM decisions.
# ---------------------------------------------------------------------------

_GENERIC_PAN_TERMS = ("pan", "pan card", "pancard", "पैन")

# Signals that a query is reporting a problem with a service already in
# progress (delay/non-delivery/dissatisfaction) rather than asking for
# guidance on how to use one -- a genuine complaint needs a human, not
# generic guidance, so a hit here forces straight-to-escalate.
_COMPLAINT_TERMS = (
    "complaint", "complain", "grievance",
    "not received", "not delivered", "not yet delivered", "not yet received",
    "have not received", "haven't received", "havent received",
    "did not receive", "didn't receive", "didnt receive",
    "still waiting", "still pending", "still not received",
    "not arrived", "hasn't arrived", "hasnt arrived", "has not arrived",
    "delayed", "delay in", "overdue", "not resolved", "no response",
    "not happy", "dissatisfied", "unsatisfied",
    "time frame", "timeframe", "beyond time", "as promised", "was promised", "was told",
)


def looks_like_complaint(query):
    """Deterministic keyword check -- not an LLM decision, same reasoning as
    the PII/confidence gates. Only used to decide whether to show the
    citizen a "file a complaint?" confirmation before running the pipeline;
    it never escalates by itself."""
    text = f" {(query or '').lower()} "
    return any(_term_matches(text, term) for term in _COMPLAINT_TERMS)


def _classify_and_score(query, service_type):
    resolved = service_type if service_type in RECORDS_BY_KEY else detect_service_key(query)
    if resolved in RECORDS_BY_KEY:
        context = CORE_SERVICE_PROFILE_CONTEXTS.get(resolved, "")
        confidence = 0.9 if context else 0.3
        return resolved, confidence

    # No specific sub-type matched (new/correction/reprint/instant e-PAN),
    # but the query clearly mentions PAN -- e.g. "how do I get a PAN card",
    # "my PAN card is lost, need a copy" don't contain the exact compound
    # phrases (new_pan/pan_reprint/etc. all require) that the strict keyword
    # lists look for. Rather than hard-escalating every naturally-phrased
    # PAN question to a human, default to new_pan (the most common starting
    # point) at a confidence that clears the agent gate -- the agent's own
    # tools (check_eligibility, check_required_documents) can still steer
    # the citizen to the right sub-service or escalate itself if genuinely
    # unclear. Only truly unrelated queries (no "pan" mention at all) still
    # hard-escalate below.
    text = f" {(query or '').lower()} "
    if any(_term_matches(text, term) for term in _GENERIC_PAN_TERMS):
        return "new_pan", 0.6

    return "", 0.2


def pii_guard_node(state: PANState) -> PANState:
    blocked = has_personal_data(f"{state.get('query', '')} {state.get('applicant_label', '')}")
    state["pii_blocked"] = blocked
    if blocked:
        state["final_answer"] = (
            "This request could not be processed because it appears to contain Aadhaar, PAN, "
            "or other sensitive personal data. Please remove any ID numbers/OTP and describe your "
            "PAN service need in words only -- enter actual numbers only on the official portal."
        )
        # Track that a blocked attempt happened (for an accurate audit trail /
        # dashboard count) without storing any of the actual query text --
        # only a fixed, generic note, never the flagged content itself.
        state["tracking_id"] = pan_tracking.create_application(
            service_type=state.get("service_type") or "new_pan",
            applicant_label=state.get("applicant_label") or "citizen",
            guidance_shown="[Request blocked: possible Aadhaar/PAN/OTP detected in input -- not stored]",
            confidence=0.0,
            status="blocked",
        )
    return state


def route_after_pii(state: PANState) -> str:
    return "blocked" if state.get("pii_blocked") else "classify"


def classify_node(state: PANState) -> PANState:
    resolved, confidence = _classify_and_score(state.get("query", ""), state.get("service_type", ""))
    state["service_type"] = resolved
    state["confidence"] = confidence
    return state


def route_after_classify(state: PANState) -> str:
    if state.get("confirmed_complaint") or state.get("confidence", 0.0) < CONFIDENCE_ESCALATION_THRESHOLD:
        return "escalate"
    return "agent"


def escalate_node(state: PANState) -> PANState:
    if state.get("confirmed_complaint"):
        _tool_escalate_to_officer(
            state,
            {"reason": "Detected as a complaint (service delay/non-delivery) -- needs human resolution, not guidance"},
        )
        state["final_answer"] = (
            "Thank you for letting us know, and sorry for the inconvenience. Your complaint has been logged "
            f"and escalated to an officer. Reference: PAN-{state.get('tracking_id')}. You'll be contacted for "
            "follow-up, or you can check Escalated to Officer for updates."
        )
    else:
        _tool_escalate_to_officer(state, {"reason": "Low confidence resolving PAN service from query"})
        state["final_answer"] = (
            "I couldn't confidently match this to a specific PAN service, so it has been sent to an "
            "officer for review. You'll be contacted, or you can check Escalated to Officer for updates."
        )
    return state


# ---------------------------------------------------------------------------
# Agent <-> tools loop.
# ---------------------------------------------------------------------------

def agent_node(state: PANState) -> PANState:
    messages = state.setdefault("messages", [])
    if not messages:
        system_prompt = (
            "You are a CSC (Common Service Centre) assistant helping a VLE guide a citizen through a "
            f"PAN card service ({state.get('service_type')}). You have tools to look up official guidance, "
            "documents, and eligibility, create a tracking record, escalate to a human officer, or check an "
            "existing application's status. Never ask for or repeat Aadhaar/PAN numbers/OTP. "
            "Respond with ONLY a single JSON object, either "
            '{"tool": "<tool_name>", "args": {...}} to call a tool, or '
            '{"final_answer": "<text>"} once you have enough information for a complete answer. '
            "Call create_tracking_record once you've given real guidance, before your final answer.\n\n"
            + _tools_prompt()
        )
        messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": f"Citizen's request: {state.get('query', '')}"})

    try:
        result = _llm_manager.generate(messages, task="rag_answer", temperature=0.1, max_tokens=500)
        content = result.content
    except AllProvidersFailedError:
        content = json.dumps({"final_answer": ""})

    messages.append({"role": "assistant", "content": content})
    state["_decision"] = _parse_decision(content)
    state["iterations"] = state.get("iterations", 0) + 1
    return state


def route_after_agent(state: PANState) -> str:
    if state.get("iterations", 0) >= MAX_AGENT_ITERATIONS:
        return "finalize"
    decision = state.get("_decision", {})
    if isinstance(decision, dict) and decision.get("tool") in TOOLS:
        return "tools"
    return "finalize"


def tools_node(state: PANState) -> PANState:
    decision = state.get("_decision", {}) or {}
    tool_name = decision.get("tool")
    args = decision.get("args") if isinstance(decision.get("args"), dict) else {}
    spec = TOOLS.get(tool_name)

    if not spec:
        result_text = f"Unknown tool '{tool_name}'."
    else:
        try:
            result_text = spec["fn"](state, args)
        except Exception as exc:
            result_text = f"Tool '{tool_name}' failed: {exc}"

    state.setdefault("tool_calls_made", []).append(tool_name)
    state.setdefault("messages", []).append(
        {"role": "user", "content": f"Result of {tool_name}: {result_text}"}
    )
    return state


def finalize_node(state: PANState) -> PANState:
    decision = state.get("_decision", {}) or {}
    if decision.get("final_answer"):
        state["final_answer"] = decision["final_answer"]
    elif not state.get("final_answer"):
        state["final_answer"] = (
            "Here is what I found:\n\n"
            + (CORE_SERVICE_PROFILE_CONTEXTS.get(state.get("service_type", "")) or "Please consult the official PAN portal.")
        )

    # Tracking-record creation was previously left entirely to the agent
    # choosing to call create_tracking_record -- but the LLM often just
    # answers directly without calling any tool (observed: tool_calls_made
    # empty on a fully successful run), so most successful requests never
    # showed up in Tracked Requests/Analytics at all. Every request that
    # reaches here (not blocked, not escalated) got real guidance, so it
    # should always be tracked -- this is bookkeeping, not a judgment call,
    # same reasoning as why the PII/escalation gates aren't left to the LLM.
    if not state.get("tracking_id"):
        _tool_create_tracking_record(state, {"guidance_summary": state["final_answer"]})

    return state


def build_pan_graph():
    graph = StateGraph(PANState)
    graph.add_node("pii_guard", pii_guard_node)
    graph.add_node("classify", classify_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "pii_guard")
    graph.add_conditional_edges("pii_guard", route_after_pii, {"blocked": END, "classify": "classify"})
    graph.add_conditional_edges("classify", route_after_classify, {"escalate": "escalate", "agent": "agent"})
    graph.add_edge("escalate", END)
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "finalize": "finalize"})
    graph.add_edge("tools", "agent")
    graph.add_edge("finalize", END)

    return graph.compile()


def _initial_state(service_type, query, applicant_label, cloud_consent, confirmed_complaint=False) -> PANState:
    return {
        "query": query or "",
        "service_type": service_type or "",
        "applicant_label": applicant_label or "citizen",
        "cloud_consent": bool(cloud_consent),
        "pii_blocked": False,
        "escalated": False,
        "escalation_reason": "",
        "confirmed_complaint": bool(confirmed_complaint),
        "messages": [],
        "tool_calls_made": [],
        "iterations": 0,
        "tracking_id": None,
        "final_answer": "",
    }


def _finalize_result(final_state: dict, node_sequence: list) -> dict:
    return {
        "final_answer": final_state.get("final_answer", ""),
        "service_type": final_state.get("service_type", ""),
        "confidence": final_state.get("confidence", 0.0),
        "pii_blocked": final_state.get("pii_blocked", False),
        "escalated": final_state.get("escalated", False),
        "escalation_reason": final_state.get("escalation_reason", ""),
        "confirmed_complaint": final_state.get("confirmed_complaint", False),
        "tracking_id": final_state.get("tracking_id"),
        "tool_calls_made": final_state.get("tool_calls_made", []),
        "node_sequence": node_sequence,
    }


class PANOrchestrator:
    def __init__(self):
        self._graph = build_pan_graph()

    def run(self, service_type, query, applicant_label, cloud_consent=False, confirmed_complaint=False):
        """Blocking, single-call convenience wrapper -- runs the whole graph
        and returns the final result. Use .stream() instead when you want to
        show live per-node progress in a UI (see PAN Mitra's New Request
        tab, which streams this exactly like TMF's TMFOrchestrator.run())."""
        initial_state = _initial_state(service_type, query, applicant_label, cloud_consent, confirmed_complaint)
        node_sequence = []
        final_state = dict(initial_state)
        for update in self._graph.stream(initial_state, stream_mode="updates"):
            for node_name, partial_state in update.items():
                node_sequence.append(node_name)
                final_state.update(partial_state)
        return _finalize_result(final_state, node_sequence)

    def stream(self, service_type, query, applicant_label, cloud_consent=False, confirmed_complaint=False):
        """Generator: yields (node_name, result_dict_so_far) after each node
        completes, so a caller can advance it one step per Streamlit rerun
        and render genuinely live progress instead of a post-hoc trace."""
        initial_state = _initial_state(service_type, query, applicant_label, cloud_consent, confirmed_complaint)
        node_sequence = []
        final_state = dict(initial_state)
        for update in self._graph.stream(initial_state, stream_mode="updates"):
            for node_name, partial_state in update.items():
                node_sequence.append(node_name)
                final_state.update(partial_state)
                yield node_name, _finalize_result(final_state, node_sequence)

    def graph_mermaid(self):
        return self._graph.get_graph().draw_mermaid()

    def graph_mermaid_png(self):
        """Rendered diagram image (calls a remote mermaid rendering service --
        needs network access). Returns None on any failure so callers can
        fall back to the offline .graph_mermaid() text instead of crashing."""
        try:
            return self._graph.get_graph().draw_mermaid_png()
        except Exception:
            return None


default_orchestrator = PANOrchestrator()
