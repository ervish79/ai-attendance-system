import sqlite3
import numpy as np
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Ensures the DB is created in the same folder as db.py
DB_PATH = os.path.join(os.path.dirname(__file__), 'attendance.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Master Students Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT NOT NULL, 
        roll_no TEXT UNIQUE NOT NULL, 
        image_path TEXT, 
        encoding BLOB NOT NULL)''')
    
    # 2. Users (Admin/Teachers)
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        username TEXT UNIQUE NOT NULL, 
        password_hash TEXT NOT NULL, 
        role TEXT NOT NULL, 
        name TEXT NOT NULL)''')
    
    # 3. Classes Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        class_name TEXT NOT NULL, 
        teacher_id INTEGER,
        start_time TEXT,
        end_time TEXT, 
        FOREIGN KEY (teacher_id) REFERENCES users (id))''')
    
    # 4. Attendance Logs
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        roll_no TEXT NOT NULL, 
        class_id INTEGER, 
        date TEXT NOT NULL, 
        time TEXT NOT NULL, 
        status TEXT DEFAULT 'Present', 
        FOREIGN KEY (roll_no) REFERENCES students (roll_no), 
        FOREIGN KEY (class_id) REFERENCES classes (id))''')
    
    # 5. Class Enrollment (Mapping)
    cursor.execute('''CREATE TABLE IF NOT EXISTS class_enrollment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT NOT NULL,
        class_id INTEGER NOT NULL,
        FOREIGN KEY (roll_no) REFERENCES students (roll_no),
        FOREIGN KEY (class_id) REFERENCES classes (id),
        UNIQUE(roll_no, class_id)
    )''')
        
    conn.commit()
    conn.close()
    print(">>> Database Initialized.")

# --- STUDENT DATA ---

def insert_student(name, roll_no, image_path, encoding_array):
    encoding_bytes = encoding_array.tobytes()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO students (name, roll_no, image_path, encoding) VALUES (?, ?, ?, ?)', 
                       (name, roll_no, image_path, encoding_bytes))
        conn.commit()
        return True, "Success"
    except sqlite3.IntegrityError:
        return False, "Roll number already exists"
    finally:
        conn.close()

def get_all_students():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, roll_no, encoding FROM students')
    rows = cursor.fetchall()
    conn.close()
    return [{
        'name': row['name'], 
        'roll_no': row['roll_no'], 
        'encoding': np.frombuffer(row['encoding'], dtype=np.float64)
    } for row in rows]

def get_simple_student_list():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, roll_no FROM students ORDER BY name ASC')
    students = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return students

# --- ATTENDANCE LOGGING (The Missing Function) ---

def log_attendance_in_db(roll_no, class_id, date, time, status="Present"):
    """Saves a detection event to the database if not already logged today."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if this student was already marked present in this class today
    cursor.execute('''SELECT id FROM attendance_logs 
                      WHERE roll_no = ? AND class_id = ? AND date = ?''', 
                   (roll_no, class_id, date))
    
    already_logged = cursor.fetchone()
    
    if already_logged is None:
        cursor.execute('''INSERT INTO attendance_logs (roll_no, class_id, date, time, status) 
                          VALUES (?, ?, ?, ?, ?)''', (roll_no, class_id, date, time, status))
        conn.commit()
        added = True
    else:
        added = False # Duplicate prevented
        
    conn.close()
    return added

# --- AUTH & USERS ---

def create_user(username, password, role, name):
    hashed_pw = generate_password_hash(password)
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password_hash, role, name) VALUES (?, ?, ?, ?)', 
                       (username, hashed_pw, role, name))
        conn.commit()
        return True, "User Created"
    except sqlite3.IntegrityError:
        return False, "Username Taken"
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# --- MANAGEMENT & ROSTERS ---

def get_all_classes():
    conn = get_connection()
    cursor = conn.cursor()
    
    # ⚡ We added teacher_id, start_time, and end_time to the SELECT statement
    cursor.execute('''
        SELECT classes.id, classes.class_name, classes.teacher_id, 
               classes.start_time, classes.end_time, users.name as teacher_name 
        FROM classes 
        LEFT JOIN users ON classes.teacher_id = users.id
    ''')
    
    classes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return classes

def get_all_teachers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, username FROM users WHERE role = 'teacher'")
    teachers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return teachers

def add_new_class(class_name, teacher_id, start_time=None, end_time=None):
    """Inserts a new class into the database with optional time limits."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # ⚡ Update the SQL query to insert the start and end times
    cursor.execute('''
        INSERT INTO classes (class_name, teacher_id, start_time, end_time)
        VALUES (?, ?, ?, ?)
    ''', (class_name, teacher_id, start_time, end_time))
    
    conn.commit()
    conn.close()

