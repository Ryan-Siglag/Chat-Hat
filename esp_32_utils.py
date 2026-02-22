import serial
import time

_state = {"ser": None}

def servo_connect(port: str, baudrate: int = 2000000, timeout: float = 1.0):
    try:
        _state["ser"] = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)
        print(f"[ESP32Servo] Connected on {port}")
    except (serial.SerialException, OSError) as e:
        print(f"[ESP32Servo] Warning: Could not open {port}: {e}. Servo disabled.")
        _state["ser"] = None

def _send_command(command: str) -> str:
    if _state["ser"] is None:
        return "DISABLED"
    full_cmd = command.strip() + "\n"
    _state["ser"].reset_input_buffer()
    _state["ser"].write(full_cmd.encode())
    deadline = time.time() + 1.0
    while time.time() < deadline:
        try:
            line = _state["ser"].readline().decode("utf-8").strip()
            if line in ("OK", "ERR"):
                return line
        except UnicodeDecodeError:
            _state["ser"].reset_input_buffer()
            continue
    return "TIMEOUT"

def servo_set_angle(angle: int) -> bool:
    if not 0 <= angle <= 180:
        raise ValueError("Angle must be between 0 and 180")
    if _state["ser"] is None:
        print(f"[ESP32Servo] Servo disabled — skipping set_angle({angle})")
        return False
    return _send_command(f"ANGLE {angle}") == "OK"

def servo_close():
    if _state["ser"] is not None and _state["ser"].is_open:
        _state["ser"].close()
        _state["ser"] = None


if __name__ == "__main__":
    servo_connect(port="COM4")
    for angle in [0, 90, 0, 90]:
        print(f"Setting angle: {angle}")
        print("Success:", servo_set_angle(angle))
        time.sleep(1)
    servo_close()