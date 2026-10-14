import json
from app import app
from database import init_db, get_db_connection

def test_full_flow():
    init_db()
    client = app.test_client()

    print("\n--- 1. Testing Registration Validation ---")
    # Missing fields
    res = client.post('/api/auth/register', json={})
    assert res.status_code == 400
    print("[PASS] Empty registration rejected")

    # Invalid password length (!= 4)
    res = client.post('/api/auth/register', json={
        "name": "Alice Developer",
        "email": "alice@mentinous.ai",
        "password": "123", # 3 chars
        "confirm_password": "123"
    })
    assert res.status_code == 400
    assert "exactly 4 characters" in res.get_json()['error']
    print("[PASS] 3-character password rejected")

    res = client.post('/api/auth/register', json={
        "name": "Alice Developer",
        "email": "alice@mentinous.ai",
        "password": "12345", # 5 chars
        "confirm_password": "12345"
    })
    assert res.status_code == 400
    assert "exactly 4 characters" in res.get_json()['error']
    print("[PASS] 5-character password rejected")

    # Password mismatch
    res = client.post('/api/auth/register', json={
        "name": "Alice Developer",
        "email": "alice@mentinous.ai",
        "password": "pass",
        "confirm_password": "diff"
    })
    assert res.status_code == 400
    assert "Passwords do not match" in res.get_json()['error']
    print("[PASS] Password mismatch rejected")

    # Successful registration for User A (Alice)
    res = client.post('/api/auth/register', json={
        "name": "Alice Morgan",
        "email": "Alice.Morgan@MentiNous.AI ", # Mixed case and spaces for normalization test
        "password": "a1b2",
        "confirm_password": "a1b2"
    })
    assert res.status_code == 201
    data_a = res.get_json()
    token_a = data_a['token']
    user_a = data_a['user']
    assert user_a['name'] == "Alice Morgan"
    assert user_a['email'] == "alice.morgan@mentinous.ai"
    print(f"[PASS] Alice registered with token: {token_a[:10]}...")

    # Duplicate normalized email registration
    res = client.post('/api/auth/register', json={
        "name": "Impostor Alice",
        "email": "alice.morgan@mentinous.ai",
        "password": "9999",
        "confirm_password": "9999"
    })
    assert res.status_code == 409
    assert "already exists" in res.get_json()['error']
    print("[PASS] Duplicate email rejected")

    # Register User B (Bob) for multi-tenant isolation testing
    res = client.post('/api/auth/register', json={
        "name": "Bob Chen",
        "email": "bob.chen@mentinous.ai",
        "password": "c3d4",
        "confirm_password": "c3d4"
    })
    assert res.status_code == 201
    token_b = res.get_json()['token']
    print("[PASS] Bob registered")

    print("\n--- 2. Testing Login & Sessions ---")
    # Invalid password
    res = client.post('/api/auth/login', json={
        "email": "alice.morgan@mentinous.ai",
        "password": "wrong"
    })
    assert res.status_code == 401
    print("[PASS] Invalid login rejected")

    # Valid login
    res = client.post('/api/auth/login', json={
        "email": "Alice.Morgan@mentinous.ai",
        "password": "a1b2"
    })
    assert res.status_code == 200
    login_data = res.get_json()
    assert login_data['user']['name'] == "Alice Morgan"
    print(f"[PASS] Alice logged in: {login_data['user']['name']}")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Verify /api/auth/me
    res = client.get('/api/auth/me', headers=headers_a)
    assert res.status_code == 200
    assert res.get_json()['user']['name'] == "Alice Morgan"
    print("[PASS] Profile fetched for authenticated session")

    print("\n--- 3. Testing Strict Multi-Tenant Data Isolation ---")
    # Alice creates a private task
    res = client.post('/api/tasks', headers=headers_a, json={
        "title": "Alice's Secret Java Practice",
        "duration_min": 120,
        "priority": "high",
        "start_time": "2026-10-14 17:00",
        "end_time": "2026-10-14 19:00"
    })
    assert res.status_code == 201
    alice_task = res.get_json()['task']
    alice_task_id = alice_task['id']
    print(f"[PASS] Alice created task ID {alice_task_id}")

    # Bob lists tasks: MUST NOT see Alice's task!
    res = client.get('/api/tasks', headers=headers_b)
    bob_tasks = res.get_json()['tasks']
    assert len(bob_tasks) == 0
    print("[PASS] Bob's task list is empty (User isolation verified)")

    # Bob attempts to update Alice's task: MUST fail with 404
    res = client.put(f'/api/tasks/{alice_task_id}', headers=headers_b, json={"title": "Hacked Title"})
    assert res.status_code == 404
    print("[PASS] Bob prevented from modifying Alice's task")

    # Bob attempts to delete Alice's task: MUST fail with 404
    res = client.delete(f'/api/tasks/{alice_task_id}', headers=headers_b)
    assert res.status_code == 404
    print("[PASS] Bob prevented from deleting Alice's task")

    print("\n--- 4. Testing Task Management & Completion Strikethrough ---")
    # Alice toggles completion
    res = client.post(f'/api/tasks/{alice_task_id}/toggle', headers=headers_a)
    assert res.status_code == 200
    assert res.get_json()['task']['status'] == 'completed'
    print("[PASS] Task marked as completed")

    # Alice un-completes
    res = client.post(f'/api/tasks/{alice_task_id}/toggle', headers=headers_a)
    assert res.status_code == 200
    assert res.get_json()['task']['status'] == 'pending'
    print("[PASS] Task completion undone (pending)")

    # Postpone task
    res = client.post(f'/api/tasks/{alice_task_id}/postpone', headers=headers_a, json={"minutes": 30})
    assert res.status_code == 200
    assert res.get_json()['task']['status'] == 'postponed'
    print("[PASS] Task postponed by 30 mins")

    print("\n--- 5. Testing AI Assistant & Scheduling Engine ---")
    # Natural language request
    res = client.post('/api/ai/propose', headers=headers_a, json={
        "prompt": "I have college until 3 PM, two hours of Java practice, and a project deadline tomorrow."
    })
    assert res.status_code == 200
    proposal = res.get_json()
    assert proposal['requires_approval'] == True
    assert len(proposal['items']) >= 2
    proposal_id = proposal['proposal_id']
    print(f"[PASS] AI schedule proposal generated ({len(proposal['items'])} items), requires approval")

    # Natural edit: "Move Java to tomorrow"
    res = client.post('/api/ai/adjust', headers=headers_a, json={
        "proposal_id": proposal_id,
        "items": proposal['items'],
        "instruction": "Move Java to tomorrow"
    })
    assert res.status_code == 200
    revised = res.get_json()
    print(f"[PASS] Schedule revised: {revised['summary']}")

    # Approve schedule
    res = client.post('/api/ai/approve', headers=headers_a, json={
        "proposal_id": proposal_id,
        "items": revised['items']
    })
    assert res.status_code == 200
    print(f"[PASS] Approved schedule: {res.get_json()['message']}")

    # Check tasks and calendar events were added for Alice
    res = client.get('/api/tasks', headers=headers_a)
    assert len(res.get_json()['tasks']) >= 3
    res_cal = client.get('/api/calendar/events', headers=headers_a)
    assert len(res_cal.get_json()['events']) >= 2
    print("[PASS] Calendar events and tasks populated seamlessly")

    print("\n--- 6. Testing Notifications Check-in ---")
    # Force an overdue task for checkin
    conn = get_db_connection()
    conn.execute("UPDATE tasks SET start_time = '2026-10-14 10:00', end_time = '2026-10-14 11:00', status = 'pending' WHERE id = ?", (alice_task_id,))
    conn.commit()
    conn.close()

    res = client.post('/api/notifications/checkin', headers=headers_a)
    assert res.status_code == 200
    notif_data = res.get_json()
    assert len(notif_data['notifications']) > 0
    notif_item = notif_data['notifications'][0]
    print(f"[PASS] Proactive check-in generated: '{notif_item['message']}'")

    # Respond with "more_time"
    res = client.post(f"/api/notifications/{notif_item['id']}/respond", headers=headers_a, json={"action": "more_time"})
    assert res.status_code == 200
    assert res.get_json()['proposal']['requires_approval'] == True
    print("[PASS] 'Need more time' responded and proposed adjustment")

    print("\n--- 7. Testing MentiExercise Game Scores ---")
    # Save Matrix Master score
    res = client.post('/api/games/scores', headers=headers_a, json={
        "game_id": "matrix-master",
        "score": 1250,
        "level_reached": 6,
        "duration_sec": 300,
        "accuracy": 92.5
    })
    assert res.status_code == 201
    assert res.get_json()['is_new_best'] == True
    print("[PASS] Game score recorded for Matrix Master")

    # Fetch scores
    res = client.get('/api/games/scores', headers=headers_a)
    assert res.status_code == 200
    scores = res.get_json()
    assert len(scores['personal_bests']) == 1
    assert scores['personal_bests'][0]['high_score'] == 1250
    print("[PASS] Personal best scores retrieved")

    print("\n--- 8. Testing End-of-Day Review & Insights ---")
    res = client.get('/api/insights/summary', headers=headers_a)
    assert res.status_code == 200
    insights = res.get_json()
    assert "metrics" in insights
    assert "weekly_trend" in insights
    assert "supportive_message" in insights
    print(f"[PASS] Insights summary: {insights['metrics']['total_tasks']} tasks, completion rate {insights['metrics']['completion_rate']}%")

    print("\n--- 9. Testing Settings & Account Recovery ---")
    # Update settings (quiet hours, theme)
    res = client.put('/api/settings', headers=headers_a, json={
        "quiet_hours_start": "23:00",
        "quiet_hours_end": "08:00",
        "theme": "dark",
        "notifications_enabled": True
    })
    assert res.status_code == 200
    print("[PASS] User preferences updated")

    # Forgot password code request
    res = client.post('/api/auth/forgot-password', json={"email": "alice.morgan@mentinous.ai"})
    assert res.status_code == 200
    code = res.get_json()['dev_recovery_code']
    print(f"[PASS] Forgot password recovery code generated: {code}")

    # Reset password with valid code
    res = client.post('/api/auth/reset-password', json={
        "email": "alice.morgan@mentinous.ai",
        "recovery_code": code,
        "new_password": "z9y8",
        "confirm_password": "z9y8"
    })
    assert res.status_code == 200
    print("[PASS] Password successfully reset to 'z9y8'")

    # Old password fails
    res = client.post('/api/auth/login', json={"email": "alice.morgan@mentinous.ai", "password": "a1b2"})
    assert res.status_code == 401
    # New password succeeds
    res = client.post('/api/auth/login', json={"email": "alice.morgan@mentinous.ai", "password": "z9y8"})
    assert res.status_code == 200
    print("[PASS] Logged in with new reset password")

    print("\n==============================================")
    print("ALL BACKEND & SECURITY SCENARIOS PASSED 100%!")
    print("==============================================")

if __name__ == '__main__':
    test_full_flow()
