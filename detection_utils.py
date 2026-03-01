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
    MAX_SEARCH = 100_000  # bytes to search before giving up
    searched = 0

    # Search for 0xFF 0xAA header byte-by-byte
    while searched < MAX_SEARCH:
        b = ser.read(1)
        if not b:
            print("Timeout waiting for header")
            return None
        searched += 1

        if b == b'\xFF':
            b2 = ser.read(1)
            if b2 == b'\xAA':
                break  # Found valid header
            # If not 0xAA, keep searching (b2 might be 0xFF, so don't discard it)
            if b2 == b'\xFF':
                # peek one more
                ser.read(0)  # no-op, just continue loop logic
                searched -= 1  # reprocess this as potential header start
    else:
        print("Could not find frame header")
        return None

    # Read length
    length_bytes = read_exact(4)
    if not length_bytes or len(length_bytes) < 4:
        print("Failed to read length")
        return None

    length = struct.unpack("<I", length_bytes)[0]

    # Sanity check on length
    if length < 100 or length > 100_000:
        print(f"Suspicious frame length: {length}, skipping")
        return None

    image_data = read_exact(length)
    if not image_data:
        print("Failed to read image data")
        return None

    # Read and verify footer
    footer = ser.read(2)
    if footer != b'\xBB\xCC':  # adjust to whatever your ESP sends
        print(f"Bad footer: {footer.hex()}")
        # Don't return None here — JPEG might still decode fine

    npimg = np.frombuffer(image_data, dtype=np.uint8)
    frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    if frame is None:
        print("cv2.imdecode failed — corrupt JPEG data")
        return None

    return frame

# ---------------- YOLO SETUP ----------------
model = YOLO("yolov8m.pt")  # minweight nano model


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