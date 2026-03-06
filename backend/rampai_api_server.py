from fastapi import FastAPI
from pydantic import BaseModel
import sqlite3
import requests
import re
import time
import uuid
import logging
from typing import Dict, Any
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import json

# ================= CONFIG =================

FAISS_INDEX_PATH = "data/schema_index.faiss"
SCHEMA_METADATA_PATH = "data/schema_metadata.json"
SCHEMA_GRAPH_PATH = "data/schema_graph.json"
SQLITE_DB_PATH = "data/ramp_data.db"

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "deepseek-coder-v2:16b"

SIMILARITY_THRESHOLD = 1.7

# ================= INIT =================

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

print("⏳ Loading embedding model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

print("📦 Loading FAISS index...")
faiss_index = faiss.read_index(FAISS_INDEX_PATH)

with open(SCHEMA_METADATA_PATH, "r") as f:
    schema_metadata = json.load(f)

with open(SCHEMA_GRAPH_PATH, "r") as f:
    schema_graph = json.load(f)

# ================= SESSION STORAGE =================

def init_logging_table():

    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_logs (
            id TEXT PRIMARY KEY,
            role TEXT,
            question TEXT,
            generated_sql TEXT,
            similarity_score REAL,
            execution_time REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

init_logging_table()

def log_query(request_id, role, question, sql, similarity, total_time):

    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO query_logs
        (id, role, question, generated_sql, similarity_score, execution_time)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (request_id, role, question, sql, similarity, total_time))

    conn.commit()
    conn.close()

# ================= QUERY CACHE =================

def check_query_cache(user_query):

    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT generated_sql
        FROM query_logs
        WHERE question = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (user_query,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]

    return None

# ================= REQUEST MODEL =================

class QueryRequest(BaseModel):
    query: str
    role: str = "user"

# ================= HELPERS =================

def is_meaningful_query(text: str) -> bool:
    return len(text.strip()) >= 3 and re.search(r"[a-zA-Z]", text)

def validate_sql(query: str) -> bool:
    query = query.strip().upper()
    return query.startswith("SELECT") and "DROP" not in query and "DELETE" not in query

# ================= SCHEMA RETRIEVAL =================

def retrieve_schemas(user_query: str):

    query_vector = embedding_model.encode([user_query])
    query_vector = np.array(query_vector).astype("float32")

    distances, indices = faiss_index.search(query_vector, 5)

    schemas = []
    tables = []
    best_distance = None

    for i, idx in enumerate(indices[0]):

        table_data = schema_metadata[idx]

        table_name = table_data.get("name", "unknown_table")

        tables.append(table_name)

        schema_text = json.dumps(table_data, indent=2)

        schemas.append(
            f"--- Table: {table_name} ---\n{schema_text}"
        )

        distance = float(distances[0][i])

        if best_distance is None or distance < best_distance:
            best_distance = distance

    return float(best_distance), "\n\n".join(schemas), tables

# ================= JOIN PATH FINDER =================

def find_join_paths(retrieved_tables):

    paths = []

    for rel in schema_graph:

        t1 = rel.get("table1")
        t2 = rel.get("table2")
        column = rel.get("column")

        if not t1 or not t2 or not column:
            continue

        if t1 in retrieved_tables or t2 in retrieved_tables:

            paths.append(
                f"{t1}.{column} = {t2}.{column}"
            )

    return "\n".join(paths)

# ================= QUERY MEMORY =================

def retrieve_similar_queries(user_query, limit=2):

    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT question, generated_sql
        FROM query_logs
        ORDER BY created_at DESC
        LIMIT 20
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return ""

    query_vec = embedding_model.encode([user_query])[0]

    scored = []

    for q, sql in rows:

        q_vec = embedding_model.encode([q])[0]

        sim = np.dot(query_vec, q_vec) / (
            np.linalg.norm(query_vec) * np.linalg.norm(q_vec)
        )

        scored.append((sim, q, sql))

    scored.sort(reverse=True)

    examples = scored[:limit]

    example_text = ""

    for sim, q, sql in examples:

        example_text += f"""
Example Question:
{q}

Example SQL:
{sql}

---
"""

    return example_text

# ================= LLM SQL GENERATION =================

def generate_sql(prompt: str):

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0}
    }

    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()

    sql = response.json().get("response", "").strip()

    if sql.startswith("```"):
        sql = sql.replace("```sql", "").replace("```", "").strip()

    if not sql.endswith(";"):
        sql += ";"

    return sql

