import os
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from database import get_db_connection, init_db
from auth import (
    validate_registration_input,
    create_user_session,
    require_auth
)
import scheduler_engine

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config.from_object(Config)

# Ensure database is initialized on startup
init_db()

# Enable CORS for API if accessed from other origins
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response

# -------------------------------------------------------------
# Frontend Page Routes
# -------------------------------------------------------------
@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/game/<game_id>')
def serve_game(game_id):
    # Standalone game pages in a new browser tab
    return send_from_directory('static/games', f'{game_id}.html')

# -------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or ''

    is_valid, error_msg = validate_registration_input(name, email, password, confirm_password)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check duplicate normalized email
    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cur.fetchone():
        conn.close()
        return jsonify({"error": "An account with this email address already exists. Please log in."}), 409

    # Generate salted hash (using scrypt)
    password_hash = generate_password_hash(password, method='scrypt')
    
    cur.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash)
    )
    user_id = cur.lastrowid
    
    # Initialize default user preferences
    cur.execute("INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    # Create session token
    token = create_user_session(user_id)

    return jsonify({
        "message": "Registration successful! Welcome to MentiNous AI.",
        "token": token,
        "user": {
            "id": user_id,
            "name": name,
            "email": email
        }
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({"error": "Please provide both email and password."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, password_hash FROM users WHERE email = ?", (email,))
    user = cur.fetchone()

    # Verify password hash
    if not user or not check_password_hash(user['password_hash'], password):
        conn.close()
        return jsonify({"error": "Invalid email or password. Please verify your credentials."}), 401

    token = create_user_session(user['id'])
    
    # Fetch preferences
    cur.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user['id'],))
    prefs = cur.fetchone()
    conn.close()

    return jsonify({
        "message": "Welcome back!",
        "token": token,
        "user": {
            "id": user['id'],
            "name": user['name'],
            "email": user['email']
        },
        "preferences": dict(prefs) if prefs else {}
    }), 200

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    conn = get_db_connection()
    conn.execute("DELETE FROM sessions WHERE token = ?", (g.user['token'],))
    conn.commit()
    conn.close()
    return jsonify({"message": "Successfully logged out."}), 200

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def get_current_user():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, created_at FROM users WHERE id = ?", (g.user['id'],))
    user = cur.fetchone()
    cur.execute("SELECT * FROM user_preferences WHERE user_id = ?", (g.user['id'],))
    prefs = cur.fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "user": {
            "id": user['id'],
            "name": user['name'],
            "email": user['email'],
            "created_at": user['created_at']
        },
        "preferences": dict(prefs) if prefs else {}
    }), 200

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({"error": "Email address is required."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = cur.fetchone()

    if not user:
        conn.close()
        return jsonify({
            "message": "If an account exists with this email, a recovery code has been generated.",
            "smtp_configured": False
        }), 200

    import random
    recovery_code = f"{random.randint(100000, 999999)}"
    expires = (datetime.utcnow() + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')

    cur.execute(
        "UPDATE users SET reset_token = ?, reset_expires = ? WHERE id = ?",
        (recovery_code, expires, user['id'])
    )
    conn.commit()
    conn.close()

    return jsonify({
        "message": "A recovery code has been generated.",
        "smtp_configured": False,
        "dev_recovery_code": recovery_code,
        "note": "SMTP email delivery is not configured in this prototype. Use the on-screen recovery code to reset your password."
    }), 200

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    recovery_code = (data.get('recovery_code') or '').strip()
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not email or not recovery_code or not new_password:
        return jsonify({"error": "All fields are required."}), 400

    if len(new_password) != 4:
        return jsonify({"error": "New password must be exactly 4 characters for this prototype."}), 400

    if new_password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, reset_token, reset_expires FROM users WHERE email = ?", (email,))
    user = cur.fetchone()

    if not user or user['reset_token'] != recovery_code:
        conn.close()
        return jsonify({"error": "Invalid recovery code or email."}), 400

    if user['reset_expires']:
        expires_at = datetime.strptime(user['reset_expires'], '%Y-%m-%d %H:%M:%S')
        if datetime.utcnow() > expires_at:
            conn.close()
            return jsonify({"error": "Recovery code has expired. Please request a new one."}), 400

    new_hash = generate_password_hash(new_password, method='scrypt')
    cur.execute(
        "UPDATE users SET password_hash = ?, reset_token = NULL, reset_expires = NULL WHERE id = ?",
        (new_hash, user['id'])
    )
    # Invalidate all prior sessions for security
    cur.execute("DELETE FROM sessions WHERE user_id = ?", (user['id'],))
    conn.commit()
    conn.close()

    return jsonify({"message": "Password successfully updated! You can now log in with your new credentials."}), 200

# -------------------------------------------------------------
# Tasks & Schedule Routes (Strict Per-User Isolation)
# -------------------------------------------------------------
@app.route('/api/tasks', methods=['GET'])
@require_auth
def get_tasks():
    status_filter = request.args.get('status')
    date_filter = request.args.get('date') # e.g. YYYY-MM-DD
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = "SELECT * FROM tasks WHERE user_id = ?"
    params = [g.user['id']]
    
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
        
    if date_filter:
        query += " AND (start_time LIKE ? OR deadline LIKE ?)"
        params.extend([f"{date_filter}%", f"{date_filter}%"])
        
    query += " ORDER BY CASE WHEN status = 'completed' THEN 1 ELSE 0 END, start_time ASC, id DESC"
    
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    
    return jsonify({"tasks": [dict(r) for r in rows]}), 200

@app.route('/api/tasks', methods=['POST'])
@require_auth
def create_task():
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({"error": "Task title is required."}), 400
        
    description = (data.get('description') or '').strip()
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    duration_min = int(data.get('duration_min') or 30)
    priority = data.get('priority', 'medium').lower()
    if priority not in ('high', 'medium', 'low'):
        priority = 'medium'
    deadline = data.get('deadline')
    status = data.get('status', 'pending')
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tasks (user_id, title, description, start_time, end_time, duration_min, priority, deadline, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (g.user['id'], title, description, start_time, end_time, duration_min, priority, deadline, status))
    task_id = cur.lastrowid
    
    # Also create a calendar event if start_time is set
    if start_time:
        cur.execute("""
            INSERT INTO calendar_events (user_id, title, description, start_time, end_time, task_id, event_type)
            VALUES (?, ?, ?, ?, ?, ?, 'task_block')
        """, (g.user['id'], title, description, start_time, end_time or start_time, task_id))
        
    conn.commit()
    
    cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = dict(cur.fetchone())
    conn.close()
    
    return jsonify({"message": "Task created successfully.", "task": task}), 201

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
@require_auth
def update_task(task_id):
    data = request.get_json() or {}
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Enforce ownership check
    cur.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user['id']))
    existing = cur.fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Task not found or access denied."}), 404
        
    title = data.get('title', existing['title']).strip()
    description = data.get('description', existing['description'])
    start_time = data.get('start_time', existing['start_time'])
    end_time = data.get('end_time', existing['end_time'])
    duration_min = int(data.get('duration_min', existing['duration_min']))
    priority = data.get('priority', existing['priority'])
    deadline = data.get('deadline', existing['deadline'])
    status = data.get('status', existing['status'])
    completed_at = existing['completed_at']
    
    if status == 'completed' and existing['status'] != 'completed':
        completed_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    elif status != 'completed':
        completed_at = None

    cur.execute("""
        UPDATE tasks 
        SET title = ?, description = ?, start_time = ?, end_time = ?, 
            duration_min = ?, priority = ?, deadline = ?, status = ?, 
            completed_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
    """, (title, description, start_time, end_time, duration_min, priority, deadline, status, completed_at, task_id, g.user['id']))
    
    # Update linked calendar event if present
    cur.execute("""
        UPDATE calendar_events
        SET title = ?, description = ?, start_time = ?, end_time = ?
        WHERE task_id = ? AND user_id = ?
    """, (title, description, start_time, end_time or start_time, task_id, g.user['id']))
    
    conn.commit()
    cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = dict(cur.fetchone())
    conn.close()
    
    return jsonify({"message": "Task updated successfully.", "task": task}), 200

@app.route('/api/tasks/<int:task_id>/toggle', methods=['POST'])
@require_auth
def toggle_task_completion(task_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user['id']))
    task = cur.fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "Task not found."}), 404
        
    new_status = 'pending' if task['status'] == 'completed' else 'completed'
    completed_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') if new_status == 'completed' else None
    
    cur.execute("""
        UPDATE tasks SET status = ?, completed_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
    """, (new_status, completed_at, task_id, g.user['id']))
    conn.commit()
    
    cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    updated = dict(cur.fetchone())
    conn.close()
    
    return jsonify({"message": f"Task marked as {new_status}.", "task": updated}), 200

