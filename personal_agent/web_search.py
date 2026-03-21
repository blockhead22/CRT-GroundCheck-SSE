"""
Web Search Tool — DuckDuckGo-based search for the CRT agent.

Gives the agent "hands" to look things up on the internet.
Results are verified by CRT-as-Critic before being surfaced.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single web search result."""
    title: str
    url: str
    snippet: str
    source: str = "web"


@dataclass
class SearchResponse:
    """Complete search response."""
    query: str
    results: List[SearchResult] = field(default_factory=list)
    summary: str = ""
    error: Optional[str] = None
    searched_at: datetime = field(default_factory=datetime.now)

    def to_context_string(self) -> str:
        """Format results as context for LLM consumption."""
        if self.error:
            return f"Search failed: {self.error}"
        if not self.results:
            return f"No results found for: {self.query}"

        lines = [f"Web search results for '{self.query}':\n"]
        for i, r in enumerate(self.results, 1):
            lines.append(f"[{i}] {r.title}")
            lines.append(f"    {r.snippet}")
            lines.append(f"    Source: {r.url}")
            lines.append("")
        return "\n".join(lines)


class WebSearchTool:
    """
    DuckDuckGo-based web search.

    Usage:
        searcher = WebSearchTool()
        response = searcher.search("weather in Madison WI")
        print(response.to_context_string())
    """

    def __init__(self, max_results: int = 8, region: str = "us-en"):
        self.max_results = max_results
        self.region = region
        self._ddgs = None

    def _get_ddgs(self):
        """Lazy-init DDGS client."""
        if self._ddgs is None:
            try:
                # Try new 'ddgs' package first (renamed from duckduckgo_search)
                from ddgs import DDGS
                self._ddgs = DDGS()
            except ImportError:
                try:
                    # Fallback to old package name
                    from duckduckgo_search import DDGS
                    self._ddgs = DDGS()
                except ImportError:
                    logger.error("[WEB-SEARCH] ddgs not installed. Run: pip install ddgs")
                    raise
        return self._ddgs

    def search(self, query: str, max_results: Optional[int] = None) -> SearchResponse:
        """
        Search the web via DuckDuckGo.

        Args:
            query: Search query
            max_results: Override default max results

        Returns:
            SearchResponse with results
        """
        n = max_results or self.max_results

        try:
            ddgs = self._get_ddgs()
            raw_results = list(ddgs.text(
                query,
                region=self.region,
                max_results=n,
            ))

            results = []
            for r in raw_results:
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", r.get("link", "")),
                    snippet=r.get("body", r.get("snippet", "")),
                    source="duckduckgo",
                ))

            logger.info(f"[WEB-SEARCH] '{query}' → {len(results)} results")

            return SearchResponse(
                query=query,
                results=results,
            )

        except ImportError:
            return SearchResponse(
                query=query,
                error="duckduckgo-search package not installed",
            )
        except Exception as e:
            logger.warning(f"[WEB-SEARCH] Search failed: {e}")
            return SearchResponse(
                query=query,
                error=str(e),
            )

    def research(self, query: str, max_results: Optional[int] = None) -> SearchResponse:
        """Run a comprehensive multi-angle research search.

        Fetches the primary query results PLUS alternative-perspective
        results (counter-claims, criticism, opposing views) so the LLM
        can give a balanced, well-rounded summary.

        Returns a single SearchResponse with de-duplicated results.
        """
        n = max_results or self.max_results
        # --- primary results ---
        primary = self.search(query, max_results=n)
        if primary.error:
            return primary

        seen_urls = {r.url for r in primary.results}
        all_results = list(primary.results)

        # --- build alternative query angles ---
        alt_queries = self._generate_alt_queries(query)

        for alt_q in alt_queries:
            try:
                alt_resp = self.search(alt_q, max_results=max(3, n // 2))
                for r in alt_resp.results:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append(r)
            except Exception as e:
                logger.debug("[WEB-SEARCH] Alt query '%s' failed: %s", alt_q, e)

        logger.info(
            "[WEB-SEARCH] Research for '%s' → %d total results (%d primary + %d alt)",
            query, len(all_results), len(primary.results),
            len(all_results) - len(primary.results),
        )

        return SearchResponse(query=query, results=all_results)

    # ------------------------------------------------------------------
    @staticmethod
    def _generate_alt_queries(query: str) -> List[str]:
        """Generate 1-2 alternative search queries for balanced coverage."""
        q = query.lower().strip()
        alts: List[str] = []

        # For news / event queries — ask for criticism or reaction
        news_kw = (
            "state of the union", "speech", "address", "announcement",
            "election", "debate", "hearing", "summit", "conference",
            "legislation", "bill", "executive order", "ruling",
            "policy", "plan",
        )
        if any(k in q for k in news_kw):
            alts.append(f"{query} reaction criticism")
            alts.append(f"{query} fact check")
            return alts[:2]

        # For product / tech queries
        if any(k in q for k in ("review", "product", "vs", "compare", "best")):
            alts.append(f"{query} problems issues")
            return alts[:1]

        # For person / company queries
        if any(k in q for k in ("ceo", "founder", "company", "controversy")):
            alts.append(f"{query} criticism controversy")
            return alts[:1]

        # Generic fallback: add an 'analysis opinion' angle
        alts.append(f"{query} analysis")
        return alts[:1]

    def search_and_summarize(
        self,
        query: str,
        llm_client: Optional[Any] = None,
        max_results: Optional[int] = None,
    ) -> SearchResponse:
        """
        Search and optionally summarize results using LLM.

        Args:
            query: Search query
            llm_client: OllamaClient for summarization
            max_results: Max results to return

        Returns:
            SearchResponse with summary
        """
        response = self.search(query, max_results)

        if response.error or not response.results:
            return response

        # If we have an LLM, generate a summary
        if llm_client is not None:
            context = response.to_context_string()
            prompt = (
                f"Based on these search results, answer the question: {query}\n\n"
                f"{context}\n\n"
                "Give a concise, factual answer (2-4 sentences). "
                "Cite the source number [1], [2], etc. when using information."
            )
            try:
                summary = llm_client.generate(
                    prompt=prompt,
                    system="You are a helpful research assistant. Summarize search results accurately and concisely. Always cite sources.",
                    max_tokens=300,
                    temperature=0.3,
                )
                if isinstance(summary, dict):
                    summary = summary.get("response", "") or summary.get("text", "")
                response.summary = str(summary).strip()
            except Exception as e:
                logger.warning(f"[WEB-SEARCH] Summarization failed: {e}")
                # Fall back to showing raw results
                response.summary = response.to_context_string()
        else:
            response.summary = response.to_context_string()

        return response
