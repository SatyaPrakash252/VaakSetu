"""
VaakSetu v2.0 — NLP Engine (Claude API + Enhanced Free Fallback)
Intent extraction, entity recognition, dialect-aware summarization
"""
import os, json, logging, re
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger("vaaksetu.nlp")

# Intent taxonomy for 1092 calls
INTENT_CATEGORIES = {
    "infrastructure": ["road", "pothole", "water_supply", "electricity", "drainage", "garbage", "street_light"],
    "safety": ["domestic_violence", "assault", "harassment", "stalking", "robbery", "theft"],
    "medical": ["medical_emergency", "ambulance_needed", "hospital_complaint", "health_hazard"],
    "administrative": ["corruption", "bribery", "govt_office_complaint", "document_issue"],
    "environmental": ["noise_pollution", "air_pollution", "illegal_dumping", "tree_falling"],
    "emergency": ["fire", "flood", "building_collapse", "gas_leak", "bomb_threat", "kidnapping"],
}

SUMMARY_PROMPT = """You are VaakSetu, an AI assistant for Karnataka's 1092 helpline.
Analyze this citizen's call transcript and extract:

1. **Intent**: What is the citizen reporting? Category and subcategory.
2. **Entities**: Location, people, organizations, dates, specific items mentioned.
3. **Summary**: A clear 2-3 sentence plain-language summary.
4. **Sentiment**: Overall emotional state (calm/concerned/distressed/panicked).
5. **Urgency**: low/medium/high/critical
6. **Suggested Action**: What should the 1092 agent do next?

Handle dialect variations — the citizen may speak in:
- North Karnataka Kannada (Dharwad/Belgaum style)
- Coastal Karnataka Kannada (Mangalore/Udupi)
- Old Mysore Kannada
- Hyderabad-Karnataka Kannada
- Hindi (with regional variations)
- English (with Indian colloquialisms)
- Code-mixed (Kannada-English, Hindi-English)

Respond in JSON format only:
{
  "intent": {"category": "...", "subcategory": "...", "confidence": 0.0},
  "entities": {"location": "...", "people": [], "organizations": [], "items": []},
  "summary": "...",
  "sentiment": {"overall": "...", "negative": 0.0, "urgency_signals": []},
  "urgency": "...",
  "suggested_action": "...",
  "dialect_zone": "..."
}

Transcript: """

VERIFICATION_PROMPT = """Based on this analysis, generate a confirmation sentence that VaakSetu will speak back to the citizen in their own language ({language}).

The sentence should be: "I understand you are reporting [X] at [Y]. Is that correct?"

Analysis: {analysis}

Generate ONLY the confirmation sentence in {language}. Nothing else."""


