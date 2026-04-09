import cv2
import numpy as np
from scipy.spatial import distance as dist

# --- 1. LIVENESS: TEXTURE ANALYSIS ---
def check_liveness(face_img, threshold=35):
    """
    ANTI-SPOOFING: Texture Variance Analysis
    Detects if the face is a digital screen/printed photo vs. a physical human.
    Real skin has micro-textures; digital screens/photos look 'flat' to the Laplacian filter.
    """
    if face_img is None or face_img.size == 0:
        return False, 0
        
    # Convert to grayscale for frequency analysis
    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
    
    # Laplacian highlights edges and textures. 
    # Variance of the Laplacian tells us the 'sharpness' of the image.
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Threshold 35 is optimal for 720p webcams. 
    # If variance < 35, it's likely a photo or a blurred screen.
    is_live = variance > threshold
    return is_live, round(variance, 2)

# --- 2. MASK DETECTION: LANDMARK INTEGRITY ---
def check_mask(landmarks):
    """
    ANTI-MASK: Landmark Presence Check
    A mask usually obscures the nose tip and the entire mouth region.
    If the AI cannot find these landmarks, we flag it as a potential mask.
    """
    # Key biometric points required for a valid 'unmasked' face
    required_biometrics = ['nose_tip', 'top_lip', 'bottom_lip', 'chin']
    
    for part in required_biometrics:
        if part not in landmarks or len(landmarks[part]) == 0:
            return True # Mask/Obscuration detected
            
    return False

# --- 3. BLINK DETECTION: EYE ASPECT RATIO (EAR) ---
def calculate_ear(eye_points):
    """
    Calculates the Eye Aspect Ratio (EAR).
    Formula: ||p2-p6|| + ||p3-p5|| / (2 * ||p1-p4||)
    """
    # Compute vertical distances between eye landmarks
    v1 = dist.euclidean(eye_points[1], eye_points[5])
    v2 = dist.euclidean(eye_points[2], eye_points[4])
    
    # Compute horizontal distance
    h = dist.euclidean(eye_points[0], eye_points[3])
    
    # EAR calculation
    ear = (v1 + v2) / (2.0 * h)
    return ear

def is_blinking(landmarks, blink_threshold=0.18):
    """
    Identity Verification: Active Blink Check.
    Returns True if the averaged EAR falls below the threshold (eyes closed).
    """
    if 'left_eye' not in landmarks or 'right_eye' not in landmarks:
        return False
        
    left_ear = calculate_ear(landmarks['left_eye'])
    right_ear = calculate_ear(landmarks['right_eye'])
    
    # Average EAR for both eyes
    avg_ear = (left_ear + right_ear) / 2.0
    
    # Threshold 0.18 is standard for 'Closed' eyes.
    return avg_ear < blink_threshold, round(avg_ear, 3)