@app.route('/api/tasks/<int:task_id>/postpone', methods=['POST'])
@require_auth
def postpone_task(task_id):
    data = request.get_json() or {}
    minutes = int(data.get('minutes', 60))
    to_tomorrow = bool(data.get('tomorrow', False))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user['id']))
    task = cur.fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "Task not found."}), 404

    start_time = task['start_time']
    end_time = task['end_time']
    
    if start_time:
        st = datetime.strptime(start_time, '%Y-%m-%d %H:%M')
        et = datetime.strptime(end_time, '%Y-%m-%d %H:%M') if end_time else st + timedelta(minutes=task['duration_min'])
        
        if to_tomorrow:
            st += timedelta(days=1)
            et += timedelta(days=1)
        else:
            st += timedelta(minutes=minutes)
            et += timedelta(minutes=minutes)
            
        start_time = st.strftime('%Y-%m-%d %H:%M')
        end_time = et.strftime('%Y-%m-%d %H:%M')
    else:
        # If no time was set, schedule starting next hour
        st = datetime.now() + timedelta(minutes=minutes)
        start_time = st.strftime('%Y-%m-%d %H:%M')
        end_time = (st + timedelta(minutes=task['duration_min'])).strftime('%Y-%m-%d %H:%M')

    cur.execute("""
        UPDATE tasks SET start_time = ?, end_time = ?, status = 'postponed', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
    """, (start_time, end_time, task_id, g.user['id']))
    
    cur.execute("""
        UPDATE calendar_events SET start_time = ?, end_time = ?
        WHERE task_id = ? AND user_id = ?
    """, (start_time, end_time, task_id, g.user['id']))
    
    conn.commit()
    cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    updated = dict(cur.fetchone())
    conn.close()
    
    return jsonify({"message": "Task postponed successfully.", "task": updated}), 200

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@require_auth
def delete_task(task_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user['id']))
    if not cur.fetchone():
        conn.close()
        return jsonify({"error": "Task not found."}), 404
        
    cur.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user['id']))
    cur.execute("DELETE FROM calendar_events WHERE task_id = ? AND user_id = ?", (task_id, g.user['id']))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Task deleted successfully."}), 200

