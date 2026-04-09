from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
import cv2
import numpy as np
import base64
import os
import face_recognition
import csv
import io
from datetime import datetime

# Database Imports - Added get_simple_student_list to prevent JSON crashes
from database.db import (
    init_db, get_connection, create_user, add_new_class, 
    get_all_teachers, get_all_classes, get_user_by_username, 
    get_user_by_id, get_all_students, get_simple_student_list, insert_student,
    enroll_student_in_class, get_students_by_class
)
from ai.face_recognition_module import FaceAttendanceSystem

app = Flask(__name__)
app.secret_key = 'super_secret_ai_key_change_in_production'

# Initialize System
init_db()
ai_system = FaceAttendanceSystem()

# --- AUTH SYSTEM ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, role, name):
        self.id = id
        self.username = username
        self.role = role
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_by_id(user_id)
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['role'], user_data['name'])
    return None

# --- ROUTING ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = get_user_by_username(username)
        if user_data and check_password_hash(user_data['password_hash'], password):
            user_obj = User(user_data['id'], user_data['username'], user_data['role'], user_data['name'])
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        error = "Invalid username or password."
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ROUTING ---
# ... (Keep your /login and /logout as they are) ...

@app.route('/')
@login_required
def index():
    return render_template('index.html', current_user=current_user)

@app.route('/dashboard')
@login_required
def dashboard():
    # ⚡ INTELLIGENT ROUTING: Send teachers to their own specialized HUD
    if current_user.role == 'teacher':
        return render_template('teacher_dashboard.html', current_user=current_user)
    
    # Admins still go to the main Global Command Center
    return render_template('dashboard.html', current_user=current_user)

# --- TEACHER SPECIFIC APIs ---

@app.route('/api/teacher_stats', methods=['GET'])
@login_required
def teacher_stats():
    """Provides data specifically for the logged-in teacher's dashboard"""
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized access.'}), 403
        
    try:
        from database.db import get_teacher_classes, get_teacher_attendance_logs
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        # 1. Get classes assigned to this teacher
        my_classes = get_teacher_classes(current_user.id)
        
        # 2. Get today's attendance logs for just their classes
        my_logs = get_teacher_attendance_logs(current_user.id, today_date)
        
        # 3. Calculate metrics
        total_my_students = sum([c['student_count'] for c in my_classes])
        present_today = len(my_logs)
        
        return jsonify({
            'success': True,
            'classes': my_classes,
            'total_students': total_my_students,
            'present_today': present_today,
            'logs': my_logs
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    


@app.route('/api/get_my_classes', methods=['GET'])
@login_required
def get_my_classes():
    """Returns all classes for Admin, or ONLY assigned classes for a Teacher."""
    try:
        from database.db import get_all_classes, get_teacher_classes
        
        if current_user.role == 'admin':
            # Admins get universal access
            classes = get_all_classes()
        else:
            # Teachers only get their specific classes
            classes = get_teacher_classes(current_user.id)
            
        return jsonify({'success': True, 'classes': classes})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    

@app.route('/api/student_report', methods=['GET'])
@login_required
def student_report():
    """Generates a historical audit for a specific student."""
    if current_user.role != 'teacher': 
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    roll_no = request.args.get('roll_no')
    class_id = request.args.get('class_id')

    if not roll_no or not class_id:
        return jsonify({'success': False, 'message': 'Missing Parameters'}), 400

    try:
        from database.db import get_student_attendance_report
        report = get_student_attendance_report(roll_no, class_id)
        return jsonify({'success': True, 'report': report})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route('/api/export_class_report', methods=['GET'])
@login_required
def export_class_report():
    """Generates a CSV summary of all students in a specific class."""
    if current_user.role != 'teacher': return "Unauthorized", 403
    class_id = request.args.get('class_id')
    if not class_id: return "Missing class_id", 400

    from database.db import get_students_by_class, get_student_attendance_report, get_connection
    
    # Get Class Name for the file name
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT class_name FROM classes WHERE id = ?', (class_id,))
    class_data = cursor.fetchone()
    class_name = class_data['class_name'] if class_data else "Class"
    conn.close()

    students = get_students_by_class(class_id)
    
    # Create an in-memory CSV file
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Name', 'Roll Number', 'Days Present', 'Total Active Days', 'Attendance %', 'Status'])
    
    for s in students:
        r = get_student_attendance_report(s['roll_no'], class_id)
        cw.writerow([s['name'], s['roll_no'], r['days_present'], r['total_active_days'], f"{r['percentage']}%", r['status']])
        
    output = Response(si.getvalue(), mimetype='text/csv')
    output.headers["Content-Disposition"] = f"attachment; filename={class_name}_Summary_Report.csv"
    return output


@app.route('/api/export_student_report', methods=['GET'])
@login_required
def export_student_report():
    """Generates a detailed CSV of every date/time a specific student was present."""
    if current_user.role != 'teacher': return "Unauthorized", 403
    class_id = request.args.get('class_id')
    roll_no = request.args.get('roll_no')
    if not class_id or not roll_no: return "Missing Parameters", 400

    from database.db import get_student_attendance_report
    r = get_student_attendance_report(roll_no, class_id)
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Time', 'Status'])
    
    for log in r['history']:
        cw.writerow([log['date'], log['time'], 'Verified Present'])
        
    output = Response(si.getvalue(), mimetype='text/csv')
    output.headers["Content-Disposition"] = f"attachment; filename=Student_{roll_no}_Detailed_Audit.csv"
    return output

@app.route('/api/class_roster_status', methods=['GET'])
@login_required
def class_roster_status():
    """Fetches the live drill-down roster for a specific class."""
    if current_user.role != 'teacher': 
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    class_id = request.args.get('class_id')
    # Default to today if no date is provided
    date_str = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))

    if not class_id:
        return jsonify({'success': False, 'message': 'Missing class_id'}), 400

    try:
        from database.db import get_class_roster_status
        data = get_class_roster_status(class_id, date_str)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    

