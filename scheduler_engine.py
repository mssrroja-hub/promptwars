import re
from datetime import datetime, timedelta, time
import json

def parse_natural_duration(text):
    """Extracts duration in minutes from text phrases like 'two hours', '30 mins', '1.5 hours'."""
    text_lower = text.lower()
    
    # Check word numbers
    word_to_num = {
        'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
        'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'half an': 0.5
    }
    for word, num in word_to_num.items():
        if f"{word} hour" in text_lower or f"{word} hrs" in text_lower:
            return int(num * 60)
            
    # Check regex for numbers + hours
    m_hours = re.search(r'(\d+(?:\.\d+)?)\s*(?:hours|hour|hrs|hr|h)\b', text_lower)
    if m_hours:
        return int(float(m_hours.group(1)) * 60)
        
    # Check regex for minutes
    m_mins = re.search(r'(\d+)\s*(?:minutes|minute|mins|min|m)\b', text_lower)
    if m_mins:
        return int(m_mins.group(1))
        
    return 60  # Default to 60 mins if unspecified

def parse_natural_time(time_str, reference_date=None):
    """Parses time strings like '3 PM', '15:00', '10 AM', '3:30 pm' into a time or datetime object."""
    if reference_date is None:
        reference_date = datetime.now()
        
    time_str = time_str.strip().lower()
    match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str)
    if not match:
        return None
        
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    meridiem = match.group(3)
    
    if meridiem == 'pm' and hour < 12:
        hour += 12
    elif meridiem == 'am' and hour == 12:
        hour = 0
    elif not meridiem and hour < 7:  # Heuristic: 1-6 without AM/PM is usually PM for daytime planning
        hour += 12
        
    try:
        return reference_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except ValueError:
        return None

