# CSC Copilot — Codex Development Prompt

> **Partially stale (Session 3 cleanup note):** the "Already implemented" /
> "Gaps to close" lists below predate `backend/document_extractors.py`
> (multi-format ingestion — PDF/DOCX/TXT/CSV/XLSX/PPTX already exists) and
> `CSC_ADMIN_PASSWORD` (admin gating already exists). This file is kept as
> a forward-looking spec for the CSC-LLM fine-tuning initiative it
> describes, not as a claim about current state — see `AUDIT_REPORT.md`
> for a verified, current gap analysis and `CLEANUP_NOTES.md` for history.

Use this document as the master specification when extending the CSC AI Assistant codebase.
The goal is **not** a generic chatbot — build a full **Knowledge Management + Retrieval + Voice Copilot platform** for Common Service Centres (CSC) / Digital Seva.

---

## Project Context (Current Codebase)

**Stack:** Python, Streamlit, Supabase Postgres + pgvector, OpenAI embeddings (to migrate), multi-provider LLM APIs.

**Key files:**

| File | Role |
|------|------|
| `app.py` | Streamlit UI — chat, voice, admin ingestion panel (`?admin=1`) |
| `mas_engine.py` | Q&A orchestration — retrieval, guardrails, LLM, local fallback |
| `database.py` | pgvector storage + cosine similarity search |
| `knowledge.py` | URL/PDF ingestion, parent-child chunking |
| `crawler.py` | BFS crawl of official CSC/gov domains |
| `guardrails.py` | Domain allowlist, DPDP redaction |
| `voice_assistant.py` | Whisper STT (optional), language detection |
| `hitl.py` | Human-in-the-loop review queue (SQLite) |
| `csc_knowledge_schema.sql` | DB schema — `documents`, `csc_knowledge`, indexes |

**Already implemented:** URL crawl, PDF ingest, pgvector RAG, guardrails, HITL, voice mode (browser STT/TTS + optional Whisper), multi-provider LLM chain, DPDP consent gating.

**Gaps to close:** Multi-format ingestion, semantic chunking, bge embeddings, hybrid search + reranking, admin KB dashboard, citations UI, fine-tuned CSC-LLM, Coqui TTS, admin password enforcement.

---

## CSC-LLM Architecture (Do NOT Train From Scratch)

Do **not** train a foundation model from scratch. Build a **CSC-specific LLM** using continued pretraining + instruction tuning on university GPUs (A100/H200/B200).

```text
Base Model
    ↓
Qwen 3 / Llama 3.3 / DeepSeek
    ↓
Continued Pretraining on CSC Documents
    ↓
Instruction Tuning on CSC Q&A
    ↓
CSC-LLM
    ↓
RAG Layer
    ↓
Voice Assistant
```

### Recommended Model

```text
Qwen3 14B Instruct + LoRA Fine-tuning
```

| Model | Notes |
|-------|-------|
| Qwen3 8B | Best overall for lightweight deployment |
| Qwen3 14B | **Recommended** — best quality/cost balance |
| Llama 3.3 70B | High quality, expensive |
| DeepSeek R1 Distill 14B | Good reasoning |
| Mistral Small | Lightweight edge deployment |

### Training Stack

```text
Unsloth + TRL + PEFT + QLoRA + vLLM
```

### Data Sources

Collect official CSC corpora:

- CSC Service Manuals
- Digital Seva Portal guides
- PM-KISAN SOPs
- DigiPay documentation
- Passport / PAN Service guides
- Ayushman Bharat guides
- e-Shram documentation
- VLE training material
- CSC FAQs

### Training Pipeline

```text
Official Documents
       ↓
Cleaning
       ↓
Chunking
       ↓
Synthetic Q&A Generation
       ↓
Instruction Dataset
       ↓
Fine-Tuning (QLoRA)
       ↓
CSC-LLM (vLLM serve)
```

### Instruction Dataset Format

Target: **50,000–200,000** CSC-specific instruction pairs.

```json
{
  "instruction": "How can a VLE register a farmer under PM-KISAN?",
  "input": "",
  "output": "Step 1 ... Step 2 ... Step 3 ..."
}
```

### Voice Architecture

```text
User Speech
      ↓
Whisper (STT)
      ↓
Hybrid Retrieval + Reranking
      ↓
CSC-LLM
      ↓
Coqui TTS
      ↓
Audio Response
```

### Separation of Concerns

- **CSC-LLM** — fine-tuned generation (tone, Hindi/English, VLE step-by-step guidance)
- **RAG embeddings** — retrieval model (bge-large-en-v1.5 / bge-m3), separate from generation
- **API fallbacks** — dev-only; production demo uses vLLM-served CSC-LLM

---

==================================================
DOCUMENT INGESTION & INDEXING SYSTEM
==================================================

Add a complete enterprise-grade document ingestion and indexing pipeline.

The CSC AI Assistant must support dynamic knowledge base expansion without code changes.

==================================================
SUPPORTED SOURCES
==================================================

Admin users can ingest knowledge from:

1. PDF
2. DOCX
3. TXT
4. CSV
5. XLSX
6. PPTX
7. Official URLs
8. Government Websites
9. CSC Circulars
10. Service Guidelines

==================================================
ADMIN WORKFLOW
==================================================

Admin clicks:

📎

