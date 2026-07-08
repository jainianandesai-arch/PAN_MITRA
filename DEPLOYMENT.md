# Streamlit Cloud Deployment Guide

## Quick Start for Streamlit Cloud

### Option 1: Modern Architecture (Recommended) ✅

**Entry Point:** `app.py`

This is the new, clean Streamlit architecture optimized for cloud deployment.

```bash
streamlit run app.py
```

**Structure:**
- Multi-page app with sidebar navigation
- 6 professional dashboards
- Clean Streamlit Cloud integration
- Modern UI with consistent styling

**Deploy to Streamlit Cloud:**
1. Push to GitHub: `git push origin main`
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "New app"
4. Set **App URL** to: `app.py`
5. Deploy

---

### Option 2: Legacy Support ⚠️

**Entry Point:** `streamlit_app.py`

This maintains backward compatibility with existing backend modules.

```bash
streamlit run streamlit_app.py
```

**Use this if you need:**
- Legacy backend modules (knowledge.py, mas_engine.py, etc.)
- Existing voice features
- Original UI structure

**Deploy to Streamlit Cloud:**
1. Push to GitHub: `git push origin main`
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "New app"
4. Set **App URL** to: `streamlit_app.py`
5. Deploy

---

## Configuration

### Streamlit Cloud Settings

In **Streamlit Cloud Dashboard** → Your App → **Settings**:

#### 1. **Advanced Settings** (if needed)

```
Python version: 3.11+
Install dependencies using: pip
Requirements file path: requirements.txt
```

#### 2. **Secrets Manager**

Add all secrets here (they map to `.streamlit/secrets.toml`). This is the
**actual, code-verified list** — see `backend/secrets.toml.txt` for the
canonical template (same values, ready to paste) and `.env.example` for
the same list in local-`.env` format:

```toml
# LLM providers — backend/llm/config/models.yaml routes across whichever
# of these are configured; not all are required, but at least one is.
GROQ_API_KEY = "..."
GEMINI_API_KEY = "..."
OPENROUTER_API_KEY = "..."
HF_TOKEN = "..."
GROK_API_KEY = "..."

# Embeddings + LLM fallback (OpenAI)
OPENAI_API_KEY = "sk-..."

# Database — Postgres + pgvector (Neon or Supabase). NOTE: the code reads
# these five separate fields (backend/database.py's DB_SECRET_NAMES), not
# a single DATABASE_URL — split your connection string into these:
DB_HOST = "..."
DB_PORT = "6543"
DB_NAME = "postgres"
DB_USER = "..."
DB_PASSWORD = "..."

# Web search fallback (optional)
TAVILY_API_KEY = "..."

# Voice (optional — falls back to browser Web Speech API if unset)
OPENAI_AUDIO_API_KEY = "..."

# Admin route password
CSC_ADMIN_PASSWORD = "..."

# Other settings
DPDP_REDACTION_ENABLED = true
HITL_ENABLED = true
```

---

## Database Setup

### PostgreSQL + pgvector (Required)

**Choose one:**

