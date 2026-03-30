"""Unified Tool Definition Registry for CRT.

Single source of truth for all tools available to the agent.
Used by:
  - LLM Intent Router (Tier 2/3) — tool schemas sent to LLM for routing
  - _build_plan() — parameter mapping
  - _execute_step() — dispatch validation

Sprint 13 / v2.9
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema primitives
# ---------------------------------------------------------------------------

@dataclass
class ToolParam:
    """Describes a single parameter for a tool."""
    name: str
    type: str  # "string", "integer", "boolean", "object", "array"
    description: str
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[str]] = None


@dataclass
class ToolDefinition:
    """Complete definition for one CRT tool."""
    name: str                                   # e.g. "file_read"
    description: str                            # Human-readable, used in LLM prompt
    parameters: List[ToolParam] = field(default_factory=list)
    access_layer: int = 1                       # 1-6 from the access layer model
    checkpoint_tier: str = "none"               # "none", "medium", "high"
    examples: List[str] = field(default_factory=list)  # Example user messages
    intent_type: str = ""                       # Maps to semantic intent name
    synthesis_mode: str = "smart"               # "always" | "on_request" | "never" | "smart"

    def to_llm_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI-compatible function-calling schema."""
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for p in self.parameters:
            prop: Dict[str, Any] = {"type": p.type, "description": p.description}
            # OpenAI strictly requires "items" on every array schema
            if p.type == "array":
                prop["items"] = {"type": "string"}
            if p.enum:
                prop["enum"] = p.enum
            if p.default is not None:
                prop["default"] = p.default
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        schema: Dict[str, Any] = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                },
            },
        }
        if required:
            schema["function"]["parameters"]["required"] = required
        return schema


# ---------------------------------------------------------------------------
# Tool Registry — all CRT tools
# ---------------------------------------------------------------------------

TOOL_REGISTRY: Dict[str, ToolDefinition] = {}


def _register(td: ToolDefinition) -> None:
    TOOL_REGISTRY[td.name] = td


# ---- system_info ----
_register(ToolDefinition(
    name="system_info",
    description="Get current system information including CPU, RAM, disk, GPU usage and OS details",
    parameters=[],
    access_layer=1,
    checkpoint_tier="none",
    intent_type="system_info",
    synthesis_mode="smart",
    examples=[
        "how's my system",
        "what's my cpu usage",
        "system status",
        "show system info",
        "what does my system look like right now",
        "how much ram am I using",
        "check my disk space",
    ],
))

# ---- file_read ----
_register(ToolDefinition(
    name="file_read",
    description="Read the contents of a file at the given path and return its text",
    parameters=[
        ToolParam("path", "string", "Absolute or relative file path to read", required=True),
    ],
    access_layer=2,
    checkpoint_tier="none",
    intent_type="file_read",
    synthesis_mode="smart",
    examples=[
        "read this file",
        "show me the contents of config.yaml",
        "open the README",
        "what's in this file",
        "read ROADMAP.md and summarize it",
        "tell me what's in ACTION_EXECUTION.md",
    ],
))

# ---- file_write ----
_register(ToolDefinition(
    name="file_write",
    description="Create or overwrite a file at the given path with the specified content",
    parameters=[
        ToolParam("path", "string", "File path to write to", required=True),
        ToolParam("content", "string", "Content to write to the file", required=True),
    ],
    access_layer=3,
    checkpoint_tier="medium",
    intent_type="file_write",
    synthesis_mode="never",
    examples=[
        "create a file called test.txt with hello world",
        "write a new config file",
        "save this to notes.md",
        "create an HTML page",
    ],
))

# ---- dir_list ----
_register(ToolDefinition(
    name="dir_list",
    description="List files and directories at the given path",
    parameters=[
        ToolParam("path", "string", "Directory path to list (defaults to project root)", required=False, default="."),
    ],
    access_layer=1,
    checkpoint_tier="none",
    intent_type="dir_list",
    synthesis_mode="on_request",
    examples=[
        "what's in this folder",
        "list the files",
        "show me the directory contents",
        "what files are in /data",
        "ls",
    ],
))

