"""
Intent Router for CRT Demo
Classifies user input and routes to appropriate handler.

PROD: Replace keyword matching with LLM-based classification
PROD: Add confidence scores for soft routing
PROD: Add intent history for context-aware routing
"""

import re
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


class Intent(Enum):
    # Fact-related
    FACT_STATEMENT = "fact_statement"      # "My name is Nick"
    FACT_QUESTION = "fact_question"        # "What is my name?"
    FACT_CORRECTION = "fact_correction"    # "No, my name is Sarah"
    
    # Task-related
    TASK_CODE = "task_code"                # "Write me a hello world"
    TASK_EXPLAIN = "task_explain"          # "Explain how X works"
    TASK_SUMMARIZE = "task_summarize"      # "Summarize this"
    TASK_GENERAL = "task_general"          # "Help me with X"
    
    # Knowledge-related
    KNOWLEDGE_QUERY = "knowledge_query"    # "What is the capital of France?"
    KNOWLEDGE_OPINION = "knowledge_opinion" # "What do you think about X?"
    
    # Social/Chat
    CHAT_GREETING = "chat_greeting"        # "Hello", "Hi there"
    CHAT_FAREWELL = "chat_farewell"        # "Goodbye", "See you"
    CHAT_SMALLTALK = "chat_smalltalk"      # "How are you?"
    CHAT_EMOTION = "chat_emotion"          # "I'm feeling sad"
    
    # Meta
    META_SYSTEM = "meta_system"            # "How do you work?"
    META_MEMORY = "meta_memory"            # "What do you know about me?"
    
    # Fallback
    UNKNOWN = "unknown"


@dataclass
class RoutedIntent:
    intent: Intent
    confidence: float  # 0.0 - 1.0
    extracted: Dict[str, Any]  # Extracted entities/params
    original: str


