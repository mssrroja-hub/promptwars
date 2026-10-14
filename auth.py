import re
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

def validate_registration_input(name, email, password, confirm_password):
    if not name or len(name.strip()) < 2:
        return False, "Full name is required (minimum 2 characters)."
    
    if not email or not re.match(EMAIL_REGEX, email.strip()):
        return False, "Please enter a valid email address."
        
    if not password or len(password) != 4:
        return False, "Password must be exactly 4 characters for this prototype."
        
    if password != confirm_password:
        return False, "Passwords do not match."
        
    return True, None

def create_user_session(user_id):
    token = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at.strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    conn.close()
    return token

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        elif request.args.get("token"):
            token = request.args.get("token").strip()

        if not token:
            return jsonify({"error": "Authentication required. No session token provided."}), 401

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.name, u.email, s.expires_at 
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
        """, (token,))
        row = cur.fetchone()
        
        if not row:
            conn.close()
            return jsonify({"error": "Invalid or expired session. Please log in again."}), 401

        # Check expiration
        expires_at = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
        if datetime.utcnow() > expires_at:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            conn.close()
            return jsonify({"error": "Session expired. Please log in again."}), 401

        g.user = {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "token": token
        }
        conn.close()
        return f(*args, **kwargs)
    return decorated_function
