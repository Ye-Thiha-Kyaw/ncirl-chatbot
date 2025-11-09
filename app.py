from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, session
from flask_cors import CORS
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
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

load_dotenv()

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# ===== SESSION CONFIGURATION FOR AUTHENTICATION =====
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))
app.permanent_session_lifetime = timedelta(hours=2)

CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# ===== DATABASE CONFIGURATION WITH CONNECTION POOLING =====
DATABASE_URL = os.environ.get("DATABASE_URL")

# Create connection pool to manage connections properly
try:
    connection_pool = psycopg2.pool.SimpleConnectionPool(
        1,  # Minimum connections
        10, # Maximum connections
        DATABASE_URL
    )
    if connection_pool:
        print("Connection pool created successfully!")
except Exception as e:
    print(f"Error creating connection pool: {e}")
    connection_pool = None

def get_db_connection():
    """Get a connection from the pool"""
    if connection_pool:
        return connection_pool.getconn()
    else:
        # Fallback to direct connection if pool fails
        return psycopg2.connect(DATABASE_URL)

def return_db_connection(conn):
    """Return connection to the pool"""
    if connection_pool:
        connection_pool.putconn(conn)
    else:
        conn.close()

# ===== ADMIN AUTHENTICATION =====
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# ===== STREAMING SPEED CONTROL =====
STREAM_DELAY = 0.03

# ===== API KEY ROTATION SYSTEM =====
class GroqAPIManager:
    def __init__(self):
        self.api_keys = [
            os.environ.get("GROQ_API_KEY_1"),
            os.environ.get("GROQ_API_KEY_2"),
            os.environ.get("GROQ_API_KEY_3"),
        ]
        self.api_keys = [key for key in self.api_keys if key]
        
        if not self.api_keys:
            raise ValueError("No API keys found in .env file")
        
        self.current_key_index = 0
        self.clients = [Groq(api_key=key) for key in self.api_keys]
        
        print(f"Loaded {len(self.api_keys)} API keys")
    
    def get_client(self):
        return self.clients[self.current_key_index]
    
    def rotate_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"Rotated to API key {self.current_key_index + 1}/{len(self.api_keys)}")
        return self.clients[self.current_key_index]
    
    def make_request(self, messages, model, temperature, max_tokens, stream=True):
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
                
                if 'rate limit' in error_str or 'quota' in error_str or '429' in error_str:
                    print(f"Rate limit hit on key {self.current_key_index + 1}, rotating...")
                    
                    if attempt < len(self.api_keys) - 1:
                        self.rotate_key()
                        continue
                    else:
                        raise Exception("All API keys have reached their rate limit")
                else:
                    raise e
        
        raise Exception("All API keys failed")

groq_manager = GroqAPIManager()

