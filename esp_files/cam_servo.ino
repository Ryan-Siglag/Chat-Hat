#include "esp_camera.h"
#include "ESP32Servo.h"

// ===== XIAO ESP32S3 Sense Camera Pin Mapping =====
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39

#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15

#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13
// ================================================

#define SERVO_PIN 3

Servo myServo;

// ---- Servo command parser ----
// Reads any available incoming bytes, buffers lines,
// and acts on "ANGLE <n>\n" commands.
// Responds with "OK\n" on success or "ERR\n" on bad input.
void handleSerialCommands() {
  static String cmdBuffer = "";

  while (Serial.available()) {
    char c = (char)Serial.read();

    if (c == '\n') {
      cmdBuffer.trim();

      if (cmdBuffer.startsWith("ANGLE ")) {
        String angleStr = cmdBuffer.substring(6);
        int angle = angleStr.toInt();

        // toInt() returns 0 on failure; guard against "ANGLE abc" → 0 being mistaken as valid
        bool valid = (angle >= 0 && angle <= 180) &&
                     (angleStr == "0" || angle != 0);

        if (valid) {
          myServo.write(angle);
          Serial.print("OK\n");
        } else {
          Serial.print("ERR\n");
        }
      } else if (cmdBuffer.length() > 0) {
        Serial.print("ERR\n");
      }

      cmdBuffer = "";
    } else {
      cmdBuffer += c;
      // Prevent runaway buffer from noise
      if (cmdBuffer.length() > 32) cmdBuffer = "";
    }
  }
}

void setup() {
  Serial.begin(2000000);
  delay(2000);

  // ESP32PWM::allocateTimer(0);
  // ESP32PWM::allocateTimer(1);
  // ESP32PWM::allocateTimer(2);
  // ESP32PWM::allocateTimer(3);

  myServo.attach(SERVO_PIN);
  myServo.write(0);  // Start at center

  Serial.println("Initializing camera...");

  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk  = XCLK_GPIO_NUM;
  config.pin_pclk  = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href  = HREF_GPIO_NUM;

  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;

  config.pin_pwdn  = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size   = FRAMESIZE_QVGA;
    config.jpeg_quality = 12;
    config.fb_count     = 2;
    config.fb_location  = CAMERA_FB_IN_PSRAM;
  } else {
    config.frame_size   = FRAMESIZE_QQVGA;
    config.jpeg_quality = 20;
    config.fb_count     = 1;
    config.fb_location  = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    while (true);
  }

  Serial.println("Camera ready");
}

void loop() {
  // Check for incoming servo commands before capturing
  handleSerialCommands();

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Capture failed");
    delay(100);
    return;
  }

  Serial.write(0xFF);
  Serial.write(0xAA);

  uint32_t len = fb->len;
  Serial.write((uint8_t*)&len, 4);

  Serial.write(fb->buf, fb->len);

  Serial.write(0xFF);
  Serial.write(0xBB);

  esp_camera_fb_return(fb);

  // Check again after frame send so commands aren't starved
  handleSerialCommands();

  delay(100);
}