@app.route('/api/manual_override', methods=['POST'])
@login_required
def manual_override():
    """Route for teachers to manually override student attendance."""
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized. Instructor clearance required.'}), 403
        
    data = request.json
    roll_no = data.get('roll_no')
    class_id = data.get('class_id')
    date_str = data.get('date')
    action = data.get('action') # 'PRESENT' or 'ABSENT'

    if not all([roll_no, class_id, date_str, action]):
        return jsonify({'success': False, 'message': 'Missing parameters.'}), 400

    try:
        from database.db import execute_manual_override
        execute_manual_override(roll_no, class_id, date_str, action)
        return jsonify({'success': True, 'message': f'Override successful: Student {roll_no} marked {action}.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ... (Keep the rest of your app.py exactly the same below this) ...

# --- CORE AI API ---
@app.route('/api/process_frame', methods=['POST'])
@login_required
def process_frame():
    data = request.json
    class_id = data.get('class_id')
    img_data = data['image'].split(',')[1]
    nparr = np.frombuffer(base64.b64decode(img_data), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # The AI engine marks attendance and returns annotated image
    annotated_frame, detected_users = ai_system.process_frame(frame, class_id=class_id)
    
    _, buffer = cv2.imencode('.jpg', annotated_frame)
    b64_string = base64.b64encode(buffer).decode('utf-8')
    
    return jsonify({
        'success': True, 
        'image': f"data:image/jpeg;base64,{b64_string}",
        'detected_users': detected_users #⚡ Pass the whole array to JS
        
    })

# --- DATA & MANAGEMENT APIs ---

@app.route('/api/dashboard_stats', methods=['GET'])
@login_required
def dashboard_stats():
    try:
        from database.db import get_connection
        
        # 1. Get Master Counts using lightweight function
        students = get_simple_student_list()
        teachers = get_all_teachers()
        classes = get_all_classes()
        
        total_students = len(students)
        total_teachers = len(teachers)
        total_classes = len(classes)
        
        # 2. Get Today's Attendance
        today_date = datetime.now().strftime("%Y-%m-%d")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT students.name as Name, attendance_logs.roll_no as 'Roll No', 
                   attendance_logs.time as Time, attendance_logs.status as Status
            FROM attendance_logs 
            JOIN students ON attendance_logs.roll_no = students.roll_no 
            WHERE date = ? ORDER BY time DESC
        ''', (today_date,))
        
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            'success': True, 
            'total_students': total_students,
            'total_teachers': total_teachers,
            'total_classes': total_classes,
            'present_today': len(logs), 
            'logs': logs
        })
    except Exception as e:
        print(f">>> [API ERR]: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get_management_data', methods=['GET'])
@login_required
def get_management_data():
    try:
        teachers = get_all_teachers()
        classes = get_all_classes()
        # Fetching simple list so JSON doesn't crash on face encodings
        students = get_simple_student_list() 
        
        return jsonify({
            'success': True,
            'teachers': teachers,
            'classes': classes,
            'students': students
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get_students_by_class', methods=['GET'])
@login_required
def api_get_students_by_class():
    class_id = request.args.get('class_id')
    if not class_id:
        return jsonify({'success': False, 'message': 'Missing class_id'}), 400
    students = get_students_by_class(class_id)
    return jsonify({'success': True, 'students': students})

# --- ADMIN ACTIONS ---

@app.route('/api/add_teacher', methods=['POST'])
@login_required
def add_teacher():
    if current_user.role != 'admin': return jsonify({'success': False}), 403
    data = request.json
    success, message = create_user(data['username'], data['password'], 'teacher', data['name'])
    return jsonify({'success': success, 'message': message})

@app.route('/api/add_class', methods=['POST'])
@login_required
def add_class():
    """Admin route to create a new class with an active time lock."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized. Admin access required.'}), 403
        
    data = request.json
    class_name = data.get('class_name')
    teacher_id = data.get('teacher_id')
    
    # ⚡ Catch the new time parameters sent from JavaScript
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    # Basic validation
    if not class_name or not teacher_id:
        return jsonify({'success': False, 'message': 'Class name and Teacher ID are required.'}), 400

    try:
        # Import your database function
        from database.db import add_new_class 
        
        # Pass the new time limits to the database
        add_new_class(class_name, teacher_id, start_time, end_time)
        
        return jsonify({'success': True, 'message': f'Class {class_name} initialized successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/enroll_student', methods=['POST'])
@login_required
def enroll_student():
    """Maps an existing student to a class"""
    if current_user.role != 'admin': return jsonify({'success': False}), 403
    data = request.json
    success = enroll_student_in_class(data['roll_no'], data['class_id'])
    if success:
        return jsonify({'success': True, 'message': 'Student Enrolled!'})
    return jsonify({'success': False, 'message': 'Already enrolled or error.'})


@app.route('/api/remove_student', methods=['POST'])
@login_required
def remove_student():
    """Admin route to permanently delete a student."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized. Admin level required.'}), 403
        
    data = request.json
    roll_no = data.get('roll_no')

    if not roll_no:
        return jsonify({'success': False, 'message': 'Roll Number is required.'}), 400

    try:
        from database.db import remove_student_record
        remove_student_record(roll_no)
        return jsonify({'success': True, 'message': f'Unit {roll_no} has been completely purged from the system.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- STUDENT ENROLLMENT ---

@app.route('/register_student')
@login_required
def register_student_page():
    return render_template('register_student.html')

@app.route('/api/register_student', methods=['POST'])
@login_required
def api_register_student():
    try:
        data = request.json
        name, roll_no, class_id = data.get('name'), data.get('roll_no'), data.get('class_id')
        img_base64 = data.get('image').split(',')[1]

        nparr = np.frombuffer(base64.b64decode(img_base64), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        encodings = face_recognition.face_encodings(rgb_frame)
        if not encodings:
            return jsonify({'success': False, 'message': 'Face Not Detected'})
        
        encoding = encodings[0]
        os.makedirs("dataset", exist_ok=True)
        img_path = f"dataset/{roll_no}.jpg"
        cv2.imwrite(img_path, frame)

        # 1. Insert into Master Student Table
        success, message = insert_student(name, roll_no, img_path, encoding)
        
        if success:
            # 2. Link student to the initial class
            enroll_student_in_class(roll_no, class_id)
            # 3. Force AI Engine to reload faces from memory
            ai_system.load_known_faces() 
            return jsonify({'success': True, 'message': f'Digital Profile for {name} Created!'})
        
        return jsonify({'success': False, 'message': message})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    
@app.route('/student', methods=['GET'])
def student_portal():
    """Renders the public-facing Student Read-Only Kiosk."""
    return render_template('student_portal.html')

@app.route('/api/get_student_dashboard', methods=['GET'])
def get_student_dashboard():
    """Fetches the complete attendance data for the Student Kiosk."""
    roll_no = request.args.get('roll_no')
    if not roll_no:
        return jsonify({'success': False, 'message': 'Roll Number required.'}), 400

    try:
        from database.db import get_student_kiosk_data, get_student_attendance_report
        data = get_student_kiosk_data(roll_no)

        if not data:
            return jsonify({'success': False, 'message': 'IDENTITY_NOT_FOUND: Roll Number does not exist.'}), 404

        # Calculate exact attendance stats for every single class they are in
        for c in data['classes']:
            # We reuse the powerful audit function we built in Phase 2!
            c['stats'] = get_student_attendance_report(roll_no, c['id'])

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route('/api/edit_class', methods=['POST'])
@login_required
def edit_class():
    """Admin route to update an existing class schedule."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized.'}), 403
        
    data = request.json
    class_id = data.get('class_id')
    class_name = data.get('class_name')
    teacher_id = data.get('teacher_id')
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    if not class_id or not class_name or not teacher_id:
        return jsonify({'success': False, 'message': 'Missing required fields.'}), 400

    try:
        from database.db import update_class_schedule
        update_class_schedule(class_id, class_name, teacher_id, start_time, end_time)
        return jsonify({'success': True, 'message': f'Class {class_name} updated successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)