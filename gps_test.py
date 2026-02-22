import serial
import pynmea2

ser = serial.Serial('COM4', 115200, timeout=1)  # COM port of ESP32
print("Listening for GPS data...")

while True:
    line = ser.readline().decode('ascii', errors='replace').strip()
    if line.startswith("$GPGGA") or line.startswith("$GPRMC"):
        try:
            msg = pynmea2.parse(line)
            if hasattr(msg, 'latitude') and hasattr(msg, 'longitude'):
                print(f"Latitude: {msg.latitude}, Longitude: {msg.longitude}")
        except pynmea2.ParseError:
            continue