class IntentRouter:
    """
    Route user input to appropriate handler based on intent classification.
    """
    
    # Pattern groups for classification
    PATTERNS = {
        # Fact statements - user sharing info about themselves
        Intent.FACT_STATEMENT: [
            r"^my (?:name|favorite|favourite|job|occupation|location|age|birthday)\b",
            r"^i (?:am|work|live|like|love|have|prefer)\b",
            r"^i'm (?:a|an|from|in|called)\b",
            r"^call me\b",
            r"^you can call me\b",
        ],
        
        # Fact corrections
        Intent.FACT_CORRECTION: [
            r"^(?:no|nope|actually|wrong|incorrect)",
            r"^that's (?:not|wrong|incorrect)",
            r"^it's actually\b",
        ],
        
        # Fact questions - asking about stored info
        Intent.FACT_QUESTION: [
            r"^what (?:is|was) my\b",
            r"^what's my\b",
            r"^who am i\b",
            r"^do you (?:know|remember) (?:my|what|who)\b",
            r"^tell me (?:about myself|what you know)\b",
            r"^my .+\?$",  # "my favorite color is?" - question about self
            r"^why (?:is|was) my\b",  # "why is my favorite color orange?" - about their fact
        ],
        
        # Code/programming tasks
        Intent.TASK_CODE: [
            r"(?:write|create|generate|make|code|build|implement)\s+(?:me\s+)?(?:a\s+)?(?:simple\s+)?(?:code|script|program|function|class|hello world|example)",
            r"(?:write|create|show)\s+(?:me\s+)?(?:a\s+)?(?:python|javascript|html|css|sql|java|c\+\+)",
            r"(?:how (?:do|to|would)\s+(?:i|you)\s+)?(?:code|program|implement|write)\b",
            r"(?:can you|could you|please)\s+(?:write|code|create)\b",
        ],
        
        # Explanation tasks (explicit requests only - NOT simple knowledge questions)
        Intent.TASK_EXPLAIN: [
            r"^explain\b",
            r"^describe\b",
            r"^how does .+ work\b",
            r"^why (?:is|are|does|do) .+ \w+ \w+",  # Multi-word why questions
            r"^tell me (?:how|why)\b",
        ],
        
        # Summarization
        Intent.TASK_SUMMARIZE: [
            r"(?:summarize|summary|tldr|tl;dr|brief|shorten)",
        ],
        
        # General tasks
        Intent.TASK_GENERAL: [
            r"^(?:help|assist|can you|could you|please|would you)",
            r"^(?:i need|i want)\s+(?:you to|help)",
        ],
        
        # Knowledge queries (general knowledge, not about user)
        Intent.KNOWLEDGE_QUERY: [
            r"(?:capital|president|population|currency) of\b",  # Factual lookups
            r"^what (?:is|are|was|were) (?:the|a|an)\b(?!.*\bmy\b)",
            r"^who (?:is|was|are|were)\b",
            r"^when (?:did|was|is|will)\b",
            r"^where (?:is|are|was|were)\b",
            r"^how (?:many|much|old|long|far)\b",
            r"^which .+ (?:is|are|was)\b",
        ],
        
        # Opinion/philosophy
        Intent.KNOWLEDGE_OPINION: [
            r"(?:what do you think|your opinion|do you believe|what's the point|meaning of life)",
            r"(?:should i|would you recommend)",
        ],
        
        # Greetings (short only - don't match "hello what is my name?")
        Intent.CHAT_GREETING: [
            r"^(?:hi|hello|hey|howdy|greetings|good (?:morning|afternoon|evening)|yo|sup)[!.,]?$",
            r"^(?:hi|hello|hey) there[!.,]?$",
            r"^(?:hi|hello|hey)[!]?$",
        ],
        
        # Farewells
        Intent.CHAT_FAREWELL: [
            r"^(?:bye|goodbye|see you|later|farewell|good night|take care|cya)",
            r"(?:gotta go|have to go|leaving now)",
        ],
        
        # Smalltalk
        Intent.CHAT_SMALLTALK: [
            r"^how (?:are you|r u|you doing|is it going)",
            r"^what's up\b",
            r"^how's (?:it going|everything|life)",
        ],
        
        # Emotional statements
        Intent.CHAT_EMOTION: [
            r"^i(?:'m| am) (?:feeling |so |very |really )?(?:tired|sad|happy|angry|frustrated|confused|bored|excited|anxious|stressed)",
            r"(?:feeling|felt) (?:tired|sad|happy|angry|frustrated|confused|bored|excited|anxious|stressed)",
            r"^(?:ugh|oof|sigh|yay|wow|omg)\b",
        ],
        
        # Meta - system questions
        Intent.META_SYSTEM: [
            r"(?:how do you work|how does (?:this|crt|the system) work)",
            r"(?:what are you|who are you|what kind of (?:ai|bot|assistant))",
            r"(?:your (?:architecture|design|system))",
        ],
        
        # Meta - memory questions
        Intent.META_MEMORY: [
            r"(?:what do you (?:know|remember) about me)",
            r"(?:show|list|display) (?:my )?(?:facts|memories|info)",
            r"(?:what have i told you)",
        ],
    }
    
    def __init__(self):
        # Compile patterns for efficiency
        self._compiled = {
            intent: [re.compile(p, re.IGNORECASE) for p in patterns]
            for intent, patterns in self.PATTERNS.items()
        }
    
    def classify(self, text: str) -> RoutedIntent:
        """Classify user input and return routed intent."""
        text_clean = text.strip()
        text_lower = text_clean.lower()
        
        # Priority order for checking intents (more specific first)
        priority_order = [
            Intent.CHAT_GREETING,
            Intent.CHAT_FAREWELL, 
            Intent.META_SYSTEM,
            Intent.META_MEMORY,
            Intent.FACT_CORRECTION,
            Intent.FACT_QUESTION,    # Before FACT_STATEMENT (catches "my X is?")
            Intent.FACT_STATEMENT,
            Intent.TASK_CODE,        # Specific task first
            Intent.TASK_SUMMARIZE,   # Specific task
            Intent.KNOWLEDGE_QUERY,  # Before TASK_EXPLAIN ("what is the capital" is knowledge)
            Intent.KNOWLEDGE_OPINION,
            Intent.TASK_EXPLAIN,     # More general
            Intent.TASK_GENERAL,     # Most general task
            Intent.CHAT_EMOTION,
            Intent.CHAT_SMALLTALK,
        ]
        
        # Check in priority order
        for intent in priority_order:
            if intent not in self._compiled:
                continue
            for pattern in self._compiled[intent]:
                if pattern.search(text_lower):
                    # Higher confidence for start-of-string matches
                    conf = 0.9 if pattern.pattern.startswith('^') else 0.75
                    return RoutedIntent(
                        intent=intent,
                        confidence=conf,
                        extracted=self._extract_entities(text_clean, intent),
                        original=text_clean
                    )
        
        return RoutedIntent(
            intent=Intent.UNKNOWN,
            confidence=0.5,
            extracted={},
            original=text_clean
        )
    
    def _extract_entities(self, text: str, intent: Intent) -> Dict[str, Any]:
        """Extract relevant entities based on intent type."""
        extracted = {}
        
        if intent == Intent.TASK_CODE:
            # Try to extract language
            lang_match = re.search(r'\b(python|javascript|js|typescript|ts|html|css|sql|java|c\+\+|rust|go|ruby|php|swift|kotlin)\b', text, re.I)
            if lang_match:
                lang = lang_match.group(1).lower()
                # Normalize aliases
                if lang == 'js':
                    lang = 'javascript'
                elif lang == 'ts':
                    lang = 'typescript'
                extracted['language'] = lang
            
            # Try to extract what to build
            if 'hello world' in text.lower():
                extracted['task'] = 'hello_world'
            elif 'function' in text.lower():
                extracted['task'] = 'function'
            elif 'class' in text.lower():
                extracted['task'] = 'class'
        
        return extracted


