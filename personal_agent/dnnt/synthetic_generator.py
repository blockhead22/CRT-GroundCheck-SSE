"""
Synthetic Data Generator - Bootstrap training with realistic synthetic examples
"""

import random
from typing import List, Dict, Tuple
from .data_extractor import TrainingExample


class SyntheticGenerator:
    """Generate synthetic training examples to bootstrap the model."""
    
    # Slot types and example values
    SLOTS = {
        'name': ['Nick', 'Alex', 'Sam', 'Jordan', 'Taylor', 'Casey', 'Morgan', 'Riley'],
        'favorite_color': ['blue', 'red', 'green', 'orange', 'purple', 'black', 'yellow', 'pink'],
        'favorite_food': ['pizza', 'sushi', 'tacos', 'pasta', 'burgers', 'ramen', 'curry', 'salad'],
        'occupation': ['developer', 'designer', 'teacher', 'engineer', 'artist', 'student', 'manager'],
        'hobby': ['coding', 'gaming', 'reading', 'music', 'sports', 'cooking', 'photography'],
        'pet': ['dog', 'cat', 'fish', 'bird', 'hamster', 'rabbit', 'none'],
        'location': ['New York', 'London', 'Tokyo', 'Paris', 'Berlin', 'Sydney', 'Toronto'],
        'age': ['25', '30', '35', '22', '28', '40', '45'],
    }
    
    # Query templates for different intents
    QUERY_TEMPLATES = {
        'name_ask': [
            "What is my name?",
            "What's my name?",
            "Do you know my name?",
            "Who am I?",
            "Can you tell me my name?",
            "Say my name",
        ],
        'name_tell': [
            "My name is {name}",
            "I'm {name}",
            "Call me {name}",
            "You can call me {name}",
            "{name} here",
        ],
        'favorite_ask': [
            "What is my favorite {slot}?",
            "What's my favorite {slot}?",
            "Do you know my favorite {slot}?",
            "Tell me my favorite {slot}",
        ],
        'favorite_tell': [
            "My favorite {slot} is {value}",
            "I love {value}",
            "I really like {value}",
            "{value} is my favorite {slot}",
        ],
        'general_ask': [
            "What do you know about me?",
            "Tell me what you remember",
            "What have I told you?",
            "Summarize what you know",
        ],
        'math': [
            "What is {a} + {b}?",
            "What is {a} plus {b}?",
            "Calculate {a} + {b}",
            "{a} + {b} = ?",
        ],
        'greeting': [
            "Hello!",
            "Hi there",
            "Hey",
            "Good morning",
            "Good afternoon",
        ],
        'thanks': [
            "Thanks!",
            "Thank you",
            "Thanks for that",
            "Appreciate it",
        ],
    }
    
    # Thinking patterns
    THINKING_PATTERNS = {
        'name_ask_known': """The user is asking for their name. Let me check my facts.

I have stored that their name is {name} with trust score {trust}. This is a high confidence fact.

Since the trust is high, I can answer directly and confidently. I'll keep the response friendly and concise.""",
        
        'name_ask_unknown': """The user is asking for their name, but I need to check if I have this information.

Looking through my facts... I don't see a name stored. The user hasn't told me their name yet.

I should politely ask them to share their name so I can remember it for future conversations.""",
        
        'name_tell': """The user is telling me their name is {name}. This is important identity information.

I should acknowledge this and store it as a fact. The trust should be high since it's self-reported.

I'll confirm I've noted it and use their name in my response to show I'm paying attention.""",
        
        'favorite_ask_known': """The user wants to know their favorite {slot}. Let me check my stored facts.

I have that their favorite {slot} is {value} with trust {trust}. This was told to me previously.

I'll confirm this fact in a friendly way. Since trust is high, I can be confident in my answer.""",
        
        'favorite_ask_unknown': """The user is asking about their favorite {slot}, but I need to verify I have this.

Checking my facts... I don't have their favorite {slot} stored. They haven't shared this yet.

I should let them know I don't have this information and invite them to share it.""",
        
        'favorite_tell': """The user is sharing that their favorite {slot} is {value}. This is a preference I should remember.

I'll store this as a new fact with high trust since it's coming directly from them.

I should acknowledge their preference positively and maybe ask a follow-up to show engagement.""",
        
        'math': """The user is asking a simple math question: {a} + {b}.

This is a straightforward arithmetic calculation. {a} plus {b} equals {result}.

I'll give a direct answer since this is factual. No need for elaboration unless they ask.""",
        
        'greeting': """The user is greeting me. I should respond warmly.

{name_context}

I'll return the greeting in a friendly manner and perhaps ask how I can help.""",
        
        'general_summary': """The user wants to know what I remember about them. Let me compile my facts.

I have the following stored:
{facts_summary}

I should present this information clearly and let them know they can correct anything.""",
        
        'unknown': """The user's query is: "{query}"

I'm not sure what they're asking about or I don't have relevant information.

I should acknowledge I don't understand or don't have that information, and ask for clarification.""",
    }
    
    # Response templates
    RESPONSE_TEMPLATES = {
        'name_known': [
            "Your name is {name}!",
            "You're {name}!",
            "I have your name as {name}.",
            "Hi {name}! That's what you told me.",
        ],
        'name_unknown': [
            "I don't think you've told me your name yet. What should I call you?",
            "I don't have your name stored. What's your name?",
            "I'm not sure - could you tell me your name?",
        ],
        'name_confirm': [
            "Nice to meet you, {name}! I'll remember that.",
            "Got it, {name}! I've noted your name.",
            "Hello {name}! I'll remember you.",
        ],
        'favorite_known': [
            "Your favorite {slot} is {value}!",
            "I have that as {value}.",
            "You told me {value} is your favorite {slot}.",
        ],
        'favorite_unknown': [
            "I don't have your favorite {slot} stored. What is it?",
            "I'm not sure - you haven't told me your favorite {slot} yet.",
        ],
        'favorite_confirm': [
            "Great choice! I'll remember that {value} is your favorite {slot}.",
            "Nice! {value} is now saved as your favorite {slot}.",
            "{value}? Good taste! I've noted that.",
        ],
        'math': [
            "{a} + {b} equals {result}.",
            "That's {result}!",
            "The answer is {result}.",
            "{a} plus {b} is {result}.",
        ],
        'greeting': [
            "Hello! How can I help you today?",
            "Hi there! What's on your mind?",
            "Hey! Good to see you. What can I do for you?",
        ],
        'greeting_known': [
            "Hello {name}! How can I help you today?",
            "Hi {name}! What's on your mind?",
            "Hey {name}! Good to see you.",
        ],
        'summary': [
            "Here's what I know about you:\n{facts_list}\n\nLet me know if anything needs updating!",
            "From our conversations, I remember:\n{facts_list}",
        ],
        'unknown': [
            "I'm not sure I understand. Could you rephrase that?",
            "I don't have information about that. Could you tell me more?",
            "I'm not certain what you mean. Can you clarify?",
        ],
    }
    
    def __init__(self, seed: int = 42):
        random.seed(seed)
        
    def generate_user_profile(self) -> Dict[str, Tuple[str, float]]:
        """Generate a random user profile with facts and trust scores."""
        profile = {}
        
        # Randomly select which slots this user has shared
        num_slots = random.randint(2, len(self.SLOTS))
        selected_slots = random.sample(list(self.SLOTS.keys()), num_slots)
        
        for slot in selected_slots:
            value = random.choice(self.SLOTS[slot])
            trust = round(random.uniform(0.7, 0.98), 2)
            profile[slot] = (value, trust)
            
        return profile
    
    def format_facts(self, profile: Dict[str, Tuple[str, float]]) -> List[str]:
        """Format profile as fact strings."""
        facts = []
        for slot, (value, trust) in profile.items():
            facts.append(f"{slot}={value} ({trust})")
        return facts
    
    def generate_name_ask_example(self, profile: Dict) -> TrainingExample:
        """Generate example for asking name."""
        query = random.choice(self.QUERY_TEMPLATES['name_ask'])
        
        if 'name' in profile:
            name, trust = profile['name']
            thinking = self.THINKING_PATTERNS['name_ask_known'].format(
                name=name, trust=trust
            )
            response = random.choice(self.RESPONSE_TEMPLATES['name_known']).format(name=name)
            facts = self.format_facts(profile)
        else:
            thinking = self.THINKING_PATTERNS['name_ask_unknown']
            response = random.choice(self.RESPONSE_TEMPLATES['name_unknown'])
            facts = self.format_facts(profile)
            
        return TrainingExample(query=query, facts=facts, thinking=thinking, response=response)
    
    def generate_name_tell_example(self) -> TrainingExample:
        """Generate example for telling name."""
        name = random.choice(self.SLOTS['name'])
        query = random.choice(self.QUERY_TEMPLATES['name_tell']).format(name=name)
        thinking = self.THINKING_PATTERNS['name_tell'].format(name=name)
        response = random.choice(self.RESPONSE_TEMPLATES['name_confirm']).format(name=name)
        
        return TrainingExample(query=query, facts=[], thinking=thinking, response=response)
    
    def generate_favorite_ask_example(self, profile: Dict) -> TrainingExample:
        """Generate example for asking favorite."""
        # Pick a random slot type (not name)
        slot_type = random.choice([s for s in self.SLOTS.keys() if s != 'name' and 'favorite' in s or s in ['color', 'food', 'hobby']])
        display_slot = slot_type.replace('favorite_', '').replace('_', ' ')
        
        query = random.choice(self.QUERY_TEMPLATES['favorite_ask']).format(slot=display_slot)
        
        if slot_type in profile or f'favorite_{slot_type}' in profile:
            key = slot_type if slot_type in profile else f'favorite_{slot_type}'
            value, trust = profile.get(key, profile.get(f'favorite_{slot_type}', ('unknown', 0.5)))
            thinking = self.THINKING_PATTERNS['favorite_ask_known'].format(
                slot=display_slot, value=value, trust=trust
            )
            response = random.choice(self.RESPONSE_TEMPLATES['favorite_known']).format(
                slot=display_slot, value=value
            )
        else:
            thinking = self.THINKING_PATTERNS['favorite_ask_unknown'].format(slot=display_slot)
            response = random.choice(self.RESPONSE_TEMPLATES['favorite_unknown']).format(slot=display_slot)
            
        return TrainingExample(query=query, facts=self.format_facts(profile), thinking=thinking, response=response)
    
    def generate_favorite_tell_example(self) -> TrainingExample:
        """Generate example for telling favorite."""
        slot_type = random.choice(['color', 'food', 'hobby'])
        value = random.choice(self.SLOTS.get(f'favorite_{slot_type}', self.SLOTS.get(slot_type, ['something'])))
        
        query = random.choice(self.QUERY_TEMPLATES['favorite_tell']).format(slot=slot_type, value=value)
        thinking = self.THINKING_PATTERNS['favorite_tell'].format(slot=slot_type, value=value)
        response = random.choice(self.RESPONSE_TEMPLATES['favorite_confirm']).format(slot=slot_type, value=value)
        
        return TrainingExample(query=query, facts=[], thinking=thinking, response=response)
    
    def generate_math_example(self) -> TrainingExample:
        """Generate simple math example."""
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        result = a + b
        
        query = random.choice(self.QUERY_TEMPLATES['math']).format(a=a, b=b)
        thinking = self.THINKING_PATTERNS['math'].format(a=a, b=b, result=result)
        response = random.choice(self.RESPONSE_TEMPLATES['math']).format(a=a, b=b, result=result)
        
        return TrainingExample(query=query, facts=[], thinking=thinking, response=response)
    
    def generate_greeting_example(self, profile: Dict) -> TrainingExample:
        """Generate greeting example."""
        query = random.choice(self.QUERY_TEMPLATES['greeting'])
        
        if 'name' in profile:
            name, _ = profile['name']
            name_context = f"I remember their name is {name}. I should use it to be personal."
            thinking = self.THINKING_PATTERNS['greeting'].format(name_context=name_context)
            response = random.choice(self.RESPONSE_TEMPLATES['greeting_known']).format(name=name)
        else:
            name_context = "I don't know their name yet."
            thinking = self.THINKING_PATTERNS['greeting'].format(name_context=name_context)
            response = random.choice(self.RESPONSE_TEMPLATES['greeting'])
            
        return TrainingExample(query=query, facts=self.format_facts(profile), thinking=thinking, response=response)
    
    def generate_summary_example(self, profile: Dict) -> TrainingExample:
        """Generate summary example."""
        query = random.choice(self.QUERY_TEMPLATES['general_ask'])
        
        facts = self.format_facts(profile)
        facts_summary = "\n".join(f"- {f}" for f in facts) if facts else "No facts stored yet."
        facts_list = "\n".join(f"• {f}" for f in facts) if facts else "Nothing stored yet."
        
        thinking = self.THINKING_PATTERNS['general_summary'].format(facts_summary=facts_summary)
        response = random.choice(self.RESPONSE_TEMPLATES['summary']).format(facts_list=facts_list)
        
        return TrainingExample(query=query, facts=facts, thinking=thinking, response=response)
    
    def generate_batch(self, num_examples: int = 500) -> List[TrainingExample]:
        """Generate a batch of synthetic training examples."""
        examples = []
        
        # Distribution of example types
        generators = [
            (self.generate_name_ask_example, 0.15),
            (self.generate_name_tell_example, 0.10),
            (self.generate_favorite_ask_example, 0.15),
            (self.generate_favorite_tell_example, 0.15),
            (self.generate_math_example, 0.15),
            (self.generate_greeting_example, 0.15),
            (self.generate_summary_example, 0.15),
        ]
        
        for _ in range(num_examples):
            # Generate a random profile for context
            profile = self.generate_user_profile()
            
            # Pick a generator based on distribution
            r = random.random()
            cumulative = 0
            for gen_func, prob in generators:
                cumulative += prob
                if r < cumulative:
                    try:
                        # Some generators need profile, some don't
                        if gen_func in [self.generate_name_tell_example, 
                                       self.generate_favorite_tell_example,
                                       self.generate_math_example]:
                            example = gen_func()
                        else:
                            example = gen_func(profile)
                        examples.append(example)
                    except Exception as e:
                        print(f"Error generating example: {e}")
                    break
                    
        return examples


if __name__ == "__main__":
    generator = SyntheticGenerator()
    examples = generator.generate_batch(100)
    
    print(f"Generated {len(examples)} examples\n")
    print("Sample examples:\n")
    
    for i, ex in enumerate(examples[:3]):
        print(f"--- Example {i+1} ---")
        print(ex.to_training_format())
        print()
