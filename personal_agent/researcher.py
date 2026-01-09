"""
Research Agent - Web Search + SSE Integration

Phase D+ capabilities with honest contradiction checking.
"""

import os
from typing import List, Dict, Optional
import tempfile
from pathlib import Path

from sse import SSEClient


class ResearchAgent:
    """
    Research assistant that searches the web and uses SSE for contradictions.
    
    Phase D+ Features:
    - Searches web for information
    - Indexes search results with SSE
    - Finds contradictions in research
    - Learns which sources are reliable (based on your feedback)
    
    Requires: pip install requests beautifulsoup4 (or tavily-python for paid API)
    """
    
    def __init__(self, search_api_key: Optional[str] = None):
        """
        Initialize research agent.
        
        Args:
            search_api_key: Optional Tavily API key for better search
                          If None, uses basic web scraping
        """
        self.search_api_key = search_api_key
        self.sse_indices: Dict[str, SSEClient] = {}
        
        # Try to import search libraries
        try:
            if search_api_key:
                from tavily import TavilyClient
                self.searcher = TavilyClient(api_key=search_api_key)
                self.search_mode = "tavily"
            else:
                import requests
                from bs4 import BeautifulSoup
                self.searcher = None
                self.search_mode = "basic"
                print("Using basic web scraping (install tavily-python for better results)")
        except ImportError:
            print("Warning: Search libraries not installed")
            print("Install: pip install requests beautifulsoup4 tavily-python")
            self.search_mode = "none"
    
    def search_web(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        Search the web for information.
        
        Returns list of: {title, url, snippet}
        """
        if self.search_mode == "tavily":
            response = self.searcher.search(query, max_results=num_results)
            return [
                {
                    'title': r.get('title', ''),
                    'url': r.get('url', ''),
                    'snippet': r.get('content', '')
                }
                for r in response.get('results', [])
            ]
        
        elif self.search_mode == "basic":
            # Basic DuckDuckGo search (rate limited, use sparingly)
            import requests
            from bs4 import BeautifulSoup
            
            url = f"https://lite.duckduckgo.com/lite/"
            params = {'q': query}
            
            try:
                response = requests.get(url, params=params, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                results = []
                for link in soup.find_all('a', href=True)[:num_results]:
                    if link.get('href', '').startswith('http'):
                        results.append({
                            'title': link.get_text().strip(),
                            'url': link['href'],
                            'snippet': ''
                        })
                
                return results
            except Exception as e:
                print(f"Search error: {e}")
                return []
        
        else:
            print("No search capability available")
            return []
    
    def research_topic(
        self,
        topic: str,
        num_sources: int = 3
    ) -> Dict[str, any]:
        """
        Research a topic and find contradictions in results.
        
        Phase D+ violation: Stores research results for learning.
        
        Returns:
            {
                'query': topic,
                'sources': [...],
                'contradictions': [...],
                'summary': '...'
            }
        """
        print(f"🔍 Researching: {topic}")
        
        # Search web
        results = self.search_web(topic, num_results=num_sources)
        
        if not results:
            return {
                'query': topic,
                'sources': [],
                'contradictions': [],
                'summary': 'No results found'
            }
        
        # Combine snippets into document
        research_text = f"# Research: {topic}\n\n"
        for i, result in enumerate(results, 1):
            research_text += f"## Source {i}: {result['title']}\n"
            research_text += f"URL: {result['url']}\n"
            research_text += f"{result['snippet']}\n\n"
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(research_text)
            temp_path = f.name
        
        # Index with SSE
        output_dir = f"personal_agent/research/{topic.replace(' ', '_')}"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        os.system(f'python -m sse.cli compress --input "{temp_path}" --out "{output_dir}"')
        
        # Load index
        index_path = f"{output_dir}/index.json"
        if os.path.exists(index_path):
            client = SSEClient(index_path)
            self.sse_indices[topic] = client
            
            # Find contradictions
            contradictions = client.get_all_contradictions()
            
            print(f"✓ Found {len(contradictions)} contradictions in research")
            
            # Cleanup
            os.unlink(temp_path)
            
            return {
                'query': topic,
                'sources': results,
                'contradictions': contradictions,
                'summary': f"Searched {len(results)} sources, found {len(contradictions)} contradictions"
            }
        
        return {
            'query': topic,
            'sources': results,
            'contradictions': [],
            'summary': 'Indexing failed'
        }
    
    def compare_sources(self, topic: str) -> str:
        """
        Show contradictions between sources about a topic.
        """
        if topic not in self.sse_indices:
            return f"No research indexed for '{topic}'. Run research_topic() first."
        
        client = self.sse_indices[topic]
        contradictions = client.get_all_contradictions()
        
        if not contradictions:
            return f"No contradictions found in research about '{topic}'"
        
        output = f"Contradictions in research about '{topic}':\n\n"
        
        for i, contra in enumerate(contradictions, 1):
            output += f"--- Contradiction {i} ---\n"
            output += client.format_contradiction(contra)
            output += "\n\n"
        
        return output


# Example usage
if __name__ == "__main__":
    # Initialize
    researcher = ResearchAgent()
    
    # Research a topic
    results = researcher.research_topic("benefits of sleep", num_sources=3)
    
    print(f"\n{results['summary']}\n")
    
    # Show contradictions
    if results['contradictions']:
        print(researcher.compare_sources("benefits of sleep"))
