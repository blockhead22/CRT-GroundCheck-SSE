"""
Code Agent
Writes production code and implements features
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from ..task import Task
from ..llm_client import LLMClient


class CodeAgent(BaseAgent):
    """
    Implementation agent
    
    Responsibilities:
    - Write production code
    - Implement features
    - Refactor existing code
    - Follow boundaries (validated by BoundaryAgent)
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__("CodeAgent")
        self.boundaries = None  # Set by context
        self.llm = llm_client  # Optional LLM for code generation
    
    def execute(self, task: Task) -> Dict:
        """Execute code generation task"""
        self.log(f"Executing: {task.description[:50]}")
        
        # Get boundaries from context (from BoundaryAgent)
        self.boundaries = task.context.get("forbidden_patterns", {})
        
        description = task.description.lower()
        code_type = task.context.get("code_type", "").lower()
        
        if code_type == "html" or "html" in description:
            return self._generate_html(task)
        
        elif code_type == "css" or "css" in description:
            return self._generate_css(task)
        
        elif "test" in description and ("boundary" in description or "phase_6" in description):
            return self._generate_boundary_tests(task.context)
        
        elif "sseclient" in description or "safe wrapper" in description:
            return self._generate_safe_client(task.context)
        
        elif "multi-frame" in description or "multiframeexplainer" in description:
            return self._generate_multi_frame(task.context)
        
        else:
            # Generic code generation
            return self._generate_generic_code(task)
    
    def _generate_boundary_tests(self, context: dict) -> Dict:
        """Generate boundary test code"""
        code = '''"""
Phase 6 Boundary Tests
Tests that ensure SSE never crosses into Phase D-G
"""

import pytest


class TestOutcomeMeasurementForbidden:
    """Verify no outcome measurement exists"""
    
    def test_no_outcome_tracking_tables(self):
        """No database tables for tracking outcomes"""
        # Check database schema
        forbidden_tables = [
            "outcome_data", "recommendation_results",
            "user_followed_advice", "success_metrics"
        ]
        # Implementation: scan schema, ensure none exist
        pass
    
    def test_no_measure_success_methods(self):
        """No methods that measure recommendation success"""
        forbidden_methods = [
            "measure_success", "track_outcome",
            "record_user_action", "measure_recommendation_success"
        ]
        # Implementation: scan all classes, ensure none exist
        pass
    
    def test_recommendations_not_logged_with_outcomes(self):
        """Recommendations logged without outcome tracking"""
        # Can log "recommendation made"
        # Cannot log "recommendation followed" or "recommendation worked"
        pass


class TestPersistentStateForbidden:
    """Verify no persistent learning state"""
    
    def test_no_model_update_methods(self):
        """No methods that update models based on outcomes"""
        forbidden = ["update_model", "learn_from", "improve_confidence"]
        pass
    
    def test_state_is_stateless(self):
        """Each request is independent"""
        # Same input = same output, regardless of history
        pass


class TestConfidenceScoringForbidden:
    """Verify no confidence scores assigned"""
    
    def test_no_confidence_in_contradictions(self):
        """Contradictions have no confidence scores"""
        pass
    
    def test_no_reliability_ratings(self):
        """No rating of claim reliability"""
        pass


class TestTruthFilteringForbidden:
    """Verify all contradictions shown equally"""
    
    def test_no_filtering_by_truth(self):
        """No contradictions filtered by perceived truth"""
        pass
    
    def test_all_contradictions_returned(self):
        """All detected contradictions returned"""
        pass


class TestExplanationRankingForbidden:
    """Verify explanations not ranked"""
    
    def test_no_best_explanation_selection(self):
        """No 'best' explanation picked"""
        pass
    
    def test_all_frames_equal_weight(self):
        """All explanation frames have equal weight"""
        pass
'''
        
        return {
            "file": "tests/test_phase_6_boundaries.py",
            "code": code,
            "tests": 11,
            "categories": 5
        }
    
    def _generate_safe_client(self, context: dict) -> Dict:
        """Generate SSEClient safe wrapper"""
        code = '''"""
SSE Safe Client
Exposes only Phase A-C methods, blocks Phase D-G operations
"""


class SSEClient:
    """
    Safe wrapper around SSE
    Only 9 methods permitted (Phase A-C)
    """
    
    def __init__(self, sse_instance):
        self._sse = sse_instance
    
    # PHASE A: Observation (4 methods)
    
    def extract_contradictions(self, text: str):
        """Extract contradictions from text"""
        return self._sse.extract_contradictions(text)
    
    def get_claims(self, text: str):
        """Extract claims"""
        return self._sse.extract_claims(text)
    
    def get_provenance(self, contradiction_id: str):
        """Get provenance for contradiction"""
        return self._sse.get_provenance(contradiction_id)
    
    def navigate_contradictions(self, filters: dict = None):
        """Navigate contradiction space"""
        return self._sse.navigate(filters)
    
    # PHASE B: Reasoning (2 methods)
    
    def explain_contradiction(self, contradiction_id: str, num_frames: int = 5):
        """Generate multiple explanation frames (unranked)"""
        # Returns 5 frames, no ranking
        return self._sse.multi_frame_explain(contradiction_id, num_frames)
    
    def cite_sources(self, contradiction_id: str):
        """Get source citations"""
        return self._sse.cite_sources(contradiction_id)
    
    # PHASE C: Recommendations (3 methods)
    
    def suggest_investigation(self, contradiction_id: str):
        """Suggest areas to investigate (stateless)"""
        return self._sse.suggest_investigation(contradiction_id)
    
    def log_recommendation(self, recommendation: str):
        """Log recommendation (write-only, no outcome tracking)"""
        # FORBIDDEN: measure if user followed it
        return self._sse.log_recommendation(recommendation)
    
    def get_recommendation_log(self):
        """Get recommendation history (no outcome data)"""
        # Returns: [{"recommendation": "...", "timestamp": "..."}]
        # NOT: [{"recommendation": "...", "followed": true}]
        return self._sse.get_recommendation_log()
    
    # FORBIDDEN METHODS (do not exist)
    # measure_recommendation_success()  <- Phase D
    # track_user_action()               <- Phase D
    # update_model()                    <- Phase E
    # get_confidence_score()            <- Phase D
    # filter_by_truth()                 <- Phase C violation
    # rank_explanations()               <- Phase B violation
'''
        
        return {
            "file": "sse/client.py",
            "code": code,
            "methods": 9,
            "forbidden_methods_documented": 6
        }
    
    def _generate_multi_frame(self, context: dict) -> Dict:
        """Generate MultiFrameExplainer"""
        code = '''"""
Multi-Frame Explanation Engine (Phase B)
Generates multiple explanation frames WITHOUT ranking
"""


class MultiFrameExplainer:
    """
    Generates 5 independent explanation frames
    CRITICAL: No ranking, all frames equal
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def explain(self, contradiction: dict) -> list[dict]:
        """
        Generate 5 explanation frames
        
        Returns:
            List of 5 frames (NO RANKING, NO CONFIDENCE SCORES)
        """
        frames = [
            self._frame_cultural(contradiction),
            self._frame_temporal(contradiction),
            self._frame_contextual(contradiction),
            self._frame_psychological(contradiction),
            self._frame_research(contradiction)
        ]
        
        # FORBIDDEN: sort, rank, score, filter
        # All frames returned equally
        return frames
    
    def _frame_cultural(self, contradiction: dict) -> dict:
        """Frame 1: Cultural/social perspective"""
        prompt = f"""
        Explain this contradiction from a cultural/social perspective.
        Do not judge which is correct.
        
        Contradiction: {contradiction}
        """
        return {"frame": "cultural", "explanation": self.llm.generate(prompt)}
    
    def _frame_temporal(self, contradiction: dict) -> dict:
        """Frame 2: Temporal (time-based) perspective"""
        prompt = f"""
        Explain how this contradiction might reflect change over time.
        Do not resolve the contradiction.
        
        Contradiction: {contradiction}
        """
        return {"frame": "temporal", "explanation": self.llm.generate(prompt)}
    
    def _frame_contextual(self, contradiction: dict) -> dict:
        """Frame 3: Contextual (situation-dependent) perspective"""
        return {"frame": "contextual", "explanation": "..."}
    
    def _frame_psychological(self, contradiction: dict) -> dict:
        """Frame 4: Psychological perspective"""
        return {"frame": "psychological", "explanation": "..."}
    
    def _frame_research(self, contradiction: dict) -> dict:
        """Frame 5: Research/evidence perspective"""
        return {"frame": "research", "explanation": "..."}
'''
        
        return {
            "file": "sse/multi_frame_explainer.py",
            "code": code,
            "frames": 5,
            "ranking": "NONE (forbidden)"
        }
    
    def _generate_generic_code(self, task: Task) -> Dict:
        """Generic code generation"""
        if self.llm:
            # Use LLM to generate code
            self.log("Using LLM for code generation...")
            
            instruction = task.description
            context = f"""
Task context: {task.context}
Boundaries: No outcome measurement, no persistent learning, no confidence scoring.
"""
            
            code = self.llm.generate_code(
                instruction=instruction,
                context=context,
                language="python"
            )
            
            return {
                "code": code,
                "status": "generated (LLM)",
                "model": self.llm.model
            }
        else:
            # Fallback to template
            return {
                "code": f"# Implementation for: {task.description}",
                "status": "generated (template)"
            }
    
    def _generate_html(self, task: Task) -> Dict:
        """Generate HTML for website"""
        business_name = task.context.get("business", "Business")
        
        # Template HTML
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{business_name} - Premium Custom Stickers</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header>
        <nav>
            <div class="logo">{business_name}</div>
            <ul class="nav-links">
                <li><a href="#home">Home</a></li>
                <li><a href="#products">Products</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>

    <section id="home" class="hero">
        <div class="hero-content">
            <h1>Premium Custom Stickers</h1>
            <p>Transform your ideas into stunning, high-quality stickers</p>
            <button class="cta-button">Shop Now</button>
        </div>
    </section>

    <section id="products" class="products">
        <h2>Our Products</h2>
        <div class="product-grid">
            <div class="product-card">
                <div class="product-image"></div>
                <h3>Die-Cut Stickers</h3>
                <p>Custom shapes, vibrant colors</p>
                <span class="price">From $5.99</span>
            </div>
            <div class="product-card">
                <div class="product-image"></div>
                <h3>Vinyl Stickers</h3>
                <p>Waterproof and durable</p>
                <span class="price">From $7.99</span>
            </div>
            <div class="product-card">
                <div class="product-image"></div>
                <h3>Holographic Stickers</h3>
                <p>Eye-catching shine</p>
                <span class="price">From $9.99</span>
            </div>
            <div class="product-card">
                <div class="product-image"></div>
                <h3>Clear Stickers</h3>
                <p>Transparent background</p>
                <span class="price">From $6.99</span>
            </div>
        </div>
    </section>

    <section id="about" class="about">
        <h2>About {business_name}</h2>
        <p>We're passionate about bringing your designs to life with premium quality stickers. 
           From small businesses to artists and hobbyists, we help everyone express their creativity.</p>
        <div class="features">
            <div class="feature">
                <h3>🎨 Custom Designs</h3>
                <p>Upload your artwork or work with our design team</p>
            </div>
            <div class="feature">
                <h3>⚡ Fast Turnaround</h3>
                <p>Most orders ship within 3-5 business days</p>
            </div>
            <div class="feature">
                <h3>✨ Premium Quality</h3>
                <p>Eco-friendly materials, vibrant printing</p>
            </div>
        </div>
    </section>

    <section id="contact" class="contact">
        <h2>Get In Touch</h2>
        <form class="contact-form">
            <input type="text" placeholder="Your Name" required>
            <input type="email" placeholder="Your Email" required>
            <textarea placeholder="Your Message" rows="5" required></textarea>
            <button type="submit">Send Message</button>
        </form>
    </section>

    <footer>
        <p>&copy; 2026 {business_name}. All rights reserved.</p>
        <div class="social-links">
            <a href="#">Instagram</a>
            <a href="#">Facebook</a>
            <a href="#">Twitter</a>
        </div>
    </footer>
