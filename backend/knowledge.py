import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from .crawler import crawl_website
from .database import store_vector
from .document_extractors import SUPPORTED_FILE_TYPES, detect_language, extract_document
from .env_config import get_setting_int as _setting_int
from .guardrails import allowed_domains_label, is_allowed_url, setting
from .service_catalog import service_urls


DEFAULT_PARENT_CHUNK_SIZE = 2200
DEFAULT_PARENT_OVERLAP = 220
DEFAULT_CHILD_CHUNK_SIZE = 700
DEFAULT_CHILD_OVERLAP = 140


def _clean_text(text):

    lines = []
    for raw_line in (text or "").splitlines():
        line = " ".join(raw_line.split())
        if line:
            lines.append(line)

    if not lines:
        return " ".join((text or "").split())

    return "\n".join(lines)


def _split_recursively(text, chunk_size, overlap):

    clean = _clean_text(text)
    if not clean:
        return []

    chunks = []
    units = re.split(r"(?<=[.!?।])\s+|\n+", clean)

    expanded_units = []
    for unit in units:
        unit = unit.strip()
        if not unit:
            continue
        if len(unit) <= chunk_size:
            expanded_units.append(unit)
            continue

        words = unit.split()
        current_words = []
        current_length = 0
        for word in words:
            extra = len(word) + (1 if current_words else 0)
            if current_words and current_length + extra > chunk_size:
                expanded_units.append(" ".join(current_words))
                current_words = []
                current_length = 0
            current_words.append(word)
            current_length += extra
        if current_words:
            expanded_units.append(" ".join(current_words))

    current = ""
    for unit in expanded_units:
        next_text = f"{current} {unit}".strip() if current else unit
        if len(next_text) > chunk_size and current:
            chunks.append(current)
            tail = current[-overlap:].strip() if overlap else ""
            current = f"{tail} {unit}".strip() if tail else unit
        else:
            current = next_text

    if current:
        chunks.append(current)

    deduped = []
    for chunk in chunks:
        if chunk and chunk not in deduped:
            deduped.append(chunk)

    return deduped


