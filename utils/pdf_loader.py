import io
from pathlib import Path
from typing import List, Dict, Union

def extract_text_from_pdf(pdf_source: Union[str, Path, bytes, io.BytesIO]) -> str:
    """
    Extracts full text from a PDF file path, bytes, or BytesIO buffer using pypdf.
    Falls back gracefully if pypdf is not installed or file is plain text.
    """
    if isinstance(pdf_source, (str, Path)):
        p = Path(pdf_source)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        if p.suffix.lower() in [".txt", ".md"]:
            return p.read_text(encoding="utf-8")
        with open(p, "rb") as f:
            pdf_bytes = io.BytesIO(f.read())
    elif isinstance(pdf_source, bytes):
        pdf_bytes = io.BytesIO(pdf_source)
    else:
        pdf_bytes = pdf_source

    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_bytes)
        text_chunks = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_chunks.append(f"--- [صفحة {i+1}] ---\n" + page_text)
        return "\n\n".join(text_chunks)
    except ImportError:
        # If pypdf is not installed yet, try to decode as text if possible
        try:
            pdf_bytes.seek(0)
            return pdf_bytes.read().decode("utf-8", errors="ignore")
        except Exception as e:
            return f"Error extracting text: {e}"

def split_text_into_chunks(text: str, chunk_size: int = 600, overlap: int = 100) -> List[Dict[str, Union[str, int]]]:
    """
    Splits text into sliding window chunks for RAG embedding.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current_chunk = ""
    chunk_id = 1

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}".strip()
        else:
            if current_chunk:
                chunks.append({
                    "id": chunk_id,
                    "text": current_chunk
                })
                chunk_id += 1
            # Start new chunk with possible overlap if long
            current_chunk = para

    if current_chunk:
        chunks.append({
            "id": chunk_id,
            "text": current_chunk
        })

    return chunks
