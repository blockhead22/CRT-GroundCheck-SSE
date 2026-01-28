"""
Data Extractor - Pull training examples from reasoning traces database
"""

import sqlite3
import json
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import glob


@dataclass
class TrainingExample:
    """A single training example with query, facts, thinking, and response."""
    query: str
    facts: List[str]  # List of "slot=value (trust)" strings
    thinking: str
    response: str
    confidence: float = 0.7
    thread_id: str = ""
    
    def to_training_format(self) -> str:
        """Format as training sequence."""
        facts_str = "\n".join(f"- {f}" for f in self.facts) if self.facts else "(no facts)"
        return (
            f"<query>{self.query}</query>\n"
            f"<facts>\n{facts_str}\n</facts>\n"
            f"<think>{self.thinking}</think>\n"
            f"<response>{self.response}</response>"
        )
    
    def to_dict(self) -> Dict:
        return asdict(self)


class DataExtractor:
    """Extract training data from CRT memory databases."""
    
    def __init__(self, db_pattern: str = "personal_agent/crt_memory_t_*.db"):
        self.db_pattern = db_pattern
        
    def find_databases(self) -> List[str]:
        """Find all thread-specific databases."""
        return glob.glob(self.db_pattern)
    
    def extract_from_db(self, db_path: str) -> List[TrainingExample]:
        """Extract training examples from a single database."""
        examples = []
        
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            
            # Check if reasoning_traces table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='reasoning_traces'"
            )
            if not cursor.fetchone():
                conn.close()
                return []
            
            # Get reasoning traces with thinking content
            traces = conn.execute("""
                SELECT trace_id, query, thinking_content, response_summary, 
                       thread_id, model, metadata, created_at
                FROM reasoning_traces
                WHERE thinking_content IS NOT NULL 
                AND LENGTH(thinking_content) > 50
                ORDER BY created_at DESC
            """).fetchall()
            
            # Get facts/memories for context
            memories = {}
            try:
                mem_rows = conn.execute("""
                    SELECT memory_id, text, trust, slot_type, slot_value
                    FROM memories
                    WHERE trust > 0.5
                    ORDER BY trust DESC
                    LIMIT 100
                """).fetchall()
                
                for m in mem_rows:
                    memories[m['memory_id']] = {
                        'text': m['text'],
                        'trust': m['trust'],
                        'slot_type': m['slot_type'],
                        'slot_value': m['slot_value']
                    }
            except:
                pass  # memories table might not exist
            
            conn.close()
            
            # Build training examples
            for trace in traces:
                query = trace['query'] or ""
                thinking = trace['thinking_content'] or ""
                response = trace['response_summary'] or ""
                
                # Skip if missing key components
                if not query or not thinking or len(thinking) < 50:
                    continue
                
                # Extract facts from metadata if available
                facts = []
                try:
                    metadata = json.loads(trace['metadata'] or '{}')
                    # Add any referenced memories as facts
                    for mem_id in metadata.get('memory_ids', []):
                        if mem_id in memories:
                            m = memories[mem_id]
                            if m['slot_type'] and m['slot_value']:
                                facts.append(f"{m['slot_type']}={m['slot_value']} ({m['trust']:.2f})")
                            else:
                                facts.append(f"{m['text'][:100]} ({m['trust']:.2f})")
                except:
                    pass
                
                # Also extract facts mentioned in thinking
                fact_patterns = [
                    r"name[=:]\s*(\w+)",
                    r"favorite\s+(\w+)[=:]\s*(\w+)",
                    r"trust[=:]?\s*([\d.]+)",
                ]
                
                example = TrainingExample(
                    query=query.strip(),
                    facts=facts,
                    thinking=thinking.strip(),
                    response=response.strip() if response else "",
                    thread_id=trace['thread_id'] or ""
                )
                examples.append(example)
                
        except Exception as e:
            print(f"Error extracting from {db_path}: {e}")
            
        return examples
    
    def extract_all(self) -> List[TrainingExample]:
        """Extract from all databases."""
        all_examples = []
        
        for db_path in self.find_databases():
            examples = self.extract_from_db(db_path)
            all_examples.extend(examples)
            print(f"Extracted {len(examples)} examples from {db_path}")
            
        # Also check shared DB
        shared_db = "personal_agent/crt_memory_shared.db"
        if Path(shared_db).exists():
            examples = self.extract_from_db(shared_db)
            all_examples.extend(examples)
            print(f"Extracted {len(examples)} examples from {shared_db}")
            
        return all_examples
    
    def extract_reflection_data(self) -> List[Dict]:
        """Extract reflection traces for confidence learning."""
        reflections = []
        
        for db_path in self.find_databases():
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                
                rows = conn.execute("""
                    SELECT * FROM reflection_traces
                    WHERE confidence_score IS NOT NULL
                """).fetchall()
                
                for row in rows:
                    reflections.append({
                        'confidence_score': row['confidence_score'],
                        'confidence_label': row['confidence_label'],
                        'reasoning': row['reasoning'],
                        'hallucination_risk': row['hallucination_risk'],
                        'fact_checks': json.loads(row['fact_checks'] or '[]')
                    })
                    
                conn.close()
            except:
                pass
                
        return reflections
    
    def save_training_data(self, examples: List[TrainingExample], output_path: str = "data/training_examples.jsonl"):
        """Save extracted examples to JSONL file."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for ex in examples:
                f.write(json.dumps(ex.to_dict(), ensure_ascii=False) + '\n')
                
        print(f"Saved {len(examples)} examples to {output_path}")
        
    def load_training_data(self, input_path: str = "data/training_examples.jsonl") -> List[TrainingExample]:
        """Load examples from JSONL file."""
        examples = []
        
        if not Path(input_path).exists():
            return examples
            
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                examples.append(TrainingExample(**data))
                
        return examples


if __name__ == "__main__":
    # Test extraction
    extractor = DataExtractor()
    examples = extractor.extract_all()
    print(f"\nTotal examples extracted: {len(examples)}")
    
    if examples:
        print("\nSample example:")
        print(examples[0].to_training_format()[:500])
        
        extractor.save_training_data(examples)