</body>
</html>'''
        
        return {
            "code": html,
            "file_type": "html",
            "status": "generated"
        }
    
    def _generate_css(self, task: Task) -> Dict:
        """Generate CSS for website"""
        
        # Template CSS
        css = '''* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

:root {
    --primary: #FF6B9D;
    --secondary: #C06C84;
    --accent: #F67280;
    --dark: #355C7D;
    --light: #F8F9FA;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: var(--dark);
    line-height: 1.6;
}

header {
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    color: white;
    padding: 1rem 0;
    position: sticky;
    top: 0;
    z-index: 1000;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

nav {
    max-width: 1200px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 2rem;
}

.logo {
    font-size: 1.8rem;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 2px;
}

.nav-links {
    display: flex;
    list-style: none;
    gap: 2rem;
}

.nav-links a {
    color: white;
    text-decoration: none;
    font-weight: 500;
    transition: opacity 0.3s;
}

.nav-links a:hover {
    opacity: 0.8;
}

.hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    text-align: center;
    padding: 8rem 2rem;
    position: relative;
    overflow: hidden;
}

.hero h1 {
    font-size: 3.5rem;
    margin-bottom: 1rem;
    animation: fadeInUp 1s ease;
}

.hero p {
    font-size: 1.5rem;
    margin-bottom: 2rem;
}