Modal opens:

--------------------------------
Add Knowledge Source
--------------------------------

Source Type

( ) URL
( ) PDF
( ) DOCX
( ) TXT
( ) XLSX
( ) PPTX

URL:
[________________]

Upload File:
[Choose File]

[ Ingest ]

--------------------------------

==================================================
INGESTION PIPELINE
==================================================

Document
    ↓
Text Extraction
    ↓
Cleaning
    ↓
Metadata Extraction
    ↓
Semantic Chunking
    ↓
Embeddings
    ↓
Vector Database
    ↓
Index Creation
    ↓
Search Ready

==================================================
CHUNKING
==================================================

Implement semantic chunking.

Requirements:

- Preserve headings
- Preserve tables
- Preserve lists
- Preserve section hierarchy

Chunk Size:
800–1200 tokens

Chunk Overlap:
150–250 tokens

==================================================
METADATA EXTRACTION
==================================================

Extract and store:

- Source Name
- File Name
- Upload Date
- Department
- Service Type
- Language
- URL
- Version
- Page Number

Example:

{
  "source": "PM-KISAN Guidelines",
  "department": "Agriculture",
  "service": "PM-KISAN",
  "language": "English",
  "page": 12
}

==================================================
EMBEDDINGS
==================================================

Use:

Primary:
BAAI/bge-large-en-v1.5

Fallback:
bge-m3

Support:

- Hindi
- English
- Mixed language queries

==================================================
VECTOR DATABASE
==================================================

Use existing vector store if present.

Otherwise support:

1. ChromaDB
2. FAISS
3. PostgreSQL + pgvector

Must be configurable.

==================================================
INDEX MANAGEMENT
==================================================

Admin Dashboard:

--------------------------------
Knowledge Base
--------------------------------

Documents Indexed: 253

Chunks: 48,120

Embeddings: Ready

Last Updated:
2026-06-20

--------------------------------

[ Reindex All ]

[ Delete Source ]

[ Refresh Index ]

--------------------------------

==================================================
HYBRID SEARCH
==================================================

Implement:

1. Vector Search
2. BM25 Search
3. Reranking

Pipeline:

User Query
    ↓
Hybrid Retrieval
    ↓
Cross Encoder Reranking
    ↓
Top Context
    ↓
LLM

==================================================
RERANKING
==================================================

Use:

BAAI/bge-reranker-large

or

ms-marco cross encoder

==================================================
AUTO INDEXING
==================================================

When new document uploaded:

1. Validate
2. Extract text
3. Chunk
4. Generate embeddings
5. Store vectors
6. Update index

No manual steps required.

==================================================
INDEXING STATUS UI
==================================================

Show progress:

Uploading...
██████████░░░░░

Chunking...
████████████░░░

Embedding...
██████████████░

Indexing...
████████████████

✓ Knowledge Ready

==================================================
CITATIONS
==================================================

Every answer must display source citations.

Example:

Source:
PM-KISAN Operational Guidelines
Page 12

Source:
CSC DigiPay Manual
Section 4.2

==================================================
KNOWLEDGE GOVERNANCE
==================================================

Admin can:

- View indexed documents
- Delete documents
- Rebuild index
- Refresh embeddings
- Audit sources

Users cannot access these controls.

==================================================
VOICE + KNOWLEDGE INTEGRATION
==================================================

Voice Query
    ↓
Whisper
    ↓
Hybrid Retrieval
    ↓
Reranking
    ↓
CSC LLM
    ↓
Coqui TTS
    ↓
Voice Response

==================================================
FINAL GOAL
==================================================

Create a CSC Copilot with:

✓ Voice Assistant
✓ Own Fine-Tuned CSC LLM
✓ RAG
✓ Document Ingestion
✓ Auto Indexing
✓ Hybrid Search
✓ Reranking
✓ Citations
✓ Admin Dashboard
✓ Hindi + English Support
✓ DPDP Compliance
✓ Enterprise Scale Architecture

---

## Implementation Priorities

When implementing, follow this order:

1. **Ingestion expansion** — multi-format extractors in `knowledge.py`, admin modal in `app.py`
2. **Embeddings migration** — replace OpenAI with bge in `database.py`; add config in `secrets.toml.txt`
3. **Semantic chunking** — heading/table-aware chunker; 800–1200 token targets
4. **Hybrid search** — PostgreSQL `tsvector` BM25 + vector fusion in `database.py`
5. **Reranking** — cross-encoder pass in `mas_engine.py` before LLM call
6. **Citations** — surface metadata from retrieved chunks in chat UI
7. **Admin dashboard** — KB stats, delete/reindex, progress bars; enforce `CSC_ADMIN_PASSWORD`
8. **CSC-LLM** — `training/` scripts (Unsloth SFT), vLLM endpoint, wire into `mas_engine.py`
9. **Voice** — Coqui TTS server-side playback in `voice_assistant.py`

## Coding Conventions

- Match existing Python style: minimal abstractions, flat modules, Streamlit secrets via `guardrails.setting()`
- Reuse `guardrails.py` domain allowlist for all URL ingestion
- Require DPDP cloud consent before embedding/storage (existing pattern in `knowledge.py`)
- Never expose admin controls without authenticated admin session
- Keep Hindi + English + Hinglish support in all user-facing strings and LLM prompts
