"""
CSC Mitra AI – Global CSS Design System
All visual tokens, glassmorphism, animations, and typography in one place.
Import and call apply_global_css() once per page to activate.
"""

import streamlit as st


# ── Design tokens ─────────────────────────────────────────────────────────────
_GLOBAL_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap');

:root {
  --primary:       #005bac;
  --primary-light: #e0f0ff;
  --accent:        #ff6b00;
  --success:       #16a34a;
  --warning:       #d97706;
  --danger:        #dc2626;
  --ink:           #0f172a;
  --muted:         #64748b;
  --surface:       #ffffff;
  --bg:            #f1f5f9;
  --border:        #e2e8f0;
  --radius:        12px;
  --shadow-sm:     0 1px 3px rgba(15,23,42,.08), 0 1px 2px rgba(15,23,42,.06);
  --shadow-md:     0 4px 16px rgba(15,23,42,.10), 0 2px 6px rgba(15,23,42,.06);
  --shadow-lg:     0 10px 30px rgba(15,23,42,.12), 0 4px 10px rgba(15,23,42,.08);
}

/* ── Base ──────────────────────────────────────────────────────────────────── */
html, body,
[class*="css"],
.stMarkdown, .stTextInput, .stTextArea,
.stButton, .stSelectbox, .stRadio {
  font-family: Inter, "Noto Sans Devanagari", "Nirmala UI", system-ui, sans-serif !important;
}

.stApp { background: var(--bg); color: var(--ink); font-size: 17px; }

/* ── Widget label / body text sizing ──────────────────────────────────────────
   Streamlit's default label/caption text renders quite small (~14px) and was
   reading as "dull" -- bump it app-wide so forms and body copy feel substantial. */
.stSelectbox label, .stTextInput label, .stTextArea label,
.stCheckbox label, .stMultiSelect label, .stRadio label {
  font-size: 1.05rem !important; font-weight: 600 !important; color: var(--ink) !important;
}
.stMarkdown p, .stMarkdown li { font-size: 1.02rem; line-height: 1.65; }
[data-testid="stCaptionContainer"] { font-size: .92rem !important; }
.stButton > button, [data-testid="stFormSubmitButton"] > button { font-size: 1rem; }

.block-container {
  max-width: 100%;
  width: 96vw;
  padding-top: 1.5rem;
  padding-bottom: 3.5rem;
  padding-left: 2rem;
  padding-right: 2rem;
}

/* ── Sidebar ───────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  border-right: 1px solid #334155;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stSelectbox > div,
[data-testid="stSidebar"] .stCheckbox { border-color: #334155 !important; }

/* ── Navigation tabs ───────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background: var(--surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
  border-radius: 8px;
  font-weight: 600;
  font-size: .93rem;
  padding: 8px 18px;
  transition: background .15s, color .15s;
}
.stTabs [aria-selected="true"] {
  background: var(--primary) !important;
  color: #ffffff !important;
}

/* ── Cards ─────────────────────────────────────────────────────────────────── */
.csc-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  padding: 1.25rem 1.4rem;
  margin-bottom: 1rem;
  transition: box-shadow .2s;
}
.csc-card:hover { box-shadow: var(--shadow-md); }
.csc-card-glass {
  background: rgba(255,255,255,0.72);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.5);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
  padding: 1.25rem 1.4rem;
  margin-bottom: 1rem;
}

/* ── Hero banner ───────────────────────────────────────────────────────────── */
.csc-hero {
  background: linear-gradient(135deg, #005bac 0%, #0284c7 50%, #0891b2 100%);
  border-radius: var(--radius);
  padding: 1.6rem 1.8rem;
  margin-bottom: 1.2rem;
  position: relative;
  overflow: hidden;
}
.csc-hero::after {
  content: '';
  position: absolute;
  top: -40%; right: -10%;
  width: 320px; height: 320px;
  background: rgba(255,255,255,.07);
  border-radius: 50%;
}
.csc-hero h1 { color: #fff; font-size: 1.7rem; font-weight: 800; margin: 0 0 6px; }
.csc-hero p  { color: rgba(255,255,255,.87); font-size: .97rem; margin: 0; }

/* ── Greeting / empty state ────────────────────────────────────────────────── */
.csc-greeting {
  text-align: center;
  padding: 2.5rem 1rem;
  color: var(--muted);
}
.csc-greeting h2 { font-size: 1.45rem; font-weight: 700; color: var(--ink); margin-bottom: .4rem; }
.csc-greeting p  { font-size: 1rem; }

/* ── Quick prompt chips ─────────────────────────────────────────────────────── */
.prompt-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: .6rem 0 1.2rem;
  justify-content: center;
}
.prompt-chip {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: .85rem;
  font-weight: 500;
  padding: 6px 14px;
  cursor: pointer;
  transition: border-color .15s, background .15s;
}
.prompt-chip:hover {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--primary);
}