# -------------------------------------------------------------
# Calendar Routes (Strict Per-User Isolation)
# -------------------------------------------------------------
@app.route('/api/calendar/events', methods=['GET'])
@require_auth
def get_calendar_events():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Fetch manual calendar events
    cur.execute("SELECT * FROM calendar_events WHERE user_id = ? ORDER BY start_time ASC", (g.user['id'],))
    events = [dict(r) for r in cur.fetchall()]
    
    # 2. Fetch all scheduled tasks to guarantee unified view without duplicate collisions
    cur.execute("""
        SELECT id, title, description, start_time, end_time, deadline, priority, status
        FROM tasks 
        WHERE user_id = ? AND (start_time IS NOT NULL OR deadline IS NOT NULL)
        ORDER BY start_time ASC
    """, (g.user['id'],))
    tasks = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    return jsonify({
        "events": events,
        "tasks": tasks
    }), 200

@app.route('/api/calendar/events', methods=['POST'])
@require_auth
def create_calendar_event():
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({"error": "Event title is required."}), 400
        
    start_time = data.get('start_time')
    end_time = data.get('end_time') or start_time
    description = (data.get('description') or '').strip()
    all_day = 1 if data.get('all_day') else 0
    event_type = data.get('event_type', 'event')
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO calendar_events (user_id, title, description, start_time, end_time, all_day, event_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (g.user['id'], title, description, start_time, end_time, all_day, event_type))
    event_id = cur.lastrowid
    conn.commit()
    
    cur.execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,))
    event = dict(cur.fetchone())
    conn.close()
    
    return jsonify({"message": "Calendar event created.", "event": event}), 201

