from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, session
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import os
from groq import Groq
from dotenv import load_dotenv
import json
import csv
import io
import time
from functools import wraps
import secrets
from hybrid_followup_system import get_hybrid_followup_questions

# ===== POSTGRESQL SUPPORT =====
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("⚠️  psycopg2 not available - PostgreSQL disabled (SQLite will be used)")

from urllib.parse import urlparse

load_dotenv()

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# ===== SESSION CONFIGURATION FOR AUTHENTICATION =====
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))
app.permanent_session_lifetime = timedelta(hours=2)  # Session expires after 2 hours

CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# ===== ADMIN AUTHENTICATION =====
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # Change in .env file!

# ===== STREAMING SPEED CONTROL =====
STREAM_DELAY = 0.03  # ← ADJUST THIS: 0.01 = fast, 0.05 = slow, 0 = instant

# ===== DATABASE CONFIGURATION =====
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and PSYCOPG2_AVAILABLE:
    print("🐘 Using PostgreSQL database")
    USE_POSTGRES = True
else:
    if DATABASE_URL and not PSYCOPG2_AVAILABLE:
        print("⚠️  DATABASE_URL found but psycopg2 not installed - falling back to SQLite")
    print("📁 Using SQLite database (local development)")
    USE_POSTGRES = False

# ===== DATABASE CONNECTION HELPER =====
def get_db_connection():
    """Get database connection based on environment"""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect('chatbot.db')
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn

# ===== API KEY ROTATION SYSTEM =====
class GroqAPIManager:
    def __init__(self):
        # Load all API keys from .env
        self.api_keys = [
            os.environ.get("GROQ_API_KEY_1"),
            os.environ.get("GROQ_API_KEY_2"),
            os.environ.get("GROQ_API_KEY_3"),
        ]
        # Filter out None values
        self.api_keys = [key for key in self.api_keys if key]
        
        if not self.api_keys:
            raise ValueError("No API keys found in .env file")
        
        self.current_key_index = 0
        self.clients = [Groq(api_key=key) for key in self.api_keys]
        
        print(f"Loaded {len(self.api_keys)} API keys")
    
    def get_client(self):
        """Get current Groq client"""
        return self.clients[self.current_key_index]
    
    def rotate_key(self):
        """Switch to next API key"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"Rotated to API key {self.current_key_index + 1}/{len(self.api_keys)}")
        return self.clients[self.current_key_index]
    
    def make_request(self, messages, model, temperature, max_tokens, stream=True):
        """Make API request with automatic key rotation on rate limit"""
        for attempt in range(len(self.api_keys)):
            try:
                client = self.get_client()
                
                response = client.chat.completions.create(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream
                )
                
                return response
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Check if it's a rate limit error
                if 'rate limit' in error_str or 'quota' in error_str or '429' in error_str:
                    print(f"Rate limit hit on key {self.current_key_index + 1}, rotating...")
                    
                    # Try next key if available
                    if attempt < len(self.api_keys) - 1:
                        self.rotate_key()
                        continue
                    else:
                        raise Exception("All API keys have reached their rate limit")
                else:
                    # Different error, don't rotate
                    raise e
        
        raise Exception("All API keys failed")

# Initialize API manager
groq_manager = GroqAPIManager()

# ===== DATABASE SETUP =====
def init_db():
    """Initialize database tables (works for both SQLite and PostgreSQL)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        # PostgreSQL syntax
        cursor.execute('''CREATE TABLE IF NOT EXISTS conversations
                     (id SERIAL PRIMARY KEY,
                      user_message TEXT,
                      bot_response TEXT,
                      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS knowledge_base
                     (id SERIAL PRIMARY KEY,
                      category TEXT,
                      question TEXT,
                      answer TEXT,
                      source TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # API Usage Tracking Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS api_usage
                     (id SERIAL PRIMARY KEY,
                      api_key_index INTEGER,
                      tokens_used INTEGER,
                      request_count INTEGER DEFAULT 1,
                      cost DECIMAL(10, 6),
                      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      date DATE DEFAULT CURRENT_DATE)''')
        
        # Create index for faster date queries
        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_api_usage_date 
                      ON api_usage(date, api_key_index)''')
    else:
        # SQLite syntax
        cursor.execute('''CREATE TABLE IF NOT EXISTS conversations
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_message TEXT,
                      bot_response TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS knowledge_base
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      category TEXT,
                      question TEXT,
                      answer TEXT,
                      source TEXT,
                      created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        # API Usage Tracking Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS api_usage
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      api_key_index INTEGER,
                      tokens_used INTEGER,
                      request_count INTEGER DEFAULT 1,
                      cost REAL,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                      date DATE DEFAULT CURRENT_DATE)''')
        
        # Create index for faster date queries
        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_api_usage_date 
                      ON api_usage(date, api_key_index)''')
    
    # Check if sample data already exists
    cursor.execute('SELECT COUNT(*) FROM knowledge_base')
    count_result = cursor.fetchone()
    
    # Handle both dict-like and tuple results
    if isinstance(count_result, dict):
        count = count_result['count']
    else:
        count = count_result[0] if count_result else 0
    
    # Only insert sample data if table is empty
    if count == 0:
        sample_data = [
            ('admissions', 'How do I apply to NCIRL?', 
             'You can apply through the CAO system for undergraduate courses or directly through the NCIRL website for postgraduate programs. Visit www.ncirl.ie/apply for more information.',
             'NCIRL Student Hub'),
            ('library', 'What are the library opening hours?', 
             'The NCIRL library is open Monday-Friday 8:30am-9:30pm, Saturday 9am-5pm. Hours may vary during exam periods and holidays.',
             'NCIRL Student Hub'),
            ('support', 'Where can I get academic support?', 
             'NCIRL offers tutoring services, writing center support, and academic advising. Visit the Student Hub or book appointments through the student portal.',
             'NCIRL Student Hub'),
            ('facilities', 'What facilities are available on campus?', 
             'NCIRL campus includes computer labs, library, gym, cafeteria, student lounge, and study spaces. All facilities are accessible with your student ID card.',
             'NCIRL Student Hub'),
        ]
        
        if USE_POSTGRES:
            # PostgreSQL placeholder syntax
            for data in sample_data:
                cursor.execute('INSERT INTO knowledge_base (category, question, answer, source) VALUES (%s, %s, %s, %s)', data)
        else:
            # SQLite placeholder syntax
            cursor.executemany('INSERT INTO knowledge_base (category, question, answer, source) VALUES (?, ?, ?, ?)', sample_data)
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# ===== HELPER FUNCTIONS =====
def get_knowledge_context():
    """Get knowledge base context for AI - limited to 50 entries for performance"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # LIMIT to 50 entries to prevent slowdown with large databases
    cursor.execute('SELECT category, question, answer FROM knowledge_base LIMIT 50')
    knowledge = cursor.fetchall()
    conn.close()

    context = "You are a helpful NCIRL (National College of Ireland) student support assistant. Use this knowledge base to answer questions:\n\n"
    for item in knowledge:
        cat = item['category'] if isinstance(item, dict) else item[0]
        q = item['question'] if isinstance(item, dict) else item[1]
        a = item['answer'] if isinstance(item, dict) else item[2]
        context += f"Category: {cat}\nQ: {q}\nA: {a}\n\n"

    return context

def save_conversation(user_msg, bot_resp):
    """Save conversation to database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute('INSERT INTO conversations (user_message, bot_response) VALUES (%s, %s)',
                      (user_msg, bot_resp))
    else:
        cursor.execute('INSERT INTO conversations (user_message, bot_response) VALUES (?, ?)',
                      (user_msg, bot_resp))

    conn.commit()
    conn.close()