def _chunk_text(text, max_chars=3500):

    return _split_recursively(text, max_chars, max(0, max_chars // 8))


def _source_category(source, text=""):

    host = urlparse(source or "").netloc.lower()
    haystack = f"{host} {text[:500]}".lower()
    categories = (
        ("pm_kisan", ("pmkisan", "pm kisan", "farmer", "kisan")),
        ("pan", ("pan", "protean", "tinpan", "utiitsl", "income tax")),
        ("digipay", ("digipay", "cash withdrawal", "aeps", "csccloud")),
        ("e_shram", ("eshram", "e-shram", "labour", "shram")),
        ("ayushman", ("ayushman", "pmjay", "nha")),
        ("digital_seva", ("digitalseva", "digital seva", "csc")),
    )

    for category, terms in categories:
        if any(term in haystack for term in terms):
            return category

    return "general"


CATEGORY_META = {
    "pm_kisan": ("Agriculture", "PM-KISAN"),
    "pan": ("Finance", "PAN"),
    "digipay": ("Banking", "DigiPay"),
    "e_shram": ("Labour", "e-Shram"),
    "ayushman": ("Health", "Ayushman Bharat"),
    "digital_seva": ("CSC", "Digital Seva"),
    "general": ("General", "CSC Services"),
}


def _service_meta(category, department="", service_type=""):
    default_department, default_service = CATEGORY_META.get(category, CATEGORY_META["general"])
    return department.strip() or default_department, service_type.strip() or default_service


def _report_progress(callback, stage, percent):
    if callback:
        callback(stage, percent)


def _doc_id(source, text):

    fingerprint = f"{source}\n{text[:4000]}".encode("utf-8", "ignore")
    return hashlib.sha256(fingerprint).hexdigest()[:16]


def _metadata_prefix(metadata):

    lines = [
        f"Source: {metadata.get('source_name') or metadata['source']}",
        f"Document ID: {metadata['document_id']}",
        f"Parent Chunk: {metadata['parent_id']}",
        f"Child Chunk: {metadata['chunk_id']}",
        f"Category: {metadata['category']}",
    ]
    if metadata.get("department"):
        lines.append(f"Department: {metadata['department']}")
    if metadata.get("service"):
        lines.append(f"Service: {metadata['service']}")
    if metadata.get("language"):
        lines.append(f"Language: {metadata['language']}")
    if metadata.get("page"):
        lines.append(f"Page: {metadata['page']}")
    if metadata.get("section"):
        lines.append(f"Section: {metadata['section']}")
    if metadata.get("file_name"):
        lines.append(f"File: {metadata['file_name']}")

    return "\n".join(lines) + "\n\n"


def _prepare_index_chunks(text, source, title="", max_chunks=None, extra_metadata=None):

    clean = _clean_text(text)
    if not clean:
        return []

    parent_size = _setting_int("PARENT_CHUNK_SIZE", DEFAULT_PARENT_CHUNK_SIZE)
    parent_overlap = _setting_int("PARENT_CHUNK_OVERLAP", DEFAULT_PARENT_OVERLAP)
    child_size = _setting_int("CHILD_CHUNK_SIZE", DEFAULT_CHILD_CHUNK_SIZE)
    child_overlap = _setting_int("CHILD_CHUNK_OVERLAP", DEFAULT_CHILD_OVERLAP)
    max_chunks = max_chunks or _setting_int("MAX_CHUNKS_PER_DOCUMENT", 80)
    document_id = _doc_id(source, clean)
    category = _source_category(source, clean)
    department, service = _service_meta(
        category,
        (extra_metadata or {}).get("department", ""),
        (extra_metadata or {}).get("service", ""),
    )
    language = (extra_metadata or {}).get("language") or detect_language(clean)
    base_metadata = {
        "source": source,
        "source_name": (extra_metadata or {}).get("source_name") or title or source,
        "title": title,
        "file_name": (extra_metadata or {}).get("file_name", ""),
        "upload_date": (extra_metadata or {}).get("upload_date", ""),
        "department": department,
        "service": service,
        "language": language,
        "url": source if source.startswith("http") else (extra_metadata or {}).get("url", ""),
        "version": (extra_metadata or {}).get("version", "1.0"),
        "document_id": document_id,
        "category": category,
        "chunking": "parent_child_recursive",
    }
    if extra_metadata:
        for key in ("page", "section"):
            if extra_metadata.get(key):
                base_metadata[key] = extra_metadata[key]

    prepared = []
    parents = _split_recursively(clean, parent_size, parent_overlap)
    for parent_index, parent_text in enumerate(parents, start=1):
        parent_id = f"{document_id}-p{parent_index:03d}"
        children = _split_recursively(parent_text, child_size, child_overlap)
        for child_index, child_text in enumerate(children, start=1):
            chunk_index = len(prepared)
            chunk_id = f"{parent_id}-c{child_index:03d}"
            metadata = {
                **base_metadata,
                "parent_id": parent_id,
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
            }
            prepared.append(
                {
                    "content": _metadata_prefix(metadata) + child_text,
                    "metadata": metadata,
                }
            )
            if len(prepared) >= max_chunks:
                return prepared

    return prepared


def _prepare_document_chunks(extracted, source, max_chunks=None, extra_metadata=None):
    prepared = []
    max_chunks = max_chunks or _setting_int("MAX_CHUNKS_PER_DOCUMENT", 80)

    for section in extracted.sections:
        section_text = section.text.strip()
        if not section_text:
            continue

        if section.section:
            section_text = f"## {section.section}\n{section_text}"
        if section.page:
            section_text = f"[Page {section.page}]\n{section_text}"

        section_meta = dict(extra_metadata or {})
        if section.page:
            section_meta["page"] = section.page
        if section.section:
            section_meta["section"] = section.section

        section_chunks = _prepare_index_chunks(
            section_text,
            source,
            title=extracted.title,
            max_chunks=max_chunks - len(prepared),
            extra_metadata=section_meta,
        )
        prepared.extend(section_chunks)
        if len(prepared) >= max_chunks:
            break

    return prepared


def _store_chunks(chunks, human_reviewed=False, progress_callback=None):

    stored = 0
    failed = 0
    last_error = ""
    total = max(len(chunks), 1)

    for index, chunk in enumerate(chunks, start=1):
        try:
            metadata = chunk["metadata"]
            ok, message = store_vector(
                chunk["content"],
                source=metadata["source"],
                human_reviewed=human_reviewed,
                metadata=metadata,
                document_id=metadata["document_id"],
                parent_id=metadata["parent_id"],
                chunk_id=metadata["chunk_id"],
                chunk_index=metadata["chunk_index"],
                category=metadata["category"],
            )
            if ok:
                stored += 1
            else:
                failed += 1
                last_error = message
        except Exception as e:
            print(f"Bad chunk skipped: {e}")
            failed += 1
            last_error = str(e)
            continue

        embed_progress = 0.55 + (0.30 * index / total)
        _report_progress(progress_callback, "Embedding", embed_progress)
        _report_progress(progress_callback, "Indexing", 0.88 + (0.10 * index / total))

    return stored, failed, last_error


def add_knowledge(input_data, cloud_consent=False, human_reviewed=False):

    if not cloud_consent:
        return "Knowledge was not stored because DPDP cloud storage/embedding consent was not granted."

    if not human_reviewed:
        return "Knowledge was not stored because human review approval was not granted."

    if input_data.startswith("http"):
        if not is_allowed_url(input_data):
            return f"Blocked by CSC guardrail. Only these domains are allowed: {allowed_domains_label()}."

        pages = crawl_website(input_data)
        if not pages:
            return f"No allowed CSC pages were found. Allowed domains: {allowed_domains_label()}."

        stored = 0
        failed = 0
        last_error = ""

        for page in pages:
            chunks = _prepare_index_chunks(page["content"], page["url"], title=page.get("title", ""))
            page_stored, page_failed, page_error = _store_chunks(chunks, human_reviewed=human_reviewed)
            stored += page_stored
            failed += page_failed
            last_error = page_error or last_error

        detail = f" Last error: {last_error}" if last_error and failed else ""
        return f"Website knowledge indexed: {stored} semantic chunks stored. {failed} chunks failed.{detail}"

    return "Manual pasted knowledge is blocked by CSC guardrail. Add a URL from an allowed CSC domain instead."


def ingest_knowledge_source(
    source_type,
    *,
    official_url="",
    uploaded_file=None,
    cloud_consent=False,
    human_reviewed=False,
    department="",
    service_type="",
    source_name="",
    progress_callback=None,
):

    source_type = (source_type or "").strip().lower()

    if not cloud_consent:
        return "Knowledge was not stored because DPDP cloud storage/embedding consent was not granted."

    if not human_reviewed:
        return "Knowledge was not stored because human review approval was not granted."

    _report_progress(progress_callback, "Uploading", 0.08)

    if source_type == "url":
        if not official_url:
            return "Enter an official URL to ingest."
        _report_progress(progress_callback, "Extracting", 0.25)
        result = add_knowledge(
            official_url,
            cloud_consent=cloud_consent,
            human_reviewed=human_reviewed,
        )
        _report_progress(progress_callback, "Knowledge Ready", 1.0)
        return result

    if source_type not in SUPPORTED_FILE_TYPES:
        return f"Unsupported source type: {source_type}."

    if not uploaded_file:
        return "Choose a file to upload first."

    if not official_url or not is_allowed_url(official_url):
        return f"Blocked by CSC guardrail. Use an allowed official URL as the document source: {allowed_domains_label()}."

    _report_progress(progress_callback, "Extracting", 0.22)

    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    try:
        extracted = extract_document(source_type, uploaded_file)
        
        if not extracted or not extracted.sections:
            return "File contains no usable content"
    except Exception as e:
        return f"Failed to process file: {e}"

    upload_date = datetime.now(timezone.utc).isoformat()
    language = detect_language(extracted.full_text)
    extra_metadata = {
        "source_name": source_name.strip() or extracted.title,
        "file_name": extracted.file_name,
        "upload_date": upload_date,
        "department": department,
        "service": service_type,
        "language": language,
        "url": official_url,
        "version": "1.0",
    }

    _report_progress(progress_callback, "Chunking", 0.42)

    chunks = _prepare_document_chunks(
        extracted,
        official_url,
        extra_metadata=extra_metadata,
    )
    if not chunks:
        return "No indexable chunks were produced from this document."

    _report_progress(progress_callback, "Embedding", 0.58)

    stored, failed, last_error = _store_chunks(
        chunks,
        human_reviewed=human_reviewed,
        progress_callback=progress_callback,
    )

    _report_progress(progress_callback, "Knowledge Ready", 1.0)

    detail = f" Last error: {last_error}" if last_error and failed else ""
    return (
        f"{source_type.upper()} knowledge ingested: {stored} semantic chunks stored "
        f"from {extracted.file_name}. {failed} chunks failed.{detail}"
    )


def add_pdf_knowledge(pdf_file, official_url, cloud_consent=False, human_reviewed=False):

    return ingest_knowledge_source(
        "pdf",
        official_url=official_url,
        uploaded_file=pdf_file,
        cloud_consent=cloud_consent,
        human_reviewed=human_reviewed,
    )


def index_csc_service_guides(cloud_consent=False, max_sites=None, human_reviewed=False):

    if not cloud_consent:
        return "Service guides were not indexed because DPDP cloud storage/embedding consent was not granted."

    if not human_reviewed:
        return "Service guides were not indexed because human review approval was not granted."

    stored = 0
    failed = 0
    visited = 0

    if max_sites is None:
        try:
            max_sites = int(setting("CSC_SERVICE_INDEX_LIMIT", "12"))
        except ValueError:
            max_sites = 12

    for url in service_urls()[:max_sites]:
        visited += 1
        pages = crawl_website(url, max_pages=3)
        if not pages:
            failed += 1
            continue

        for page in pages:
            chunks = _prepare_index_chunks(page["content"], page["url"], title=page.get("title", ""))
            page_stored, page_failed, _ = _store_chunks(chunks, human_reviewed=human_reviewed)
            stored += page_stored
            failed += page_failed

    return f"Indexed {stored} semantic chunks from {visited} official start URLs. {failed} chunks failed."
