from pathlib import Path
import os
import json
import faiss
import numpy as np
import re
from datetime import datetime

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError
from sentence_transformers import SentenceTransformer

load_dotenv()


current_dir = os.getcwd()
DATA = os.path.join(current_dir, "data/glossaries")
STORE = os.path.join(current_dir, "store")

os.makedirs(STORE, exist_ok=True)
EMB = SentenceTransformer("BAAI/bge-m3")


def get_database():
    app_env = os.getenv("APP_ENV", "dev").lower()
    db_name = os.getenv("DB_NAME", "dupilot")
    if app_env == "dev":
        uri = os.getenv("MONGO_URL_DEV", "mongodb://localhost:27017")
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    else:
        endpoint = os.environ["DOCDB_ENDPOINT"]
        port = os.getenv("DOCDB_PORT", "27017")
        params = os.getenv("DOCDB_PARAMS", "replicaSet=rs0&retryWrites=false&tls=true")
        ca = os.getenv("DOCDB_CA_PATH", "/etc/ssl/certs/global-bundle.pem")
        user = os.environ["DOCDB_USER"]
        pwd = os.environ["DOCDB_PASSWORD"]
        uri = f"mongodb://{user}:{pwd}@{endpoint}:{port}/{db_name}?{params}"
        client = MongoClient(
            uri,
            tls=True,
            tlsCAFile=ca,
            serverSelectionTimeoutMS=5000,
        )
    return client[db_name]


def normalize(s):
    return re.sub(r"\s+", " ", s).strip()


def glossary_docs():
    docs = []
    with open(DATA / "base.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            term = item["term"]
            domain = item.get("domain", "")
            uid = "|".join(
                filter(
                    None,
                    [
                        normalize(term).lower(),
                        normalize(domain).lower() if domain else None,
                    ],
                )
            )
            doc = (
                "Term: {term} | Preferred: {pref} | Forbidden: {forb} | "
                "Aliases: {ali} | Notes: {notes} | Examples: {ex} | Domain: {dom}"
            ).format(
                term=item["term"],
                pref=item["preferred"],
                forb=", ".join(item.get("forbidden", [])),
                ali=", ".join(item.get("aliases", [])),
                notes=item.get("notes", ""),
                ex="; ".join(item.get("examples", [])),
                dom=item.get("domain", ""),
            )
            docs.append(
                {
                    "kind": "glossary",
                    "uid": uid or normalize(term).lower(),
                    "text": normalize(doc),
                    "raw": item,
                }
            )
    return docs


def example_docs():
    p = DATA / "examples.jsonl"
    if not p.exists():
        return []
    docs = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            base_id = item.get("id") or normalize(item["text"])[:80]
            doc = ("Example: {t} | Lang: {lang} | Hint: {hint}").format(
                t=item["text"], lang=item.get("lang", ""), hint=item.get("hint", "")
            )
            docs.append(
                {
                    "kind": "example",
                    "uid": normalize(base_id).lower(),
                    "text": normalize(doc),
                    "raw": item,
                }
            )
    return docs


def build_index(name, docs, embeddings):
    emb = np.array(embeddings, dtype=np.float32)
    if emb.size == 0:
        print(f"Skip index for {name}: no documents.")
        return
    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)
    faiss.write_index(index, str(STORE / f"{name}.faiss"))
    with open(STORE / f"{name}.jsonl", "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"Indexed {name}: {len(docs)} items.")


# upsert to documentdb
def upsert_documents(db, collection_name, docs, embeddings):
    if not docs:
        return

    coll = db[collection_name]
    operations = []
    now = datetime.now()

    for doc, vec in zip(docs, embeddings):
        payload = {
            "kind": doc["kind"],
            "text": doc["text"],
            "raw": doc["raw"],
            "embedding": vec.tolist(),
            "updated_at": now,
        }
        operations.append(
            UpdateOne(
                {"uid": doc["uid"]},
                {
                    "$set": payload,
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
        )

    if not operations:
        return

    try:
        result = coll.bulk_write(operations)
    except PyMongoError as exc:
        raise SystemExit(f"Mongo upsert failed for {collection_name}: {exc}") from exc

    upserted = len(result.upserted_ids) if result.upserted_ids else 0
    modified = result.modified_count
    print(
        f"Mongo upsert for {collection_name}: {upserted} inserted, {modified} updated."
    )


def main():
    db = get_database()

    glossary_entries = glossary_docs()
    if glossary_entries:
        texts = [d["text"] for d in glossary_entries]
        emb = EMB.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        upsert_documents(db, "glossaries", glossary_entries, emb)
        build_index("glossary", glossary_entries, emb)
    else:
        print("No glossary documents found; skipping glossary ingestion.")

    example_entries = example_docs()
    if example_entries:
        texts = [d["text"] for d in example_entries]
        emb = EMB.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        upsert_documents(db, "examples", example_entries, emb)
        build_index("examples", example_entries, emb)
    else:
        print("No example documents found; skipping example ingestion.")


if __name__ == "__main__":
    main()