# ================= SQL REPAIR =================

def repair_sql(original_sql, error_message, schemas):

    repair_prompt = f"""
The following SQL query failed.

SQL:
{original_sql}

Error:
{error_message}

Database Schema:
{schemas}

Fix the SQL query.

Rules:
- Return ONLY corrected SQL
- Use valid SQLite syntax
- End with semicolon

Corrected SQL:
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": repair_prompt,
        "stream": False,
        "options": {"temperature": 0}
    }

    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()

    sql = response.json().get("response", "").strip()

    if sql.startswith("```"):
        sql = sql.replace("```sql", "").replace("```", "").strip()

    if not sql.endswith(";"):
        sql += ";"

    return sql

# ================= SQL EXECUTION =================

def execute_sql(query: str) -> Dict[str, Any]:

    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    cursor.execute(query)

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    conn.close()

    return {
        "columns": columns,
        "rows": rows
    }

# ================= MAIN ENDPOINT =================

@app.post("/query")
def query_database(request: QueryRequest):

    request_id = str(uuid.uuid4())
    start_time = time.time()

    logging.info(f"[{request_id}] Incoming query: {request.query}")

    if not is_meaningful_query(request.query):
        return {
            "request_id": request_id,
            "success": False,
            "error": "Query not meaningful."
        }

    try:

        # ---------- CACHE CHECK ----------

        cached_sql = check_query_cache(request.query)

        if cached_sql:

            logging.info(f"[{request_id}] Cache hit")

            results = execute_sql(cached_sql)

            return {
                "request_id": request_id,
                "success": True,
                "cached": True,
                "sql": cached_sql,
                "results": results
            }

        # ---------- RETRIEVAL ----------

        retrieval_start = time.time()

        best_distance, schemas, tables = retrieve_schemas(request.query)
        join_paths = find_join_paths(tables)

        retrieval_time = round(time.time() - retrieval_start, 4)

        if best_distance is None or best_distance > SIMILARITY_THRESHOLD:

            return {
                "request_id": request_id,
                "success": False,
                "error": "Query not relevant to database schema.",
                "retrieval_time_sec": retrieval_time
            }

        example_block = retrieve_similar_queries(request.query)

        generation_start = time.time()

        prompt = f"""
You are a SQLite SQL generator.

Rules:
- Return ONLY valid SQLite SQL
- No explanations
- End with semicolon

RELEVANT JOIN PATHS:
{join_paths}

SCHEMA:
{schemas}

PAST SUCCESSFUL QUERY EXAMPLES:
{example_block}

USER QUESTION:
{request.query}

SQL:
"""

        sql_query = generate_sql(prompt)

        generation_time = round(time.time() - generation_start, 4)

        if not validate_sql(sql_query):

            return {
                "request_id": request_id,
                "success": False,
                "error": "Invalid or unsafe SQL generated."
            }

        # ---------- EXECUTION ----------

        execution_start = time.time()

        try:

            results = execute_sql(sql_query)

        except Exception as sql_error:

            repaired_sql = repair_sql(sql_query, str(sql_error), schemas)

            results = execute_sql(repaired_sql)
            sql_query = repaired_sql

        execution_time = round(time.time() - execution_start, 4)

        total_time = round(time.time() - start_time, 4)

        log_query(
            request_id,
            request.role,
            request.query,
            sql_query,
            best_distance,
            total_time
        )

        base_response = {
            "request_id": request_id,
            "success": True,
            "results": results
        }

        if request.role == "admin":

            base_response.update({
                "sql": sql_query,
                "retrieved_tables": tables,
                "similarity_score": best_distance,
                "timing": {
                    "retrieval_sec": retrieval_time,
                    "generation_sec": generation_time,
                    "execution_sec": execution_time,
                    "total_sec": total_time
                }
            })

        return base_response

    except Exception as e:

        logging.error(f"[{request_id}] Error: {str(e)}")

        return {
            "request_id": request_id,
            "success": False,
            "error": str(e)
        }

# ================= ADMIN HISTORY =================

@app.get("/history")
def get_history(role: str = "user"):

    if role != "admin":
        return {"error": "Access denied"}

    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, role, question, generated_sql,
               similarity_score, execution_time, created_at
        FROM query_logs
        ORDER BY created_at DESC
        LIMIT 50
    """)

    rows = cursor.fetchall()

    conn.close()

    return {"history": rows}