.cta-button {
    background: var(--accent);
    color: white;
    border: none;
    padding: 1rem 3rem;
    font-size: 1.2rem;
    border-radius: 50px;
    cursor: pointer;
    transition: transform 0.3s, box-shadow 0.3s;
}

.cta-button:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 25px rgba(0,0,0,0.2);
}

.products {
    max-width: 1200px;
    margin: 4rem auto;
    padding: 2rem;
}

.products h2 {
    text-align: center;
    font-size: 2.5rem;
    margin-bottom: 3rem;
}

.product-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 2rem;
}

.product-card {
    background: white;
    border-radius: 15px;
    padding: 1.5rem;
    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    transition: transform 0.3s, box-shadow 0.3s;
    text-align: center;
}

.product-card:hover {
    transform: translateY(-10px);
    box-shadow: 0 15px 30px rgba(0,0,0,0.2);
}

.product-image {
    width: 100%;
    height: 200px;
    background: linear-gradient(135deg, var(--primary), var(--accent));
    border-radius: 10px;
    margin-bottom: 1rem;
}

.product-card h3 {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
}

.price {
    display: block;
    font-size: 1.3rem;
    font-weight: bold;
    color: var(--primary);
}

.about {
    background: var(--light);
    padding: 4rem 2rem;
}

