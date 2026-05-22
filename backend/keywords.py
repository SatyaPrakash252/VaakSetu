"""
VaakSetu — Enhanced Keyword Spotting Engine
Tier 1/2/3 keyword database across Kannada, Hindi, and English
With Aho-Corasick matching, fuzzy matching, transliterations, dialect variants
"""
import json, os, logging, re
from typing import Dict, List, Any

logger = logging.getLogger("vaaksetu.keywords")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Tier 1: Immediate danger (triggers instant alert)
# Tier 2: Escalation needed (raises priority)
# Tier 3: General distress (monitoring)

KEYWORDS_DB = {
    "kn": {
        1: ["ಕೊಲ್ಲುತ್ತಾರೆ", "ಸಾಯಿಸುತ್ತಾರೆ", "ಹೊಡೆಯುತ್ತಿದ್ದಾರೆ", "ಬೆಂಕಿ", "ರಕ್ತ",
            "ಬಚಾವ್", "ಸಹಾಯ", "ಅತ್ಯಾಚಾರ", "ಕಿಡ್ನಾಪ್", "ಬಾಂಬ್",
            "ಕೊಲ್ಲು", "ಸಾಯಿ", "ಹೊಡಿ", "ಸಾವು", "ಹತ್ಯೆ"],
        2: ["ಪೊಲೀಸ್", "ಆಂಬುಲೆನ್ಸ್", "ಆಸ್ಪತ್ರೆ", "ಗಾಯ", "ಅಪಘಾತ",
            "ಕಳ್ಳತನ", "ಲಂಚ", "ಭ್ರಷ್ಟಾಚಾರ", "ಬೆದರಿಕೆ", "ದೌರ್ಜನ್ಯ"],
        3: ["ಸಮಸ್ಯೆ", "ದೂರು", "ಕಷ್ಟ", "ತೊಂದರೆ", "ನೀರು", "ರಸ್ತೆ",
            "ಗುಂಡಿ", "ಕರೆಂಟ್", "ಕಸ", "ಶೌಚಾಲಯ"]
    },
    "hi": {
        1: [
            # Core danger keywords (Devanagari)
            "बचाओ", "मारो", "मार", "मारना", "मारेगा", "मार डालो", "मार दालेगा",
            "मार रहा है", "मार रहा", "मार रही", "मारो मत",
            "खून", "चाकू", "चाक़ू", "आग", "बम", "बॉम्ब",
            "किडनैप", "अपहरण", "रेप", "बलात्कार",
            "मदद", "मदद करो", "सहायता", "बचाव",
            "मरना", "मर जाऊंगा", "मर जाऊंगी", "मर रहा", "मार डालेगा",
            "जान", "जान से मारना", "जान का खतरा",
            "गोली", "बंदूक", "हथियार",
            # Romanized Hindi (CRITICAL for text input matching)
            "bachao", "bachaao", "bachaw", "bachav", "bacho",
            "bachao bachao", "bachao bachao bachao",
            "maar", "marna", "maar raha hai", "maar raha", "maar rahi",
            "maar rahi hai", "maar dala", "maar daalega", "maar dalega",
            "maar do", "maar daalo", "maarna", "maro", "maro mat",
            "khoon", "khun", "chaku", "chaaku",
            "aag", "aag lagi", "aag laga do",
            "bomb", "kidnap", "rape",
            "madad", "madad karo", "madad kijiye",
            "help karo", "help chahiye",
            "sahaya", "sahayata",
            "jaan", "jaan se", "jaan ka khatra",
            "goli", "bandook", "hathiyaar",
            "marna hai", "mar jaunga", "mar jaungi",
            "darr", "darr lag raha", "dar lag raha hai", "bahut darr",
        ],
        2: [
            "पुलिस", "एम्बुलेंस", "अस्पताल", "चोरी", "धमकी",
            "रिश्वत", "ज़ुल्म", "हमला", "डर", "दर्द",
            # Romanized
            "police", "ambulance", "hospital", "chori", "dhamki",
            "rishwat", "zulm", "hamla", "attack", "dard",
            "domestic violence", "violence", "assault",
            "maar peet", "maarpeet", "ladai", "ladaai",
        ],
        3: [
            "समस्या", "शिकायत", "परेशानी", "सड़क", "बिजली",
            "पानी", "गंदा", "सफाई",
            # Romanized
            "problem", "shikayat", "pareshani", "sadak", "bijli",
            "pani", "ganda", "safai", "complaint", "mushkil",
            "dikkat", "takleef", "taklif",
        ]
    },
    "en": {
        1: [
            "kill", "kill me", "killing", "killer",
            "murder", "murdered", "murdering",
            "stab", "stabbing", "stabbed",
            "fire", "on fire", "burning",
            "blood", "bleeding", "bleed",
            "bomb", "bombing", "explosive",
            "kidnap", "kidnapped", "kidnapping", "abducted", "abduction",
            "rape", "raped", "raping", "molest", "molested",
            "help", "help me", "save me", "save us", "help us",
            "dying", "die", "dead", "death",
            "attack", "attacked", "attacking",
            "shoot", "shooting", "shot", "gun", "gunshot",
            "weapon", "knife", "sword",
            "threat", "threatening", "threaten",
            "hostage", "ransom",
            "suicide", "suicidal",
        ],
        2: [
            "police", "ambulance", "hospital", "emergency",
            "injury", "injured", "hurt", "wound", "wounded",
            "accident", "crash",
            "theft", "stolen", "robbed", "robbery", "robbing",
            "assault", "assaulted",
            "domestic violence", "abuse", "abused", "abusing",
            "harass", "harassment", "stalking", "stalker",
            "danger", "dangerous",
        ],
        3: [
            "problem", "complaint", "issue", "concern",
            "road", "pothole", "water", "electricity",
            "garbage", "corruption", "bribe",
            "broken", "damaged", "flooding", "noise",
        ]
    }
}