@app.route('/api/calendar/events/<int:event_id>', methods=['DELETE'])
@require_auth
def delete_calendar_event(event_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM calendar_events WHERE id = ? AND user_id = ?", (event_id, g.user['id']))
    conn.commit()
    conn.close()
    return jsonify({"message": "Event deleted."}), 200

# -------------------------------------------------------------
# AI Assistant & Scheduling Engine Routes
# -------------------------------------------------------------
@app.route('/api/ai/propose', methods=['POST'])
@require_auth
def ai_propose_schedule():
    data = request.get_json() or {}
    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return jsonify({"error": "Please provide your schedule description or commitments."}), 400
        
    # Query current user's existing tasks to avoid scheduling conflicts
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE user_id = ? AND status != 'completed'", (g.user['id'],))
    existing_tasks = [dict(r) for r in cur.fetchall()]
    
    # Run deterministic neural-heuristic schedule extraction
    proposal_data = scheduler_engine.analyze_user_schedule_request(prompt, existing_tasks)
    
    # Store proposal for explicit approval flow
    cur.execute("""
        INSERT INTO schedule_proposals (user_id, raw_prompt, summary, proposals_json, conflicts_json, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    """, (
        g.user['id'],
        prompt,
        proposal_data['summary'],
        json.dumps(proposal_data['items']),
        json.dumps(proposal_data['conflicts'])
    ))
    proposal_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        "proposal_id": proposal_id,
        "summary": proposal_data['summary'],
        "items": proposal_data['items'],
        "conflicts": proposal_data['conflicts'],
        "mode": proposal_data['mode'],
        "requires_approval": True
    }), 200

@app.route('/api/ai/adjust', methods=['POST'])
@require_auth
def ai_adjust_schedule():
    data = request.get_json() or {}
    proposal_id = data.get('proposal_id')
    items = data.get('items')
    instruction = (data.get('instruction') or '').strip()
    
    if not instruction:
        return jsonify({"error": "Please provide an adjustment instruction."}), 400
        
    if not items and proposal_id:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT proposals_json FROM schedule_proposals WHERE id = ? AND user_id = ?", (proposal_id, g.user['id']))
        row = cur.fetchone()
        conn.close()
        if row:
            items = json.loads(row['proposals_json'])
            
    if not items:
        return jsonify({"error": "No active proposal items found to adjust."}), 400
        
    revised_data = scheduler_engine.adjust_schedule_proposal(items, instruction)
    
    # Update proposal record
    if proposal_id:
        conn = get_db_connection()
        conn.execute("""
            UPDATE schedule_proposals 
            SET summary = ?, proposals_json = ?, conflicts_json = ?
            WHERE id = ? AND user_id = ?
        """, (
            revised_data['summary'],
            json.dumps(revised_data['items']),
            json.dumps(revised_data['conflicts']),
            proposal_id,
            g.user['id']
        ))
        conn.commit()
        conn.close()
        
    return jsonify({
        "proposal_id": proposal_id,
        "summary": revised_data['summary'],
        "items": revised_data['items'],
        "conflicts": revised_data['conflicts'],
        "mode": revised_data['mode'],
        "requires_approval": True
    }), 200

@app.route('/api/ai/approve', methods=['POST'])
@require_auth
def ai_approve_schedule():
    data = request.get_json() or {}
    proposal_id = data.get('proposal_id')
    items = data.get('items')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if not items and proposal_id:
        cur.execute("SELECT proposals_json FROM schedule_proposals WHERE id = ? AND user_id = ?", (proposal_id, g.user['id']))
        row = cur.fetchone()
        if row:
            items = json.loads(row['proposals_json'])
            
    if not items:
        conn.close()
        return jsonify({"error": "No schedule items to approve."}), 400

    created_tasks = []
    # Commit tasks and calendar events only upon explicit user approval
    for item in items:
        cur.execute("""
            INSERT INTO tasks (user_id, title, description, start_time, end_time, duration_min, priority, deadline, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            g.user['id'],
            item['title'],
            item.get('notes', ''),
            item.get('start_time'),
            item.get('end_time'),
            item.get('duration_min', 60),
            item.get('priority', 'medium'),
            item.get('deadline')
        ))
        t_id = cur.lastrowid
        
        # Link to calendar event
        if item.get('start_time'):
            cur.execute("""
                INSERT INTO calendar_events (user_id, title, description, start_time, end_time, task_id, event_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                g.user['id'],
                item['title'],
                item.get('notes', ''),
                item['start_time'],
                item.get('end_time', item['start_time']),
                t_id,
                'commitment' if item.get('type') == 'fixed' else 'task_block'
            ))
            
        created_tasks.append({"id": t_id, "title": item['title']})

    if proposal_id:
        cur.execute("UPDATE schedule_proposals SET status = 'approved' WHERE id = ? AND user_id = ?", (proposal_id, g.user['id']))

    conn.commit()
    conn.close()
    
    return jsonify({
        "message": f"Schedule successfully approved and applied! {len(created_tasks)} tasks added to your plan.",
        "created_tasks": created_tasks
    }), 200

