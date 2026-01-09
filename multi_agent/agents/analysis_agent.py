"""
Analysis Agent
Performs semantic search, code analysis, and research
"""

import os
from typing import List, Dict, Any, Optional
from .base_agent import BaseAgent
from ..task import Task
from ..llm_client import LLMClient


class AnalysisAgent(BaseAgent):
    """
    Deep analysis and research agent
    
    Responsibilities:
    - Semantic search across codebase
    - Find related implementations
    - Extract information from documents
    - Research best practices
    """
    
    def __init__(self, workspace_path: str = ".", llm_client: Optional[LLMClient] = None):
        super().__init__("AnalysisAgent")
        self.workspace_path = workspace_path
        self.llm = llm_client  # Optional LLM for semantic understanding
    
    def execute(self, task: Task) -> Any:
        """Execute analysis task"""
        self.log(f"Executing: {task.description[:50]}")
        
        description = task.description.lower()
        
        if "read" in description and "roadmap" in description:
            return self._read_roadmap(task.context.get("feature", ""))
        
        elif "search" in description or "find" in description:
            query = task.context.get("query", task.description)
            return self._search_codebase(query)
        
        elif "extract" in description:
            return self._extract_info(task.context)
        
        else:
            # Generic analysis
            return self._analyze_request(task.description)
    
    def _read_roadmap(self, feature_name: str) -> Dict:
        """Read roadmap for specific feature pseudocode"""
        roadmap_files = [
            "COMPLETE_IMPLEMENTATION_ROADMAP.md",
            "PHASE_6_BOUNDARIES_IMPLEMENTATION.md",
            "PROPER_FUTURE_ROADMAP.md"
        ]
        
        pseudocode = []
        found_in = []
        
        for filename in roadmap_files:
            filepath = os.path.join(self.workspace_path, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Search for feature
                    if feature_name.lower() in content.lower():
                        found_in.append(filename)
                        # Extract relevant sections (simplified)
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if feature_name.lower() in line.lower():
                                # Get surrounding context
                                start = max(0, i - 5)
                                end = min(len(lines), i + 20)
                                pseudocode.extend(lines[start:end])
                except Exception as e:
                    self.log(f"Error reading {filename}: {e}")
        
        return {
            "feature": feature_name,
            "found_in": found_in,
            "pseudocode": pseudocode if pseudocode else [f"# Pseudocode for {feature_name} not found in roadmap"],
            "summary": f"Found in {len(found_in)} files" if found_in else "Not found"
        }
    
    def _search_codebase(self, query: str) -> Dict:
        """Search codebase for patterns/keywords"""
        results = {
            "query": query,
            "matches": [],
            "files_scanned": 0
        }
        
        # Search Python files
        for root, dirs, files in os.walk(self.workspace_path):
            # Skip common ignore directories
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', 'venv']]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    results["files_scanned"] += 1
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        if query.lower() in content.lower():
                            # Find line numbers
                            lines = content.split('\n')
                            matching_lines = [
                                (i+1, line) for i, line in enumerate(lines)
                                if query.lower() in line.lower()
                            ]
                            
                            results["matches"].append({
                                "file": filepath,
                                "lines": matching_lines[:5]  # First 5 matches
                            })
                    except Exception as e:
                        pass  # Skip files that can't be read
        
        return results
    
    def _extract_info(self, context: dict) -> Dict:
        """Extract specific information based on context"""
        extract_type = context.get("extract_type", "unknown")
        
        if extract_type == "pr_diff":
            # Extract PR diff (placeholder)
            return {"pr": context.get("pr_number", "unknown"), "diff": []}
        
        return {"extracted": [], "type": extract_type}
    
    def _analyze_request(self, request: str) -> Dict:
        """Generic request analysis"""
        if self.llm:
            self.log("Using LLM for request analysis...")
            try:
                analysis = self.llm.generate(
                    f"Analyze this request and suggest implementation approach: {request}",
                    system_prompt="You are a technical analyst. Provide concise, actionable insights."
                )
                return {
                    "request": request,
                    "analysis": analysis,
                    "llm_used": True,
                    "model": self.llm.model
                }
            except Exception as e:
                self.log(f"LLM analysis error: {e}")
        
        return {
            "request": request,
            "analysis": "Request analyzed (pattern matching only)",
            "suggestions": [],
            "llm_used": False
        }
