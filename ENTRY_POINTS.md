# Repository Entry Points

## ⚡ Quick Reference

### For Streamlit Cloud Deployment

| Use Case | Entry Point | Status |
|----------|------------|--------|
| **New App (Recommended)** | `app.py` | ✅ Modern |
| **Legacy Compatibility** | `streamlit_app.py` | ⚠️ Updated |

---

## 🆕 Modern Entry Point: `app.py`

**Recommended for:** Streamlit Cloud deployment, new projects

### Features
- ✅ Clean multi-page architecture
- ✅ 6 professional dashboards
- ✅ Modern UI with consistent styling
- ✅ Streamlit Cloud optimized
- ✅ No legacy code baggage

### How to Use
```bash
# Local testing
streamlit run app.py

# Streamlit Cloud
# Set App URL to: app.py
```

### Structure
```
app.py (Home)
└── pages/
    ├── 1_CSC_Assistant.py
    ├── 2_Grievance_Redressal.py
    ├── 3_Knowledge_Base.py
    ├── 4_VLE_Dashboard.py
    ├── 5_Officer_Dashboard.py
    └── 6_Admin_Dashboard.py
```

---

## 🔧 Legacy Entry Point: `streamlit_app.py`

**Recommended for:** Existing codebases, backward compatibility

### Features
- ✅ Uses legacy backend modules
- ✅ Voice features support
- ✅ Original UI structure
- ✅ **Fixed import issues** (v2.0)

### What Was Fixed
```python
# ✅ NOW INCLUDES PROPER PATH HANDLING:
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ✅ ERROR HANDLING FOR MISSING MODULES:
try:
    from backend.knowledge import ingest_knowledge_source
except ImportError as e:
    st.warning(f"⚠️ Could not load module: {e}")
    ingest_knowledge_source = None
```

### How to Use
```bash
# Local testing
streamlit run streamlit_app.py

# Streamlit Cloud
# Set App URL to: streamlit_app.py
```

---

## 📦 Backend Package Structure

**Corrected — see `CLEANUP_NOTES.md` for the full history.** An earlier
version of this file listed `backend/agents/`, `backend/services/`,
`backend/workflows/`, `backend/models/`, `backend/graph/`, and `backend/db/`
as existing packages. They did exist as files at one point, but nothing
that actually runs (`app.py`, `streamlit_app.py`, `pages/*.py`,
`mas_engine.py`) ever imported them — confirmed by grep, then removed in
a prior cleanup session. This is what's actually in `backend/` today:

```
backend/
├── __init__.py              ✅ Makes backend importable (no eager imports —
│                                see the file's own docstring for why that
│                                specifically matters here)
├── llm/                      ✅ The one real subpackage — config-driven LLM
│   │                            routing with health tracking and fallback
│   ├── manager.py, router.py, registry.py, scoring.py, health.py,
│   │   telemetry.py, fallback.py, providers/
│   └── config/models.yaml, config/routing.yaml
│
├── mas_engine.py             ✅ Main orchestrator — ask(query, ...) does
│                                retrieval → confidence scoring → HITL
│                                routing → PII redaction → LLM call →
│                                output guardrail → DPDP notice, all in
│                                one function. (Named "mas_engine" but is
│                                a single pipeline, not a multi-agent
│                                system — see AUDIT_REPORT.md.)
├── database.py               ✅ pgvector store + cosine similarity search
├── knowledge.py               ✅ Ingestion: chunking, parent/child, metadata
├── document_extractors.py    ✅ PDF/DOCX/TXT/CSV/XLSX/PPTX → text
├── crawler.py                ✅ BFS crawler, allow-listed domains only
├── guardrails.py              ✅ Domain allowlist (70+ official CSC/gov domains)
├── hitl.py                   ✅ SQLite human-review queue
├── voice_assistant.py        ✅ Whisper STT + OpenAI TTS (turn-based, not
│                                streaming — see AUDIT_REPORT.md)
├── env_config.py             ✅ Shared secrets/env-var accessor (single
│                                implementation used by every module below
│                                instead of 5 copy-pasted versions)
├── pii_patterns.py           ✅ Shared PII detect/redact patterns
├── adaptive_response.py, builtin_guides.py, core_knowledge_pack.py,
│   service_catalog.py, tavily_search.py    ✅ Supporting modules
└── tests/test_llm_manager.py ✅ 6 tests, all passing, no network needed
```

Every module here is a **flat module directly inside `backend/`**, not a
further-nested package — `mas_engine.py` imports its siblings as
`from database import vector_search`, not `from backend.database import
...`. That only works because `backend/` itself is *also* put on
`sys.path` (see the path-setup code in `app.py`, `streamlit_app.py`, and
each file under `pages/`), alongside the repo root. It's fragile (depends
on import order across files that don't coordinate) but it does work
today — see `AUDIT_REPORT.md` §4.5 if you want the details.

