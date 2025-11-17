# hybrid_followup_system.py
"""
Hybrid Follow-Up Question Generator
Combines fast rule-based matching with intelligent AI generation

Strategy:
1. Try fast rule-based matching first (common questions)
2. If no good match, use Groq AI to generate contextual suggestions
3. Always have fallback for errors

Author: Ye Thiha Kyaw
"""

import json
from typing import List, Optional

# ===== RULE-BASED CATEGORIES (Fast Path) =====

FOLLOW_UP_CATEGORIES = {
    "library": {
        "triggers": [
            "library hours", "library opening", "library time", "library open",
            "library close", "library schedule", "when does library"
        ],
        "suggestions": [
            "How do I book a study room?",
            "What are the library printing services?",
            "How can I access online library resources?"
        ]
    },
    
    "admissions": {
        "triggers": [
            "how to apply", "application process", "admission requirements",
            "apply to ncirl", "apply to nci", "applying for", "admission",
            "entry requirements", "how do i apply"
        ],
        "suggestions": [
            "What documents do I need for application?",
            "What are the application deadlines?",
            "How long does the admission process take?"
        ]
    },
    
    "courses": {
        "triggers": [
            "available courses", "what courses", "course offerings",
            "programs available", "degree programs", "what can i study"
        ],
        "suggestions": [
            "How do I register for courses?",
            "Can I change my course after registration?",
            "What is the course schedule?"
        ]
    },
    
    "fees": {
        "triggers": [
            "tuition fees", "how much", "cost of", "fees for",
            "payment", "tuition cost", "price of course", "how much does"
        ],
        "suggestions": [
            "What payment methods are accepted?",
            "Are there any scholarships available?",
            "Can I pay fees in installments?"
        ]
    },
    
    "facilities": {
        "triggers": [
            "student hub", "cafeteria", "gym", "facilities",
            "campus facilities", "sports center", "food court", "canteen"
        ],
        "suggestions": [
            "What are the cafeteria hours?",
            "Is there a gym on campus?",
            "Where can I print documents?"
        ]
    },
    
    "it_services": {
        "triggers": [
            "wifi", "email", "password", "student portal", "moodle",
            "internet", "reset password", "login", "computer lab"
        ],
        "suggestions": [
            "How do I reset my student portal password?",
            "How do I connect to campus WiFi?",
            "Where can I get IT support?"
        ]
    },
    
    "accommodation": {
        "triggers": [
            "accommodation", "housing", "where to live", "dormitory",
            "student residence", "halls", "rooms"
        ],
        "suggestions": [
            "How much does student accommodation cost?",
            "How do I apply for accommodation?",
            "What facilities are in the accommodation?"
        ]
    },
    
    "support": {
        "triggers": [
            "counseling", "mental health", "student support", "help",
            "support services", "student services", "need help"
        ],
        "suggestions": [
            "How do I book a counseling appointment?",
            "What disability support services are available?",
            "How can I get academic support?"
        ]
    },
    
    "exams": {
        "triggers": [
            "exam", "assessment", "test", "evaluation",
            "exam dates", "exam timetable", "examination"
        ],
        "suggestions": [
            "When are the exam dates?",
            "Where can I find exam timetables?",
            "What happens if I miss an exam?"
        ]
    },
    
    "international": {
        "triggers": [
            "international student", "visa", "foreign student",
            "overseas student", "non-eu"
        ],
        "suggestions": [
            "What visa do I need to study in Ireland?",
            "Are there English language requirements?",
            "What support is available for international students?"
        ]
    }
}


# ===== RULE-BASED MATCHING (FAST) =====

def match_rule_based_category(user_question: str, bot_answer: str) -> Optional[List[str]]:
    """
    Fast rule-based matching using trigger words
    
    Returns:
        List of suggestions if match found, None otherwise
    """
    # Combine question and answer for better matching
    combined_text = f"{user_question} {bot_answer}".lower()
    
    # Check each category for trigger matches
    for category, data in FOLLOW_UP_CATEGORIES.items():
        for trigger in data["triggers"]:
            if trigger in combined_text:
                return data["suggestions"][:3]
    
    return None  # No match found


# ===== AI-POWERED GENERATION (SMART) =====