# Simple response templates for when no LLM available
TEMPLATES = {
    Intent.CHAT_GREETING: [
        "Hello! How can I help you today?",
        "Hi there! What would you like to know or do?",
        "Hey! Ready to chat or help with something.",
    ],
    Intent.CHAT_FAREWELL: [
        "Goodbye! Take care!",
        "See you later!",
        "Bye! Feel free to come back anytime.",
    ],
    Intent.CHAT_SMALLTALK: [
        "I'm doing well, thanks for asking! How about you?",
        "All good here! What's on your mind?",
    ],
    Intent.CHAT_EMOTION: [
        "I hear you. Want to talk about it, or shall we do something else?",
        "Thanks for sharing that with me. Is there anything I can help with?",
    ],
    Intent.KNOWLEDGE_OPINION: [
        "That's a deep question! I'm a memory-focused AI, so I'm better at remembering facts about you than philosophical debates. What do YOU think?",
    ],
    Intent.META_MEMORY: [
        "Use the 'facts' command to see what I know about you!",
    ],
    Intent.TASK_CODE: {
        'hello_world': {
            'python': 'print("Hello, World!")',
            'javascript': 'console.log("Hello, World!");',
            'html': '<!DOCTYPE html>\n<html>\n<body>\n  <h1>Hello, World!</h1>\n</body>\n</html>',
            'default': 'print("Hello, World!")  # Python',
        },
        'default': "I can help with code! Tell me what language and what you'd like to build.",
    },
    Intent.UNKNOWN: [
        "I'm not sure how to help with that. You can:\n- Tell me facts about yourself (\"My name is...\")\n- Ask what I know (\"What is my name?\")\n- Ask me to write code (\"Write a Python hello world\")",
    ],
}


def get_template_response(routed: RoutedIntent) -> Optional[str]:
    """Get a template response for an intent (no LLM needed)."""
    import random
    
    template = TEMPLATES.get(routed.intent)
    
    if template is None:
        return None
    
    if isinstance(template, list):
        return random.choice(template)
    
    if isinstance(template, dict):
        # Handle nested templates (like code tasks)
        if routed.intent == Intent.TASK_CODE:
            task = routed.extracted.get('task', 'default')
            lang = routed.extracted.get('language', 'default')
            
            task_templates = template.get(task, template.get('default'))
            if isinstance(task_templates, dict):
                return task_templates.get(lang, task_templates.get('default'))
            return task_templates
    
    return None