# ===== DATABASE SETUP =====
def init_db():
    """Initialize PostgreSQL database with tables and sample data"""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS conversations
                     (id SERIAL PRIMARY KEY,
                      user_message TEXT,
                      bot_response TEXT,
                      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge_base
                     (id SERIAL PRIMARY KEY,
                      category TEXT,
                      question TEXT,
                      answer TEXT,
                      source TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        c.execute('SELECT COUNT(*) FROM knowledge_base')
        count = c.fetchone()[0]
        
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
            
            c.executemany('INSERT INTO knowledge_base (category, question, answer, source) VALUES (%s, %s, %s, %s)', 
                          sample_data)
        
        conn.commit()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database initialization error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_db_connection(conn)

try:
    init_db()
except Exception as e:
    print(f"Failed to initialize database: {e}")

# ===== HELPER FUNCTIONS =====
def get_knowledge_context():
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT category, question, answer FROM knowledge_base')
        knowledge = c.fetchall()
        
        context = "You are a helpful NCIRL (National College of Ireland) student support assistant. Use this knowledge base to answer questions:\n\n"
        for cat, q, a in knowledge:
            context += f"Category: {cat}\nQ: {q}\nA: {a}\n\n"
        
        return context
    finally:
        if conn:
            return_db_connection(conn)

def save_conversation(user_msg, bot_resp):
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('INSERT INTO conversations (user_message, bot_response) VALUES (%s, %s)',
                  (user_msg, bot_resp))
        conn.commit()
    except Exception as e:
        print(f"Error saving conversation: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_db_connection(conn)

# ===== AUTHENTICATION DECORATOR =====
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ===== AUTHENTICATION ROUTES =====
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        password = request.json.get('password')
        
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session.permanent = True
            return jsonify({'success': True}), 200
        else:
            return jsonify({'success': False, 'error': 'Invalid password'}), 401
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# ===== PUBLIC ROUTES =====
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html')

# ===== CHAT ROUTE =====
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        context = get_knowledge_context()
        
        def generate():
            full_response = ""
            
            try:
                messages = [
                    {
                        "role": "system",
                        "content": context + "\nRespond naturally and conversationally like a helpful human assistant. Be friendly, empathetic, and informative. When listing items, use numbered lists (1. 2. 3.) with clear line breaks. Format course names and important terms in bold using **text** syntax. When mentioning web pages or resources, format them as clickable links using [Link Text](URL) markdown syntax. For example: [English Language Requirements](https://www.ncirl.ie/english-requirements). Remember the conversation context and refer back to previous questions when the user says 'yes', 'no', or gives short responses."
                    }
                ]
                
                for msg in conversation_history[-10:]:
                    messages.append({"role": "user", "content": msg['user']})
                    messages.append({"role": "assistant", "content": msg['bot']})
                
                messages.append({"role": "user", "content": user_message})
                
                stream = groq_manager.make_request(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                    max_tokens=1024,
                    stream=True
                )
                
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        
                        yield f"data: {json.dumps({'content': content})}\n\n"
                        time.sleep(STREAM_DELAY)
                
                save_conversation(user_message, full_response)
                
                yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                print(f"Error in chat: {str(e)}")
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
        return jsonify({'error': str(e)}), 500

# ===== API KEY STATUS ROUTES =====
@app.route('/api-status', methods=['GET'])
def api_status():
    return jsonify({
        'current_key': groq_manager.current_key_index + 1,
        'total_keys': len(groq_manager.api_keys),
        'active_key_partial': groq_manager.api_keys[groq_manager.current_key_index][:10] + "..."
    })

@app.route('/rotate-key', methods=['POST'])
def manual_rotate():
    groq_manager.rotate_key()
    return jsonify({
        'message': 'Key rotated successfully',
        'current_key': groq_manager.current_key_index + 1,
        'total_keys': len(groq_manager.api_keys)
    })

# ===== KNOWLEDGE BASE ROUTES =====
@app.route('/add_knowledge', methods=['POST'])
@admin_required
def add_knowledge():
    conn = None
    try:
        data = request.json
        category = data.get('category', '')
        question = data.get('question', '')
        answer = data.get('answer', '')
        source = data.get('source', 'User Input')
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('INSERT INTO knowledge_base (category, question, answer, source) VALUES (%s, %s, %s, %s)',
                  (category, question, answer, source))
        conn.commit()
        
        return jsonify({'message': 'Knowledge added successfully'}), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/upload_csv', methods=['POST'])
@admin_required
def upload_csv():
    conn = None
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400
        
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        required_columns = ['category', 'question', 'answer']
        
        if not all(col in csv_reader.fieldnames for col in required_columns):
            return jsonify({
                'error': f'CSV must contain columns: {", ".join(required_columns)}. Optional: source'
            }), 400
        
        conn = get_db_connection()
        c = conn.cursor()
        
        added_count = 0
        skipped_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                category = row.get('category', '').strip()
                question = row.get('question', '').strip()
                answer = row.get('answer', '').strip()
                source = row.get('source', 'CSV Import').strip()
                
                if not category or not question or not answer:
                    skipped_count += 1
                    errors.append(f"Row {row_num}: Missing required fields")
                    continue
                
                c.execute('INSERT INTO knowledge_base (category, question, answer, source) VALUES (%s, %s, %s, %s)',
                         (category, question, answer, source))
                added_count += 1
                
            except Exception as e:
                skipped_count += 1
                errors.append(f"Row {row_num}: {str(e)}")
        
        conn.commit()
        
        return jsonify({
            'message': f'Successfully imported {added_count} entries',
            'added': added_count,
            'skipped': skipped_count,
            'errors': errors
        }), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/download_sample_csv', methods=['GET'])
def download_sample_csv():
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
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('SELECT id, category, question, answer, source, created_at FROM knowledge_base ORDER BY created_at DESC')
        rows = c.fetchall()
        
        knowledge = []
        for row in rows:
            knowledge.append({
                'id': row['id'],
                'category': row['category'],
                'question': row['question'],
                'answer': row['answer'],
                'source': row['source'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None
            })
        
        return jsonify(knowledge), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/update_knowledge/<int:id>', methods=['PUT', 'OPTIONS'])
@admin_required
def update_knowledge(id):
    if request.method == 'OPTIONS':
        return '', 204
    
    conn = None
    try:
        data = request.json
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''UPDATE knowledge_base 
                     SET category=%s, question=%s, answer=%s, source=%s 
                     WHERE id=%s''',
                  (data['category'], data['question'], data['answer'], data['source'], id))
        conn.commit()
        return jsonify({'message': 'Knowledge updated successfully'}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/delete_knowledge/<int:id>', methods=['DELETE', 'OPTIONS'])
@admin_required
def delete_knowledge(id):
    if request.method == 'OPTIONS':
        return '', 204
    
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('DELETE FROM knowledge_base WHERE id=%s', (id,))
        conn.commit()
        return jsonify({'message': 'Knowledge deleted successfully'}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/history', methods=['GET'])
@admin_required
def get_history():
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('SELECT user_message, bot_response, timestamp FROM conversations ORDER BY timestamp DESC LIMIT 50')
        rows = c.fetchall()
        
        history = []
        for row in rows:
            history.append({
                'user_message': row['user_message'],
                'bot_response': row['bot_response'],
                'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None
            })
        
        return jsonify(history), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

# ===== CLEANUP ON SHUTDOWN =====
@app.teardown_appcontext
def shutdown_session(exception=None):
    if connection_pool:
        connection_pool.closeall()

# ===== RUN APPLICATION =====
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)