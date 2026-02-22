import serial
import struct
import cv2
import numpy as np
import time
from ultralytics import YOLO

# ---------------- SERIAL SETUP ----------------
ser = serial.Serial("COM4", 2000000, timeout=1)
ser.setDTR(False)
ser.setRTS(False)
time.sleep(2)

def read_exact(n):
    data = b''
    while len(data) < n:
        chunk = ser.read(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


# ---------------- FRAME GRAB ----------------
def grab_frame():
    # Drain old data
    while ser.in_waiting:
        ser.read(ser.in_waiting)

    # Now wait for fresh frame
    while True:
        b1 = ser.read(1)
        if not b1:
            return None
        if b1 == b'\xFF' and ser.read(1) == b'\xAA':
            break

    length_bytes = read_exact(4)
    if not length_bytes:
        return None

    length = struct.unpack("<I", length_bytes)[0]

    image_data = read_exact(length)
    if not image_data:
        return None

    ser.read(2)

    npimg = np.frombuffer(image_data, dtype=np.uint8)
    frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    return frame

# ---------------- YOLO SETUP ----------------
model = YOLO("yolov8n.pt")  # lightweight nano model


# ---------------- DETECTION FUNCTION ----------------

CONF_THRESHOLD = 0.4  # adjust as needed

def detect(frame, display=True):
    results = model(frame, verbose=False)
    boxes = results[0].boxes

    labels = []  # default empty

    if boxes is None or len(boxes) == 0:
        print("No objects detected")
        # if display:
        #     cv2.imshow("Annotated Frame", frame)
        #     cv2.waitKey(1)
        return frame, labels

    detections = []

    for box in boxes:
        conf = float(box.conf[0])
        if conf < CONF_THRESHOLD:
            continue  # skip low-confidence

        cls = int(box.cls[0])
        label = model.names[cls]
        detections.append((conf, label, box))

    if len(detections) == 0:
        print(f"No objects above {CONF_THRESHOLD}")
        # if display:
        #     cv2.imshow("Annotated Frame", frame)
        #     cv2.waitKey(1)
        return frame, labels

    # Sort by confidence
    detections.sort(reverse=True, key=lambda x: x[0])
    top3 = detections[:3]

    print(f"\nTop Objects (conf ≥ {CONF_THRESHOLD}):")
    for conf, label, _ in top3:
        print(f"{label} ({conf:.2f})")

    # Draw bounding boxes
    for conf, label, box in top3:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame,
                    f"{label} {conf:.2f}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2)

    labels = [label for _, label, _ in top3]

    # if display:
    #     cv2.imshow("Annotated Frame", frame)
    #     cv2.waitKey(1)

    return frame, labels

# ---------------- MAIN LOOP ----------------
def main():
    print("Press ENTER to run detection. Type 'q' + ENTER to quit.")

    cv2.namedWindow("Annotated Frame", cv2.WINDOW_NORMAL)  # create window once

    while True:
        input("Press Enter to detect (or type 'q' to quit)...")
        frame = grab_frame()
        if frame is None:
            print("Failed to grab frame")
            continue

        annotated, labels = detect(frame)
        print("Detected:", labels)

        cv2.imshow("Annotated Frame", annotated)
        key = cv2.waitKey(1)  # short delay to refresh the window

        # Optional: quit by pressing 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()