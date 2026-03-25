# 🎓 NCIRL Student Support Chatbot

An intelligent AI-powered chatbot designed to help students at National College of Ireland (NCIRL) with academic queries, campus information, and student services.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📋 Table of Contents

- [Features](#features)
- [Demo](#demo)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Security](#security)
- [Performance](#performance)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## ✨ Features

### 🤖 Intelligent AI Assistant
- **Dual AI Model System**: Uses Llama 3.1 8B for filtering and Llama 3.3 70B for responses
- **Smart Relevance Filtering**: Automatically rejects non-NCIRL questions
- **Keyword-Based Search**: Fast database search with SQL LIKE pattern matching
- **Hybrid Context Loading**: Uses 5 targeted entries for specific questions, 50 entries for general queries

### 💬 Conversational Experience
- **Real-time Streaming**: Character-by-character response display
- **Conversation Memory**: Maintains context across messages (last 10 messages)
- **Follow-up Suggestions**: Hybrid rule-based and AI-generated suggestions
- **Natural Language Understanding**: Handles pronouns and context references

### 🎨 User Interface
- **Responsive Design**: Mobile-first approach (320px - 1920px+)
- **Dark/Light Mode**: Toggle between themes with smooth transitions
- **Real-time Updates**: Server-sent events for live responses
- **Accessible**: WCAG compliant with reduced motion support

### 📊 Admin Panel
- **Knowledge Base Management**: Upload CSV files with Q&A pairs
- **Real-time Analytics**: API usage tracking and performance metrics
- **Secure Authentication**: Password-protected admin access
- **Bulk Upload**: Add multiple entries at once via CSV

### 🔒 Security Features
- **Environment Variables**: Secure credential storage
- **API Key Rotation**: 3 keys with automatic failover
- **Rate Limiting**: Prevent abuse and overload
- **Encrypted Connections**: PostgreSQL SSL support
- **Session Management**: Secure conversation tracking

### 📈 Performance Optimization
- **Smart Caching**: Keyword search reduces API calls by 60%
- **Database Indexing**: Fast query performance
- **Lazy Loading**: On-demand resource loading
- **API Cost Tracking**: Monitor and optimize usage


## 🛠 Technology Stack

### Backend
- **Framework**: Flask 3.0.0
- **Database**: PostgreSQL 14+ / SQLite (development)
- **AI Models**: Llama 3.1 8B, Llama 3.3 70B via Groq API
- **API Client**: Groq Python SDK

### Frontend
- **HTML5/CSS3**: Semantic markup and modern CSS
- **JavaScript**: Vanilla JS (no frameworks)
- **Real-time**: Server-Sent Events (SSE)
- **Responsive**: Mobile-first design

### Deployment
- **Hosting**: Railway / Heroku compatible
- **Database**: Managed PostgreSQL
- **Environment**: Python 3.8+

## 🏗 System Architecture

```
┌─────────────────┐
│  User Question  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ STEP 1: Relevance Check │
│ (Llama 3.1 8B)          │
└────────┬────────────────┘
         │
    ┌────┴────┐
    │         │
  NO│        │YES
    │         │
    ▼         ▼
┌───────┐  ┌──────────────────────┐
│Reject │  │ STEP 2: Keyword      │
└───────┘  │ Search (SQL LIKE)    │
           └────────┬─────────────┘
                    │
              ┌─────┴─────┐
              │           │
           3+ │           │ 0-2
           matches       matches
              │           │
              ▼           ▼
        ┌─────────┐ ┌──────────┐
        │ Use 5   │ │ Load 50  │
        │ entries │ │ entries  │
        └────┬────┘ └────┬─────┘
             │           │
             └─────┬─────┘
                   ▼
        ┌──────────────────────┐
        │ STEP 3: AI Response  │
        │ (Llama 3.3 70B)      │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │ STEP 4: Follow-ups   │
        │ & Save History       │
        └──────────────────────┘
```

### Key Design Decisions

1. **Relevance-First Approach**: Filter irrelevant questions before database lookup
2. **Smart Context Loading**: Use targeted entries when possible, broader context when needed
3. **Dual Model Strategy**: Small model for filtering, large model for generation
4. **API Cost Optimization**: Minimize unnecessary API calls

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- PostgreSQL 14+ (or SQLite for development)
- Groq API keys (free tier available)

### Step 1: Clone Repository

```bash
git clone https://github.com/Ye-Thiha-Kyaw/ncirl-chatbot.git
cd chatbot-project
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up Environment Variables

Create a `.env` file in the project root:

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/chatbot_db

# Groq API Keys (get from https://console.groq.com)
GROQ_API_KEY_1=gsk_your_first_key_here
GROQ_API_KEY_2=gsk_your_second_key_here
GROQ_API_KEY_3=gsk_your_third_key_here

# Admin Password
ADMIN_PASSWORD=your_secure_admin_password

# Flask Secret Key (generate with: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your_secret_key_here

# Optional: For development, use SQLite
# DATABASE_URL=sqlite:///chatbot.db
```

### Step 5: Initialize Database

```bash
python app.py
# Database tables will be created automatically on first run
```

### Step 6: Run the Application

```bash
# Development
python app.py

# Production (with Gunicorn)
gunicorn app:app --bind 0.0.0.0:5000
```

Visit `http://localhost:5000` in your browser.

## ⚙️ Configuration

### Database Setup

#### PostgreSQL (Production)

```bash
# Install PostgreSQL
# Create database
createdb chatbot_db

# Update .env with connection string
DATABASE_URL=postgresql://username:password@localhost:5432/chatbot_db
```

#### SQLite (Development)

```env
# In .env file
DATABASE_URL=sqlite:///chatbot.db
```

### Groq API Keys

1. Sign up at [Groq Console](https://console.groq.com)
2. Create 3 API keys (free tier: 14,400 requests/day per key)
3. Add to `.env` file

### Admin Access

Set admin password in `.env`:
```env
ADMIN_PASSWORD=YourSecurePassword123!
```

Access admin panel at: `http://localhost:5000/admin`

## 🚀 Usage

### For Students

1. **Ask Questions**: Type any NCIRL-related question
2. **Get Instant Answers**: Receive AI-generated responses in real-time
3. **Explore Topics**: Click follow-up suggestions
4. **Clear History**: Use 🗑️ button to reset conversation

### For Administrators

1. **Login**: Navigate to `/admin` and enter password
2. **Upload Knowledge**: Use CSV upload to add Q&A pairs
3. **Monitor Usage**: View API call statistics
4. **Manage Data**: Edit or delete knowledge base entries

### CSV Format for Knowledge Base

```csv
category,question,answer,source
Library Services,What are library hours?,The library is open Monday-Friday 8am-10pm...,NCIRL Library 2024
IT Support,How do I reset my password?,Visit portal.ncirl.ie and click Forgot Password...,IT Department 2024
```

**Required columns:**
- `category`: Topic classification
- `question`: Student question
- `answer`: Detailed response
- `source`: Reference/attribution

## 📚 API Documentation

### Chat Endpoint

**POST** `/chat`

Send a message to the chatbot.

**Request Body:**
```json
{
  "message": "What are the library hours?",
  "session_id": "session_12345" // optional
}
```

**Response:** Server-Sent Events (SSE)

```
data: {"content": "The"}
data: {"content": " library"}
data: {"content": " is"}
...
data: {"done": true, "follow_ups": ["When does the library close?", ...]}
```

### Admin Routes

**GET** `/admin` - Admin panel (requires authentication)

**POST** `/admin/upload` - Upload CSV file
```json
// Request: multipart/form-data
// Field: file (CSV file)

// Response:
{
  "message": "Successfully added 30 entries"
}
```

**GET** `/get_knowledge` - Get all knowledge base entries

**POST** `/update_knowledge/<id>` - Update specific entry

**DELETE** `/delete_knowledge/<id>` - Delete entry

**POST** `/clear-chat` - Clear conversation history

## 📁 Project Structure

```
chatbot-project/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not in repo)
├── .gitignore                  # Git ignore rules
├── README.md                   # This file
│
├── static/
│   ├── css/
│   │   └── style.css          # Main stylesheet (1107 lines)
│   ├── js/
│   │   └── index.js           # Frontend logic
│   └── images/
│       ├── ncirl_logo.png     # College logo
│       └── Flag_of_Ireland.gif # Irish flag
│
├── templates/
│   ├── index.html             # Main chat interface
│   ├── admin.html             # Admin panel
│   ├── admin_login.html       # Admin login
│   └── performance_showcase.html # Performance metrics
│
├── data/
│   ├── sample_data.csv        # Initial knowledge base
│   ├── thiha_info.csv         # Developer info
│   └── demo_presentation.csv  # Demo dataset (30 entries)
│
└── docs/
    └── images/                # Screenshots for README
```

## 🔒 Security

### Best Practices Implemented

✅ **Environment Variables**: Sensitive data not in code
✅ **Password Hashing**: Admin passwords securely stored
✅ **SQL Injection Prevention**: Parameterized queries
✅ **XSS Protection**: Input sanitization
✅ **CORS Configuration**: Controlled cross-origin requests
✅ **Session Security**: Secure session management
✅ **API Key Rotation**: Automatic failover

### Security Checklist

- [ ] Change default admin password
- [ ] Add `.env` to `.gitignore`
- [ ] Use HTTPS in production
- [ ] Enable PostgreSQL SSL
- [ ] Set up firewall rules
- [ ] Regular dependency updates
- [ ] Monitor API usage

## ⚡ Performance

### Optimization Strategies

1. **Smart Context Loading**
   - 5 entries for specific questions (80% of queries)
   - 50 entries for general questions (20% of queries)
   - Result: 60% reduction in token usage

2. **API Cost Management**
   - 3 rotating API keys
   - 43,200 free requests/day
   - Cost tracking per request
   - Average: $0.0006 per question

3. **Database Optimization**
   - Indexed question/answer columns
   - LIMIT clauses on queries
   - Connection pooling

### Performance Metrics

| Metric | Value |
|--------|-------|
| Average Response Time | 2-3 seconds |
| Token Usage (specific) | ~860 tokens |
| Token Usage (general) | ~7,660 tokens |
| API Calls per Question | 2 (relevance + answer) |
| Cost per 100 Questions | ~$0.06 |
| Daily Capacity | 43,200 requests (free tier) |

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add docstrings to functions
- Test thoroughly before submitting
- Update README if adding features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

**Developer**: Thiha
**Email**: yethihakyawythk121@gmail.com
**LinkedIn**: https://www.linkedin.com/in/ye-thiha-kyaw-74864a100/)
**Project Link**: https://ncirl-chatbot.up.railway.app/

## 🙏 Acknowledgments

- **National College of Ireland** - Project inspiration
- **Groq** - AI model hosting and API
- **Meta AI** - Llama 3.1 and 3.3 models
- **Flask Community** - Web framework
- **PostgreSQL** - Database system

---

## 🗺️ Roadmap

### Planned Features

- [ ] Multi-language support (Irish, Spanish, etc.)
- [ ] Voice input/output
- [ ] PDF document upload and analysis
- [ ] Email notifications for important updates
- [ ] Mobile app (React Native)
- [ ] Vector database for semantic search
- [ ] Advanced analytics dashboard
- [ ] Integration with NCIRL student portal

### Version History

**v1.0.0** (Current)
- Initial release
- Basic chat functionality
- Admin panel
- Dark/light mode
- Conversation memory

---

**Made with ❤️ for NCIRL Students**

*Last Updated: December 2024*
