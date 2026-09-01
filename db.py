import os
import json
import sqlite3
import datetime
from dotenv import load_dotenv, find_dotenv

# Load local environment variables with robust path detection
script_dir = os.path.dirname(os.path.abspath(__file__))
for env_filename in [".env", ".env.txt", ".env.local"]:
    env_path = os.path.join(script_dir, env_filename)
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=True)
load_dotenv(find_dotenv(usecwd=True), override=True)

# Google Cloud Firestore state
_firestore_client = None
_using_firestore = False
_active_database_id = None
_firestore_error_msg = None

def get_storage_mode() -> str:
    """Returns whether the app is using Cloud Firestore or Local SQLite."""
    if _using_firestore:
        return f"☁️ GCP Firestore ({_active_database_id})"
    return "💾 Local SQLite"

def get_firestore_warning() -> str | None:
    """Returns an actionable warning message if Firestore configuration failed."""
    return _firestore_error_msg

def _init_firestore():
    global _firestore_client, _using_firestore, _active_database_id, _firestore_error_msg
    _using_firestore = False
    _firestore_client = None
    _active_database_id = None
    _firestore_error_msg = None

    try:
        from google.cloud import firestore
        from google.oauth2 import service_account

        service_account_info = None
        
        # Check Streamlit secrets
        try:
            import streamlit as st
            if "gcp_service_account" in st.secrets:
                service_account_info = dict(st.secrets["gcp_service_account"])
        except Exception:
            pass

        # Check JSON string in environment variable
        if not service_account_info and os.getenv("GCP_SERVICE_ACCOUNT_JSON"):
            try:
                service_account_info = json.loads(os.getenv("GCP_SERVICE_ACCOUNT_JSON"))
            except Exception:
                pass

        credentials = None
        project_id = None

        if service_account_info:
            credentials = service_account.Credentials.from_service_account_info(service_account_info)
            project_id = credentials.project_id
        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            # Uses environment variable file path
            pass
        elif os.path.exists("serviceAccountKey.json"):
            credentials = service_account.Credentials.from_service_account_file("serviceAccountKey.json")
            project_id = credentials.project_id

        # Determine target database ID (check env/secrets or try standard names)
        configured_db_id = (
            os.getenv("FIRESTORE_DATABASE") or 
            os.getenv("GCP_DATABASE_ID") or 
            os.getenv("DATABASE_ID") or 
            "id-diet-coach-db"
        )
        candidate_db_ids = [configured_db_id, "id-diet-coach-db", "(default)"]
        # Remove duplicates preserving order
        candidate_db_ids = list(dict.fromkeys(candidate_db_ids))

        # Try connecting to candidate database IDs
        for db_name in candidate_db_ids:
            try:
                if credentials:
                    client = firestore.Client(credentials=credentials, project=project_id, database=db_name)
                else:
                    client = firestore.Client(database=db_name)

                # Test write/delete
                test_ref = client.collection("_healthcheck").document("ping")
                test_ref.set({"ping": True, "time": datetime.datetime.now().isoformat()})
                test_ref.delete()
                
                _firestore_client = client
                _using_firestore = True
                _active_database_id = db_name
                _firestore_error_msg = None
                return
            except Exception as e:
                err_str = str(e)
                if "404" not in err_str:
                    _firestore_error_msg = f"Firestore error: {err_str[:120]}"

        if not _using_firestore and not _firestore_error_msg:
            _firestore_error_msg = f"Could not find a valid Firestore database in project `{project_id}`."

    except Exception as e:
        _firestore_error_msg = f"Firestore init failed ({str(e)[:100]}). Falling back to local storage."
        _using_firestore = False
        _firestore_client = None

# ----------------- SQLite Fallback Helper ----------------- #
DB_PATH = "chat_history.db"