def generate_ai_followups(user_question: str, bot_answer: str, groq_client) -> List[str]:
    """
    Use Groq AI to generate intelligent follow-up questions
    
    Args:
        user_question: User's original question
        bot_answer: Bot's response
        groq_client: Groq client instance
        
    Returns:
        List of 3 AI-generated follow-up questions
    """
    
    prompt = f"""You are helping students at NCIRL (National College of Ireland). Based on this conversation, suggest 3 short, practical follow-up questions the student might want to ask next.

Student asked: "{user_question}"
Bot answered: "{bot_answer}"

Generate 3 specific follow-up questions (each under 60 characters) that naturally continue this conversation. Focus on practical student needs.

Respond with ONLY a JSON array of exactly 3 strings. Example: ["Question 1?", "Question 2?", "Question 3?"]

Your response (JSON array only):"""

    try:
        # Use fast model for quick generation
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Fast & cheap
            messages=[
                {
                    "role": "system",
                    "content": "You generate relevant follow-up questions for student support conversations. Always respond with valid JSON arrays only, no other text."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=150,
            timeout=5.0  # 5 second timeout
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Clean up response (remove markdown if present)
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        # Parse JSON
        if response_text.startswith('['):
            follow_ups = json.loads(response_text)
        else:
            # Try to find JSON array in response
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                follow_ups = json.loads(json_match.group())
            else:
                raise ValueError("No JSON array found in response")
        
        # Validate and return
        if isinstance(follow_ups, list) and len(follow_ups) >= 3:
            # Clean up questions (remove extra quotes, trim)
            cleaned = [q.strip().strip('"').strip("'") for q in follow_ups[:3]]
            return cleaned
        else:
            print(f"AI returned invalid format: {follow_ups}")
            return get_default_fallback()
            
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Response was: {response_text[:200]}")
        return get_default_fallback()
    except Exception as e:
        print(f"AI generation error: {e}")
        return get_default_fallback()


# ===== FALLBACK QUESTIONS =====

def get_default_fallback() -> List[str]:
    """Default questions when everything else fails"""
    return [
        "What are the library hours?",
        "How do I contact student support?",
        "What courses are available at NCIRL?"
    ]


# ===== MAIN HYBRID FUNCTION =====

def get_hybrid_followup_questions(
    user_question: str, 
    bot_answer: str, 
    groq_client,
    use_ai: bool = True,
    debug: bool = False
) -> List[str]:
    """
    Hybrid approach: Try fast rules first, fallback to AI
    
    Args:
        user_question: User's question
        bot_answer: Bot's response
        groq_client: Groq client for AI generation
        use_ai: Whether to use AI if rules don't match (default: True)
        debug: Print debug information
        
    Returns:
        List of 3 follow-up questions
    """
    
    # STEP 1: Try fast rule-based matching
    if debug:
        print(f"[HYBRID] Trying rule-based matching...")
    
    rule_based_result = match_rule_based_category(user_question, bot_answer)
    
    if rule_based_result:
        if debug:
            print(f"[HYBRID] ✅ Rule-based match found!")
        return rule_based_result
    
    # STEP 2: No rule match, try AI if enabled
    if use_ai:
        if debug:
            print(f"[HYBRID] No rule match, using AI generation...")
        
        ai_result = generate_ai_followups(user_question, bot_answer, groq_client)
        
        if debug:
            print(f"[HYBRID] ✅ AI generated suggestions")
        
        return ai_result
    
    # STEP 3: AI disabled, return fallback
    if debug:
        print(f"[HYBRID] AI disabled, returning fallback")
    
    return get_default_fallback()


# ===== STATISTICS (Optional - for monitoring) =====

class FollowUpStats:
    """Track which method is being used - good for your report!"""
    
    def __init__(self):
        self.rule_based_count = 0
        self.ai_generated_count = 0
        self.fallback_count = 0
        self.total_count = 0
    
    def record_rule_based(self):
        self.rule_based_count += 1
        self.total_count += 1
    
    def record_ai(self):
        self.ai_generated_count += 1
        self.total_count += 1
    
    def record_fallback(self):
        self.fallback_count += 1
        self.total_count += 1
    
    def get_stats(self):
        if self.total_count == 0:
            return {
                "rule_based_percent": 0,
                "ai_generated_percent": 0,
                "fallback_percent": 0,
                "total_requests": 0
            }
        
        return {
            "rule_based_percent": round(self.rule_based_count / self.total_count * 100, 1),
            "ai_generated_percent": round(self.ai_generated_count / self.total_count * 100, 1),
            "fallback_percent": round(self.fallback_count / self.total_count * 100, 1),
            "total_requests": self.total_count,
            "rule_based_count": self.rule_based_count,
            "ai_generated_count": self.ai_generated_count,
            "fallback_count": self.fallback_count
        }

# Global stats tracker (optional)
stats_tracker = FollowUpStats()


# ===== QUICK TEST FUNCTION =====

def test_hybrid_system():
    """Test the hybrid system with sample queries"""
    
    print("🧪 Testing Hybrid Follow-Up System\n")
    
    test_cases = [
        {
            "question": "What are the library hours?",
            "answer": "The library is open Mon-Fri 8:30am-9:30pm, Sat 9am-5pm.",
            "expected": "rule-based"
        },
        {
            "question": "My laptop broke and I need help urgently",
            "answer": "You can use campus computer labs or contact IT support.",
            "expected": "AI"
        },
        {
            "question": "How do I apply for admission?",
            "answer": "Apply through CAO for undergraduate courses.",
            "expected": "rule-based"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['question']}")
        result = match_rule_based_category(test['question'], test['answer'])
        
        if result:
            print(f"✅ Rule-based match: {result}")
        else:
            print(f"⚡ Would use AI for this query")
        print()


if __name__ == "__main__":
    # Run tests if file is executed directly
    test_hybrid_system()