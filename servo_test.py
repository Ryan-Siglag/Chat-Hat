from esp_32_utils import servo_connect, servo_set_angle, servo_close
import time

# Connect once at the start
servo_connect(port="COM4")

# Use anywhere in your code
servo_set_angle(0)
time.sleep(1)
servo_set_angle(90)
time.sleep(1)

# Close when done
servo_close()