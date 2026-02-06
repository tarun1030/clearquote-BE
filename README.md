# ClearQuote - Natural Language to SQL Query System
A production-ready FastAPI application that converts natural language questions about vehicle damage, repairs, and quotes into SQL queries, executes them against a PostgreSQL database, and returns human-readable answers powered by Google's Gemini AI.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Folder Structure](#-folder-structure)
- [Prerequisites](#-prerequisites)
- [Installation & Setup](#-installation--setup)
- [Configuration](#-configuration)
- [API Endpoints](#-api-endpoints)
- [Database Schema](#-database-schema)
- [Usage Examples](#-usage-examples)
- [Development](#-development)
- [Docker Deployment](#-docker-deployment)

---

## ✨ Features

- **Natural Language Processing**: Ask questions in plain English about vehicle data
- **AI-Powered SQL Generation**: Uses Google Gemini 2.5 Flash to convert questions to SQL
- **SQL Validation & Security**: Multi-layer SQL injection prevention and query validation
- **Human-Readable Answers**: AI formats raw database results into conversational responses
- **Dynamic Configuration**: Update database and API settings via REST endpoints
- **Health Monitoring**: Built-in health checks and connection testing
- **Full CRUD Support**: Fetch, query, and manage vehicle damage data
- **Docker Ready**: Complete containerized deployment with Docker Compose

---

## 🏗 Architecture

### System Flow

```
┌─────────────────┐
│  User Question  │
│ (Natural Lang.) │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│   Gemini API Client     │
│   (nl_to_sql)           │
│   • Schema Context      │
│   • Prompt Engineering  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   SQL Validator         │
│   • Blocks DDL/DML      │
│   • Sanitizes queries   │
│   • Table whitelisting  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   PostgreSQL Database   │
│   • vehicle_cards       │
│   • damage_detections   │
│   • repairs             │
│   • quotes              │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Gemini API Client     │
│   (format_answer)       │
│   • Result formatting   │
│   • Context enrichment  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────┐
│  Human Answer   │
└─────────────────┘
```

### Component Overview

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Layer** | FastAPI | REST endpoints, request/response handling |
| **AI Layer** | Google Gemini 2.5 | NL→SQL conversion, answer formatting |
| **Validation** | Custom Validator | SQL injection prevention, query sanitization |
| **Database** | PostgreSQL 16 | Data storage with asyncpg driver |
| **ORM** | SQLAlchemy 2.0 | Async database operations |
| **Configuration** | JSON File Storage | Runtime-updateable settings |

---

## 📁 Folder Structure

```
clearquote/
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container definition
├── docker-compose.yml         # Multi-container orchestration
│
├── config.py                  # Configuration management (JSON-based)
├── database.py                # SQLAlchemy models & async engine
├── pipeline.py                # Core NL→SQL→Execute→Answer logic
├── gemini_client.py           # Google Gemini API integration
├── sql_validator.py           # SQL security & validation
├── schema_context.py          # Database schema for AI context
├── schemas.py                 # Pydantic request/response models
│
├── routes/
│   ├── query_routes.py        # /api/query, /api/debug, /api/examples
│   ├── config_routes.py       # /api/config/* (API key, DB URL)
│   ├── data_routes.py         # /api/data/fetch
│   └── health_routes.py       # /api/health, /api/schema
│
├── scripts/
│   └── seed_dataset.py        # Database seeding script
│
└── data/
    └── config.json            # Runtime configuration storage
```

---

## 🔧 Prerequisites

- **Python 3.11+**
- **PostgreSQL 16** (or use Docker)
- **Google Gemini API Key** ([Get one here](https://ai.google.dev/))
- **Docker & Docker Compose** (optional, for containerized deployment)

---

## 🚀 Installation & Setup

### Option 1: Local Development

#### 1. Clone the Repository
```bash
git clone https://github.com/tarun1030/clearquote-BE.git
cd clearquote
```

#### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Set Up PostgreSQL

**Manual Setup:**
```sql
CREATE DATABASE clearquote;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE clearquote TO postgres;
```

**Or use the provided Docker container:**
```bash
docker-compose up -d postgres
```

#### 5. Configure Environment
Create a `.env` file (optional, can use API endpoints instead):
```env
DB_URL=postgresql://postgres:postgres@localhost:5432/clearquote
GEMINI_API_KEY=your_gemini_api_key_here
```

#### 6. Seed the Database
```bash
python scripts/seed_dataset.py
```

#### 7. Run the Application
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Visit: http://localhost:8000/docs

---

### Option 2: Docker Deployment

#### 1. Create `.env` File
```env
POSTGRES_DB=clearquote
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
RUN_DB_SEED=1
```

#### 2. Build and Run
```bash
docker-compose up --build
```

The API will be available at: http://localhost:8000

#### 3. Stop Containers
```bash
docker-compose down
```

#### 4. Reset Everything (including data)
```bash
docker-compose down -v
```

---

## ⚙️ Configuration

### Dynamic Configuration (Recommended)

ClearQuote supports runtime configuration updates via API endpoints:

#### Set Gemini API Key
```bash
curl -X POST http://localhost:8000/api/config/api-key \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your_gemini_api_key"}'
```

#### Set Database URL
```bash
curl -X POST http://localhost:8000/api/config/db-url \
  -H "Content-Type: application/json" \
  -d '{"db_url": "postgresql://user:password@host:5432/dbname"}'
```

#### Check Configuration Status
```bash
curl http://localhost:8000/api/config/status
```

### Configuration File

Configuration is stored in `data/config.json`:
```json
{
  "GEMINI_API_KEY": "your_key_here",
  "DB_URL": "postgresql://postgres:postgres@localhost:5432/clearquote",
  "GEMINI_MODEL": "gemini-2.5-flash"
}
```

---

## 🔌 API Endpoints

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Query Endpoints

#### POST `/api/query`
Execute a natural language query and get a human-readable answer.

**Request:**
```json
{
  "question": "What is the average repair cost for rear bumper damages in the last 30 days?"
}
```

**Response:**
```json
{
  "question": "What is the average repair cost...",
  "generated_sql": "SELECT AVG(r.repair_cost)...",
  "validated_sql": "SELECT AVG(r.repair_cost)...",
  "row_count": 1,
  "answer": "The average repair cost for rear bumper damages in the last 30 days is ₹1,247.50 (based on 12 repairs).",
  "error": null,
  "stage": "completed"
}
```

#### POST `/api/debug`
Same as `/api/query` but includes raw database rows for debugging.

**Response includes additional field:**
```json
{
  ...
  "rows": [
    {"average_repair_cost": 1247.50, "matching_repairs": 12}
  ]
}
```

#### GET `/api/examples`
Get example questions to try.

**Response:**
```json
{
  "examples": [
    "What is the average repair cost for rear bumper damages in the last 30 days?",
    "How many vehicles had severe damages on the front panel this month?",
    ...
  ]
}
```

---

### Configuration Endpoints

#### POST `/api/config/api-key`
Update the Gemini API key.

**Request:**
```json
{
  "api_key": "your_new_api_key"
}
```

#### POST `/api/config/db-url`
Update the database connection string.

**Request:**
```json
{
  "db_url": "postgresql://user:password@host:5432/dbname"
}
```

#### POST `/api/config/validate-api-key`
Test an API key without saving it.

#### POST `/api/config/validate-db-url`
Test a database URL without saving it.

#### POST `/api/config/test-connection`
Test both database and API key connections.

**Response:**
```json
{
  "overall_status": "healthy",
  "database": {
    "status": "connected",
    "is_connected": true,
    "database_name": "clearquote"
  },
  "gemini_api": {
    "status": "valid",
    "is_valid": true,
    "available_models": 15
  },
  "timestamp": "2026-02-06 10:30:45.123456"
}
```

#### GET `/api/config/status`
Get current configuration status.

---

### Data Endpoints

#### POST `/api/data/fetch`
Retrieve data from specified tables.

**Request:**
```json
{
  "tables": ["vehicle_cards", "damage_detections"],
  "limit": 100
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully fetched data from 2 table(s)",
  "data": {
    "vehicle_cards": [...],
    "damage_detections": [...]
  },
  "row_counts": {
    "vehicle_cards": 50,
    "damage_detections": 75
  }
}
```

---

### Health Endpoints

#### GET `/api/health`
Health check with database connectivity test.

**Response:**
```json
{
  "status": "ok",
  "db": "ok",
  "model": "gemini-2.5-flash"
}
```

#### GET `/api/schema`
Retrieve the database schema context used by the AI.

---

## 🗄 Database Schema

### Tables

#### `vehicle_cards`
Stores vehicle information.

| Column | Type | Description |
|--------|------|-------------|
| card_id | INTEGER (PK) | Auto-incrementing ID |
| vehicle_type | VARCHAR(50) | car, truck, van, suv |
| manufacturer | VARCHAR(100) | Toyota, BMW, Ford, etc. |
| model | VARCHAR(100) | Camry, 3 Series, etc. |
| manufacture_year | INTEGER | 4-digit year |
| created_at | TIMESTAMP | Record creation time |

#### `damage_detections`
Stores detected vehicle damages.

| Column | Type | Description |
|--------|------|-------------|
| damage_id | INTEGER (PK) | Auto-incrementing ID |
| card_id | INTEGER (FK) | → vehicle_cards.card_id |
| panel_name | VARCHAR(100) | front bumper, rear bumper, etc. |
| damage_type | VARCHAR(100) | scratch, dent, crack, rust, etc. |
| severity | VARCHAR(50) | low, medium, high, severe |
| confidence | FLOAT | 0.0 - 1.0 |
| detected_at | TIMESTAMP | Detection time |

#### `repairs`
Stores repair records.

| Column | Type | Description |
|--------|------|-------------|
| repair_id | INTEGER (PK) | Auto-incrementing ID |
| card_id | INTEGER (FK) | → vehicle_cards.card_id |
| panel_name | VARCHAR(100) | Same as damage_detections |
| repair_action | VARCHAR(200) | repaint, replace panel, etc. |
| repair_cost | NUMERIC(12,2) | Cost in local currency |
| approved | BOOLEAN | Approval status |
| created_at | TIMESTAMP | Record creation time |

#### `quotes`
Stores cost estimates.

| Column | Type | Description |
|--------|------|-------------|
| quote_id | INTEGER (PK) | Auto-incrementing ID |
| card_id | INTEGER (FK) | → vehicle_cards.card_id |
| total_estimated_cost | NUMERIC(12,2) | Total estimate |
| currency | VARCHAR(10) | INR |
| generated_at | TIMESTAMP | Quote generation time |

---

## 💡 Usage Examples

### Example Questions

```python
# Simple aggregation
"What is the average repair cost for rear bumper damages?"

# Time-based filtering
"How many vehicles had severe damages this month?"

# Complex joins
"Which vehicles have both a damage detection and an approved repair?"

# Statistical analysis
"Which car models have the highest repair cost variance?"

# Multi-condition queries
"Show me all unapproved repairs with a cost greater than 500"
```

### Python Client Example

```python
import requests

BASE_URL = "http://localhost:8000"

# Ask a question
response = requests.post(
    f"{BASE_URL}/api/query",
    json={"question": "How many severe damages were detected this week?"}
)

result = response.json()
print(result["answer"])
# Output: "There were 7 severe damages detected this week across 5 vehicles."
```

### cURL Example

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the total cost of all quotes this month?"}'
```

---

## 🛠 Development

### Running Tests

```bash
# Unit tests
pytest tests/

# With coverage
pytest --cov=. --cov-report=html
```

### Code Quality

```bash
# Format code
black .

# Lint
flake8 .

# Type checking
mypy .
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_URL` | None | PostgreSQL connection string |
| `DATABASE_URL` | None | Alternative to DB_URL |
| `GEMINI_API_KEY` | None | Google Gemini API key |
| `GEMINI_MODEL` | gemini-2.5-flash | AI model to use |
| `RUN_DB_SEED` | 1 | Auto-seed DB on startup (Docker) |

---

## 🐳 Docker Deployment

### Build Custom Image

```bash
docker build -t clearquote:latest .
```

### Run Standalone Container

```bash
docker run -d \
  -p 8000:8000 \
  -e DB_URL="postgresql://user:pass@host:5432/db" \
  -e GEMINI_API_KEY="your_key" \
  clearquote:latest
```

### Production Deployment

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  api:
    image: clearquote:latest
    environment:
      - DB_URL=${DB_URL}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - RUN_DB_SEED=0
    restart: always
    ports:
      - "8000:8000"
```

---

## 🔒 Security Features

### SQL Injection Prevention

1. **Statement Whitelisting**: Only SELECT queries allowed
2. **Token Blocking**: Dangerous functions (pg_sleep, COPY, etc.) blocked
3. **Table Validation**: Only known tables can be queried
4. **Parameterized Queries**: SQLAlchemy text() with parameter binding
5. **Multi-layer Validation**: AI + Rule-based validation

### Best Practices

- API keys stored in JSON config file (excluded from version control)
- Database passwords URL-encoded automatically
- CORS configured (restrict in production)
- No raw SQL execution from user input
- Async operations prevent blocking attacks

---

## 🐛 Troubleshooting

### Common Issues

#### Database Connection Failed

```bash
# Check PostgreSQL is running
docker-compose ps

# Test connection manually
psql -h localhost -U postgres -d clearquote

# Verify DB_URL format
# Correct: postgresql://user:password@host:5432/dbname
# Wrong:   postgres://... (missing 'ql')
```

#### Gemini API Errors

```bash
# Test API key
curl -X POST http://localhost:8000/api/config/validate-api-key \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your_key"}'

# Check available models
python -c "import google.generativeai as genai; genai.configure(api_key='KEY'); print(list(genai.list_models()))"
```

#### Password Special Characters

If your database password contains special characters:

```python
# Bad
postgresql://user:p@ssw0rd!@host:5432/db

# Good (URL-encoded automatically)
# The system handles this for you, just use the raw password
```

#### Docker Volume Permissions

```bash
# Fix permission issues
sudo chown -R $(whoami):$(whoami) ./data

# Or reset volumes
docker-compose down -v
docker-compose up --build
```

---

## 📊 Performance Optimization

- **Connection Pooling**: Enabled via SQLAlchemy (`pool_pre_ping=True`)
- **Async Operations**: All database calls are non-blocking
- **Query Limits**: Default 100-row limit prevents excessive data transfer
- **Result Caching**: Consider adding Redis for frequently asked questions

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- **FastAPI**: Modern, fast web framework
- **Google Gemini**: Powerful AI language model
- **PostgreSQL**: Robust relational database
- **SQLAlchemy**: Excellent ORM with async support
---

**Made with ❤️ for intelligent vehicle damage management**
