"""
PAN Mitra — Main Application
A single-purpose PAN card services assistant: New PAN, Correction, Reprint,
and Instant e-PAN, guided end-to-end by a LangGraph tool-calling agent
(agent <-> tools loop), with local request tracking, officer escalation,
a live pipeline view, and analytics.
"""

import sys
import os
import logging
from datetime import datetime

# ── Python path ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pandas as pd
import streamlit as st

logging.basicConfig(level=logging.INFO)

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="PAN Mitra",
    page_icon="🪪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ──────────────────────────────────────────────────────────────
from components.styles import apply_global_css
from components.sidebar import render_sidebar
from components.header import chakra_svg
from components.mermaid import render_mermaid

apply_global_css()

# ── Backend imports (all wrapped; no crash on missing deps) ───────────────────
try:
    from backend.pan_graph import default_orchestrator, CONFIDENCE_ESCALATION_THRESHOLD
    from backend import pan_tracking
    BACKEND_READY = True
except ImportError as e:
    logging.error(f"backend.pan_graph/pan_tracking: {e}")
    default_orchestrator = None
    CONFIDENCE_ESCALATION_THRESHOLD = 0.5
    pan_tracking = None
    BACKEND_READY = False

try:
    from backend.llm import default_manager as _llm_manager, AllProvidersFailedError as _LLMAllFailedError
    from backend.llm import user_override as _llm_override
    LLM_PROVIDER_UI_READY = True
except ImportError as e:
    logging.error(f"backend.llm: {e}")
    _llm_manager = None
    _LLMAllFailedError = Exception
    _llm_override = None
    LLM_PROVIDER_UI_READY = False


# ── Constants ─────────────────────────────────────────────────────────────────
SERVICE_OPTIONS = [
    ("", "🤖 Not sure — let the assistant detect"),
    ("new_pan", "🆕 New PAN Application"),
    ("pan_correction", "✏️ PAN Correction / Change"),
    ("pan_reprint", "🔁 PAN Reprint / Duplicate PAN"),
    ("instant_epan", "⚡ Instant e-PAN (free, Aadhaar-based)"),
]
SERVICE_LABELS = {key: label for key, label in SERVICE_OPTIONS if key}
SERVICE_LABELS[""] = "Unresolved"
SERVICE_KEY_BY_LABEL = {label: key for key, label in SERVICE_OPTIONS}

STATUS_META = {
    "guidance_provided": ("Guidance Provided", "blue", "#1d4ed8"),
    "escalated": ("Escalated", "amber", "#d97706"),
    "submitted_by_vle": ("Submitted", "blue", "#005bac"),
    "completed": ("Completed", "green", "#16a34a"),
    "blocked": ("Blocked (PII)", "red", "#dc2626"),
}

NODE_LABELS = {
    "pii_guard": "🛡️ PII Guard",
    "classify": "🧭 Classify",
    "escalate": "🧑‍💼 Escalate",
    "agent": "🤖 Agent",
    "tools": "🔧 Tools",
    "finalize": "✅ Finalize",
}


# ── Tab renderers ────────────────────────────────────────────────────────────
def _render_live_node_flow(sequence, active_node=None, blocked=False):
    """Renders the growing chain of nodes completed so far, plus one more box
    for the node currently running (pulsing) if given. Grows left-to-right as
    the generator advances -- handles the agent<->tools loop naturally since
    it's just appending, not indexing into a fixed set of positions."""
    boxes = []
    for node in sequence:
        css_class = "pan-node-tool" if node == "tools" else "pan-node-done"
        boxes.append(f'<div class="pan-node {css_class}">{NODE_LABELS.get(node, node)}</div>')
        boxes.append('<div class="pan-arrow">→</div>')
    if active_node:
        css_class = "pan-node-blocked" if blocked else "pan-node-active"
        boxes.append(f'<div class="pan-node {css_class}">{NODE_LABELS.get(active_node, active_node)} …</div>')
    elif boxes:
        boxes.pop()  # no active node after the last completed one -> drop the trailing arrow
    st.markdown(f'<div class="pan-node-flow">{"".join(boxes)}</div>', unsafe_allow_html=True)


