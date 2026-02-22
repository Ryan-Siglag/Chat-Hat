import serial
import time

class ESP32Servo:
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Allow ESP32 to reset

    def _send_command(self, command: str) -> str:
        full_cmd = command.strip() + "\n"
        self.ser.write(full_cmd.encode())

        response = self.ser.readline().decode().strip()
        return response

    def set_angle(self, angle: int) -> bool:
        if not 0 <= angle <= 180:
            raise ValueError("Angle must be between 0 and 180")

        response = self._send_command(f"ANGLE {angle}")
        return response == "OK"

    def close(self):
        if self.ser.is_open:
            self.ser.close()


# Example usage
if __name__ == "__main__":
    servo = ESP32Servo(port="COM4")  # Change to your port

    for angle in [0, 45, 90, 135, 180]:
        print(f"Setting angle: {angle}")
        success = servo.set_angle(angle)
        print("Response:", success)
        time.sleep(1)

    servo.close()