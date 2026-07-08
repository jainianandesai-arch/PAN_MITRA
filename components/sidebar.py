"""
PAN Mitra – Sidebar Component
Dark-themed sidebar with navigation status and session info.
"""

import streamlit as st


_NAV_ITEMS = [
    ("🆕", "New Request", "Start a PAN service request"),
    ("📋", "Tracked Requests", "Follow up on submitted requests"),
    ("⚠️", "Escalated to Officer", "Human-in-the-loop review queue"),
    ("🕸️", "Pipeline View", "Live LangGraph agent trace"),
    ("📊", "Analytics", "Request volume & status breakdown"),
    ("⚙️", "Settings", "AI provider & preferences"),
]


def render_sidebar() -> dict:
    """
    Render the sidebar (brand, connection status, nav list, PAN request
    stats). Returns {} -- kept as a dict for call-site compatibility, but
    there are no global settings here: cloud consent and language are
    collected per-request on the New Request form, not globally.
    """
    with st.sidebar:
        # ── Brand ──────────────────────────────────────────────────────────────
        st.markdown(
            """
<div style="padding:1rem 0 .5rem;border-bottom:1px solid #334155;margin-bottom:1rem">
  <div style="font-size:1.3rem;font-weight:800;letter-spacing:-.3px">🪪 PAN Mitra</div>
  <div style="font-size:.78rem;color:#94a3b8;margin-top:2px">
    End-to-end PAN Card Assistant
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        # ── Connection status ───────────────────────────────────────────────────
        backend_ok = st.session_state.get("backend_available", True)
        dot_color  = "#22c55e" if backend_ok else "#ef4444"
        label      = "Connected" if backend_ok else "Backend Offline"
        st.markdown(
            f"""
<div style="display:flex;align-items:center;gap:8px;background:#1e293b;
            border:1px solid #334155;border-radius:8px;padding:8px 12px;
            margin-bottom:1rem;font-size:.82rem;font-weight:600;color:#e2e8f0">
  <span style="width:8px;height:8px;border-radius:50%;background:{dot_color};
               display:inline-block;animation:pulse-anim 1.4s infinite"></span>
  {label}
</div>
""",
            unsafe_allow_html=True,
        )

        # ── Navigation hint ─────────────────────────────────────────────────────
        st.markdown(
            '<div style="font-size:.72rem;font-weight:700;color:#64748b;'
            'letter-spacing:.06em;text-transform:uppercase;margin-bottom:.5rem">'
            "Navigation</div>",
            unsafe_allow_html=True,
        )
        for icon, name, desc in _NAV_ITEMS:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:8px;padding:6px 4px;'
                f'border-radius:6px;font-size:.87rem;color:#cbd5e1">'
                f'<span style="font-size:1rem">{icon}</span>'
                f'<span style="font-weight:600">{name}</span>'
                f'<span style="color:#475569;font-size:.78rem">— {desc}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div style="border-top:1px solid #334155;margin:1rem 0"></div>',
            unsafe_allow_html=True,
        )

        # ── Session quick stats ─────────────────────────────────────────────────
        try:
            from backend import pan_tracking
            stats = pan_tracking.stats()
        except ImportError:
            stats = {"total": 0, "by_status": {}}
        total = stats.get("total", 0)
        escalated = stats.get("by_status", {}).get("escalated", 0)
        st.markdown(
            f"""
<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;
            padding:10px 12px;font-size:.8rem;color:#94a3b8">
  <div style="font-weight:700;color:#e2e8f0;margin-bottom:6px">📈 PAN Requests</div>
  <div>Total tracked: <b style="color:#e2e8f0">{total}</b></div>
  <div>Awaiting officer: <b style="color:#e2e8f0">{escalated}</b></div>
</div>
""",
            unsafe_allow_html=True,
        )

        # ── Footer ──────────────────────────────────────────────────────────────
        st.markdown(
            '<div style="position:absolute;bottom:1rem;left:0;right:0;'
            'text-align:center;font-size:.72rem;color:#475569">'
            "PAN Mitra © 2026 | LangGraph Tool-Calling Agent</div>",
            unsafe_allow_html=True,
        )

    return {}
