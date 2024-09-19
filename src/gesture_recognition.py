import cv2
import mediapipe as mp
import numpy as np
import time
import serial

try:
    ser = serial.Serial('COM10', 9600)
    time.sleep(2)  # Wait for the connection to establish
except serial.SerialException:
    print("Failed to connect to serial port. Please check your port settings and try again.")
    exit()

# Initialize MediaPipe hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.9, min_tracking_confidence=0.9)

def calculate_distances(hand_landmarks, image_width, image_height, alpha=0.1, deadzone=0.03):
    # Update to include Thumb Tip and Pinky MCP for the new distance calculation
    tip_ids = [mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
               mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP, mp_hands.HandLandmark.THUMB_TIP]
    wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
    wrist_coords = np.array([wrist.x * image_width, wrist.y * image_height])
    
    pinky_mcp = hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_MCP]
    pinky_mcp_coords = np.array([pinky_mcp.x * image_width, pinky_mcp.y * image_height])

    middle_finger_base = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
    middle_finger_base_coords = np.array([middle_finger_base.x * image_width, middle_finger_base.y * image_height])
    reference_distance = np.linalg.norm(wrist_coords - middle_finger_base_coords)

    normalized_distances = np.zeros(len(tip_ids))
    for i, tip_id in enumerate(tip_ids[:-1]):  # Exclude the thumb tip in this loop
        fingertip = hand_landmarks.landmark[tip_id]
        fingertip_coords = np.array([fingertip.x * image_width, fingertip.y * image_height])
        distance = np.linalg.norm(fingertip_coords - wrist_coords)
        normalized_distances[i] = distance / reference_distance

    # Distance for the thumb tip from the pinky MCP
    thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]
    thumb_tip_coords = np.array([thumb_tip.x * image_width, thumb_tip.y * image_height])
    thumb_distance = np.linalg.norm(thumb_tip_coords - pinky_mcp_coords)
    normalized_distances[-1] = thumb_distance / reference_distance  # Add thumb distance to the output

    # Apply Exponential Moving Average (EMA) with deadzone consideration
    global ema_distances
    if 'ema_distances' not in globals():
        ema_distances = np.copy(normalized_distances)
    else:
        for i in range(len(normalized_distances)):
            if abs(normalized_distances[i] - ema_distances[i]) > deadzone:
                ema_distances[i] = alpha * normalized_distances[i] + (1 - alpha) * ema_distances[i]
    return ema_distances

def calibrate(cap, calibration_time=10):
    print("Calibrating for {} seconds...".format(calibration_time))
    min_distances = np.full(5, np.inf)  # Update for 5 fingers including the thumb
    max_distances = np.zeros(5)  # Update for 5 fingers including the thumb
    start_time = time.time()
    while time.time() - start_time < calibration_time:
        success, image = cap.read()
        if not success:
            continue
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = hands.process(image_rgb)
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                distances = calculate_distances(hand_landmarks, image.shape[1], image.shape[0])
                min_distances = np.fmin(min_distances, distances)
                max_distances = np.fmax(max_distances, distances)
        cv2.putText(image, "Calibrating...", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.imshow('Finger to Palm Distance', image)
        if cv2.waitKey(5) & 0xFF == ord("q"):
            break
    print("Calibration completed.")
    return min_distances, max_distances

def map_to_range(value, min_val, max_val, index):
    """ Map a value from one range to another, with specific output range based on the index. """
    if index == 2 or index == 3:  # Check if it's the third value
        mapped_value = int(np.clip(((max_val - value) / (max_val - min_val)) * 180, 0, 180))
    else:
        mapped_value = int(np.clip(((value - min_val) / (max_val - min_val)) * 180, 0, 180))
    
    return 15 * round(mapped_value / 15)  # Round to nearest multiple of 5


# Start video capture
cap = cv2.VideoCapture(0)

# Calibrate
min_distances, max_distances = calibrate(cap)

# For tracking changes in values to send
previous_values = None
print("Starting main loop...")
while cap.isOpened():
    success, image = cap.read()
    if not success:
        continue

    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(image_rgb)
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            distances = calculate_distances(hand_landmarks, image.shape[1], image.shape[0])
            mapped_values = [map_to_range(distances[i], min_distances[i], max_distances[i], i) for i in range(len(distances))]
            print(mapped_values)
            data_string = ','.join(map(str, mapped_values)) + '\n'
            try:
                ser.write(data_string.encode('utf-8'))
            except serial.SerialException:
                print("Serial communication failed. Please check the connection and try again.")
                ser.close()
                cap.release()
                cv2.destroyAllWindows()
                exit()
            time.sleep(0.1)
    cv2.imshow('Finger to Palm Distance', image)
    if cv2.waitKey(5) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
ser.close()