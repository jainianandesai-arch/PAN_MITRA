# Assets

This folder is currently a placeholder. It previously contained
`css/styles.css`, which was removed during a cleanup pass (see
`CLEANUP_NOTES.md`) because no page ever loaded it — `app.py` and each
page under `pages/` define their own inline `st.markdown("""<style>...`
blocks instead, and those inline styles already redefine some of the same
class names (e.g. `.feature-card`) with different values, so loading the
old stylesheet on top of them would have caused visual conflicts rather
than fixed anything.

If you want a real shared stylesheet across all pages, that's a genuine
follow-up task: pick one canonical set of colors/classes, load it once
(e.g. from `app.py`), and remove the per-page inline `<style>` duplication
in favor of it — not just drop a file back in here.