def search_knowledge_base(user_question):
    """
    Search knowledge base for relevant answer FIRST (before AI check)

    Returns:
        tuple: (found: bool, matches: list or None)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Simple keyword search in questions and answers
    if USE_POSTGRES:
        cursor.execute('''
            SELECT category, question, answer
            FROM knowledge_base
            WHERE LOWER(question) LIKE %s
               OR LOWER(answer) LIKE %s
            LIMIT 5
        ''', (f'%{user_question.lower()}%', f'%{user_question.lower()}%'))
    else:
        cursor.execute('''
            SELECT category, question, answer
            FROM knowledge_base
            WHERE LOWER(question) LIKE ?
               OR LOWER(answer) LIKE ?
            LIMIT 5
        ''', (f'%{user_question.lower()}%', f'%{user_question.lower()}%'))

    results = cursor.fetchall()
    conn.close()

    if results:
        # Found potential matches
        matches = []
        for row in results:
            if isinstance(row, dict):
                matches.append({
                    'category': row['category'],
                    'question': row['question'],
                    'answer': row['answer']
                })
            else:
                matches.append({
                    'category': row[0],
                    'question': row[1],
                    'answer': row[2]
                })
        return True, matches

    return False, None

def log_api_usage(api_key_index, tokens_used, cost):
    """Log API usage to database for real-time tracking"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if USE_POSTGRES:
            cursor.execute('''INSERT INTO api_usage 
                           (api_key_index, tokens_used, cost) 
                           VALUES (%s, %s, %s)''',
                          (api_key_index, tokens_used, cost))
        else:
            cursor.execute('''INSERT INTO api_usage 
                           (api_key_index, tokens_used, cost) 
                           VALUES (?, ?, ?)''',
                          (api_key_index, tokens_used, cost))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging API usage: {e}")

