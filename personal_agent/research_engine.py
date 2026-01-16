"""
Research Engine - Search and fetch sources for research queries.

M3: Phase 1 - Local document search (no web scraping yet).
M3.5: Add web search with DuckDuckGo + BeautifulSoup.

Architecture:
1. Search: Find relevant documents (local files, later web)
2. Fetch: Retrieve document content
3. Extract: Pull relevant quotes with char offsets
4. Package: Create EvidencePacket with citations
"""

from typing import List, Optional, Tuple
from datetime import datetime
import re
from pathlib import Path

from .evidence_packet import Citation, EvidencePacket


class ResearchEngine:
    """
    Research engine for finding and citing sources.
    
    Phase 1 (Current): Local document search
    - Search markdown/text files in workspace
    - Extract quotes with context
    - Generate citations with char offsets
    
    Phase 2 (M3.5): Web search
    - DuckDuckGo search integration
    - BeautifulSoup HTML parsing
    - Intelligent quote extraction
    """
    
    def __init__(self, workspace_root: Optional[str] = None):
        """
        Initialize research engine.
        
        Args:
            workspace_root: Root directory for local document search.
                          If None, only web search will work (M3.5).
        """
        self.workspace_root = Path(workspace_root) if workspace_root else None
    
    def research(
        self,
        query: str,
        max_sources: int = 3,
        search_local: bool = True,
        search_web: bool = False,
    ) -> EvidencePacket:
        """
        Execute a research query and return evidence packet.
        
        Args:
            query: Research question
            max_sources: Maximum number of sources to cite
            search_local: Search local documents
            search_web: Search web (M3.5, not implemented yet)
        
        Returns:
            EvidencePacket with summary and citations
        """
        citations: List[Citation] = []
        
        # Phase 1: Local document search
        if search_local and self.workspace_root:
            local_citations = self._search_local_documents(query, max_sources)
            citations.extend(local_citations)
        
        # Phase 2: Web search (M3.5 - not implemented yet)
        if search_web:
            # web_citations = self._search_web(query, max_sources)
            # citations.extend(web_citations)
            pass
        
        # Generate summary from citations
        summary = self._synthesize_summary(query, citations)
        
        # Create evidence packet
        packet = EvidencePacket.create(
            query=query,
            summary=summary,
            citations=citations[:max_sources],  # Limit to max_sources
        )
        
        return packet
    
    def _search_local_documents(
        self,
        query: str,
        max_results: int = 3,
    ) -> List[Citation]:
        """
        Search local markdown/text files for relevant content.
        
        Args:
            query: Search query
            max_results: Maximum number of citations to return
        
        Returns:
            List of citations from local files
        """
        citations: List[Citation] = []
        
        if not self.workspace_root or not self.workspace_root.exists():
            return citations
        
        # Search for markdown and text files
        file_patterns = ["*.md", "*.txt"]
        search_terms = self._extract_search_terms(query)
        
        for pattern in file_patterns:
            for file_path in self.workspace_root.rglob(pattern):
                # Skip hidden files and common excludes
                if any(part.startswith('.') for part in file_path.parts):
                    continue
                if 'node_modules' in file_path.parts or '__pycache__' in file_path.parts:
                    continue
                
                try:
                    content = file_path.read_text(encoding='utf-8')
                    
                    # Find relevant quotes
                    file_citations = self._extract_quotes(
                        content,
                        search_terms,
                        str(file_path),
                    )
                    citations.extend(file_citations)
                    
                    if len(citations) >= max_results:
                        break
                        
                except Exception:
                    # Skip files that can't be read
                    continue
            
            if len(citations) >= max_results:
                break
        
        return citations[:max_results]
    
    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract key search terms from query."""
        # Simple implementation: split on common words
        stopwords = {'what', 'when', 'where', 'how', 'why', 'is', 'the', 'a', 'an'}
        words = re.findall(r'\b\w+\b', query.lower())
        return [w for w in words if w not in stopwords and len(w) > 2]
    
    def _extract_quotes(
        self,
        content: str,
        search_terms: List[str],
        source_url: str,
    ) -> List[Citation]:
        """
        Extract relevant quotes from document content.
        
        Args:
            content: Document text
            search_terms: Keywords to search for
            source_url: Source file path or URL
        
        Returns:
            List of citations with char offsets
        """
        citations: List[Citation] = []
        
        # Find paragraphs containing search terms
        paragraphs = content.split('\n\n')
        
        for para_idx, paragraph in enumerate(paragraphs):
            # Check if paragraph contains any search terms
            para_lower = paragraph.lower()
            if not any(term in para_lower for term in search_terms):
                continue
            
            # Find paragraph position in original content
            para_start = content.find(paragraph)
            if para_start == -1:
                continue
            
            para_end = para_start + len(paragraph)
            
            # Extract first sentence or first 200 chars as quote
            quote_text = self._extract_quote_snippet(paragraph)
            
            citation = Citation(
                quote_text=quote_text,
                source_url=source_url,
                char_offset=(para_start, para_end),
                fetched_at=datetime.now(),
                confidence=0.7,  # Medium confidence for keyword matching
            )
            citations.append(citation)
        
        return citations
    
    def _extract_quote_snippet(self, paragraph: str, max_length: int = 200) -> str:
        """Extract a snippet from paragraph for citation."""
        # Remove extra whitespace
        text = ' '.join(paragraph.split())
        
        # Try to get first sentence
        match = re.match(r'^([^.!?]+[.!?])', text)
        if match:
            sentence = match.group(1).strip()
            if len(sentence) <= max_length:
                return sentence
        
        # Fall back to truncate
        if len(text) <= max_length:
            return text
        
        return text[:max_length].rsplit(' ', 1)[0] + '...'
    
    def _synthesize_summary(
        self,
        query: str,
        citations: List[Citation],
    ) -> str:
        """
        Synthesize summary from citations.
        
        For now, simple concatenation. In production, this would
        use an LLM to synthesize a coherent answer from sources.
        
        Args:
            query: Original query
            citations: List of citations
        
        Returns:
            Summary text
        """
        if not citations:
            return f"No sources found for: {query}"
        
        # Simple implementation: concatenate quotes
        summary_parts = [f"[{i+1}] {cite.quote_text}" 
                        for i, cite in enumerate(citations)]
        
        summary = "Based on the following sources:\n\n" + "\n\n".join(summary_parts)
        
        return summary
    
    def fetch(self, url: str) -> str:
        """
        Fetch content from URL or file path.
        
        Phase 1: File paths only
        Phase 2 (M3.5): Add HTTP support with requests
        
        Args:
            url: File path or URL
        
        Returns:
            Document content as text
        """
        if url.startswith('http://') or url.startswith('https://'):
            # M3.5: Implement with requests + BeautifulSoup
            raise NotImplementedError("Web fetching not implemented yet (M3.5)")
        
        # Local file
        return Path(url).read_text(encoding='utf-8')