.about h2 {
    text-align: center;
    font-size: 2.5rem;
    margin-bottom: 2rem;
}

.about p {
    max-width: 800px;
    margin: 0 auto 3rem;
    text-align: center;
    font-size: 1.2rem;
}

.features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 2rem;
    max-width: 1200px;
    margin: 0 auto;
}

.feature {
    text-align: center;
    padding: 2rem;
}

.contact {
    max-width: 600px;
    margin: 4rem auto;
    padding: 2rem;
}

.contact h2 {
    text-align: center;
    font-size: 2.5rem;
    margin-bottom: 2rem;
}

.contact-form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.contact-form input,
.contact-form textarea {
    padding: 1rem;
    border: 2px solid #ddd;
    border-radius: 8px;
    font-size: 1rem;
}

.contact-form button {
    background: var(--primary);
    color: white;
    border: none;
    padding: 1rem;
    font-size: 1.1rem;
    border-radius: 8px;
    cursor: pointer;
}

footer {
    background: var(--dark);
    color: white;
    text-align: center;
    padding: 2rem;
}

.social-links {
    margin-top: 1rem;
    display: flex;
    justify-content: center;
    gap: 2rem;
}

.social-links a {
    color: white;
    text-decoration: none;
}

@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@media (max-width: 768px) {
    .hero h1 {
        font-size: 2.5rem;
    }
}'''
        
        return {
            "code": css,
            "file_type": "css",
            "status": "generated"
        }
