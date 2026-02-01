"""
Privacy Filter for Moltbook Posts
Removes personal information before posting to Moltbook.com
"""

import re
from typing import Dict, List, Optional


class PrivacyFilter:
    """Sanitizes content to remove personal information."""
    
    def __init__(self):
        # Personal information patterns to redact
        self.personal_patterns = [
            # Names
            (r'\bNick\b', '[human]'),
            (r'\bNick Block\b', '[human]'),
            (r'\bBlockhead\b', '[human]'),
            
            # Email patterns
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[email]'),
            
            # Phone numbers (various formats)
            (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[phone]'),
            (r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b', '[phone]'),
            
            # Addresses (basic patterns)
            (r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct)\b', '[address]'),
            
            # Social Security Numbers
            (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),
            
            # Credit card patterns
            (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[card]'),
            
            # Specific locations that might be too revealing
            (r'\bMicrosoft\b', '[employer]'),
            
            # Possessive references to human
            (r'\bmy human(?:\'s)?\s+(?:name is\s+)?[A-Z][a-z]+\b', 'my human'),
            (r'\b(?:named|called)\s+Nick\b', 'my human'),
        ]
        
        # Terms that reveal too much personal context
        self.sensitive_terms = [
            'my human Nick',
            'Nick and I',
            'working with Nick',
        ]
    
    def sanitize_text(self, text: str) -> str:
        """Remove personal information from text."""
        if not text:
            return text
        
        sanitized = text
        
        # Apply pattern replacements
        for pattern, replacement in self.personal_patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        # Remove sensitive multi-word terms
        for term in self.sensitive_terms:
            sanitized = sanitized.replace(term, 'my human')
        
        return sanitized
    
    def sanitize_post(self, title: str, content: str) -> Dict[str, str]:
        """Sanitize both title and content of a post."""
        return {
            'title': self.sanitize_text(title),
            'content': self.sanitize_text(content)
        }
    
    def sanitize_comment(self, content: str) -> str:
        """Sanitize comment content."""
        return self.sanitize_text(content)
    
    def check_for_leaks(self, text: str) -> List[str]:
        """Check if text contains potential personal information leaks."""
        leaks = []
        
        # Check for name patterns
        if re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', text):
            leaks.append("Possible full name detected")
        
        # Check for email
        if re.search(r'@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}', text):
            leaks.append("Email address detected")
        
        # Check for phone numbers
        if re.search(r'\d{3}[-.]?\d{3}[-.]?\d{4}', text):
            leaks.append("Phone number detected")
        
        # Check for specific personal names we know about
        if re.search(r'\bNick\b', text, re.IGNORECASE):
            leaks.append("Human's name detected")
        
        return leaks


def test_privacy_filter():
    """Test the privacy filter."""
    filter = PrivacyFilter()
    
    test_cases = [
        ("My human Nick helps me", "My human [human] helps me"),
        ("Working with Nick Block on this", "Working with [human] on this"),
        ("Email me at test@example.com", "Email me at [email]"),
        ("Call 555-123-4567", "Call [phone]"),
        ("I work at Microsoft", "I work at [employer]"),
        ("My human's name is Nick", "My human"),
        ("This is safe content", "This is safe content"),
    ]
    
    print("🧪 TESTING PRIVACY FILTER\n")
    
    for original, expected in test_cases:
        result = filter.sanitize_text(original)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{original}'")
        print(f"   → '{result}'")
        if result != expected:
            print(f"   Expected: '{expected}'")
        print()
    
    # Check leak detection
    print("🔍 LEAK DETECTION TEST\n")
    leak_test = "My name is Nick Block and you can email me at nick@example.com"
    leaks = filter.check_for_leaks(leak_test)
    print(f"Text: '{leak_test}'")
    print(f"Leaks detected: {leaks}")


if __name__ == "__main__":
    test_privacy_filter()
