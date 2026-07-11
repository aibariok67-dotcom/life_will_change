import cv2
import mediapipe as mp
import webbrowser
import time
import math
import numpy as np

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,  # We only need one hand to trigger
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)
mp_draw = mp.solutions.drawing_utils

# Cooldown configuration
COOLDOWN_TIME = 8.0  # Cooldown in seconds to prevent opening multiple tabs
last_trigger_time = 0.0

# Persona 5 Royal - Life Will Change YouTube Link (User-provided)
MUSIC_URL = "https://www.youtube.com/watch?v=dsuJZx24V_A&list=RDdsuJZx24V_A&start_radio=1"


def get_distance_2d(p1, p2):
    """Calculate the 2D Euclidean distance between two landmarks."""
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def draw_futuristic_hud(frame, gesture_detected, cooldown_remaining):
    """Draw a premium, stylish HUD overlay on the video frame."""
    h, w, _ = frame.shape
    
    # 1. Top Cinematic Bar (Semi-transparent black overlay)
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 60), (15, 15, 20), -1)
    # 2. Bottom Cinematic Bar
    cv2.rectangle(overlay, (0, h - 50), (w, h), (15, 15, 20), -1)
    
    # Apply the semi-transparent overlay (alpha blending)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    
    # 3. HUD Titles and status
    cv2.putText(frame, "PHANTOM THIEVES MUSIC TRIGGER", (20, 38), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    
    if cooldown_remaining > 0:
        status_text = f"COOLDOWN: {cooldown_remaining:.1f}s"
        status_color = (0, 165, 255)  # Orange
        # Draw small progress bar at the bottom
        bar_width = int((cooldown_remaining / COOLDOWN_TIME) * (w - 40))
        cv2.rectangle(frame, (20, h - 20), (20 + bar_width, h - 15), (0, 165, 255), -1)
    else:
        status_text = "READY TO TRIGGER"
        status_color = (0, 255, 128)  # Neon green
        # Draw ready line at the bottom
        cv2.rectangle(frame, (20, h - 20), (w - 20, h - 15), (0, 255, 128), -1)
        
    cv2.putText(frame, status_text, (w - 220, 38), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2, cv2.LINE_AA)
                
    # 4. Instructions
    cv2.putText(frame, "Show V-gesture (Peace Sign) to play 'Life Will Change'", (20, h - 28), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(frame, "Press 'Q' to Exit", (w - 150, h - 28), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA)

    # 5. Big trigger alert if gesture detected
    if gesture_detected and cooldown_remaining <= 0:
        # Drawing a pulsing box in the center
        box_color = (0, 0, 255)  # Red (Persona 5 Theme)
        cv2.rectangle(frame, (w // 2 - 250, h // 2 - 60), (w // 2 + 250, h // 2 + 60), box_color, 4)
        cv2.rectangle(frame, (w // 2 - 245, h // 2 - 55), (w // 2 + 245, h // 2 + 55), (10, 10, 15), -1)
        
        cv2.putText(frame, "LIFE WILL CHANGE", (w // 2 - 180, h // 2 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(frame, "TAKING YOUR HEART...", (w // 2 - 150, h // 2 + 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)

def detect_v_gesture(landmarks):
    """
    Detects if the hand landmarks form a 'V' gesture (Peace sign).
    Returns (is_v_gesture, index_middle_ratio)
    """
    # Reference scale: distance between wrist (0) and middle finger MCP joint (9)
    palm_scale = get_distance_2d(landmarks[0], landmarks[9])
    if palm_scale == 0:
        return False, 0.0

    # 1. Index finger state (Tip: 8, PIP joint: 6)
    index_open = landmarks[8].y < landmarks[6].y

    # 2. Middle finger state (Tip: 12, PIP joint: 10)
    middle_open = landmarks[12].y < landmarks[10].y

    # 3. Ring finger state (Tip: 16, PIP joint: 14)
    ring_closed = landmarks[16].y > landmarks[14].y

    # 4. Pinky finger state (Tip: 20, PIP joint: 18)
    pinky_closed = landmarks[20].y > landmarks[18].y

    # 5. Index-to-Middle finger separation (V shape width)
    # Distance between Index tip (8) and Middle tip (12)
    index_middle_dist = get_distance_2d(landmarks[8], landmarks[12])
    ratio = index_middle_dist / palm_scale

    # V gesture conditions:
    # - Index and Middle fingers must be open/extended.
    # - Ring and Pinky fingers must be closed/folded.
    # - The distance ratio between index and middle tips should be significant (> 0.30).
    is_v = index_open and middle_open and ring_closed and pinky_closed and (ratio > 0.30)
    
    return is_v, ratio

def configure_camera(cap):
    """Apply standard 640x480 MJPG settings to avoid V4L2 bandwidth timeouts."""
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    except Exception as e:
        pass

def get_camera_indices():
    """Detect and return list of working camera indices, skipping loopback devices."""
    import os
    indices = []
    try:
        # Scan /sys/class/video4linux on Linux to find devices
        if os.path.exists('/sys/class/video4linux'):
            devices = os.listdir('/sys/class/video4linux')
            # Sort them so video0 comes before video1, etc.
            for dev in sorted(devices, key=lambda x: int(x[5:]) if x[5:].isdigit() else 0):
                if dev.startswith('video'):
                    idx = int(dev[5:])
                    # Read name of the device
                    with open(f'/sys/class/video4linux/{dev}/name', 'r') as f:
                        name = f.read().strip().lower()
                    # Skip loopback devices (e.g. OBS Virtual Camera)
                    if 'loopback' in name:
                        print(f"[INFO] Skipping loopback device: {dev} ({name})")
                        continue
                    indices.append(idx)
    except Exception:
        pass

    # Fallback if detection failed or returned empty list
    if not indices:
        indices = [0, 1, 2]
    return indices

def main():
    global last_trigger_time
    import sys

    # Determine camera index (auto-detect or user-specified)
    cap = None
    if len(sys.argv) > 1:
        try:
            user_idx = int(sys.argv[1])
            print(f"[INFO] Opening user-specified camera index: {user_idx}...")
            cap = cv2.VideoCapture(user_idx)
            if cap.isOpened():
                configure_camera(cap)
            else:
                print(f"[ERROR] Could not open camera with index {user_idx}.")
                return
        except ValueError:
            print(f"[WARNING] Invalid index '{sys.argv[1]}'. Proceeding with auto-detection.")

    if cap is None:
        camera_list = get_camera_indices()
        # Auto-detect camera index by trying common indices
        for idx in camera_list:
            print(f"[INFO] Checking camera index {idx}...")
            test_cap = cv2.VideoCapture(idx)
            if test_cap.isOpened():
                configure_camera(test_cap)
                print(f"[INFO] Camera {idx} opened and configured. Testing frame grab...")
                ret, test_frame = test_cap.read()
                if ret and test_frame is not None:
                    print(f"[SUCCESS] Found working camera: index {idx}")
                    cap = test_cap
                    break
                else:
                    print(f"[WARNING] Camera {idx} timed out or failed to grab frame.")
                    test_cap.release()


        
    if cap is None or not cap.isOpened():
        print("\n[ERROR] No working webcams found!")
        print("Suggestions:")
        print("  1. Make sure your webcam is plugged in and not in use by another app (e.g. Zoom, browser).")
        print("  2. If you know your camera index, specify it explicitly, e.g.:")
        print("     ./venv/bin/python main.py 2")
        return

    print("\n" + "="*50)
    print("  PERSONA 5 ROYAL MUSIC TRIGGER INITIALIZED")
    print("  Show a 'V' gesture (Peace sign) to the camera.")
    print("  Press 'Q' in the window to exit.")
    print("="*50 + "\n")

    # Custom styling specs for MediaPipe drawing
    # Persona 5 colors: Red (0, 0, 255) and Black/Grey, with white details
    landmark_spec = mp_draw.DrawingSpec(color=(255, 255, 255), thickness=2, circle_radius=3)
    connection_spec = mp_draw.DrawingSpec(color=(0, 0, 255), thickness=2)

    consecutive_failures = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            consecutive_failures += 1
            if consecutive_failures > 15:  # Allow up to 15 failed frames (~0.5s) before exiting
                print("\n[ERROR] Connection to webcam lost. Exiting.")
                break
            time.sleep(0.03)
            continue
        consecutive_failures = 0


        # Flip frame horizontally for natural mirror view
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Convert the BGR image to RGB for MediaPipe processing
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        current_time = time.time()
        cooldown_remaining = max(0.0, COOLDOWN_TIME - (current_time - last_trigger_time))

        gesture_detected = False

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Classify the gesture
                is_v, ratio = detect_v_gesture(hand_landmarks.landmark)
                
                # Dynamic drawing color based on trigger state
                if is_v and cooldown_remaining <= 0:
                    gesture_detected = True
                    # Set skeleton drawing to bright green/cyan to indicate recognition
                    active_conn_spec = mp_draw.DrawingSpec(color=(0, 255, 128), thickness=3)
                    active_land_spec = mp_draw.DrawingSpec(color=(255, 255, 255), thickness=3, circle_radius=4)
                else:
                    active_conn_spec = connection_spec
                    active_land_spec = landmark_spec

                # Draw the hand skeleton
                mp_draw.draw_landmarks(
                    frame, 
                    hand_landmarks, 
                    mp_hands.HAND_CONNECTIONS,
                    active_land_spec,
                    active_conn_spec
                )

                # Show V-gesture stats (ratio) on screen near the wrist
                wrist = hand_landmarks.landmark[0]
                wrist_x, wrist_y = int(wrist.x * w), int(wrist.y * h)
                cv2.putText(
                    frame, 
                    f"V-Ratio: {ratio:.2f}", 
                    (wrist_x - 40, wrist_y + 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.5, 
                    (255, 255, 255), 
                    1, 
                    cv2.LINE_AA
                )

        # Trigger music play if gesture is active and not on cooldown
        if gesture_detected and cooldown_remaining <= 0:
            print("\n[!] TARGET ACQUIRED: V-gesture detected!")
            print(f"[!] Stealing your heart... Opening Life Will Change: {MUSIC_URL}")
            webbrowser.open_new(MUSIC_URL)
            last_trigger_time = current_time
            # Update cooldown to reflect the trigger immediately
            cooldown_remaining = COOLDOWN_TIME

        # Draw HUD overlays on frame
        draw_futuristic_hud(frame, gesture_detected, cooldown_remaining)

        # Display the output
        cv2.imshow("Persona 5 V-Gesture Music Player", frame)

        # Break loop with 'q' or ESC
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    print("\nScript terminated. Have a good day, Phantom Thief!")

if __name__ == "__main__":
    main()
