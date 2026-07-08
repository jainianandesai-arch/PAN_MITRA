"""
PAN Mitra – Header Component
Top-of-page hero banner with branding and status indicator.
"""

import math

import streamlit as st


def chakra_svg(css_class: str = "pan-chakra") -> str:
    """Ashoka-Chakra-inspired motif (24 spokes) -- a generic wheel design, not
    a reproduction of the Emblem of India. Reused by the cover page too."""
    spokes = "".join(
        '<line x1="50" y1="50" x2="{:.1f}" y2="{:.1f}" stroke="#ffffff" stroke-width="1.4"/>'.format(
            50 + 44 * math.cos(math.radians(i * 15)),
            50 + 44 * math.sin(math.radians(i * 15)),
        )
        for i in range(24)
    )
    return (
        f'<svg class="{css_class}" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="50" cy="50" r="46" fill="none" stroke="#ffffff" stroke-width="3"/>'
        '<circle cx="50" cy="50" r="6" fill="#ffffff"/>' + spokes + "</svg>"
    )


def render_header(title: str = "🪪 PAN Mitra", subtitle: str | None = None) -> None:
    """Render the page hero banner."""
    subtitle = subtitle or (
        "End-to-end PAN card assistance — New PAN, Correction, Reprint, and Instant e-PAN — "
        "guided by a LangGraph tool-calling agent."
    )
    backend_ok = st.session_state.get("backend_available", True)
    status_html = (
        '<span class="csc-badge csc-badge-green"><span class="pulse-dot"></span> Connected</span>'
        if backend_ok else
        '<span class="csc-badge csc-badge-red">⚠ Backend Offline</span>'
    )
    st.markdown(
        f"""
<div class="csc-hero pan-hero">
  {chakra_svg()}
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:.6rem">
    <div>
      <h1 style="margin:0 0 4px">{title}</h1>
      <p style="color:rgba(255,255,255,.85);margin:0;font-size:.95rem">{subtitle}</p>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
      {status_html}
      <span style="font-size:.72rem;color:rgba(255,255,255,.55)">
        DPDP Compliant · Official Sources Only
      </span>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
