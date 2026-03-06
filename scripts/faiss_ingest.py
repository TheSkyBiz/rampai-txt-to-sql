import json
import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# --- CONFIGURATION ---
DICTIONARY_PATH = "data/dictionary.json"
FAISS_INDEX_PATH = "data/schema_index.faiss"
METADATA_PATH = "data/schema_metadata.json"

print("⏳ Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")


def build_faiss_index():

    try:
        with open(DICTIONARY_PATH, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ dictionary.json not found.")
        return

    if not data.get("tables"):
        print("⚠️ No tables found in JSON.")
        return

    embeddings = []
    metadata = []

    print("🚀 Generating embeddings...")

    for table in data["tables"]:

        col_names = ", ".join([c["name"] for c in table["columns"]])

        text_to_embed = (
            f"Table: {table['name']}. "
            f"Description: {table['description']}. "
            f"Columns: {col_names}"
        )

        vector = model.encode(text_to_embed)

        embeddings.append(vector)
        metadata.append(table)

    embeddings = np.array(embeddings).astype("float32")

    dim = embeddings.shape[1]

    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    faiss.write_index(index, FAISS_INDEX_PATH)

    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"✅ FAISS index built with {len(metadata)} tables")
    print(f"📦 Saved index to {FAISS_INDEX_PATH}")


if __name__ == "__main__":
    build_faiss_index()