# -------------------------------------------------------------
# Missed-Task Notifications & Proactive Check-ins
# -------------------------------------------------------------
@app.route('/api/notifications/checkin', methods=['POST'])
@require_auth
def check_missed_tasks():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check quiet hours
    cur.execute("SELECT quiet_hours_start, quiet_hours_end, notifications_enabled FROM user_preferences WHERE user_id = ?", (g.user['id'],))
    pref = cur.fetchone()
    
    now = datetime.now()
    current_time_str = now.strftime('%H:%M')
    
    if pref and pref['notifications_enabled']:
        q_start = pref['quiet_hours_start'] or '22:00'
        q_end = pref['quiet_hours_end'] or '07:00'
        # If currently inside quiet hours
        if q_start > q_end: # Spans midnight (e.g. 22:00 to 07:00)
            in_quiet = current_time_str >= q_start or current_time_str <= q_end
        else:
            in_quiet = q_start <= current_time_str <= q_end
            
        if in_quiet:
            conn.close()
            return jsonify({"notifications": [], "in_quiet_hours": True}), 200

    # Find tasks where end_time has passed within last 6 hours and task is still pending or in_progress
    now_iso = now.strftime('%Y-%m-%d %H:%M')
    six_hours_ago = (now - timedelta(hours=6)).strftime('%Y-%m-%d %H:%M')
    
    cur.execute("""
        SELECT t.* FROM tasks t
        LEFT JOIN notifications n ON t.id = n.task_id AND n.action_taken != 'none'
        WHERE t.user_id = ? 
          AND t.status IN ('pending', 'in_progress')
          AND t.end_time IS NOT NULL
          AND t.end_time <= ?
          AND t.end_time >= ?
          AND n.id IS NULL
        ORDER BY t.end_time ASC
        LIMIT 3
    """, (g.user['id'], now_iso, six_hours_ago))
    missed_tasks = cur.fetchall()

    created_notifs = []
    for t in missed_tasks:
        end_time_dt = datetime.strptime(t['end_time'], '%Y-%m-%d %H:%M')
        display_time = end_time_dt.strftime('%I:%M %p').lstrip('0')
        msg = f"MentiNous AI — Your {t['title']} was scheduled to finish at {display_time}. Did you finish it, or do you need more time?"
        
        cur.execute("""
            INSERT INTO notifications (user_id, task_id, message, notification_type, action_taken, is_read)
            VALUES (?, ?, ?, 'task_checkin', 'none', 0)
        """, (g.user['id'], t['id'], msg))
        notif_id = cur.lastrowid
        
        created_notifs.append({
            "id": notif_id,
            "task_id": t['id'],
            "task_title": t['title'],
            "message": msg,
            "end_time": t['end_time'],
            "actions": ["completed", "more_time", "reschedule", "dismiss"]
        })
        
    conn.commit()
    
    # Return all unread notifications
    cur.execute("""
        SELECT n.*, t.title as task_title 
        FROM notifications n
        LEFT JOIN tasks t ON n.task_id = t.id
        WHERE n.user_id = ? AND n.action_taken = 'none'
        ORDER BY n.created_at DESC
    """, (g.user['id'],))
    all_notifs = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    return jsonify({
        "notifications": all_notifs,
        "newly_generated": len(created_notifs),
        "in_quiet_hours": False
    }), 200