class NLPEngine:
    def __init__(self):
        self._ready = True
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.client = None
        if self.api_key and self.api_key != "sk-ant-your-key-here":
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                logger.info("NLPEngine: Claude API connected")
            except Exception as e:
                logger.warning(f"Claude API not available: {e}")
        else:
            logger.info("NLPEngine: Running in mock mode (no API key)")

    async def process(self, text: str, language: str = "auto", dialect_zone: str = "general") -> Dict[str, Any]:
        """Process transcript through Claude for intent/entity/summary extraction"""
        if self.client:
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": SUMMARY_PROMPT + text}]
                )
                content = response.content[0].text
                # Try to parse JSON from response
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    return json.loads(content.strip())
                except json.JSONDecodeError:
                    return self._build_result(text, language, raw_response=content)
            except Exception as e:
                logger.error(f"Claude API error: {e}")
                return self._mock_process(text, language, dialect_zone)
        else:
            return self._mock_process(text, language, dialect_zone)

    async def generate_verification(self, analysis: Dict, language: str) -> str:
        """Generate verification sentence for citizen confirmation"""
        if self.client:
            try:
                prompt = VERIFICATION_PROMPT.format(language=language, analysis=json.dumps(analysis))
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()
            except Exception as e:
                logger.error(f"Verification generation error: {e}")
        
        summary = analysis.get("summary", "your issue")
        location = analysis.get("entities", {}).get("location", "your area")
        return f"I understand you are reporting {summary} at {location}. Is that correct?"

    def _mock_process(self, text: str, language: str, dialect_zone: str = "general") -> Dict[str, Any]:
        """Enhanced free NLP when Claude API is not available"""
        text_lower = text.lower()
        words = text_lower.split()
        
        # Intent detection with comprehensive word lists
        category = "general"
        subcategory = "complaint"
        urgency = "low"
        sentiment_neg = 0.2
        urgency_signals = []

        # Negation handling — "not safe" should increase threat
        negation_words = {"not", "no", "nahi", "nahi", "nahin", "mat", "never", "don't", "dont", "can't", "cant", "won't", "wont", "illa", "beda"}
        has_negation = any(w in negation_words for w in words)
        safety_words_raw = ["safe", "ok", "fine", "theek", "thik", "achha"]
        negated_safety = has_negation and any(w in safety_words_raw for w in words)

        # Plea patterns (high urgency)
        plea_patterns = ["please help", "help me", "save me", "save us", "help us",
                        "bachao", "madad karo", "madad chahiye", "help karo", "sahaya",
                        "please save", "i beg", "begging"]
        has_plea = any(p in text_lower for p in plea_patterns)

        # Violence patterns
        violence_patterns = ["maar", "chaku", "chaaku", "gun", "goli", "bandook",
                           "stab", "hit", "beat", "punch", "kick", "slap",
                           "hathiyaar", "weapon", "knife", "sword",
                           "maar raha", "maar daalega"]
        has_violence = any(p in text_lower for p in violence_patterns)

        # Medical patterns
        medical_patterns = ["ambulance", "hospital", "bleeding", "injured", "accident",
                          "fracture", "unconscious", "heart attack", "stroke",
                          "aspatal", "asptre", "khoon", "chot"]
        has_medical = any(p in text_lower for p in medical_patterns)

        # Infrastructure patterns
        infra_patterns = ["road", "pothole", "water", "electricity", "garbage", "drain",
                        "sewage", "street light", "footpath", "bridge",
                        "sadak", "bijli", "pani", "safai", "nali",
                        "raste", "gundi", "current"]
        has_infra = any(p in text_lower for p in infra_patterns)

        # Emergency / Tier 1 patterns
        emergency_words = [
            "help", "help me", "save", "save me", "dying", "die", "dead", "death",
            "kill", "killing", "murder", "stab", "fire", "blood", "bomb", "gun",
            "shoot", "shooting", "hostage", "suicide",
            "bachao", "bachaao", "maar", "maarna", "maar raha", "maar daalega",
            "madad", "madad karo", "help karo",
            "jaan", "jaan se", "khoon", "chaku", "goli", "bandook",
            "marna", "mar jaunga", "mar jaungi",
            "darr", "darr lag raha", "bahut darr",
            "\u092c\u091a\u093e\u0913", "\u092e\u093e\u0930", "\u092e\u093e\u0930\u0928\u093e", "\u0916\u0942\u0928", "\u092e\u0926\u0926", "\u0938\u0939\u093e\u092f\u0924\u093e", "\u091c\u093e\u0928",
            "\u0cb8\u0cb9\u0cbe\u0caf", "\u0c95\u0cca\u0cb2\u0ccd\u0cb2\u0cc1", "\u0cac\u0c9a\u0cbe\u0cb5\u0ccd", "\u0cac\u0cc6\u0c82\u0c95\u0cbf", "\u0cb0\u0c95\u0ccd\u0ca4",
        ]
        
        safety_words = [
            "violence", "domestic violence", "assault", "harass", "abuse",
            "maar raha hai", "maar rahi hai", "maar peet", "maarpeet",
            "dhamki", "darr", "dar", "ladai",
            "\u0ca6\u0ccc\u0cb0\u0ccd\u0c9c\u0ca8\u0ccd\u0caf", "\u0cac\u0cc6\u0ca6\u0cb0\u0cbf\u0c95\u0cc6",
            "\u095b\u0941\u0932\u094d\u092e", "\u0927\u092e\u0915\u0940", "\u0921\u0930", "\u0939\u092e\u0932\u093e",
        ]

        # Count matches for scoring
        emergency_count = sum(1 for w in emergency_words if w in text_lower)
        safety_count = sum(1 for w in safety_words if w in text_lower)

        if negated_safety:
            emergency_count += 1  # "not safe" boosts threat

        if emergency_count >= 2 or (has_plea and has_violence):
            category = "emergency"
            subcategory = "immediate_danger"
            urgency = "critical"
            sentiment_neg = 0.95
            urgency_signals = ["multiple_emergency_keywords", "immediate_threat"]
        elif emergency_count == 1 or has_plea:
            category = "emergency"
            subcategory = "danger_reported"
            urgency = "critical"
            sentiment_neg = 0.85
            urgency_signals = ["emergency_keyword_detected"]
        elif safety_count > 0 or has_violence:
            category = "safety"
            subcategory = "violence_reported"
            urgency = "high"
            sentiment_neg = 0.75
            urgency_signals = ["safety_concern"]
        elif has_medical:
            category = "medical"
            subcategory = "medical_emergency"
            urgency = "high"
            sentiment_neg = 0.6
            urgency_signals = ["medical_attention_needed"]
        elif has_infra:
            category = "infrastructure"
            subcategory = "civic_issue"
            urgency = "medium"
            sentiment_neg = 0.3

        # Extract phone numbers (Indian format)
        phone_match = re.search(r'(\+91[\s-]?)?[6-9]\d{9}', text)
        phone = phone_match.group(0) if phone_match else None

        # Extract location hints
        location = "Bengaluru"
        location_patterns = ["near ", "at ", "in ", "ke paas ", "ke pass ", "mein ", "me "]
        for lp in location_patterns:
            idx = text_lower.find(lp)
            if idx >= 0:
                loc_text = text[idx + len(lp):].split(',')[0].split('.')[0].strip()
                if len(loc_text) > 2 and len(loc_text) < 60:
                    location = loc_text.title()
                    break

        # Generate appropriate summary with templates
        text_preview = text[:100].replace('\n', ' ').strip()
        if category == "emergency" and has_violence:
            summary = f"EMERGENCY: Citizen reporting violent situation — {text_preview}"
        elif category == "emergency":
            summary = f"EMERGENCY: Citizen in distress — {text_preview}"
        elif category == "safety":
            summary = f"SAFETY ALERT: Violence/threat reported — {text_preview}"
        elif category == "medical":
            summary = f"MEDICAL: Emergency medical situation — {text_preview}"
        elif category == "infrastructure":
            summary = f"CIVIC COMPLAINT: Infrastructure issue — {text_preview}"
        else:
            summary = f"Citizen report: {text_preview}"

        confidence = min(1.0, 0.75 + (emergency_count * 0.05))

        entities = {"location": location, "people": [], "organizations": ["BBMP"], "items": []}
        if phone:
            entities["phone"] = phone

        return {
            "intent": {"category": category, "subcategory": subcategory, "confidence": confidence},
            "entities": entities,
            "summary": summary,
            "sentiment": {"overall": "panicked" if urgency == "critical" else "concerned",
                          "negative": sentiment_neg, "urgency_signals": urgency_signals},
            "urgency": urgency,
            "suggested_action": f"Route to {category} department for immediate attention",
            "dialect_zone": dialect_zone if dialect_zone != "general" else ("karnataka" if language == "kn" else "general"),
        }

    def _build_result(self, text: str, language: str, raw_response: str = "") -> Dict:
        result = self._mock_process(text, language)
        result["raw_ai_response"] = raw_response
        return result

    def is_ready(self) -> bool:
        return self._ready