def enroll_student_in_class(roll_no, class_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO class_enrollment (roll_no, class_id) VALUES (?, ?)', 
                       (roll_no, class_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False 
    finally:
        conn.close()

def get_students_by_class(class_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.name, s.roll_no 
        FROM students s
        JOIN class_enrollment e ON s.roll_no = e.roll_no
        WHERE e.class_id = ?
        ORDER BY s.name ASC
    ''', (class_id,))
    students = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return students


# --- TEACHER DASHBOARD SPECIFIC FUNCTIONS ---

def get_teacher_classes(teacher_id):
    """Fetches only the classes assigned to a specific teacher."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, class_name FROM classes WHERE teacher_id = ?', (teacher_id,))
    classes = [dict(row) for row in cursor.fetchall()]
    
    # Get student counts for each class
    for c in classes:
        cursor.execute('SELECT COUNT(*) FROM class_enrollment WHERE class_id = ?', (c['id'],))
        c['student_count'] = cursor.fetchone()[0]
        
    conn.close()
    return classes

def get_teacher_attendance_logs(teacher_id, date):
    """Fetches today's attendance logs ONLY for classes owned by this teacher."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT students.name as Name, attendance_logs.roll_no as 'Roll No', 
               attendance_logs.time as Time, attendance_logs.status as Status,
               classes.class_name as ClassName
        FROM attendance_logs 
        JOIN students ON attendance_logs.roll_no = students.roll_no 
        JOIN classes ON attendance_logs.class_id = classes.id
        WHERE classes.teacher_id = ? AND attendance_logs.date = ?
        ORDER BY attendance_logs.time DESC
    ''', (teacher_id, date))
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return logs


# --- ANALYTICS & AUDIT ---

def get_student_attendance_report(roll_no, class_id):
    """Calculates the 75% attendance rule and fetches history."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Calculate Total Active Sessions for this specific class
    cursor.execute('''SELECT COUNT(DISTINCT date) FROM attendance_logs WHERE class_id = ?''', (class_id,))
    total_active_days = cursor.fetchone()[0] or 0

    # 2. Calculate Days Present for this specific student
    cursor.execute('''SELECT COUNT(DISTINCT date) FROM attendance_logs WHERE class_id = ? AND roll_no = ?''', (class_id, roll_no))
    days_present = cursor.fetchone()[0] or 0

    # 3. Fetch their exact historical log for audit purposes
    cursor.execute('''SELECT date, time FROM attendance_logs WHERE class_id = ? AND roll_no = ? ORDER BY date DESC''', (class_id, roll_no))
    history = [dict(row) for row in cursor.fetchall()]

    conn.close()

    # Math: Calculate Percentage
    percentage = 0
    if total_active_days > 0:
        percentage = round((days_present / total_active_days) * 100, 1)

    # Threshold Logic
    status = "ELIGIBLE" if percentage >= 75.0 else "WARNING_DEBARMENT"

    return {
        'total_active_days': total_active_days,
        'days_present': days_present,
        'percentage': percentage,
        'history': history,
        'status': status
    }

# --- DRILL-DOWN ROSTER LOGIC ---

def get_class_roster_status(class_id, date_str):
    """Returns all enrolled students and their Present/Absent status for a specific date."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Get ALL enrolled students for this class
    cursor.execute('''
        SELECT s.roll_no, s.name
        FROM students s
        JOIN class_enrollment ce ON s.roll_no = ce.roll_no
        WHERE ce.class_id = ?
    ''', (class_id,))
    all_students = [dict(row) for row in cursor.fetchall()]

    # 2. Get the students who actually scanned in today
    cursor.execute('''
        SELECT roll_no, time 
        FROM attendance_logs 
        WHERE class_id = ? AND date = ?
    ''', (class_id, date_str))
    present_records = {row['roll_no']: row['time'] for row in cursor.fetchall()}

    conn.close()

    # 3. Process the data
    roster = []
    present_count = 0
    absent_count = 0

    for student in all_students:
        roll = student['roll_no']
        if roll in present_records:
            status = 'PRESENT'
            time_logged = present_records[roll]
            present_count += 1
        else:
            status = 'ABSENT'
            time_logged = '--:--'
            absent_count += 1

        roster.append({
            'name': student['name'],
            'roll_no': roll,
            'status': status,
            'time': time_logged
        })

    return {
        'total_enrolled': len(all_students),
        'present_count': present_count,
        'absent_count': absent_count,
        'roster': roster
    }

def check_class_time_lock(class_id):
    """Returns True if the current time is within the class schedule, False otherwise."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT start_time, end_time FROM classes WHERE id = ?', (class_id,))
    class_data = cursor.fetchone()
    conn.close()

    if not class_data or not class_data['start_time'] or not class_data['end_time']:
        return True # Default to open if admin forgot to set times

    from datetime import datetime
    now_time = datetime.now().strftime("%H:%M")
    
    # Compare 24-hour time strings (e.g., "14:30" >= "10:00")
    if class_data['start_time'] <= now_time <= class_data['end_time']:
        return True
    return False


# --- RECONFIGURATION LOGIC ---

def update_class_schedule(class_id, class_name, teacher_id, start_time, end_time):
    """Updates an existing class's name, assigned teacher, and time lock."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE classes 
        SET class_name = ?, teacher_id = ?, start_time = ?, end_time = ?
        WHERE id = ?
    ''', (class_name, teacher_id, start_time, end_time, class_id))
    
    conn.commit()
    conn.close()


# --- TERMINATION PROTOCOL ---

def remove_student_record(roll_no):
    """Completely erases a student and all their associated data from the system."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Erase all their past attendance logs
    cursor.execute('DELETE FROM attendance_logs WHERE roll_no = ?', (roll_no,))
    
    # 2. Remove them from all active class rosters
    cursor.execute('DELETE FROM class_enrollment WHERE roll_no = ?', (roll_no,))
    
    # 3. Terminate their main student profile
    cursor.execute('DELETE FROM students WHERE roll_no = ?', (roll_no,))
    
    conn.commit()
    conn.close()

# --- STUDENT KIOSK LOGIC ---

def get_student_kiosk_data(roll_no):
    """Fetches a student's profile and all their enrolled classes."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Verify student exists
    cursor.execute('SELECT name FROM students WHERE roll_no = ?', (roll_no,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return None

    # 2. Get all classes they are enrolled in, plus the teacher's name
    cursor.execute('''
        SELECT c.id, c.class_name, u.name as teacher_name
        FROM class_enrollment ce
        JOIN classes c ON ce.class_id = c.id
        LEFT JOIN users u ON c.teacher_id = u.id
        WHERE ce.roll_no = ?
    ''', (roll_no,))
    classes = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        'student_name': student['name'], 
        'roll_no': roll_no, 
        'classes': classes
    }


# --- EXECUTIVE OVERRIDE LOGIC ---

def execute_manual_override(roll_no, class_id, date_str, action):
    """Allows a teacher to manually grant or revoke attendance."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if action == 'PRESENT':
        # Check if they are already marked present so we don't duplicate
        cursor.execute('SELECT id FROM attendance_logs WHERE roll_no = ? AND class_id = ? AND date = ?', (roll_no, class_id, date_str))
        if not cursor.fetchone():
            # Insert a manual log. We use "EXCUSED" as the time so admins know the AI didn't scan them
            cursor.execute('''
                INSERT INTO attendance_logs (roll_no, class_id, date, time) 
                VALUES (?, ?, ?, 'EXCUSED')
            ''', (roll_no, class_id, date_str))
            
    elif action == 'ABSENT':
        # Erase their attendance record for that specific day
        cursor.execute('''
            DELETE FROM attendance_logs 
            WHERE roll_no = ? AND class_id = ? AND date = ?
        ''', (roll_no, class_id, date_str))
        
    conn.commit()
    conn.close()