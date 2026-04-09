import face_recognition
import os
import sys
from database.db import init_db, insert_student

def add_new_student(name, roll_no, image_path):
    print(f"Processing image for {name}...")
    
    if not os.path.exists(image_path):
        print(f"Error: Image {image_path} not found.")
        sys.exit(1)

    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)

    if len(encodings) == 0:
        print("Error: No face detected. Please use a clearer photo.")
        sys.exit(1)
    if len(encodings) > 1:
        print("Warning: Multiple faces detected. Using the first detected face.")

    encoding = encodings[0]
    insert_student(name, roll_no, image_path, encoding)
    print("Done!")

if __name__ == '__main__':
    init_db()
    os.makedirs("dataset", exist_ok=True)

    print("--- Add New Student to System ---")
    name = input("Enter Student Name: ")
    roll_no = input("Enter Roll Number: ")
    
    print("\nPlease place an image of the student in the 'dataset' folder.")
    filename = input("Enter the filename (e.g., john.jpg): ")
    
    image_path = os.path.join("dataset", filename)
    add_new_student(name, roll_no, image_path)