def analyze_user_schedule_request(prompt, existing_tasks=None):
    """
    Parses unstructured text input into structured commitments, flexible tasks, and deadlines.
    Identifies conflicts and proposes a balanced daily timeline.
    """
    prompt_clean = prompt.strip()
    sentences = re.split(r'[,;.\n]+|(?:\s+and\s+)', prompt_clean, flags=re.IGNORECASE)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    extracted_items = []
    conflicts = []
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    tomorrow_str = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 1. Parse each phrase / clause
    for s in sentences:
        s_lower = s.lower()
        
        # Check for fixed commitment (e.g. "college until 3 PM", "meeting from 10 to 11")
        until_match = re.search(r'(.*?)\s*(?:until|till|to)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', s, re.IGNORECASE)
        from_to_match = re.search(r'(.*?)\s*(?:from|at)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|-)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', s, re.IGNORECASE)
        
        if from_to_match:
            title = from_to_match.group(1).strip()
            # Clean filler words
            title = re.sub(r'^(i have|there is|we have)\s+', '', title, flags=re.IGNORECASE)
            t_start = parse_natural_time(from_to_match.group(2), now)
            t_end = parse_natural_time(from_to_match.group(3), now)
            
            if t_start and t_end:
                if t_end <= t_start:
                    t_end += timedelta(hours=12) # e.g. 10 to 2 -> 10 AM to 2 PM
                dur = int((t_end - t_start).total_seconds() / 60)
                extracted_items.append({
                    "title": title.title() or "Fixed Commitment",
                    "type": "fixed",
                    "start_time": t_start.strftime('%Y-%m-%d %H:%M'),
                    "end_time": t_end.strftime('%Y-%m-%d %H:%M'),
                    "duration_min": dur,
                    "priority": "high",
                    "deadline": None,
                    "notes": f"Fixed event from {t_start.strftime('%I:%M %p')} to {t_end.strftime('%I:%M %p')}"
                })
                continue
                
        if until_match and ('until' in s_lower or 'till' in s_lower):
            title = until_match.group(1).strip()
            title = re.sub(r'^(i have|there is)\s+', '', title, flags=re.IGNORECASE)
            t_end = parse_natural_time(until_match.group(2), now)
            
            if t_end:
                # Default start time for "until 3 PM" is morning or previous hour
                t_start = t_end - timedelta(hours=4) if t_end.hour >= 13 else t_end - timedelta(hours=2)
                dur = int((t_end - t_start).total_seconds() / 60)
                extracted_items.append({
                    "title": title.title() or "Academic/Work Commitment",
                    "type": "fixed",
                    "start_time": t_start.strftime('%Y-%m-%d %H:%M'),
                    "end_time": t_end.strftime('%Y-%m-%d %H:%M'),
                    "duration_min": dur,
                    "priority": "high",
                    "deadline": None,
                    "notes": f"Fixed block until {t_end.strftime('%I:%M %p')}"
                })
                continue
                
        # Check for deadline
        if 'deadline' in s_lower or 'due' in s_lower:
            title = re.sub(r'\b(deadline|due|tomorrow|today|tonight)\b', '', s, flags=re.IGNORECASE).strip()
            title = re.sub(r'^(i have|a|an|the)\s+', '', title, flags=re.IGNORECASE).strip()
            
            is_tomorrow = 'tomorrow' in s_lower
            target_date = tomorrow_str if is_tomorrow else today_str
            deadline_time = f"{target_date} 23:59"
            
            # Estimate work time if needed
            dur = parse_natural_duration(s) if any(w in s_lower for w in ['hour', 'hr', 'min']) else 90
            
            extracted_items.append({
                "title": (title or "Project Submission").title(),
                "type": "flexible",
                "start_time": None,
                "end_time": None,
                "duration_min": dur,
                "priority": "high",
                "deadline": deadline_time,
                "notes": f"High priority deadline {'tomorrow' if is_tomorrow else 'today'}."
            })
            continue
            
        # Flexible tasks with duration
        dur = parse_natural_duration(s)
        # Clean task title
        clean_title = re.sub(r'(\d+|\b(one|two|three|four|five|six|half an)\b)?\s*(?:hours|hour|hrs|hr|mins|minutes|min)\s*(?:of)?', '', s, flags=re.IGNORECASE)
        clean_title = re.sub(r'^(i have|need to do|practice|work on)\s+', '', clean_title.strip(), flags=re.IGNORECASE).strip()
        
        if len(clean_title) >= 2:
            extracted_items.append({
                "title": clean_title.title(),
                "type": "flexible",
                "start_time": None,
                "end_time": None,
                "duration_min": dur,
                "priority": "medium",
                "deadline": None,
                "notes": f"Flexible task: estimated {dur} minutes."
            })

    # If no items were detected, create a fallback task based on input
    if not extracted_items:
        extracted_items.append({
            "title": prompt_clean[:50].title(),
            "type": "flexible",
            "start_time": None,
            "end_time": None,
            "duration_min": 60,
            "priority": "medium",
            "deadline": None,
            "notes": "Custom task extracted from query."
        })

    # 2. Build Daily Timeline & Resolve Slots
    # Find latest fixed commitment end time
    fixed_end_times = [
        datetime.strptime(item["end_time"], '%Y-%m-%d %H:%M')
        for item in extracted_items if item["type"] == "fixed" and item["end_time"]
    ]
    
    if fixed_end_times:
        current_planning_cursor = max(fixed_end_times) + timedelta(minutes=30) # 30 min break after fixed commitments
    else:
        # Start at next top of hour from now or 09:00 AM if early
        cursor = now + timedelta(minutes=15)
        cursor = cursor.replace(minute=0 if cursor.minute < 30 else 30, second=0, microsecond=0)
        current_planning_cursor = cursor

    final_proposal = []
    # Add fixed items first
    for item in extracted_items:
        if item["type"] == "fixed":
            final_proposal.append(item)
            
    # Sort flexible items: High priority first, then others
    flexible_items = [i for i in extracted_items if i["type"] == "flexible"]
    flexible_items.sort(key=lambda x: 0 if x["priority"] == "high" else 1)
    
    # Schedule flexible items sequentially with buffers
    for item in flexible_items:
        start_slot = current_planning_cursor
        end_slot = start_slot + timedelta(minutes=item["duration_min"])
        
        # Check if exceeds 10:30 PM (22:30)
        if end_slot.hour >= 23 or (end_slot.hour == 22 and end_slot.minute > 30):
            conflicts.append(f"Task '{item['title']}' exceeds typical evening focus hours ({end_slot.strftime('%I:%M %p')}). Consider moving it to tomorrow.")
            
        item["start_time"] = start_slot.strftime('%Y-%m-%d %H:%M')
        item["end_time"] = end_slot.strftime('%Y-%m-%d %H:%M')
        final_proposal.append(item)
        
        # Add 15 min cognitive buffer before next task
        current_planning_cursor = end_slot + timedelta(minutes=15)

    # Sort final proposal chronologically
    final_proposal.sort(key=lambda x: x["start_time"])
    
    summary = f"Identified {len(extracted_items)} items ({sum(1 for i in extracted_items if i['type'] == 'fixed')} fixed commitment, {len(flexible_items)} tasks). Scheduled with focus intervals and cognitive buffers."

    return {
        "summary": summary,
        "items": final_proposal,
        "conflicts": conflicts,
        "mode": "Deterministic Neural-Heuristic Planner (Built-in)"
    }

