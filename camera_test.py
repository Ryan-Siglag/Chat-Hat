import serial
import struct
import cv2
import numpy as np
import time

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

print("Listening...")

while True:
    # search for start marker
    byte = ser.read(1)
    if not byte:
        continue

    if byte == b'\xFF':
        if ser.read(1) == b'\xAA':

            length_bytes = read_exact(4)
            if not length_bytes:
                continue

            length = struct.unpack("<I", length_bytes)[0]

            image = read_exact(length)
            if not image:
                continue

            ser.read(2)  # discard end marker

            npimg = np.frombuffer(image, dtype=np.uint8)
            frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

            if frame is not None:
                cv2.imshow("ESP32 Cam", frame)

            if cv2.waitKey(1) == 27:
                break

cv2.destroyAllWindows()