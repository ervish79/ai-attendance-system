import cv2
import face_recognition
import numpy as np
from datetime import datetime
# Added get_students_by_class to the imports
from database.db import get_all_students, log_attendance_in_db, get_students_by_class
from ai.security_checks import check_liveness, check_mask

class FaceAttendanceSystem:
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_roll_nos = []
        self.load_data()

    def load_data(self):
        """Loads all student data into memory for global reference."""
        self.known_face_encodings.clear()
        self.known_face_names.clear()
        self.known_roll_nos.clear()
        
        students = get_all_students()
        for student in students:
            self.known_face_encodings.append(student['encoding'])
            self.known_face_names.append(student['name'])
            self.known_roll_nos.append(student['roll_no'])
        print(f"AI Engine: Global Database Loaded ({len(self.known_face_encodings)} students).")

    def load_known_faces(self):
        self.load_data()

    def process_frame(self, frame, class_id=None):
        """
        Processes a frame. If class_id is provided, it ONLY looks for 
        students enrolled in that specific class.
        """
        # 1. Prepare Frame
        small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # 2. Filter Encodings by Class (The "Student System" Logic)
        search_encodings = self.known_face_encodings
        search_names = self.known_face_names
        search_rolls = self.known_roll_nos

        if class_id and class_id != "":
            # Get list of students enrolled in this specific class
            enrolled_students = get_students_by_class(class_id)
            enrolled_rolls = [s['roll_no'] for s in enrolled_students]

            # Filter our global lists to only include enrolled students
            search_encodings = []
            search_names = []
            search_rolls = []

            for i in range(len(self.known_roll_nos)):
                if self.known_roll_nos[i] in enrolled_rolls:
                    search_encodings.append(self.known_face_encodings[i])
                    search_names.append(self.known_face_names[i])
                    search_rolls.append(self.known_roll_nos[i])

        # 3. AI Detection
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
        face_landmarks_list = face_recognition.face_landmarks(rgb_small_frame, face_locations)

        # create a list to hold the whoel crowd
        detected_users = []
        class_is_active = True
        if class_id and class_id != "":
            from database.db import check_class_time_lock
            class_is_active = check_class_time_lock(class_id)

        for (top, right, bottom, left), face_encoding, landmarks in zip(face_locations, face_encodings, face_landmarks_list):
            name, roll_no, status_msg = "Unknown", "N/A", ""
            color = (0, 0, 255) # Red for Unknown

            # Security Gates
            if check_mask(landmarks):
                status_msg = "Mask Detected"
                detected_users.append({'name': 'Mask Detected', 'roll': 'Policy Restriction', 'state': 'alert'})
            else:
                face_img = small_frame[top:bottom, left:right]
                if face_img.size != 0:
                    is_live, score = check_liveness(face_img)
                    if not is_live:
                        status_msg = "Spoofing Alert"
                        detected_users.append({'name': 'SECURITY: SPOOFING', 'roll': 'Access Denied', 'state': 'alert'})
                    else:
                        # 4. Recognition Core (Using filtered search lists)
                        if len(search_encodings) > 0:
                            matches = face_recognition.compare_faces(search_encodings, face_encoding, tolerance=0.5)
                            face_distances = face_recognition.face_distance(search_encodings, face_encoding)
                            
                            best_match_index = np.argmin(face_distances)
                            if matches[best_match_index]:
                                name = search_names[best_match_index]
                                roll_no = search_rolls[best_match_index]
                                color = (0, 255, 0) # Green for Success


                                if not class_is_active:
                                    status_msg = "OUT OF HOURS"
                                    color = (0, 165, 255) #ORANGE BOX
                                    # Add the confirmed student to the group list
                                    detected_users.append({'name': name, 'roll': SCHEDULE_LOCK, 'state': 'alert'})
                                else:
                                    detected_users.append({'name': name, 'roll': roll_no, 'state': 'success'})

                                # 5. Log Attendance
                                    if class_id and class_id != "":
                                        log_attendance_in_db(
                                            roll_no, 
                                            class_id, 
                                            datetime.now().strftime("%Y-%m-%d"), 
                                            datetime.now().strftime("%H:%M:%S")
                                        )
                                    else:
                                        detected_users.append({'name': 'Unknown', 'roll': 'Unregistered', 'state': 'alert'})

            # --- Drawing Logic ---
            top *= 2; right *= 2; bottom *= 2; left *= 2
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
            
            display_text = status_msg if status_msg else f"{name} ({roll_no})"
            cv2.putText(frame, display_text, (left + 6, bottom - 6), 
                        cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

        return frame, detected_users