def _render_pan_result(result):
    st.markdown('<div class="section-hdr">Result</div>', unsafe_allow_html=True)
    if result["pii_blocked"]:
        st.error(result["final_answer"])
    elif result["escalated"]:
        st.warning(result["final_answer"])
        st.caption("This request is now in the Escalated to Officer tab.")
    else:
        badges = ""
        if result.get("tracking_id"):
            badges += f'<span class="csc-badge csc-badge-green">Reference: PAN-{result["tracking_id"]}</span> '
        badges += f'<span class="csc-badge csc-badge-blue">{SERVICE_LABELS.get(result["service_type"], "Unresolved")}</span> '
        badges += f'<span class="csc-badge csc-badge-amber">Confidence {result["confidence"]:.2f}</span>'
        st.markdown(badges, unsafe_allow_html=True)
        if result.get("tool_calls_made"):
            chips = "".join(f'<span class="pan-tool-chip">🔧 {t}</span>' for t in result["tool_calls_made"])
            st.markdown(chips, unsafe_allow_html=True)
        st.markdown("")
        st.markdown(result["final_answer"])


def _render_new_request():
    st.markdown('<div class="section-hdr">Start a PAN Service Request</div>', unsafe_allow_html=True)
    st.warning(
        "⚠️ Never enter Aadhaar number, PAN number, OTP, or bank details here. Describe the need in words only — "
        "actual ID numbers are entered only on the official government portal."
    )

    with st.form("pan_new_request_form"):
        service_label = st.selectbox("PAN service", options=[label for _, label in SERVICE_OPTIONS], key="pan_form_service")
        applicant_label = st.text_input(
            "Applicant display label",
            placeholder="e.g. Citizen at Counter 2 (no real name/ID required)",
            max_chars=100,
            key="pan_form_applicant",
        )
        query = st.text_area(
            "What does the citizen need help with?",
            placeholder="e.g. I want to apply for a new PAN card, what documents do I need?",
            height=100,
            key="pan_form_query",
        )
        cloud_consent = st.checkbox("Citizen consents to cloud AI processing", value=True, key="pan_form_consent")
        col_submit, col_clear = st.columns([3, 1])
        with col_submit:
            submitted = st.form_submit_button("Submit Request", type="primary", use_container_width=True)
        with col_clear:
            cleared = st.form_submit_button("🔄 Clear", use_container_width=True)

    if cleared:
        for key in (
            "pan_run_gen", "pan_run_result", "pan_run_error", "pan_run_phase",
            "pan_last_result", "pan_last_result_at",
            "pan_form_service", "pan_form_applicant", "pan_form_query",
            "pan_form_consent",
        ):
            st.session_state.pop(key, None)
        st.rerun()

    if submitted:
        if not query.strip():
            st.error("Please describe what the citizen needs help with.")
        else:
            st.session_state["pan_run_gen"] = default_orchestrator.stream(
                service_type=SERVICE_KEY_BY_LABEL[service_label],
                query=query.strip(),
                applicant_label=applicant_label.strip() or "citizen",
                cloud_consent=cloud_consent,
            )
            st.session_state["pan_run_result"] = None
            st.session_state["pan_run_error"] = None
            st.session_state["pan_run_phase"] = "advance"
            st.rerun()

    phase = st.session_state.get("pan_run_phase", "idle")
    flow_placeholder = st.empty()
    detail_placeholder = st.empty()

    # Every transition below ends in st.rerun() rather than relying on
    # mid-script placeholder updates to reach the browser on their own --
    # under real hosting (proxy/queueing), updates made before a later
    # blocking call (the agent node's LLM call) aren't guaranteed to flush
    # until control returns. st.rerun() is Streamlit's own guaranteed
    # commit point, so each stage is genuinely delivered. Same fix TMF's
    # Live Ingestion Demo needed for its own blocking Indexing/Sync calls.
    if phase == "advance":
        prior_result = st.session_state.get("pan_run_result")
        with flow_placeholder.container():
            st.markdown('<div class="section-hdr">Live Pipeline</div>', unsafe_allow_html=True)
            _render_live_node_flow(prior_result["node_sequence"] if prior_result else [])

        try:
            node_name, result = next(st.session_state["pan_run_gen"])
            st.session_state["pan_run_result"] = result
            about_to_run_agent = (
                (node_name == "classify" and result["confidence"] >= CONFIDENCE_ESCALATION_THRESHOLD)
                or node_name == "tools"
            )
            st.session_state["pan_run_phase"] = "waiting_agent" if about_to_run_agent else "advance"
        except StopIteration:
            st.session_state["pan_last_result"] = st.session_state.get("pan_run_result")
            st.session_state["pan_last_result_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            st.session_state["pan_run_phase"] = "done"
            st.session_state.pop("pan_run_gen", None)
        except Exception:
            import traceback
            st.session_state["pan_run_error"] = traceback.format_exc()
            st.session_state["pan_run_phase"] = "done"
            st.session_state.pop("pan_run_gen", None)
        st.rerun()

    elif phase == "waiting_agent":
        result = st.session_state.get("pan_run_result")
        with flow_placeholder.container():
            st.markdown('<div class="section-hdr">Live Pipeline</div>', unsafe_allow_html=True)
            _render_live_node_flow(result["node_sequence"] if result else [], active_node="agent")
        with detail_placeholder.container():
            st.info("🤖 Agent is thinking — deciding which tool to call next…")
        st.session_state["pan_run_phase"] = "advance"
        st.rerun()

    elif phase == "done":
        if st.session_state.get("pan_run_error"):
            st.error("The pipeline crashed. Showing the traceback from that attempt:")
            with st.expander("Full traceback (for debugging)", expanded=True):
                st.code(st.session_state["pan_run_error"], language="text")
        else:
            result = st.session_state.get("pan_run_result")
            if result:
                with flow_placeholder.container():
                    st.markdown('<div class="section-hdr">Live Pipeline</div>', unsafe_allow_html=True)
                    _render_live_node_flow(result["node_sequence"])
                _render_pan_result(result)


def _render_tracked_requests():
    st.markdown('<div class="section-hdr">Tracked PAN Requests</div>', unsafe_allow_html=True)
    status_label_by_key = {key: meta[0] for key, meta in STATUS_META.items()}
    status_key_by_label = {"All": "All", **{label: key for key, label in status_label_by_key.items()}}
    service_key_by_label_no_blank = {label: key for key, label in SERVICE_OPTIONS if key}
    service_key_by_label_no_blank["All"] = "All"

    fc1, fc2 = st.columns(2)
    status_filter_label = fc1.selectbox("Status", ["All"] + list(status_label_by_key.values()))
    service_filter_label = fc2.selectbox("Service type", ["All"] + [label for key, label in SERVICE_OPTIONS if key])

    status_filter = status_key_by_label[status_filter_label]
    service_filter = service_key_by_label_no_blank[service_filter_label]

    applications = pan_tracking.list_applications(
        status=None if status_filter == "All" else status_filter,
        service_type=None if service_filter == "All" else service_filter,
        limit=50,
    )
    if not applications:
        st.caption("No tracked requests yet — submit one from New Request.")

    for app in applications:
        label, color, _ = STATUS_META.get(app["status"], (app["status"], "blue", "#1d4ed8"))
        with st.container():
            c1, c2, c3 = st.columns([3, 3, 1.4])
            c1.markdown(
                f'<b>PAN-{app["id"]}</b> · {SERVICE_LABELS.get(app["service_type"], app["service_type"])}<br>'
                f'<span class="csc-badge csc-badge-{color}">{label}</span>',
                unsafe_allow_html=True,
            )
            with c2:
                st.caption(f"Applicant: {app['applicant_label']}")
                st.caption(f"Updated: {app['updated_at']}")
            with c3:
                if app["status"] == "guidance_provided":
                    if st.button("Mark Submitted", key=f"pan_submit_{app['id']}", use_container_width=True):
                        pan_tracking.update_status(app["id"], "submitted_by_vle")
                        st.rerun()
                elif app["status"] == "submitted_by_vle":
                    if st.button("Mark Completed", key=f"pan_complete_{app['id']}", use_container_width=True):
                        pan_tracking.update_status(app["id"], "completed")
                        st.rerun()
            with st.expander("Guidance shown"):
                st.write(app.get("guidance_shown") or "—")
        st.markdown("<hr style='margin:.2rem 0;border-color:var(--border)'>", unsafe_allow_html=True)


def _render_escalated():
    st.markdown('<div class="section-hdr">Escalated to Officer (PAN)</div>', unsafe_allow_html=True)
    reviews = pan_tracking.list_pending_escalations(limit=50)
    if not reviews:
        st.caption("No PAN requests currently awaiting officer review.")
    for item in reviews:
        rid = item["id"]
        with st.container():
            st.markdown(
                f'<div class="csc-card"><b>PAN-{rid}</b> · {SERVICE_LABELS.get(item["service_type"], item["service_type"])} · '
                f'{item.get("escalation_reason") or "Needs human review"} · confidence {item["confidence"]:.2f}<br>'
                f'<small style="color:var(--muted)">{item.get("created_at","")}</small></div>',
                unsafe_allow_html=True,
            )
            st.caption(f"Applicant: {item.get('applicant_label', '')}")
            if item.get("query"):
                st.caption(f"Query: {item['query']}")
            if st.button(f"✅ Reviewed (PAN-{rid})", key=f"pan_hitl_{rid}"):
                if pan_tracking.resolve_escalation(rid, operator_note="Reviewed via PAN Mitra"):
                    st.success(f"PAN-{rid} resolved.")
                    st.rerun()


def _render_pipeline():
    st.markdown('<div class="section-hdr">LangGraph Pipeline — Last Run</div>', unsafe_allow_html=True)
    st.caption("PAN Mitra's agent is a LangGraph tool-calling loop (agent ⇄ tools), not a fixed script — the LLM picks which of 6 real tools to call each turn.")
    result = st.session_state.get("pan_last_result")
    if not result:
        st.info("Submit a request in New Request to see the live pipeline trace here.")
    else:
        sequence = result.get("node_sequence", [])
        nodes_html = []
        for i, node in enumerate(sequence):
            css_class = "pan-node-done"
            if node == "pii_guard" and result.get("pii_blocked"):
                css_class = "pan-node-blocked"
            elif node == "tools":
                css_class = "pan-node-tool"
            nodes_html.append(f'<div class="pan-node {css_class}">{NODE_LABELS.get(node, node)}</div>')
            if i < len(sequence) - 1:
                nodes_html.append('<div class="pan-arrow">→</div>')
        st.markdown(f'<div class="pan-node-flow">{"".join(nodes_html)}</div>', unsafe_allow_html=True)

        if result.get("tool_calls_made"):
            st.markdown("**Tools actually called this run:**")
            chips = "".join(f'<span class="pan-tool-chip">🔧 {t}</span>' for t in result["tool_calls_made"])
            st.markdown(chips, unsafe_allow_html=True)
        else:
            st.caption("No tools were called on this run (blocked or escalated before reaching the agent loop).")

        with st.expander("View LangGraph definition (Mermaid)", expanded=False):
            render_mermaid(default_orchestrator.graph_mermaid())
            st.caption("Raw Mermaid source (if the diagram above doesn't render, e.g. offline):")
            st.code(default_orchestrator.graph_mermaid(), language="text")


_STATUS_STYLE = {
    "Guidance Provided": "background-color: #dbeafe; color: #1d4ed8; font-weight: 600",
    "Escalated": "background-color: #fef3c7; color: #92400e; font-weight: 600",
    "Submitted": "background-color: #dbeafe; color: #1d4ed8; font-weight: 600",
    "Completed": "background-color: #dcfce7; color: #166534; font-weight: 600",
    "Blocked (PII)": "background-color: #fee2e2; color: #991b1b; font-weight: 600",
}


def _style_status_column(val):
    return _STATUS_STYLE.get(val, "")


def _render_analytics(stats, by_status):
    status_label_by_key = {key: meta[0] for key, meta in STATUS_META.items()}
    all_status_labels = list(status_label_by_key.values())
    all_service_labels = [label for key, label in SERVICE_OPTIONS if key]

    st.markdown('<div class="section-hdr">Filters</div>', unsafe_allow_html=True)
    fc1, fc2 = st.columns(2)
    status_filter = fc1.multiselect("Status", all_status_labels, default=all_status_labels)
    service_filter = fc2.multiselect("Service type", all_service_labels, default=all_service_labels)

    selected_status_keys = {key for key, label in status_label_by_key.items() if label in status_filter}
    selected_service_keys = {SERVICE_KEY_BY_LABEL[label] for label in service_filter}

    applications = pan_tracking.list_applications(limit=200)
    filtered = [
        a for a in applications
        if a["status"] in selected_status_keys and a["service_type"] in selected_service_keys
    ]

    if not applications:
        st.info("No tracked requests yet — analytics will populate once requests come in via New Request.")
        return
    if not filtered:
        st.info("No requests match the selected filters.")
        return

    st.markdown(f"**{len(filtered)} requests** matching filters, out of {stats.get('total', 0)} total")

    rows = [
        {
            "Reference": f"PAN-{a['id']}",
            "Service": SERVICE_LABELS.get(a["service_type"], a["service_type"]),
            "Status": status_label_by_key.get(a["status"], a["status"]),
            "Confidence": round(a["confidence"], 2),
            "Applicant": a["applicant_label"],
            "Updated": a["updated_at"],
        }
        for a in filtered
    ]
    df = pd.DataFrame(rows)
    styled = df.style.map(_style_status_column, subset=["Status"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-hdr">By Service Type</div>', unsafe_allow_html=True)
    by_service_type = {}
    for a in filtered:
        by_service_type.setdefault(a["service_type"], []).append(a)

    for service_key, apps in by_service_type.items():
        escalated_count = sum(1 for a in apps if a["status"] == "escalated")
        completed_count = sum(1 for a in apps if a["status"] == "completed")
        label = SERVICE_LABELS.get(service_key, service_key)
        with st.expander(f"{label} — {len(apps)} requests · {escalated_count} escalated · {completed_count} completed"):
            for a in apps:
                status_label = status_label_by_key.get(a["status"], a["status"])
                line = f"**PAN-{a['id']}** — {a['applicant_label']} — confidence {a['confidence']:.2f} — updated {a['updated_at']}"
                if a["status"] == "escalated":
                    st.warning(line)
                elif a["status"] == "completed":
                    st.success(line)
                else:
                    st.info(f"{line} — {status_label}")


def _render_ai_provider_picker():
    """Always-visible AI Provider picker -- rendered above the tabs (not
    inside Settings) because it kept getting lost when the tab bar
    overflowed the browser width and Settings scrolled out of view."""
    if not LLM_PROVIDER_UI_READY:
        st.caption("LLM provider registry not available.")
        return

    registry = _llm_manager.registry
    model_ids = registry.all_model_ids()
    current_override = _llm_override.get_override()
    current_model_id = current_override.get("model_id", "")

    auto_label = "Auto (fallback chain)"
    options = [auto_label] + [registry.display_name(mid) for mid in model_ids]
    id_by_label = {registry.display_name(mid): mid for mid in model_ids}
    default_index = 0
    if current_model_id in model_ids:
        default_index = options.index(registry.display_name(current_model_id))

    c1, c2 = st.columns(2)
    with c1:
        chosen_label = st.selectbox("Preferred AI provider", options, index=default_index, key="llm_provider_choice")
    with c2:
        api_key_input = st.text_input(
            "API key",
            type="password",
            key="llm_provider_key",
            placeholder="Leave blank to use the key already in .env",
        )
    save_default = st.checkbox(
        "Save as default (persists across restarts)",
        value=_llm_override.has_persisted_override(),
        key="llm_provider_save_default",
    )

    if st.button("Apply & Test Connection", key="llm_provider_apply"):
        if chosen_label == auto_label:
            _llm_override.clear_override(persist=save_default)
            st.success("Using the automatic fallback chain (priority + health + telemetry scoring).")
        else:
            model_id = id_by_label[chosen_label]
            _llm_override.set_override(model_id, api_key_input.strip() or None, persist=save_default)
            with st.spinner(f"Testing {chosen_label}…"):
                try:
                    test_result = _llm_manager.generate(
                        [{"role": "user", "content": "Reply with the single word OK."}],
                        task="rag_answer",
                        max_tokens=10,
                    )
                    if test_result.model_id == model_id:
                        st.success(
                            f"✅ {chosen_label} responded: {test_result.content!r} "
                            f"({test_result.latency_ms:.0f} ms)"
                        )
                    else:
                        st.warning(
                            f"⚠️ {chosen_label} itself did not respond (check the key/model name) — "
                            f"the automatic fallback chain answered instead via `{test_result.model_id}`: "
                            f"{test_result.content!r}"
                        )
                except _LLMAllFailedError as exc:
                    st.error(f"❌ {chosen_label} did not respond, and neither did any fallback: {exc}")
            if save_default:
                st.caption("Saved as default — future app restarts will use this provider first.")


def _render_settings():
    st.markdown('<div class="section-hdr">Appearance</div>', unsafe_allow_html=True)
    st.toggle("🌙 Dark Mode", key="dark_mode",
              help="Dark mode affects sidebar; full dark mode requires browser extension.")

    st.caption("🤖 AI Provider has moved above the tabs — always visible, click to expand.")

    st.markdown('<div class="section-hdr">Backend Status</div>', unsafe_allow_html=True)
    checks = [
        ("PAN Agent (LangGraph)", default_orchestrator is not None),
        ("PAN Tracking + Escalation DB", pan_tracking is not None),
        ("LLM Provider Registry", LLM_PROVIDER_UI_READY),
    ]
    c1, c2 = st.columns(2)
    for i, (name, ok) in enumerate(checks):
        badge = "csc-badge-green" if ok else "csc-badge-red"
        icon = "✓" if ok else "✗"
        (c1 if i % 2 == 0 else c2).markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:.45rem 0;border-bottom:1px solid var(--border);font-size:.87rem">'
            f'<span>{name}</span>'
            f'<span class="csc-badge {badge}">{icon} {"OK" if ok else "Unavailable"}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_home_hero(stats):
    by_status = stats.get("by_status", {})
    st.markdown(
        f"""
<div class="pan-cover">
  {chakra_svg("pan-cover-chakra")}
  <div class="pan-cover-content">
    <div class="pan-cover-eyebrow">Common Service Centre · DPDP Compliant</div>
    <h1 class="pan-cover-title">🪪 PAN Mitra</h1>
    <div class="pan-cover-underline"></div>
    <p class="pan-cover-tagline">Where PAN card services converge — guided end-to-end by a LangGraph tool-calling agent.</p>
    <div class="pan-cover-stats">
      <div class="pan-cover-stat"><div class="n">{stats.get('total', 0)}</div><div class="l">Total Requests</div></div>
      <div class="pan-cover-stat"><div class="n">{by_status.get('guidance_provided', 0)}</div><div class="l">Guidance Provided</div></div>
      <div class="pan-cover-stat"><div class="n">{by_status.get('escalated', 0)}</div><div class="l">Escalated</div></div>
      <div class="pan-cover-stat"><div class="n">{by_status.get('completed', 0)}</div><div class="l">Completed</div></div>
    </div>
    <div class="pan-cover-chips">
      <span class="pan-cover-chip">🆕 New PAN</span>
      <span class="pan-cover-chip">✏️ Correction</span>
      <span class="pan-cover-chip">🔁 Reprint</span>
      <span class="pan-cover-chip">⚡ Instant e-PAN</span>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_landing_page(stats):
    # Full-bleed takeover: no sidebar, no Streamlit header, no block-container
    # padding -- matches how TMF's own splash hides all Streamlit chrome
    # instead of squeezing a hero into the already-padded, sidebar-narrowed
    # layout (that's why "full screen" kept not looking full screen before).
    st.markdown(
        """
<style>
section[data-testid="stSidebar"] { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }
</style>
""",
        unsafe_allow_html=True,
    )

    _render_home_hero(stats)

    st.markdown(
        '<div style="max-width:900px;margin:0 auto;padding:0 2rem">'
        '<div class="section-hdr">🤖 AI Provider — pick a model and enter your key here</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    _, mid_ai, _ = st.columns([0.5, 5, 0.5])
    with mid_ai:
        _render_ai_provider_picker()

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    _, mid_btn, _ = st.columns([2, 1, 2])
    with mid_btn:
        if st.button("Enter PAN Mitra →", type="primary", use_container_width=True, key="enter_pan_mitra"):
            st.session_state["pan_entered"] = True
            st.rerun()

    st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)

    capabilities = [
        ("🆕", "New Request", "Start a PAN request — the LangGraph agent picks the right tools to guide the citizen end-to-end."),
        ("📋", "Tracked Requests", "Every request tracked locally with status, from guidance-provided through completed."),
        ("⚠️", "Escalated to Officer", "Low-confidence or agent-flagged requests route to a human review queue automatically."),
        ("🕸️", "Pipeline View", "Watch the LangGraph agent ⇄ tools loop live, node by node, as it actually runs."),
        ("📊", "Analytics", "Filterable, styled request tables — status and service-type breakdowns at a glance."),
        ("🤖", "AI Provider Control", "Pick Groq, Gemini, OpenAI, Anthropic, or more — test the connection before you rely on it."),
    ]
    cap_cards = "".join(
        f'<div class="pan-cap-card"><div class="icon">{icon}</div>'
        f'<div class="title">{title}</div><div class="desc">{desc}</div></div>'
        for icon, title, desc in capabilities
    )
    st.markdown(
        f"""
<div style="max-width:1200px;margin:0 auto;padding:0 2rem">
  <div class="pan-cap-section-title">Platform Capabilities</div>
  <div class="pan-cap-grid">{cap_cards}</div>
  <div class="pan-footer-bar">
    <span>PAN Mitra · Common Service Centre tool · DPDP Compliant</span>
    <span>Powered by a LangGraph tool-calling agent · Official government sources only</span>
  </div>
</div>
<div style="height:2rem"></div>
""",
        unsafe_allow_html=True,
    )


# ── Main entry point ───────────────────────────────────────────────────────────
def main() -> None:
    st.session_state["backend_available"] = BACKEND_READY

    if not BACKEND_READY:
        st.error("Backend not connected — PAN Mitra requires backend.pan_graph and backend.pan_tracking.")
        st.stop()

    stats = pan_tracking.stats()

    if not st.session_state.get("pan_entered", False):
        _render_landing_page(stats)
        st.stop()

    render_sidebar()
    with st.sidebar:
        if st.button("← Back to Home", use_container_width=True, key="back_to_home"):
            st.session_state["pan_entered"] = False
            st.rerun()

    with st.expander("🤖 AI Provider", expanded=False):
        _render_ai_provider_picker()

    tab_home, tab_new, tab_tracked, tab_escalated, tab_pipeline, tab_analytics, tab_settings = st.tabs(
        ["🏠 Home", "🆕 New Request", "📋 Tracked Requests", "⚠️ Escalated to Officer", "🕸️ Pipeline View", "📊 Analytics", "⚙️ Settings"]
    )

    with tab_home:
        _render_home_hero(stats)
        st.caption("Use the tabs above to start a request, track existing ones, or watch the LangGraph agent run live in Pipeline View.")
    with tab_new:
        _render_new_request()
    with tab_tracked:
        _render_tracked_requests()
    with tab_escalated:
        _render_escalated()
    with tab_pipeline:
        _render_pipeline()
    with tab_analytics:
        _render_analytics(stats, stats.get("by_status", {}))
    with tab_settings:
        _render_settings()


main()
