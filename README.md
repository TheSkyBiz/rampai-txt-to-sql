# RampAI – Natural Language to SQL System

Experimentations on an AI-powered analytics system that converts natural language queries into SQL and executes them on an enterprise database.

The system uses:

- **FAISS** for schema retrieval
- **DeepSeek-Coder V2 (16B)** via Ollama for SQL generation
- **SQLite** as the backend database
- **FastAPI** for the API layer
- **Streamlit** for the user dashboard

---

# System Architecture

User Query  
↓  
Schema Retrieval (FAISS)  
↓  
Join Path Detection  
↓  
DeepSeek-Coder SQL Generation  
↓  
SQL Execution  
↓  
Streamlit Visualization  

---

# Installation Guide

## 1. Clone Repository

```bash
git clone https://github.com/TheSkyBiz/rampai-text-to-sql.git
cd rampai-text-to-sql
```

---

# 2. Create Python Environment

```bash
python -m venv venv
```

Activate:

Windows

```
venv\Scripts\activate
```

Linux/Mac

```
source venv/bin/activate
```

---

# 3. Install Dependencies

```
pip install -r requirements.txt
```

---

# 4. Install Ollama

Download:

https://ollama.com

Then pull the model:

```
ollama pull deepseek-coder-v2:16b
```

Start Ollama server:

```
ollama serve
```

---

# Running the System

## Start API Server

```
uvicorn api.rampai_api_server:app --reload
```

Server runs at:

```
http://127.0.0.1:8000
```

API docs:

```
http://127.0.0.1:8000/docs
```

---

## Start Dashboard

In another terminal:

```
streamlit run dashboard/enterprise_dashboard.py
```

Dashboard will open at:

```
http://localhost:8501
```

---

# Example Queries

Try asking:

```
total service amount
```

```
total service amount by workshop
```

```
top customers by service spending
```

```
revenue by technician
```

```
average service amount by vehicle type
```

```
top 5 customers by service spending
```

```
service revenue by month
```

```
show all the vehicle types
```
---

# Key Features

- Natural language → SQL conversion
- Automatic schema retrieval using embeddings
- Join path reasoning across tables
- SQL self-repair if queries fail
- Query history logging
- Interactive dashboard with visualizations

---

# Technologies Used

- Python
- FastAPI
- Streamlit
- FAISS
- Sentence Transformers
- DeepSeek-Coder
- SQLite
- Ollama

---