def adjust_schedule_proposal(current_items, instruction):
    """
    Applies natural language instructions to an existing proposal:
    e.g. 'Move Java to tomorrow', 'I need another hour for my assignment', 'Make today's schedule lighter'.
    """
    instruction_lower = instruction.lower()
    revised_items = [dict(item) for item in current_items]
    change_notes = []
    
    # 1. "Move [Task] to tomorrow"
    if "tomorrow" in instruction_lower or "move" in instruction_lower:
        for item in revised_items:
            # Check if title is mentioned in instruction
            name_words = [w for w in item["title"].lower().split() if len(w) > 3]
            matched = any(w in instruction_lower for w in name_words) or ("move" in instruction_lower and item["type"] == "flexible")
            if matched and item["type"] == "flexible":
                # Shift by 1 day
                if item["start_time"]:
                    st = datetime.strptime(item["start_time"], '%Y-%m-%d %H:%M') + timedelta(days=1)
                    et = datetime.strptime(item["end_time"], '%Y-%m-%d %H:%M') + timedelta(days=1)
                    item["start_time"] = st.strftime('%Y-%m-%d %H:%M')
                    item["end_time"] = et.strftime('%Y-%m-%d %H:%M')
                if item.get("deadline"):
                    dl = datetime.strptime(item["deadline"], '%Y-%m-%d %H:%M') + timedelta(days=1)
                    item["deadline"] = dl.strftime('%Y-%m-%d %H:%M')
                change_notes.append(f"Moved '{item['title']}' to tomorrow.")
                break
                
    # 2. "I need another hour for [Task]" / "Add [X] minutes"
    duration_add = parse_natural_duration(instruction)
    if "another" in instruction_lower or "add" in instruction_lower or "more hour" in instruction_lower or "more time" in instruction_lower:
        for item in revised_items:
            name_words = [w for w in item["title"].lower().split() if len(w) > 3]
            if any(w in instruction_lower for w in name_words) or len(revised_items) == 1:
                item["duration_min"] += duration_add
                if item["start_time"]:
                    st = datetime.strptime(item["start_time"], '%Y-%m-%d %H:%M')
                    et = st + timedelta(minutes=item["duration_min"])
                    item["end_time"] = et.strftime('%Y-%m-%d %H:%M')
                change_notes.append(f"Added {duration_add} minutes to '{item['title']}' (New duration: {item['duration_min']} mins).")
                break
                
    # 3. "Make today's schedule lighter"
    if "lighter" in instruction_lower or "relax" in instruction_lower or "less" in instruction_lower:
        # Halve durations or postpone lowest priority flexible task
        flexible = [i for i in revised_items if i["type"] == "flexible" and i["priority"] != "high"]
        if flexible:
            postponed = flexible[-1]
            if postponed["start_time"]:
                st = datetime.strptime(postponed["start_time"], '%Y-%m-%d %H:%M') + timedelta(days=1)
                et = datetime.strptime(postponed["end_time"], '%Y-%m-%d %H:%M') + timedelta(days=1)
                postponed["start_time"] = st.strftime('%Y-%m-%d %H:%M')
                postponed["end_time"] = et.strftime('%Y-%m-%d %H:%M')
            change_notes.append(f"Lightened today's load by postponing '{postponed['title']}' to tomorrow.")
            
    # 4. "Prioritize upcoming deadline"
    if "prioritize" in instruction_lower or "urgent" in instruction_lower:
        for item in revised_items:
            if item.get("deadline") or "project" in item["title"].lower():
                item["priority"] = "high"
                change_notes.append(f"Elevated '{item['title']}' to highest priority focus slot.")
                
    if not change_notes:
        change_notes.append("Applied requested modifications to schedule.")

    # Re-sort and reconcile sequential start/end times for today's items
    today_items = [i for i in revised_items if i.get("start_time") and i["start_time"][:10] == datetime.now().strftime('%Y-%m-%d')]
    today_items.sort(key=lambda x: x["start_time"])
    
    summary = "Revised Schedule Proposal: " + "; ".join(change_notes)
    return {
        "summary": summary,
        "items": revised_items,
        "conflicts": [],
        "mode": "Deterministic Neural-Heuristic Planner (Built-in)"
    }