#### A. Neon (Recommended - Free tier)
1. Sign up at [neon.tech](https://neon.tech)
2. Create project, enable the `pgvector` extension
3. Copy the connection string and split it into `DB_HOST`, `DB_PORT`,
   `DB_NAME`, `DB_USER`, `DB_PASSWORD` for Streamlit Cloud secrets (see
   above — the code reads these five fields separately, not one URL)

#### B. Supabase (Alternative)
1. Sign up at [supabase.com](https://supabase.com)
2. Create project, enable the `pgvector` extension
3. Go to Settings → Database → Connection pooling, copy the pooled
   connection details
4. Split into the five `DB_*` fields above

#### C. Local Testing
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=csc_governance
DB_USER=postgres
DB_PASSWORD=...
```

There is no ChromaDB, no ORM, and no migration tool in this codebase —
`backend/database.py` talks to Postgres directly via `psycopg2`. The
`chromadb` and `sqlalchemy` entries in `requirements.txt` are unused
leftovers (see `CLEANUP_NOTES.md`).

---

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'backend'"

**Fix:**
1. Verify `backend/__init__.py` exists
2. Commit and push to GitHub:
   ```bash
   git add backend/__init__.py
   git commit -m "Ensure backend is proper package"
   git push origin main
   ```
3. Reboot your Streamlit Cloud app
4. Check **Manage app** → **Reboot script**

### Error: "ModuleNotFoundError: No module named 'streamlit_mic_recorder'"

**Fix:**
This is optional. The app handles this gracefully.
```python
try:
    from streamlit_mic_recorder import mic_recorder
except:
    mic_recorder = None  # Feature disabled
```

### App Won't Deploy

1. **Check logs:** Streamlit Cloud → App settings → **View logs**
2. **Verify requirements.txt:** `pip freeze > requirements.txt`
3. **Commit requirements:** `git add requirements.txt && git commit -m "Update deps"`
4. **Force redeploy:** Settings → **Always rerun** → Toggle **Off** then **On**

### Slow Performance

- Check Postgres connection latency (region mismatch between Streamlit
  Cloud and your DB host is the usual cause)
- `database.py` opens a fresh connection per call (no pooling yet) — high
  concurrency will surface this first; see `AUDIT_REPORT.md` §4.5
- Optimize imports (lazy loading)

### Port/Connection Issues

Streamlit Cloud automatically assigns a port. Don't specify:
```python
# ❌ Don't do this
streamlit run app.py --server.port 8501

# ✅ Just do this
streamlit run app.py
```

---

## Local Testing Before Deployment

### Test locally first:

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install requirements
pip install -r requirements.txt

# 3. Create your local secrets/env file — either:
cp .env.example .env               # for local python-dotenv usage, or
mkdir -p .streamlit && cp backend/secrets.toml.txt .streamlit/secrets.toml

# 4. Edit with real credentials

# 5. Run app
streamlit run app.py

# 6. Visit http://localhost:8501
```

---

## Git Workflow for Deployment

```bash
# 1. Make changes
git add .
git commit -m "Add new feature or fix"

# 2. Push to main
git push origin main

# 3. Streamlit Cloud auto-deploys
# (takes 1-2 minutes)

# 4. Check deployment status
# Go to share.streamlit.io → Your App → Status
```

---

## Performance Tips

### 1. Use Streamlit Cloud Cache
```python
@st.cache_data
def expensive_query():
    return fetch_data()

@st.cache_resource
def init_llm():
    return llm_client()
```

### 2. Lazy Load Heavy Modules
```python
import streamlit as st

if "llm" not in st.session_state:
    from backend.mas_engine import ask  # Load only when needed
    st.session_state.llm = ask
```

### 3. Optimize Requirements
Only include needed packages. Remove:
- `jupyter`, `jupyterlab` (not needed for production)
- Heavy ML packages if not used
- Development dependencies

### 4. Stream Responses
```python
with st.spinner("Processing..."):
    for token in llm_stream_response():
        st.write(token, end="")
```

---

## Monitoring

### View Logs
Streamlit Cloud → Your App → **Settings** → **Logs**

### Health Check
Monitor **App resets** and **Memory usage**

### Errors
Check Streamlit Cloud dashboard for:
- Deployment failures
- Runtime errors
- Restart count

---

## Scaling (If Needed)

### When to upgrade:
- App keeps restarting (memory full)
- Timeouts on queries
- Concurrent users > 50

### Options:
1. **Streamlit Cloud Pro** ($5-20/month)
2. **Docker deployment** (Heroku, Railway, Render) — see `backend/Dockerfile`
3. **Separate API + frontend** — genuine re-architecture, not a config change; see `AUDIT_REPORT.md`

---

## Final Checklist Before Production

- [ ] `backend/__init__.py` exists
- [ ] `requirements.txt` is up-to-date
- [ ] `.streamlit/config.toml` configured (optional — only needed for
      custom theming/server settings)
- [ ] All secrets added to Streamlit Cloud, matching `backend/secrets.toml.txt`
- [ ] Postgres connection tested locally (`DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`)
- [ ] `pgvector` extension enabled on the Postgres instance
- [ ] Deployed and tested in staging
- [ ] Logs reviewed for errors

---

## Support

**Streamlit Cloud Issues:**
- [Streamlit Community Forum](https://discuss.streamlit.io)
- [Streamlit Docs](https://docs.streamlit.io)

**Application Issues:**
- Check `streamlit_app.py` or `app.py` error handling
- Review backend module imports
- See `AUDIT_REPORT.md` for known gaps vs. a larger enterprise-scope brief
