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

# ===== POSTGRESQL SUPPORT =====
import psycopg2
from psycopg2.extras import RealDictCursor
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

if DATABASE_URL:
    print("🐘 Using PostgreSQL database")
    USE_POSTGRES = True
else:
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
    """Get knowledge base context for AI"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT category, question, answer FROM knowledge_base')
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

# ===== CHAT ROUTE WITH STREAMING =====
@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        knowledge_context = get_knowledge_context()
        
        system_prompt = f"""{knowledge_context}

When answering:
1. Be friendly and conversational (use Irish expressions naturally)
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
                stream = groq_manager.make_request(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                    max_tokens=1024,
                    stream=True
                )
                
                full_response = ""
                
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        
                        yield f"data: {json.dumps({'content': content})}\n\n"
                        time.sleep(STREAM_DELAY)
                
                yield f"data: {json.dumps({'done': True})}\n\n"
                
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
    """Check current API key status"""
    return jsonify({
        'current_key': groq_manager.current_key_index + 1,
        'total_keys': len(groq_manager.api_keys),
        'active_key_partial': groq_manager.api_keys[groq_manager.current_key_index][:10] + "..."
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