---

## ✅ Verified Imports

These imports work today (verified by actually running them, not assumed):

```python
from backend.knowledge import ingest_knowledge_source
from backend.document_extractors import SUPPORTED_FILE_TYPES
from backend.hitl import list_pending_reviews, resolve_review
from backend.mas_engine import ask
from backend.guardrails import setting as guardrail_setting
from backend.voice_assistant import (
    normalize_voice_language,
    transcribe_with_whisper,
    whisper_stt_enabled,
    synthesize_with_openai,
    openai_audio_enabled,
)

# LLM Manager (config-driven model routing/fallback):
from llm import default_manager as llm_manager
```

**Not real** (an earlier version of this file claimed these worked — they
don't, because the package doesn't exist):
```python
from backend.agents import fusion_agent, intent_agent, ...  # ❌ no such package
```

---

## 🚀 Deployment Decision Tree

```
Is this a new project?
├─ YES → Use app.py ✅
│        (Modern, clean, recommended)
│
└─ NO → Use streamlit_app.py ⚠️
        (Legacy support, backward compatible)
```

---

## 🔍 How to Check If Everything Works

### 1. Verify Backend Package
```bash
python -c "import backend; print('✅ Backend package imports correctly')"
```

### 2. Verify the LLM Manager
```bash
cd backend && python -m pytest tests/test_llm_manager.py -v
```

### 3. Test Legacy Imports
```bash
python -c "from backend.knowledge import ingest_knowledge_source; print('✅ Legacy imports work')"
```

### 4. Run Streamlit App
```bash
streamlit run app.py
# OR
streamlit run streamlit_app.py
```

---

## 📝 Key Files Changed/Added (v2.0)

| File | Change | Status |
|------|--------|--------|
| `app.py` | Created (new entry point) | ✨ NEW |
| `streamlit_app.py` | Fixed imports + error handling | 🔧 UPDATED |
| `backend/__init__.py` | Created (package marker); later stripped of the eager `agents` import that used to run on every backend import — see `CLEANUP_NOTES.md` | 🔧 UPDATED |
| `DEPLOYMENT.md` | Created (deployment guide) | ✨ NEW |
| `ENTRY_POINTS.md` | Created (this file); corrected in the Session 3 cleanup pass to match the real backend structure | ✨ NEW / 🔧 UPDATED |

---

## 🎯 Streamlit Cloud Deployment Steps

### Using Modern Entry Point (app.py)

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "v2.0: Fixed imports and modernized structure"
   git push origin main
   ```

2. **Create Streamlit Cloud App:**
   - Visit [share.streamlit.io](https://share.streamlit.io)
   - Click "New app"
   - Select your repo
   - **Set "Main file path" to: `app.py`**
   - Click "Deploy"

3. **Add Secrets:**
   - Go to app settings
   - Click "Secrets"
   - Use `backend/secrets.toml.txt` as your template (it matches the
     actual env vars the code reads — see `.env.example` for the same
     list in `.env` format)
   - Save

4. **Test:**
   - Visit your app URL
   - Test each page/feature

---

## ⚡ Quick Test

```bash
# 1. Clone repo
git clone https://github.com/manutevari/cscagent.git
cd cscagent

# 2. Create venv
python -m venv venv
source venv/bin/activate

# 3. Install deps
pip install -r requirements.txt

# 4. Run with modern app
streamlit run app.py

# OR run with legacy app
streamlit run streamlit_app.py

# 5. Visit http://localhost:8501
```

---

## 📚 Documentation

- **AUDIT_REPORT.md** - Honest gap analysis against the full enterprise-scope brief
- **DEPLOYMENT.md** - Complete deployment guide
- **README.md** - Project overview and architecture
- **docs/architecture.md** - System design (matches what's actually built)
- **docs/workflow.md** - Actual query-handling workflow
- **CLEANUP_NOTES.md** - History of what's been removed/fixed and why
- **.env.example** - Environment variables reference (matches the code)

---

## ⚠️ If Import Still Fails on Streamlit Cloud

1. **Verify file exists:**
   ```bash
   ls -la backend/__init__.py
   ```

2. **Commit and push:**
   ```bash
   git add backend/__init__.py
   git commit -m "Ensure backend/__init__.py is tracked"
   git push
   ```

3. **Hard reboot Streamlit Cloud app:**
   - App Settings → "Always rerun" → toggle OFF then ON
   - Or delete and recreate the app

4. **Check logs:**
   - App Settings → "Logs" tab
   - Look for import errors

---

## 🎉 You're Ready!

Both entry points work today. Choose one and deploy to Streamlit Cloud. See **DEPLOYMENT.md** for detailed instructions.
