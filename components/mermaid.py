"""
PAN Mitra – Mermaid Diagram Component
Renders a Mermaid diagram string (e.g. LangGraph's `.draw_mermaid()` output)
as an actual flowchart in the browser, instead of a raw-text code block.

mermaid.js is vendored under assets/vendor/ (not pulled from a CDN) so the
diagram renders even on networks that block third-party JS -- see
assets/vendor/README.md for how it got there / how to update it.
"""

import json
import os

import streamlit.components.v1 as components

_VENDOR_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "vendor", "mermaid.min.js",
)

_mermaid_js_cache = None


def _load_mermaid_js() -> str:
    global _mermaid_js_cache
    if _mermaid_js_cache is None:
        with open(_VENDOR_JS_PATH, encoding="utf-8") as f:
            _mermaid_js_cache = f.read()
    return _mermaid_js_cache


def render_mermaid(diagram: str, height: int = 420) -> None:
    """Render `diagram` (Mermaid syntax) client-side via the vendored mermaid.js.

    Diagrams like LangGraph's `.draw_mermaid()` output embed raw `<p>` tags in
    node labels, so the source is passed to `mermaid.render()` as a JS string
    (via `mermaid.initialize(startOnLoad=false)`) rather than dropped into a
    `<div class="mermaid">` -- the browser's HTML parser would otherwise turn
    those `<p>` tags into real child elements before mermaid ever sees the
    text, breaking the diagram."""
    diagram_js_literal = json.dumps(diagram).replace("</script>", "<\\/script>")
    html = f"""
    <div id="mermaid-container" style="font-family: -apple-system, sans-serif;"></div>
    <script>
{_load_mermaid_js()}
    </script>
    <script>
      mermaid.initialize({{ startOnLoad: false, theme: "neutral", flowchart: {{ curve: "basis" }} }});

      // The first render() call in a fresh iframe can silently collapse to
      // an empty "-8 -8 16 16" diagram (an internal mermaid layout timing
      // issue) instead of erroring, so retry with backoff until a real
      // (non-degenerate) result comes back.
      async function renderWithRetry(attempts) {{
        let lastSvg = "";
        for (let i = 0; i < attempts; i++) {{
          const result = await mermaid.render("mermaid-graph-" + i, {diagram_js_literal});
          lastSvg = result.svg;
          const m = lastSvg.match(/viewBox="[-\\d.]+ [-\\d.]+ ([\\d.]+) ([\\d.]+)"/);
          const degenerate = m && parseFloat(m[1]) < 20 && parseFloat(m[2]) < 20;
          if (!degenerate) return lastSvg;
          await new Promise((r) => setTimeout(r, 400));
        }}
        return lastSvg;
      }}

      function reportHeight() {{
        const h = document.body.scrollHeight + 24;
        window.parent.postMessage({{ type: "streamlit:setFrameHeight", height: h }}, "*");
      }}

      renderWithRetry(15).then((svg) => {{
        document.getElementById("mermaid-container").innerHTML = svg;
        reportHeight();
      }}).catch((err) => {{
        document.getElementById("mermaid-container").textContent = "Mermaid render error: " + err;
        reportHeight();
      }});
    </script>
    """
    components.html(html, height=height, scrolling=False)