@app.route('/api/notifications/<int:notif_id>/respond', methods=['POST'])
@require_auth
def respond_notification(notif_id):
    data = request.get_json() or {}
    action = data.get('action') # 'completed', 'more_time', 'reschedule', 'dismiss'
    
    if action not in ('completed', 'more_time', 'reschedule', 'dismiss'):
        return jsonify({"error": "Invalid notification action."}), 400
        
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM notifications WHERE id = ? AND user_id = ?", (notif_id, g.user['id']))
    notif = cur.fetchone()
    if not notif:
        conn.close()
        return jsonify({"error": "Notification not found."}), 404
        
    task_id = notif['task_id']
    proposal = None

    if action == 'completed' and task_id:
        cur.execute("""
            UPDATE tasks SET status = 'completed', completed_at = CURRENT_TIMESTAMP 
            WHERE id = ? AND user_id = ?
        """, (task_id, g.user['id']))
        msg_result = "Task marked as completed! Great job."
        
    elif action == 'more_time' and task_id:
        # User requested more time: Propose extending task by 30 mins and shift subsequent tasks
        cur.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, g.user['id']))
        task = cur.fetchone()
        if task:
            # Generate proposed schedule adjustment
            now = datetime.now()
            new_end = (now + timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M')
            proposal = {
                "summary": f"Proposed extending '{task['title']}' by 30 minutes until {datetime.strptime(new_end, '%Y-%m-%d %H:%M').strftime('%I:%M %p')}.",
                "task_id": task_id,
                "new_start_time": now.strftime('%Y-%m-%d %H:%M'),
                "new_end_time": new_end,
                "requires_approval": True
            }
        msg_result = "Schedule adjustment proposal generated for review."
        
    elif action == 'reschedule' and task_id:
        # Move to tomorrow morning
        tomorrow_10am = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0).strftime('%Y-%m-%d %H:%M')
        cur.execute("""
            UPDATE tasks SET start_time = ?, status = 'postponed' 
            WHERE id = ? AND user_id = ?
        """, (tomorrow_10am, task_id, g.user['id']))
        msg_result = "Task rescheduled to tomorrow 10:00 AM."
        
    elif action == 'dismiss':
        # Dismissing does NOT mark task as failed or completed
        msg_result = "Reminder dismissed. Task remains in your schedule."
        
    cur.execute("""
        UPDATE notifications SET action_taken = ?, is_read = 1 
        WHERE id = ? AND user_id = ?
    """, (action, notif_id, g.user['id']))
    conn.commit()
    conn.close()
    
    return jsonify({
        "message": msg_result,
        "action": action,
        "proposal": proposal
    }), 200

# -------------------------------------------------------------
# MentiExercise Routes (Scores & Personal Bests)
# -------------------------------------------------------------
@app.route('/api/games/scores', methods=['GET'])
@require_auth
def get_game_scores():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get personal bests and history per game
    cur.execute("""
        SELECT game_id, 
               MAX(score) as high_score, 
               MAX(level_reached) as highest_level,
               COUNT(*) as sessions_played,
               AVG(accuracy) as average_accuracy
        FROM game_scores 
        WHERE user_id = ? 
        GROUP BY game_id
    """, (g.user['id'],))
    bests = [dict(r) for r in cur.fetchall()]
    
    cur.execute("""
        SELECT * FROM game_scores 
        WHERE user_id = ? 
        ORDER BY played_at DESC LIMIT 10
    """, (g.user['id'],))
    history = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    return jsonify({
        "personal_bests": bests,
        "recent_history": history
    }), 200

@app.route('/api/games/scores', methods=['POST'])
@require_auth
def save_game_score():
    data = request.get_json() or {}
    game_id = data.get('game_id')
    if game_id not in ('matrix-master', 'memory-shift', 'neurosprint', 'star-dash'):
        return jsonify({"error": "Invalid game identifier."}), 400
        
    score = int(data.get('score', 0))
    level_reached = int(data.get('level_reached', 1))
    duration_sec = int(data.get('duration_sec', 0))
    accuracy = float(data.get('accuracy', 100.0))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO game_scores (user_id, game_id, score, level_reached, duration_sec, accuracy)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (g.user['id'], game_id, score, level_reached, duration_sec, accuracy))
    conn.commit()
    
    # Check if this is a new personal best
    cur.execute("SELECT MAX(score) as best FROM game_scores WHERE user_id = ? AND game_id = ?", (g.user['id'], game_id))
    best_row = cur.fetchone()
    is_new_best = (score >= best_row['best']) if best_row else True
    conn.close()
    
    return jsonify({
        "message": "Game score recorded successfully!",
        "is_new_best": is_new_best,
        "score": score,
        "level": level_reached
    }), 201