# ---- search_code ----
_register(ToolDefinition(
    name="search_code",
    description="Search the codebase for a text pattern (like grep). Returns matching lines with file paths and line numbers. Read-only, no side effects.",
    parameters=[
        ToolParam("pattern", "string", "Text or regex pattern to search for", required=True),
        ToolParam("path", "string", "Directory to search in (default: project root)", required=False, default="."),
        ToolParam("glob", "string", "File glob filter, e.g. '*.py' or '*.md'", required=False),
        ToolParam("max_results", "integer", "Maximum number of matching lines to return", required=False, default=30),
    ],
    access_layer=2,
    checkpoint_tier="none",
    intent_type="search_code",
    synthesis_mode="smart",
    examples=[
        "search for belief_speech in the code",
        "find where governance is called",
        "grep for TODO in python files",
        "search the codebase for tension_detector",
        "where is the trust scoring logic",
        "find all uses of CRTMemorySystem",
    ],
))

# ---- project_scan ----
_register(ToolDefinition(
    name="project_scan",
    description="Scan project directory for structure, git status, and key files",
    parameters=[
        ToolParam("path", "string", "Project root path to scan", required=False, default="."),
    ],
    access_layer=1,
    checkpoint_tier="none",
    intent_type="project_scan",
    synthesis_mode="always",
    examples=[
        "what's the git status",
        "scan this project",
        "show project structure",
        "what's changed in the repo",
    ],
))

# ---- shell_exec ----
_register(ToolDefinition(
    name="shell_exec",
    description="Execute a shell command and return stdout/stderr",
    parameters=[
        ToolParam("command", "string", "The shell command to run", required=True),
        ToolParam("cwd", "string", "Working directory for the command", required=False),
    ],
    access_layer=4,
    checkpoint_tier="high",
    intent_type="shell_exec",
    synthesis_mode="never",
    examples=[
        "run npm install",
        "execute python script.py",
        "run the tests",
        "pip install requests",
    ],
))

# ---- git_exec ----
_register(ToolDefinition(
    name="git_exec",
    description="Execute a git command (status, log, diff, commit, etc.)",
    parameters=[
        ToolParam("args", "array", "Git subcommand and arguments, e.g. ['status'] or ['commit', '-m', 'fix']", required=True),
        ToolParam("cwd", "string", "Working directory for git", required=False),
    ],
    access_layer=3,
    checkpoint_tier="medium",
    intent_type="git_action",
    synthesis_mode="never",
    examples=[
        "git status",
        "commit these changes",
        "show the git log",
        "git diff",
        "create a new branch",
    ],
))

# ---- fetch_url ----
_register(ToolDefinition(
    name="fetch_url",
    description="Fetch content from a URL (HTTP GET) and return the response body",
    parameters=[
        ToolParam("url", "string", "The URL to fetch", required=True),
    ],
    access_layer=2,
    checkpoint_tier="none",
    intent_type="url_fetch",
    synthesis_mode="smart",
    examples=[
        "fetch https://example.com",
        "get the contents of this URL",
        "download this page",
        "what's at this link",
    ],
))

# ---- desktop_action ----
_register(ToolDefinition(
    name="desktop_action",
    description="Perform a literal desktop automation action (open apps, click UI elements, type text, take screenshots). ONLY for physical computer control — NEVER for questions, opinions, memory recall, or reflective conversation.",
    parameters=[
        ToolParam("task", "string", "Natural language description of the desktop task to perform", required=True),
    ],
    access_layer=5,
    checkpoint_tier="high",
    intent_type="desktop_action",
    synthesis_mode="never",
    examples=[
        "open notepad",
        "take a screenshot",
        "open chrome and go to google",
        "click the start menu",
    ],
))