# =====  NCIRL RELEVANCE CHECKER (NEW!) =====
def is_ncirl_related(user_question, groq_client):
    """
    Check if the question is related to NCIRL using AI
    
    Returns:
        tuple: (is_relevant: bool, reason: str)
    """
    
    prompt = f"""You are a filter for NCIRL (National College of Ireland) student support chatbot.

Analyze if this question is related to NCIRL or general student/education topics:

Question: "{user_question}"

NCIRL-RELATED topics include:
- NCIRL admissions, courses, fees, facilities, campus
- Library, IT services, student support at NCIRL
- General student questions (study tips, exam stress, time management)
- Education-related topics (how to write essays, research methods)
- Career advice for students
- General academic questions

NOT NCIRL-RELATED (reject these):
- Random trivia, jokes, entertainment
- Programming/coding tutorials (unless about NCIRL computing courses)
- General knowledge questions (history, science facts, geography)
- Personal advice unrelated to education
- Weather, sports scores, news
- Math problems, translations
- Recipe requests, travel advice (unless about studying in Ireland)

Respond with ONLY ONE WORD:
- "YES" if related to NCIRL or general student/education topics
- "NO" if completely unrelated

Your response (one word only):"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Fast model for filtering
            messages=[
                {
                    "role": "system",
                    "content": "You are a relevance filter. Respond with only YES or NO."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,  # Low temperature for consistent filtering
            max_tokens=10,
            timeout=5.0
        )
        
        result = response.choices[0].message.content.strip().upper()
        
        if "YES" in result:
            return True, "Question is NCIRL-related"
        elif "NO" in result:
            return False, "Question is not NCIRL-related"
        else:
            # If unclear, allow it (fail open to avoid blocking legitimate queries)
            return True, "Unclear, allowing question"
            
    except Exception as e:
        print(f"⚠️ Relevance check error: {e}")
        # On error, allow question (fail open to avoid blocking legitimate queries)
        return True, f"Error in check: {e}"


def get_daily_api_usage():
    """Get today's API usage statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute('''
            SELECT 
                api_key_index,
                SUM(tokens_used) as total_tokens,
                SUM(request_count) as total_requests,
                SUM(cost) as total_cost
            FROM api_usage
            WHERE date = CURRENT_DATE
            GROUP BY api_key_index
            ORDER BY api_key_index
        ''')
    else:
        cursor.execute('''
            SELECT 
                api_key_index,
                SUM(tokens_used) as total_tokens,
                SUM(request_count) as total_requests,
                SUM(cost) as total_cost
            FROM api_usage
            WHERE date = DATE('now')
            GROUP BY api_key_index
            ORDER BY api_key_index
        ''')
    
    results = cursor.fetchall()
    conn.close()
    
    # Format results
    usage_data = {}
    for row in results:
        key_index = row['api_key_index'] if isinstance(row, dict) else row[0]
        tokens = row['total_tokens'] if isinstance(row, dict) else row[1]
        requests = row['total_requests'] if isinstance(row, dict) else row[2]
        cost = row['total_cost'] if isinstance(row, dict) else row[3]
        
        usage_data[key_index] = {
            'tokens': tokens or 0,
            'requests': requests or 0,
            'cost': float(cost) if cost else 0.0
        }
    
    return usage_data

# ===== AUTHENTICATION DECORATOR =====
def admin_required(f):
    """
    Decorator to protect admin routes
    Redirects to login page if not authenticated
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ===== AUTHENTICATION ROUTES =====
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """
    Admin login page and authentication
    """
    # If already logged in, redirect to admin panel
    if session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        password = request.json.get('password')
        
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session.permanent = True  # Makes session persistent
            return jsonify({'success': True}), 200
        else:
            return jsonify({'success': False, 'error': 'Invalid password'}), 401
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """
    Logout admin and clear session
    """
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# ===== MAIN ROUTES =====
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
@admin_required  # Protect admin route with authentication
def admin():
    """
    Admin panel - only accessible when logged in
    """
    return render_template('admin.html')

@app.route('/performance')
def performance_showcase():
    """
    performance showcase page - demonstrates advanced features and cost analysis
    """
    return render_template('performance_showcase.html')

# ===== 
#  OPTIMIZED CHAT ROUTE: DATABASE FIRST, THEN FILTER =====
@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '')

        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # ✨ STEP 1: Check if question is NCIRL-related FIRST
        groq_client = groq_manager.get_client()
        is_relevant, reason = is_ncirl_related(user_message, groq_client)

        print(f"Relevance check: '{user_message}' -> {is_relevant} ({reason})")

        if not is_relevant:
            #  Return polite rejection for non-NCIRL questions
            def generate_rejection():
                rejection_message = (
                    "I'm specifically designed to help with **NCIRL (National College of Ireland)** "
                    "related questions and general **student/education topics**. \n\n"
                    "Your question seems to be outside my area of expertise. "
                    "Could you ask me something about:\n\n"
                    "• NCIRL admissions, courses, or facilities\n"
                    "• Student support services\n"
                    "• Study tips and exam preparation\n"
                    "• Campus life and accommodation\n"
                    "• General academic questions\n\n"
                    "How can I help you with your studies at NCIRL today?"
                )

                # Stream the rejection message
                for char in rejection_message:
                    yield f"data: {json.dumps({'content': char})}\n\n"
                    time.sleep(0.01)

                # Send completion without follow-ups for rejected questions
                yield f"data: {json.dumps({'done': True, 'follow_ups': []})}\n\n"

            return Response(
                stream_with_context(generate_rejection()),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no'
                }
            )

        #  Question is relevant - search for specific knowledge first
        found_in_db, db_matches = search_knowledge_base(user_message)

        if found_in_db and len(db_matches) >= 3:
            # Found good matches - use them for faster, targeted response
            print(f"✅ Found {len(db_matches)} relevant entries - Using targeted knowledge")
            knowledge_context = "You are a helpful NCIRL student support assistant. Use this relevant information to answer:\n\n"
            for match in db_matches:
                knowledge_context += f"Category: {match['category']}\n"
                knowledge_context += f"Q: {match['question']}\n"
                knowledge_context += f"A: {match['answer']}\n\n"
        else:
            # Not enough specific matches - load broader context
            print(f"⚠️ Limited matches - Loading broader knowledge (50 entries)")
            knowledge_context = get_knowledge_context()
        
        system_prompt = f"""{knowledge_context}

When answering:
1. Be friendly and conversational in clear, professional English
2. If you find relevant info in the knowledge base, use it
3. If the question isn't in the knowledge base, provide helpful general information
4. Keep responses concise but complete
5. Use formatting like **bold** for emphasis and numbered lists when helpful"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        def generate():
            try:
                # Track which key we're using
                current_key_index = groq_manager.current_key_index
                
                stream = groq_manager.make_request(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                    max_tokens=1024,
                    stream=True
                )
                
                full_response = ""
                token_count = 0
                
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        # Estimate tokens (rough: ~4 chars per token)
                        token_count += len(content) // 4
                        
                        yield f"data: {json.dumps({'content': content})}\n\n"
                        time.sleep(STREAM_DELAY)
                
                # Calculate cost ($0.59 per 1M tokens)
                cost = (token_count / 1_000_000) * 0.59
                
                # Log API usage to database
                log_api_usage(current_key_index, token_count, cost)
                
                # ✨ GENERATE FOLLOW-UP QUESTIONS
                try:
                    groq_client = groq_manager.get_client()
                    follow_ups = get_hybrid_followup_questions(
                        user_question=user_message,
                        bot_answer=full_response,
                        groq_client=groq_client,
                        use_ai=True,
                        debug=False
                    )
                    print(f"Generated follow-ups: {follow_ups}")
                except Exception as e:
                    print(f"Follow-up generation error: {e}")
                    follow_ups = [
                        "What are the library hours?",
                        "How do I contact student support?",
                        "What courses are available?"
                    ]
                
                # ✨ SEND WITH FOLLOW-UPS
                yield f"data: {json.dumps({'done': True, 'follow_ups': follow_ups})}\n\n"
                
                # Save conversation after streaming completes
                save_conversation(user_message, full_response)
                
            except Exception as e:
                print(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({'error': 'An error occurred'}), 500

# ===== API STATUS ROUTES =====
@app.route('/api-status', methods=['GET'])
def api_status():
    """Get real-time API usage statistics"""
    # Get today's usage from database
    daily_usage = get_daily_api_usage()
    
    # Prepare key data
    keys_data = []
    total_requests = 0
    total_tokens = 0
    total_cost = 0.0
    
    for i in range(len(groq_manager.api_keys)):
        usage = daily_usage.get(i, {'tokens': 0, 'requests': 0, 'cost': 0.0})
        
        keys_data.append({
            'name': f'Key {i+1}',
            'requests': usage['requests'],
            'limit': 14400,  # Groq free tier limit
            'tokens': usage['tokens'],
            'cost': usage['cost'],
            'is_active': (i == groq_manager.current_key_index)
        })
        
        total_requests += usage['requests']
        total_tokens += usage['tokens']
        total_cost += usage['cost']
    
    return jsonify({
        'activeKey': groq_manager.current_key_index + 1,
        'totalCost': round(total_cost, 6),
        'totalTokens': total_tokens,
        'requestsToday': total_requests,
        'keys': keys_data,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/rotate-key', methods=['POST'])
def manual_rotate():
    """Manually rotate to next API key"""
    groq_manager.rotate_key()
    return jsonify({
        'message': 'Key rotated successfully',
        'current_key': groq_manager.current_key_index + 1,
        'total_keys': len(groq_manager.api_keys)
    })

# ===== KNOWLEDGE BASE ROUTES (PROTECTED) =====
@app.route('/add_knowledge', methods=['POST'])
@admin_required
def add_knowledge():
    try:
        data = request.json
        category = data.get('category', '')
        question = data.get('question', '')
        answer = data.get('answer', '')
        source = data.get('source', 'User Input')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if USE_POSTGRES:
            cursor.execute('INSERT INTO knowledge_base (category, question, answer, source) VALUES (%s, %s, %s, %s)',
                          (category, question, answer, source))
        else:
            cursor.execute('INSERT INTO knowledge_base (category, question, answer, source) VALUES (?, ?, ?, ?)',
                          (category, question, answer, source))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Knowledge added successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload_csv', methods=['POST'])
@admin_required
def upload_csv():
    """Upload CSV file with bulk knowledge entries"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400
        
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        # Expected columns: category, question, answer, source
        required_columns = ['category', 'question', 'answer']
        
        # Check if required columns exist
        if not all(col in csv_reader.fieldnames for col in required_columns):
            return jsonify({
                'error': f'CSV must contain columns: {", ".join(required_columns)}. Optional: source'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        added_count = 0
        skipped_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                category = row.get('category', '').strip()
                question = row.get('question', '').strip()
                answer = row.get('answer', '').strip()
                source = row.get('source', 'CSV Import').strip()
                
                # Validate required fields
                if not category or not question or not answer:
                    skipped_count += 1
                    errors.append(f"Row {row_num}: Missing required fields")
                    continue
                
                # Insert into database
                if USE_POSTGRES:
                    cursor.execute('INSERT INTO knowledge_base (category, question, answer, source) VALUES (%s, %s, %s, %s)',
                                 (category, question, answer, source))
                else:
                    cursor.execute('INSERT INTO knowledge_base (category, question, answer, source) VALUES (?, ?, ?, ?)',
                                 (category, question, answer, source))
                
                added_count += 1
                
            except Exception as e:
                skipped_count += 1
                errors.append(f"Row {row_num}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Successfully imported {added_count} entries',
            'added': added_count,
            'skipped': skipped_count,
            'errors': errors
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_sample_csv', methods=['GET'])
def download_sample_csv():
    """Download a sample CSV template"""
    sample_csv = """category,question,answer,source
admissions,What are the application deadlines?,Applications for undergraduate courses close on February 1st. Postgraduate applications are accepted year-round.,NCIRL Admissions
fees,How much are the tuition fees?,Undergraduate EU students pay approximately €3000 per year. Non-EU and postgraduate fees vary by program.,NCIRL Finance Office
library,Can I borrow books from the library?,Yes! Students can borrow up to 10 books for 2 weeks. Late returns incur fines of €1 per day.,NCIRL Library
courses,What programs does NCIRL offer?,NCIRL offers programs in Business Computing IT Accounting Marketing Psychology and more. Visit ncirl.ie for full list.,NCIRL Website"""
    
    return Response(
        sample_csv,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=knowledge_base_template.csv"}
    )

@app.route('/get_knowledge', methods=['GET'])
@admin_required
def get_knowledge():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, category, question, answer, source, created_at FROM knowledge_base')
        rows = cursor.fetchall()
        conn.close()
        
        knowledge = []
        for row in rows:
            if isinstance(row, dict):
                knowledge.append({
                    'id': row['id'],
                    'category': row['category'],
                    'question': row['question'],
                    'answer': row['answer'],
                    'source': row['source'],
                    'created_at': str(row['created_at'])
                })
            else:
                knowledge.append({
                    'id': row[0],
                    'category': row[1],
                    'question': row[2],
                    'answer': row[3],
                    'source': row[4],
                    'created_at': row[5]
                })
        
        return jsonify(knowledge), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update_knowledge/<int:id>', methods=['PUT', 'OPTIONS'])
@admin_required
def update_knowledge(id):
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if USE_POSTGRES:
            cursor.execute('''UPDATE knowledge_base 
                             SET category=%s, question=%s, answer=%s, source=%s 
                             WHERE id=%s''',
                          (data['category'], data['question'], data['answer'], data['source'], id))
        else:
            cursor.execute('''UPDATE knowledge_base 
                             SET category=?, question=?, answer=?, source=? 
                             WHERE id=?''',
                          (data['category'], data['question'], data['answer'], data['source'], id))
        
        conn.commit()
        conn.close()
        return jsonify({'message': 'Knowledge updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_knowledge/<int:id>', methods=['DELETE', 'OPTIONS'])
@admin_required
def delete_knowledge(id):
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if USE_POSTGRES:
            cursor.execute('DELETE FROM knowledge_base WHERE id=%s', (id,))
        else:
            cursor.execute('DELETE FROM knowledge_base WHERE id=?', (id,))
        
        conn.commit()
        conn.close()
        return jsonify({'message': 'Knowledge deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== HISTORY ROUTE =====
@app.route('/history', methods=['GET'])
@admin_required
def get_history():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_message, bot_response, timestamp FROM conversations ORDER BY timestamp DESC LIMIT 50')
        rows = cursor.fetchall()
        conn.close()
        
        history = []
        for row in rows:
            if isinstance(row, dict):
                history.append({
                    'user_message': row['user_message'],
                    'bot_response': row['bot_response'],
                    'timestamp': str(row['timestamp'])
                })
            else:
                history.append({
                    'user_message': row[0],
                    'bot_response': row[1],
                    'timestamp': row[2]
                })
        
        return jsonify(history), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== RUN APPLICATION =====
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)