/* ── Chat messages ──────────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  margin-bottom: .75rem;
  padding: .9rem 1.1rem;
}
[data-testid="stChatMessage"][data-testid*="user"] {
  background: var(--primary-light);
  border-color: #bfdbfe;
}
[data-testid="stChatMessageContent"] { line-height: 1.7; }

/* ── Input area ─────────────────────────────────────────────────────────────── */
textarea {
  border-radius: 10px !important;
  border-color: var(--border) !important;
  font-size: 1rem !important;
}
textarea:focus { border-color: var(--primary) !important; box-shadow: 0 0 0 3px rgba(0,91,172,.14) !important; }

/* ── Buttons ────────────────────────────────────────────────────────────────── */
.stButton > button,
[data-testid="stFormSubmitButton"] > button {
  border-radius: 9px;
  font-weight: 600;
  min-height: 40px;
  transition: transform .12s, box-shadow .12s;
}
.stButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }
.stButton > button[kind="primary"],
.stButton > button[kind="primaryFormSubmit"],
[data-testid="stFormSubmitButton"] > button[kind="primary"],
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {
  background: var(--primary); border-color: var(--primary); color: #fff;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[kind="primaryFormSubmit"]:hover,
[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]:hover {
  background: #004a8c; border-color: #004a8c; color: #fff;
}

/* ── Form controls (checkboxes, radios, multiselect/select tags) ─────────────── */
input[type="checkbox"], input[type="radio"] { accent-color: var(--primary); }
[data-baseweb="tag"] {
  background-color: var(--primary) !important;
  border-color: var(--primary) !important;
}
[data-baseweb="tag"] span { color: #fff !important; }
[data-baseweb="select"] [role="button"]:focus-within,
div[data-baseweb="base-input"]:focus-within { border-color: var(--primary) !important; }
.stSlider [data-baseweb="slider"] div[role="slider"] { background-color: var(--primary) !important; }

/* ── Metric cards ────────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.2rem;
  box-shadow: var(--shadow-sm);
}
[data-testid="stMetricLabel"]  { font-size: .83rem; font-weight: 600; color: var(--muted); }
[data-testid="stMetricValue"]  { font-size: 1.7rem; font-weight: 800; color: var(--ink);   }
[data-testid="stMetricDelta"]  { font-size: .82rem; font-weight: 600; }

/* ── Status badges ───────────────────────────────────────────────────────────── */
.csc-badge {
  display: inline-flex; align-items: center; gap: 5px;
  border-radius: 999px; font-size: .78rem; font-weight: 700;
  padding: 3px 10px; white-space: nowrap;
}
.csc-badge-green  { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
.csc-badge-blue   { background: #dbeafe; color: #1d4ed8; border: 1px solid #bfdbfe; }
.csc-badge-amber  { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
.csc-badge-red    { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }

/* ── Pulse dot animation ─────────────────────────────────────────────────────── */
.pulse-dot {
  display: inline-block; width: 8px; height: 8px;
  border-radius: 50%; background: var(--success);
  animation: pulse-anim 1.4s ease-in-out infinite;
}
@keyframes pulse-anim {
  0%, 100% { opacity: .3; transform: scale(.8); }
  50%       { opacity: 1;  transform: scale(1.1); }
}

/* ── Section header ──────────────────────────────────────────────────────────── */
.section-hdr {
  font-size: 1rem; font-weight: 800; color: var(--ink);
  border-left: 3px solid var(--primary); padding-left: 10px;
  margin: 1.4rem 0 .8rem;
}

/* ── PAN Mitra theme: Indian tricolor + Ashoka Chakra motif, built from ──────
   the design tokens above (--accent≈saffron, --surface=white, --success≈green,
   --primary=navy) so the whole app reads as one system. The tricolor is a
   ::before pseudo-element fused to the hero box itself (not a separate div)
   so it can never show a gap or corner mismatch, and is bold enough (10px)
   to actually read at a glance instead of disappearing at normal zoom. */
.pan-tricolor { display: none; } /* superseded by .pan-hero::before below; kept as a no-op so old markup doesn't break */
.pan-hero { position: relative; overflow: hidden; padding-top: calc(1.6rem + 6px) !important; }
.pan-hero::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 10px;
  background: linear-gradient(90deg,
    var(--accent) 0%, var(--accent) 33%,
    #ffffff 33%, #ffffff 66%,
    var(--success) 66%, var(--success) 100%);
}
.pan-chakra { position: absolute; top: calc(50% + 5px); right: 22px; transform: translateY(-50%); width: 110px; height: 110px; opacity: .3; }

/* ── Cover page ────────────────────────────────────────────────────────────── */
.pan-cover {
  position: relative; overflow: hidden;
  background: linear-gradient(150deg, #002a4d 0%, #005bac 45%, #0891b2 100%);
  border-radius: var(--radius);
  padding: 3.5rem 2rem 3rem;
  margin-bottom: 1.4rem;
  text-align: center;
}
.pan-cover-chakra {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 640px; height: 640px; opacity: .08;
}
.pan-cover-content { position: relative; z-index: 1; }
.pan-cover-eyebrow {
  color: rgba(255,255,255,.65); font-size: .78rem; font-weight: 700;
  letter-spacing: .16em; text-transform: uppercase; margin-bottom: .8rem;
}
.pan-cover-title { color: #fff; font-size: 4.2rem; font-weight: 800; margin: 0; line-height: 1.05; }
.pan-cover-underline {
  width: 280px; height: 7px; margin: 1.3rem auto 1.4rem;
  background: linear-gradient(90deg,
    var(--accent) 0%, var(--accent) 33%,
    #ffffff 33%, #ffffff 66%,
    var(--success) 66%, var(--success) 100%);
  border-radius: 999px;
}
.pan-cover-tagline { color: rgba(255,255,255,.9); font-size: 1.4rem; margin: 0 0 2.4rem; font-weight: 400; }
.pan-cover-stats { display: flex; justify-content: center; gap: 3.5rem; flex-wrap: wrap; margin-bottom: 2.4rem; }
.pan-cover-stat { text-align: center; }
.pan-cover-stat .n { color: #fff; font-size: 2.6rem; font-weight: 800; }
.pan-cover-stat .l { color: rgba(255,255,255,.7); font-size: .85rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.pan-cover-chips { display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }
.pan-cover-chip {
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.35);
  color: #fff; border-radius: 999px; font-size: 1rem; font-weight: 600;
  padding: 9px 20px; backdrop-filter: blur(4px);
}

/* ── Landing page: capabilities grid + footer ─────────────────────────────── */
.pan-cap-section-title {
  font-size: .8rem; font-weight: 800; color: var(--primary);
  text-transform: uppercase; letter-spacing: .12em;
  border-bottom: 2px solid var(--accent); display: inline-block;
  padding-bottom: .5rem; margin-bottom: 1.5rem;
}
.pan-cap-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.1rem;
}
@media (max-width: 900px) { .pan-cap-grid { grid-template-columns: 1fr; } }
.pan-cap-card {
  background: var(--surface); border: 1px solid var(--border);
  border-top: 3px solid var(--primary); border-radius: 8px;
  padding: 1.3rem 1.4rem;
}
.pan-cap-card .icon { font-size: 1.6rem; margin-bottom: .5rem; }
.pan-cap-card .title { font-size: 1.05rem; font-weight: 700; color: var(--ink); margin-bottom: .3rem; }
.pan-cap-card .desc { font-size: .9rem; color: var(--muted); line-height: 1.5; }
.pan-footer-bar {
  background: var(--ink); border-radius: var(--radius);
  padding: 1rem 2rem; margin-top: 2rem;
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: .5rem;
  font-size: .8rem; color: rgba(255,255,255,.45);
}
.pan-node-flow { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: .6rem 0 1rem; }
.pan-node {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  min-width: 100px; padding: .7rem .5rem;
  border-radius: var(--radius); border: 1px solid var(--border); background: var(--surface);
  font-size: .78rem; font-weight: 700; color: var(--muted);
}
.pan-node-done { border-color: var(--success); background: #f0fdf4; color: #166534; }
.pan-node-tool { border-color: var(--accent); background: #fff7ed; color: #9a3412; }
.pan-node-blocked { border-color: var(--danger); background: #fef2f2; color: #991b1b; }
.pan-node-active {
  border-color: var(--primary); background: var(--primary-light); color: var(--primary);
  animation: pan-node-pulse 1.4s ease-in-out infinite;
}
@keyframes pan-node-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(0,91,172,.25); }
  50%      { box-shadow: 0 0 0 6px rgba(0,91,172,0); }
}
.pan-arrow { color: var(--border); font-size: 1.3rem; font-weight: 900; }
.pan-tool-chip {
  display: inline-flex; align-items: center; gap: 5px;
  background: var(--primary-light); color: var(--primary);
  border: 1px solid #bfdbfe; border-radius: 999px;
  font-size: .78rem; font-weight: 700; padding: 4px 12px; margin: 3px 4px 3px 0;
}
/* ── Responsive ──────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .block-container { padding-left: .9rem; padding-right: .9rem; }
  .csc-hero h1 { font-size: 1.3rem; }
  .stTabs [data-baseweb="tab"] { padding: 6px 12px; font-size: .85rem; }
}
"""


def apply_global_css() -> None:
    """Inject the shared design system CSS. Call once at the top of any page."""
    st.markdown(f"<style>{_GLOBAL_CSS}</style>", unsafe_allow_html=True)


def card(content_html: str, cls: str = "csc-card") -> None:
    """Render wrapped content inside a styled card div."""
    st.markdown(f'<div class="{cls}">{content_html}</div>', unsafe_allow_html=True)


def badge(label: str, color: str = "blue") -> str:
    """Return an HTML badge string for inline use."""
    return f'<span class="csc-badge csc-badge-{color}">{label}</span>'