# -------------------------------------------------------------
# End-of-Day Review & Insights Routes
# -------------------------------------------------------------
@app.route('/api/insights/summary', methods=['GET'])
@require_auth
def get_insights_summary():
    conn = get_db_connection()
    cur = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # 1. Today's task breakdown
    cur.execute("""
        SELECT 
            COUNT(*) as total_tasks,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
            SUM(CASE WHEN status IN ('pending', 'in_progress') THEN 1 ELSE 0 END) as unfinished_tasks,
            SUM(CASE WHEN status = 'postponed' THEN 1 ELSE 0 END) as postponed_tasks,
            SUM(CASE WHEN start_time IS NULL AND deadline IS NULL AND status != 'completed' THEN 1 ELSE 0 END) as unknown_status_tasks,
            SUM(CASE WHEN status = 'completed' THEN duration_min ELSE 0 END) as completed_minutes,
            SUM(duration_min) as total_planned_minutes
        FROM tasks 
        WHERE user_id = ? AND (start_time LIKE ? OR deadline LIKE ? OR created_at LIKE ?)
    """, (g.user['id'], f"{today_str}%", f"{today_str}%", f"{today_str}%"))
    metrics = dict(cur.fetchone())
    
    # Fetch lists for end-of-day review
    cur.execute("SELECT id, title, duration_min, priority, completed_at FROM tasks WHERE user_id = ? AND status = 'completed'", (g.user['id'],))
    completed_list = [dict(r) for r in cur.fetchall()]
    
    cur.execute("SELECT id, title, duration_min, priority, start_time FROM tasks WHERE user_id = ? AND status IN ('pending', 'in_progress')", (g.user['id'],))
    unfinished_list = [dict(r) for r in cur.fetchall()]
    
    cur.execute("SELECT id, title, start_time, duration_min FROM tasks WHERE user_id = ? AND status = 'postponed'", (g.user['id'],))
    postponed_list = [dict(r) for r in cur.fetchall()]
    
    cur.execute("SELECT id, title, deadline, priority FROM tasks WHERE user_id = ? AND deadline IS NOT NULL AND status != 'completed' ORDER BY deadline ASC LIMIT 5", (g.user['id'],))
    upcoming_deadlines = [dict(r) for r in cur.fetchall()]
    
    # Weekly completion trend (last 7 days)
    weekly_trend = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as done
            FROM tasks
            WHERE user_id = ? AND (start_time LIKE ? OR completed_at LIKE ?)
        """, (g.user['id'], f"{day}%", f"{day}%"))
        row = cur.fetchone()
        weekly_trend.append({
            "date": day,
            "day_name": datetime.strptime(day, '%Y-%m-%d').strftime('%a'),
            "total": row['total'] or 0,
            "done": row['done'] or 0
        })

    conn.close()
    
    total = metrics.get('total_tasks') or 0
    done = metrics.get('completed_tasks') or 0
    completion_rate = round((done / total * 100), 1) if total > 0 else 0.0

    return jsonify({
        "metrics": {
            "total_tasks": total,
            "completed_tasks": done,
            "unfinished_tasks": metrics.get('unfinished_tasks') or 0,
            "postponed_tasks": metrics.get('postponed_tasks') or 0,
            "unknown_status_tasks": metrics.get('unknown_status_tasks') or 0,
            "completed_minutes": metrics.get('completed_minutes') or 0,
            "total_planned_minutes": metrics.get('total_planned_minutes') or 0,
            "completion_rate": completion_rate
        },
        "lists": {
            "completed": completed_list,
            "unfinished": unfinished_list,
            "postponed": postponed_list,
            "upcoming_deadlines": upcoming_deadlines
        },
        "weekly_trend": weekly_trend,
        "supportive_message": "Great effort today! Every focused minute builds meaningful momentum. Take pride in what you finished and recharge for tomorrow."
    }), 200

# -------------------------------------------------------------
# Settings & Privacy Routes
# -------------------------------------------------------------
@app.route('/api/settings', methods=['GET'])
@require_auth
def get_settings():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_preferences WHERE user_id = ?", (g.user['id'],))
    row = cur.fetchone()
    conn.close()
    return jsonify({"settings": dict(row) if row else {}}), 200

@app.route('/api/settings', methods=['PUT'])
@require_auth
def update_settings():
    data = request.get_json() or {}
    quiet_hours_start = data.get('quiet_hours_start', '22:00')
    quiet_hours_end = data.get('quiet_hours_end', '07:00')
    notifications_enabled = 1 if data.get('notifications_enabled', True) else 0
    sound_enabled = 1 if data.get('sound_enabled', True) else 0
    theme = data.get('theme', 'dark')
    default_game_duration = int(data.get('default_game_duration', 5))
    ai_mode = data.get('ai_mode', 'builtin')
    api_key = data.get('api_key', '').strip()
    
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO user_preferences (user_id, quiet_hours_start, quiet_hours_end, notifications_enabled, sound_enabled, theme, default_game_duration, ai_mode, api_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            quiet_hours_start = excluded.quiet_hours_start,
            quiet_hours_end = excluded.quiet_hours_end,
            notifications_enabled = excluded.notifications_enabled,
            sound_enabled = excluded.sound_enabled,
            theme = excluded.theme,
            default_game_duration = excluded.default_game_duration,
            ai_mode = excluded.ai_mode,
            api_key = excluded.api_key
    """, (g.user['id'], quiet_hours_start, quiet_hours_end, notifications_enabled, sound_enabled, theme, default_game_duration, ai_mode, api_key))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Preferences successfully updated."}), 200

