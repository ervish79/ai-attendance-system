# 👁️ AI Attendance Command Center

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)
![Flask](https://img.shields.io/badge/Flask-Backend-black.svg)
![SQLite](https://img.shields.io/badge/SQLite-Database-lightgrey.svg)
![Contributions welcome](https://img.shields.io/badge/contributions-welcome-orange.svg)

An automated, full-stack attendance tracking system powered by real-time facial recognition. This project eliminates manual logging by capturing, verifying, and recording user attendance into a secure database with high accuracy and low latency.

## 🚀 Key Features

* **Real-Time Facial Recognition:** Leverages advanced computer vision to detect and recognize faces in live video streams.
* **Full-Stack Integration:** Seamless data flow between the frontend UI, backend Flask processing algorithms, and the database.
* **Automated Data Logging:** Instantly records timestamps and user IDs upon successful recognition, reducing manual tracking overhead.
* **Secure Storage:** Employs SQLite for lightweight, reliable data management of user profiles and attendance logs.
* **Extensible Architecture:** Designed with modularity in mind to allow for future integrations, such as liveness detection and cloud database synchronization.

## 🏗️ System Architecture

The system follows a modular architecture to ensure clear separation of concerns across our frontend, backend, database, and AI modules:

1. **Capture Module:** Interfaces with the hardware camera to capture video frames asynchronously.
2. **Processing Engine:** Pre-processes frames and passes them through the facial recognition model to extract facial embeddings.
3. **Matching Algorithm:** Compares real-time embeddings against the registered user database using distance metrics.
4. **Backend Controller:** A Flask-based server that handles API requests, business logic, and database I/O.
5. **Database Layer (SQLite):** Maintains relational schemas for `Users` (ID, Name, Face Encoding) and `Attendance` (User ID, Timestamp, Status).

## 🛠️ Technology Stack

* **Language:** Python
* **Computer Vision & AI:** OpenCV, `face_recognition`
* **Backend Framework:** Flask
* **Database:** SQLite
* **Frontend:** HTML, CSS, JavaScript 
* **Version Control:** Git & GitHub

## ⚙️ Installation & Setup

### Prerequisites
* Python 3.8 or higher installed on your system.
* A working webcam.
* CMake (required for building certain Python CV libraries).

### 1. Clone the Repository
```bash
git clone [https://github.com/ervish79/ai-attendance-system.git](https://github.com/ervish79/ai-attendance-system.git)
cd ai-attendance-system