# ---- create_commitment ----
_register(ToolDefinition(
    name="create_commitment",
    description="Create a reminder, commitment, or scheduled task for the user",
    parameters=[
        ToolParam("intent", "string", "What the user wants to be reminded about", required=True),
        ToolParam("description", "string", "Full description of the commitment", required=False),
        ToolParam("deadline", "string", "When the reminder should fire (ISO 8601 or natural language)", required=False),
        ToolParam("recurrence", "string", "Recurrence pattern if repeating (daily, weekly, etc.)", required=False),
        ToolParam("priority", "string", "Priority level: low, medium, high", required=False, default="medium"),
    ],
    access_layer=2,
    checkpoint_tier="none",
    intent_type="create_commitment",
    synthesis_mode="never",
    examples=[
        "remind me at 5pm to do X",
        "set an alarm for tomorrow morning",
        "create a reminder to check email daily",
        "remind me every Monday to review PRs",
    ],
))

# ---- list_commitments ----
_register(ToolDefinition(
    name="list_commitments",
    description="List the user's active reminders and commitments",
    parameters=[],
    access_layer=1,
    checkpoint_tier="none",
    intent_type="list_commitments",
    synthesis_mode="never",
    examples=[
        "what are my reminders",
        "show my commitments",
        "list my upcoming tasks",
        "what do I have scheduled",
    ],
))

# ---- cancel_commitment ----
_register(ToolDefinition(
    name="cancel_commitment",
    description="Cancel or delete an existing reminder or commitment",
    parameters=[
        ToolParam("commitment_id", "string", "ID or description of the commitment to cancel", required=True),
    ],
    access_layer=2,
    checkpoint_tier="medium",
    intent_type="cancel_commitment",
    synthesis_mode="never",
    examples=[
        "cancel my 5pm reminder",
        "delete the daily standup reminder",
        "remove that commitment",
    ],
))

# ---- generate_content ----
_register(ToolDefinition(
    name="generate_content",
    description="Generate text content (code, documents, creative writing) based on a description",
    parameters=[
        ToolParam("description", "string", "What to generate", required=True),
        ToolParam("path", "string", "File path to save the generated content", required=False),
        ToolParam("language", "string", "Programming language if generating code", required=False),
    ],
    access_layer=2,
    checkpoint_tier="none",
    intent_type="generate_content",
    synthesis_mode="never",
    examples=[
        "write a Python function to sort a list",
        "generate an HTML landing page",
        "write a bash script to backup my files",
    ],
))

# ---- memory_recall ----
_register(ToolDefinition(
    name="memory_recall",
    description="Search the agent's memory for information the user previously shared",
    parameters=[
        ToolParam("query", "string", "What to recall from memory", required=True),
    ],
    access_layer=1,
    checkpoint_tier="none",
    intent_type="broad_recall",
    synthesis_mode="always",
    examples=[
        "what do you remember about my project",
        "recall my preferences",
        "what did I tell you about X",
    ],
))

# ---- http_post ----
_register(ToolDefinition(
    name="http_post",
    description="Make an HTTP POST request to an API endpoint with a JSON payload",
    parameters=[
        ToolParam("url", "string", "Full URL to POST to", required=True),
        ToolParam("payload", "object", "JSON body to send", required=True),
        ToolParam("headers", "object", "Optional HTTP headers", required=False),
    ],
    access_layer=3,
    checkpoint_tier="medium",
    intent_type="service_action",
    examples=[],
))

# ---- http_get_json ----
_register(ToolDefinition(
    name="http_get_json",
    description="Make an HTTP GET request and return the JSON response",
    parameters=[
        ToolParam("url", "string", "Full URL to GET", required=True),
        ToolParam("headers", "object", "Optional HTTP headers", required=False),
    ],
    access_layer=2,
    checkpoint_tier="none",
    intent_type="service_action",
    examples=[],
))