@app.route('/api/settings/password', methods=['PUT'])
@require_auth
def change_password():
    data = request.get_json() or {}
    current_password = data.get('current_password') or ''
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''
    
    if len(new_password) != 4:
        return jsonify({"error": "New password must be exactly 4 characters for this prototype."}), 400
        
    if new_password != confirm_password:
        return jsonify({"error": "New passwords do not match."}), 400
        
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE id = ?", (g.user['id'],))
    user = cur.fetchone()
    
    if not user or not check_password_hash(user['password_hash'], current_password):
        conn.close()
        return jsonify({"error": "Current password is incorrect."}), 400
        
    new_hash = generate_password_hash(new_password, method='scrypt')
    cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, g.user['id']))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Password changed successfully."}), 200

@app.route('/api/settings/export', methods=['GET'])
@require_auth
def export_user_data():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id, name, email, created_at FROM users WHERE id = ?", (g.user['id'],))
    user_info = dict(cur.fetchone())
    
    cur.execute("SELECT * FROM tasks WHERE user_id = ?", (g.user['id'],))
    tasks = [dict(r) for r in cur.fetchall()]
    
    cur.execute("SELECT * FROM calendar_events WHERE user_id = ?", (g.user['id'],))
    events = [dict(r) for r in cur.fetchall()]
    
    cur.execute("SELECT * FROM game_scores WHERE user_id = ?", (g.user['id'],))
    scores = [dict(r) for r in cur.fetchall()]
    
    cur.execute("SELECT * FROM user_preferences WHERE user_id = ?", (g.user['id'],))
    prefs = dict(cur.fetchone()) if cur.fetchone() else {}
    
    conn.close()
    
    export_payload = {
        "export_date": datetime.utcnow().isoformat(),
        "user": user_info,
        "preferences": prefs,
        "tasks": tasks,
        "calendar_events": events,
        "game_scores": scores
    }
    
    return jsonify(export_payload), 200

@app.route('/api/settings/account', methods=['DELETE'])
@require_auth
def delete_account():
    data = request.get_json() or {}
    confirm_text = (data.get('confirmation') or '').strip()
    
    if confirm_text != "DELETE MY ACCOUNT":
        return jsonify({"error": "Please type 'DELETE MY ACCOUNT' to confirm permanent deletion."}), 400
        
    conn = get_db_connection()
    # Cascades will automatically delete sessions, tasks, calendar_events, preferences, game_scores
    conn.execute("DELETE FROM users WHERE id = ?", (g.user['id'],))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Your account and all associated data have been permanently removed."}), 200

if __name__ == '__main__':
    print(f"Starting MentiNous AI server on http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