class KeywordEngine:
    """Enhanced multi-language keyword spotting with Aho-Corasick + fuzzy matching"""

    def __init__(self):
        self._ready = True
        self.keywords = KEYWORDS_DB
        self.dialect_keywords = {}  # dialect_zone -> [keywords]
        self._load_data_files()
        self._build_lookup()
        self._build_automaton()
        total = sum(len(v) for lang in self.keywords.values() for v in lang.values())
        dialect_total = sum(len(v) for v in self.dialect_keywords.values())
        logger.info(f"KeywordEngine loaded: {total} base keywords + {dialect_total} dialect variants across {len(self.keywords)} languages")

    def _load_data_files(self):
        """Load additional keywords and dialect variants from JSON data files"""
        for fname in ["keywords_kn.json", "keywords_hi.json", "keywords_en.json"]:
            fpath = os.path.join(DATA_DIR, fname)
            if not os.path.exists(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for lang, content in data.items():
                    if lang not in self.keywords:
                        self.keywords[lang] = {1: [], 2: [], 3: []}
                    # Merge tier keywords
                    for tier_key in ["tier1", "tier2", "tier3"]:
                        tier_num = int(tier_key[-1])
                        for kw in content.get(tier_key, []):
                            if kw not in self.keywords[lang][tier_num]:
                                self.keywords[lang][tier_num].append(kw)
                    # Load dialect zone keywords as Tier-1/2 depending on severity
                    for zone, words in content.get("dialect_zones", {}).items():
                        self.dialect_keywords[zone] = words
                        for word in words:
                            if word not in self.keywords[lang].get(1, []):
                                self.keywords[lang][1].append(word)
                logger.info(f"Loaded data file: {fname}")
            except Exception as e:
                logger.warning(f"Failed to load {fname}: {e}")

        # Load dialect map
        dialect_map_path = os.path.join(DATA_DIR, "dialect_map.json")
        if os.path.exists(dialect_map_path):
            try:
                with open(dialect_map_path, "r", encoding="utf-8") as f:
                    self.dialect_map = json.load(f)
                logger.info(f"Loaded dialect map with {len(self.dialect_map)} entries")
            except Exception as e:
                self.dialect_map = {}
                logger.warning(f"Failed to load dialect_map.json: {e}")
        else:
            self.dialect_map = {}

    def _build_lookup(self):
        """Build flat lookup dict: keyword -> (language, tier)"""
        self.lookup = {}
        for lang, tiers in self.keywords.items():
            for tier, words in tiers.items():
                for word in words:
                    self.lookup[word.lower().strip()] = {"language": lang, "tier": tier}

    def _build_automaton(self):
        """Build Aho-Corasick automaton for high-performance multi-pattern matching"""
        self._aho = None
        try:
            import ahocorasick_rs
            patterns = list(self.lookup.keys())
            if patterns:
                self._aho = ahocorasick_rs.AhoCorasick(patterns, match_kind=ahocorasick_rs.MatchKind.LeftmostLongest)
                self._aho_patterns = patterns
                logger.info(f"Aho-Corasick automaton built with {len(patterns)} patterns")
        except ImportError:
            logger.info("ahocorasick_rs not available — using substring matching fallback")
        except Exception as e:
            logger.warning(f"Aho-Corasick build failed: {e} — using fallback")

    def detect_dialect_zone(self, text: str) -> str:
        """Detect which Kannada dialect zone the caller is from based on keyword matches"""
        text_lower = text.lower()
        zone_scores = {}
        for zone, words in self.dialect_keywords.items():
            score = sum(1 for w in words if w in text_lower)
            if score > 0:
                zone_scores[zone] = score
        if zone_scores:
            return max(zone_scores, key=zone_scores.get)
        return "general"

    def _is_word_boundary_match(self, text: str, keyword: str, pos: int) -> bool:
        """Check if a keyword match occurs at word boundaries (prevents 'die' matching 'diehard')."""
        if len(keyword) >= 5:
            return True  # Long keywords are reliable as substrings
        # For short keywords, require word boundaries
        before_ok = (pos == 0) or (not text[pos - 1].isalnum())
        end = pos + len(keyword)
        after_ok = (end >= len(text)) or (not text[end].isalnum())
        return before_ok and after_ok

    def _normalize_text(self, text: str) -> str:
        """Normalize text for better matching: handle common spelling variations"""
        text = text.lower().strip()
        # Normalize common transliteration variations
        # Double vowels → single (baachao → bachao)
        text = re.sub(r'(.)\1{2,}', r'\1\1', text)  # Reduce triple+ to double
        return text

    def scan(self, text: str) -> Dict[str, Any]:
        """Scan text for keyword matches using Aho-Corasick + substring + normalized matching"""
        if not text or not text.strip():
            return {
                "total_hits": 0, "tier_counts": {1: 0, 2: 0, 3: 0},
                "hits": [], "highest_tier": None, "severity": "NONE",
                "dialect_zone": "unknown"
            }

        text_lower = text.lower()
        text_normalized = self._normalize_text(text)
        hits = []
        tier_counts = {1: 0, 2: 0, 3: 0}
        matched_keywords = set()

        # Detect dialect zone
        dialect_zone = self.detect_dialect_zone(text)

        # Pass 0: Aho-Corasick multi-pattern matching (fastest)
        if self._aho is not None:
            try:
                matches = self._aho.find_matches_as_indexes(text_lower)
                for pattern_idx, start, end in matches:
                    keyword = self._aho_patterns[pattern_idx]
                    if keyword not in matched_keywords:
                        info = self.lookup[keyword]
                        hits.append({
                            "keyword": keyword,
                            "tier": info["tier"],
                            "language": info["language"],
                            "position": start,
                            "match_type": "aho_corasick"
                        })
                        tier_counts[info["tier"]] += 1
                        matched_keywords.add(keyword)
            except Exception as e:
                logger.warning(f"Aho-Corasick scan error: {e} — falling back")

        # Pass 1: Exact substring matching with word boundary check for short keywords
        for keyword, info in self.lookup.items():
            if keyword in text_lower and keyword not in matched_keywords:
                pos = text_lower.find(keyword)
                # Word boundary check for short keywords to prevent false positives
                if not self._is_word_boundary_match(text_lower, keyword, pos):
                    continue
                hits.append({
                    "keyword": keyword,
                    "tier": info["tier"],
                    "language": info["language"],
                    "position": pos,
                    "match_type": "exact"
                })
                tier_counts[info["tier"]] += 1
                matched_keywords.add(keyword)

        # Pass 2: Normalized matching (handles extra characters)
        if text_normalized != text_lower:
            for keyword, info in self.lookup.items():
                kw_norm = self._normalize_text(keyword)
                if kw_norm in text_normalized and keyword not in matched_keywords:
                    hits.append({
                        "keyword": keyword,
                        "tier": info["tier"],
                        "language": info["language"],
                        "position": text_normalized.find(kw_norm),
                        "match_type": "normalized"
                    })
                    tier_counts[info["tier"]] += 1
                    matched_keywords.add(keyword)

        # Pass 3: Word-level matching (split text into words, check each)
        words = re.split(r'[\s,;.!?]+', text_lower)
        for word in words:
            word = word.strip()
            if not word or word in matched_keywords:
                continue
            if word in self.lookup and word not in matched_keywords:
                info = self.lookup[word]
                hits.append({
                    "keyword": word,
                    "tier": info["tier"],
                    "language": info["language"],
                    "position": text_lower.find(word),
                    "match_type": "word"
                })
                tier_counts[info["tier"]] += 1
                matched_keywords.add(word)

        # Pass 4: Fuzzy phonetic matching for common misspellings
        fuzzy_hits = self._fuzzy_match(text_lower, matched_keywords)
        for fh in fuzzy_hits:
            hits.append(fh)
            tier_counts[fh["tier"]] += 1

        # Sort by tier (highest priority first), then position
        hits.sort(key=lambda x: (x["tier"], x["position"]))

        return {
            "total_hits": len(hits),
            "tier_counts": tier_counts,
            "hits": hits,
            "highest_tier": min(h["tier"] for h in hits) if hits else None,
            "severity": self._calc_severity(tier_counts),
            "dialect_zone": dialect_zone,
        }

    def _fuzzy_match(self, text: str, already_matched: set) -> List[Dict]:
        """Phonetic/fuzzy matching for common misspellings and transliteration errors"""
        fuzzy_map = {
            # Common misspellings → canonical keyword
            "bachho": "bachao", "bachoo": "bachao", "bacho": "bachao",
            "bacchao": "bachao", "bchao": "bachao", "bachav": "bachao",
            "bacchaop": "bachao", "bacchap": "bachao", "bachaoo": "bachao",
            "maaro": "maar", "maarr": "maar",
            "marr": "maar", "maar rha": "maar raha",
            "kil": "kill", "kll": "kill", "killl": "kill",
            "kilme": "kill me", "killme": "kill me",
            "helpp": "help", "hellp": "help", "hlp": "help",
            "helpme": "help me", "saveme": "save me",
            "atack": "attack", "attck": "attack",
            "kidnep": "kidnap", "kidnaap": "kidnap",
            "suside": "suicide", "sucide": "suicide",
            "violance": "violence", "violense": "violence",
            "maar rha hai": "maar raha hai", "mar rha hai": "maar raha hai",
            "mar raha hai": "maar raha hai", "maar rha": "maar raha",
        }

        hits = []
        words = re.split(r'[\s,;.!?]+', text)
        
        # Check individual words and bigrams
        for i, word in enumerate(words):
            word = word.strip()
            if not word or word in already_matched:
                continue
            
            # Check single word fuzzy
            if word in fuzzy_map:
                canonical = fuzzy_map[word]
                if canonical in self.lookup and canonical not in already_matched:
                    info = self.lookup[canonical]
                    hits.append({
                        "keyword": canonical,
                        "tier": info["tier"],
                        "language": info["language"],
                        "position": text.find(word),
                        "match_type": "fuzzy",
                        "original": word
                    })
                    already_matched.add(canonical)
            
            # Check bigrams (two consecutive words)
            if i < len(words) - 1:
                bigram = f"{word} {words[i+1].strip()}"
                if bigram in fuzzy_map:
                    canonical = fuzzy_map[bigram]
                    if canonical in self.lookup and canonical not in already_matched:
                        info = self.lookup[canonical]
                        hits.append({
                            "keyword": canonical,
                            "tier": info["tier"],
                            "language": info["language"],
                            "position": text.find(word),
                            "match_type": "fuzzy",
                            "original": bigram
                        })
                        already_matched.add(canonical)

                # Check trigrams
                if i < len(words) - 2:
                    trigram = f"{word} {words[i+1].strip()} {words[i+2].strip()}"
                    if trigram in fuzzy_map:
                        canonical = fuzzy_map[trigram]
                        if canonical in self.lookup and canonical not in already_matched:
                            info = self.lookup[canonical]
                            hits.append({
                                "keyword": canonical,
                                "tier": info["tier"],
                                "language": info["language"],
                                "position": text.find(word),
                                "match_type": "fuzzy",
                                "original": trigram
                            })
                            already_matched.add(canonical)

        return hits

    def _calc_severity(self, tier_counts: Dict[int, int]) -> str:
        if tier_counts[1] > 0:
            return "CRITICAL"
        elif tier_counts[2] >= 2:
            return "HIGH"
        elif tier_counts[2] > 0:
            return "MEDIUM"
        elif tier_counts[3] > 0:
            return "LOW"
        return "NONE"

    def is_ready(self) -> bool:
        return self._ready
