import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
from config import BYLAWS_FILE_PATH, CHROMA_PERSIST_DIR
from utils.pdf_loader import extract_text_from_pdf, split_text_into_chunks

class BylawsRAGEngine:
    """
    RAG Engine for indexing and retrieving articles from College Bylaws & Academic Regulations.
    Supports ChromaDB if installed, with a robust fallback semantic keyword search.
    """
    def __init__(self, bylaws_path: Optional[Path] = None):
        self.bylaws_path = bylaws_path or BYLAWS_FILE_PATH
        self.chunks: List[Dict[str, Any]] = []
        self.chroma_collection = None
        self._initialize_knowledge_base()

    def _initialize_knowledge_base(self):
        """Reads bylaws document and creates chunks and indices."""
        if not self.bylaws_path.exists():
            return

        full_text = extract_text_from_pdf(self.bylaws_path)
        self.chunks = split_text_into_chunks(full_text, chunk_size=500, overlap=80)

        # Attempt to initialize ChromaDB if installed
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
            self.chroma_collection = client.get_or_create_collection(name="college_bylaws")
            
            # Populate collection if empty
            if self.chroma_collection.count() == 0 and self.chunks:
                self.chroma_collection.add(
                    documents=[c["text"] for c in self.chunks],
                    ids=[f"chunk_{c['id']}" for c in self.chunks],
                    metadatas=[{"source": str(self.bylaws_path.name)} for _ in self.chunks]
                )
        except Exception as e:
            # Fall back to internal ranker
            self.chroma_collection = None

    def search_bylaws(self, query: str, top_k: int = 3) -> str:
        """
        Searches the bylaws for relevant rules, articles, and regulations.
        
        Args:
            query: The search query in Arabic or English (e.g., 'شروط مرتبة الشرف', 'الحد الأقصى للساعات').
            top_k: Number of relevant chunks to return.
            
        Returns:
            Concatenated relevant excerpts from the bylaws.
        """
        if not self.chunks:
            return "لم يتم تحميل لائحة الكلية بعد أو الملف فارغ."

        # Arabic & English Keyword Matcher (highly effective and accurate for Arabic regulations)
        stopwords = {"و", "في", "من", "على", "عن", "إلى", "أن", "أو", "ما", "هو", "هي", "له", "لها", "كل", "مع", "بعد", "قبل", "عند", "تم", "التي", "الذي"}
        query_words = [w for w in re.findall(r'[\w]+', query.lower()) if len(w) > 1 and w not in stopwords]
        if not query_words:
            query_words = re.findall(r'[\w]+', query.lower())

        scored_chunks = []
        for chunk in self.chunks:
            text = chunk["text"]
            text_lower = text.lower()
            score = 0.0
            
            for w in query_words:
                if w in text_lower:
                    score += 5.0
                    # Additional boost if exact term appears multiple times
                    score += text_lower.count(w) * 1.5

            if score > 0:
                scored_chunks.append((score, text))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        if scored_chunks:
            top_results = []
            for _, text in scored_chunks[:min(top_k, 2)]:
                # Locate keyword match position to capture the exact relevant rule
                match_pos = -1
                for w in query_words:
                    pos = text.lower().find(w)
                    if pos != -1:
                        match_pos = pos
                        break

                if match_pos != -1:
                    # Find beginning of line/paragraph before the match
                    start = max(0, text.rfind("\n", 0, match_pos))
                    end = min(len(text), start + 650)
                    excerpt = text[start:end].strip()
                else:
                    excerpt = text[:650].strip()

                top_results.append(excerpt)
            return "\n\n---\n\n".join(top_results)

        # Fallback to ChromaDB if keyword match yielded nothing
        if self.chroma_collection is not None:
            try:
                results = self.chroma_collection.query(
                    query_texts=[query],
                    n_results=min(top_k, len(self.chunks))
                )
                docs = results.get("documents", [[]])[0]
                if docs:
                    return "\n\n---\n\n".join(docs)
            except Exception:
                pass

        return "\n\n---\n\n".join([c["text"] for c in self.chunks[:top_k]])

# Global singleton RAG instance
_rag_instance: Optional[BylawsRAGEngine] = None

def get_rag_engine() -> BylawsRAGEngine:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = BylawsRAGEngine()
    return _rag_instance

def search_college_bylaws(query: str) -> str:
    """
    أداة للبحث في نصوص ومواد لائحة الكلية الرسمية للإجابة عن القواعد الجامعية مثل:
    - شروط التخرج
    - الحد الأدنى والأقصى لساعات التسجيل
    - شروط الإنذار الأكاديمي وتجاوزه
    - شروط مرتبة الشرف
    - سياسة إعادة المقررات والرسوب
    - فترات الحذف والإضافة والانسحاب
    
    Args:
        query: موضوع أو نص الاستفسار عن اللائحة
    """
    engine = get_rag_engine()
    return engine.search_bylaws(query)