def _get_sqlite():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database (Firestore or SQLite). Always ensures SQLite schema exists as fallback."""
    _init_firestore()
    with _get_sqlite() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def list_conversations():
    """Returns a list of all conversations ordered by most recently updated."""
    if _using_firestore and _firestore_client:
        try:
            docs = _firestore_client.collection("conversations").order_by("updated_at", direction="DESCENDING").stream()
            results = []
            for doc in docs:
                data = doc.to_dict()
                results.append({
                    "id": doc.id,
                    "title": data.get("title", "Consultation"),
                    "updated_at": data.get("updated_at")
                })
            return results
        except Exception:
            pass

    with _get_sqlite() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC")
        return cursor.fetchall()

def create_conversation(conv_id: str, title: str = "New Consultation"):
    """Creates a new conversation session."""
    now_iso = datetime.datetime.now().isoformat()
    if _using_firestore and _firestore_client:
        try:
            _firestore_client.collection("conversations").document(conv_id).set({
                "title": title,
                "created_at": now_iso,
                "updated_at": now_iso
            })
            return
        except Exception:
            pass

    with _get_sqlite() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO conversations (id, title, updated_at) VALUES (?, ?, ?)",
            (conv_id, title, datetime.datetime.now())
        )

def update_conversation_title(conv_id: str, title: str):
    """Updates the title of a conversation."""
    now_iso = datetime.datetime.now().isoformat()
    if _using_firestore and _firestore_client:
        try:
            _firestore_client.collection("conversations").document(conv_id).update({
                "title": title,
                "updated_at": now_iso
            })
            return
        except Exception:
            pass

    with _get_sqlite() as conn:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, datetime.datetime.now(), conv_id)
        )

def get_conversation_messages(conv_id: str):
    """Retrieves all messages for a specific conversation in chronological order."""
    if _using_firestore and _firestore_client:
        try:
            docs = _firestore_client.collection("conversations").document(conv_id).collection("messages").order_by("created_at").stream()
            return [{"role": d.to_dict().get("role"), "content": d.to_dict().get("content")} for d in docs]
        except Exception:
            pass

    with _get_sqlite() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conv_id,)
        )
        rows = cursor.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

def save_message(conv_id: str, role: str, content: str):
    """Saves a message to the conversation."""
    now_iso = datetime.datetime.now().isoformat()
    if _using_firestore and _firestore_client:
        try:
            _firestore_client.collection("conversations").document(conv_id).collection("messages").add({
                "role": role,
                "content": content,
                "created_at": now_iso
            })
            _firestore_client.collection("conversations").document(conv_id).set({
                "updated_at": now_iso
            }, merge=True)
            return
        except Exception:
            pass

    with _get_sqlite() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conv_id, role, content)
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (datetime.datetime.now(), conv_id)
        )

def delete_conversation(conv_id: str):
    """Deletes a conversation and its messages."""
    if _using_firestore and _firestore_client:
        try:
            msgs = _firestore_client.collection("conversations").document(conv_id).collection("messages").stream()
            for m in msgs:
                m.reference.delete()
            _firestore_client.collection("conversations").document(conv_id).delete()
            return
        except Exception:
            pass

    with _get_sqlite() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))

# ----------------- User Profile Persistence ----------------- #
DEFAULT_PROFILE = {
    "age": 28,
    "sex": "Male",
    "height_cm": 175,
    "weight_kg": 75.0,
    "activity_level": "Moderately Active (moderate exercise 3-5 days/wk)",
    "goal": "Weight Loss (Deficit -20%)",
    "diet_pref": ["None / Balanced"],
    "allergies": "",
    "current_supplements": "",
    "medical_notes": ""
}

def get_user_profile() -> dict:
    """Retrieves the saved user profile from Firestore or SQLite, falling back to defaults."""
    profile = dict(DEFAULT_PROFILE)
    
    if _using_firestore and _firestore_client:
        try:
            doc = _firestore_client.collection("settings").document("user_profile").get()
            if doc.exists:
                data = doc.to_dict()
                if data:
                    profile.update(data)
                    return profile
        except Exception:
            pass

    with _get_sqlite() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM user_profile WHERE id = 'default'")
        row = cursor.fetchone()
        if row and row["data"]:
            try:
                saved = json.loads(row["data"])
                profile.update(saved)
            except Exception:
                pass

    return profile

def save_user_profile(profile_data: dict):
    """Saves the user profile to Firestore and SQLite."""
    # Ensure all default keys exist
    full_data = dict(DEFAULT_PROFILE)
    full_data.update(profile_data)
    
    if _using_firestore and _firestore_client:
        try:
            _firestore_client.collection("settings").document("user_profile").set(full_data)
        except Exception:
            pass

    # Also save to SQLite as local backup
    with _get_sqlite() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_profile (id, data, updated_at) VALUES ('default', ?, ?)",
            (json.dumps(full_data), datetime.datetime.now())
        )