# ---- store_credential ----
_register(ToolDefinition(
    name="store_credential",
    description="Securely store a credential or API key for later use",
    parameters=[
        ToolParam("key", "string", "Name to store the credential under", required=True),
        ToolParam("value", "string", "The credential value to store", required=False),
    ],
    access_layer=3,
    checkpoint_tier="medium",
    intent_type="imperative_task",
    examples=[
        "store my API key",
        "save this credential",
    ],
))

# ---- web_browse ----
_register(ToolDefinition(
    name="web_browse",
    description="Browse a website — navigate, read content, click links, fill forms, extract information",
    parameters=[
        ToolParam("task", "string", "What to do on the web (natural language)", required=True),
        ToolParam("url", "string", "Starting URL to navigate to", required=False),
    ],
    access_layer=3,
    checkpoint_tier="medium",
    synthesis_mode="always",
    intent_type="web_browse",
    examples=[
        "go to hacker news and tell me the top 5 stories",
        "search google for playwright python tutorial",
        "check the weather on weather.com",
        "go to this url and summarize the page",
        "fill out the contact form on example.com",
        "look up the latest python release notes",
        "find the pricing on that website",
    ],
))

# ---- web_search ----
_register(ToolDefinition(
    name="web_search",
    description="Search the web for external information. ONLY when user explicitly asks to search online, look something up, or needs current/external data not in memory. NEVER for opinions, personal questions about the user, or reflective conversation.",
    parameters=[
        ToolParam("query", "string", "The search query", required=True),
    ],
    access_layer=2,
    checkpoint_tier="none",
    synthesis_mode="always",
    intent_type="web_search",
    examples=[
        "search for how to use playwright",
        "look up the population of Tokyo",
        "find recent news about AI",
        "google fastapi websocket tutorial",
        "search for best python testing frameworks 2026",
    ],
))


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_tool(name: str) -> Optional[ToolDefinition]:
    """Look up a tool definition by name."""
    return TOOL_REGISTRY.get(name)


def get_synthesis_mode(tool_name: str) -> str:
    """Get the synthesis_mode for a tool. Defaults to 'smart'."""
    td = TOOL_REGISTRY.get(tool_name)
    return td.synthesis_mode if td else "smart"


def get_tools_for_intent(intent_type: str) -> List[ToolDefinition]:
    """Get all tools that match a given intent type."""
    return [t for t in TOOL_REGISTRY.values() if t.intent_type == intent_type]


# ---- inquiry_queue (Phase G4: Active Inference) ----
_register(ToolDefinition(
    name="inquiry_queue",
    description="Show what the agent is uncertain about — a prioritized queue of beliefs that need clarification, evidence, or user input to reduce uncertainty",
    parameters=[],
    access_layer=1,
    checkpoint_tier="none",
    intent_type="inquiry_queue",
    synthesis_mode="smart",
    examples=[
        "what are you uncertain about",
        "what don't you know",
        "what should I clarify",
        "show me your questions",
        "what beliefs need updating",
        "where are you confused",
    ],
))


def get_all_llm_schemas() -> List[Dict[str, Any]]:
    """Get OpenAI-compatible function schemas for ALL tools (for LLM routing)."""
    return [t.to_llm_schema() for t in TOOL_REGISTRY.values()]


def get_routing_schemas() -> List[Dict[str, Any]]:
    """Get schemas for tools suitable for intent routing.

    Excludes internal/low-level tools (http_post, http_get_json, store_credential)
    that are used in multi-step execution but not directly routed to.
    """
    _ROUTING_EXCLUDE = {"http_post", "http_get_json", "store_credential"}
    return [
        t.to_llm_schema()
        for t in TOOL_REGISTRY.values()
        if t.name not in _ROUTING_EXCLUDE
    ]


def intent_to_tool_names(intent_type: str) -> List[str]:
    """Map an intent type to tool names (replaces _INTENT_TOOL_MAP)."""
    return [t.name for t in TOOL_REGISTRY.values() if t.intent_type == intent_type]
