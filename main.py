# --- Settings ---
HAT_ATTATCHED = False
G_CAL = True

DEVICE_NAME = "USB"
SAMPLERATE = 16000
CHANNELS = 1

import sounddevice as sd
import numpy as np
import whisper
import queue
import threading
import time
import pyttsx3
import cv2
import os
import serial
import time
from openai import OpenAI
from dotenv import load_dotenv

if HAT_ATTATCHED:
    from detection_utils import grab_frame, detect
    from esp_32_utils import servo_connect, servo_set_angle, servo_close

    servo_connect(port="COM4")
    servo_set_angle(20)

if G_CAL:
    from g_cal import get_upcoming_events

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)    

PROMPT = "You are Chat Hat, an AI assistant in a hat. Answer the user quickly with a reponse no more than 20 words."
PROMPT_END = "User input: "

# --- VAD Settings ---
SILENCE_THRESHOLD = 0.01
SILENCE_DURATION = 1.2
MIN_SPEECH_DURATION = 0.5
FRAME_DURATION = 0.05

# --- Queues ---
audio_q = queue.Queue()
transcription_q = queue.Queue()
tts_q = queue.Queue()

# --- Triggers ---
chat_triggers = ['chat', 'chet', ' hat ', ' hat.', ' hat,', ' het', ' het.', '-hat']
glasses_triggers = ['glasses', 'classes']

# --- Glasses Settings ---
GLASSES_UP = 0
GLASSES_DOWN = 90

glasses = False

# --- Load Whisper model ---
print("Loading Whisper model...")
model = whisper.load_model("tiny.en")

# --- Find the right input device ---
device_info = None
device_index = None
for i, dev in enumerate(sd.query_devices()):
    if DEVICE_NAME.lower() in dev['name'].lower() and dev['max_input_channels'] > 0:
        device_info = dev
        device_index = i
        print(f"Using input device: {dev['name']}")
        break
# if device_info is None:
#     raise RuntimeError(f"Could not find audio input device containing '{DEVICE_NAME}'")

def is_speech(frame: np.ndarray, threshold: float) -> bool:
    rms = np.sqrt(np.mean(frame ** 2))
    return rms > threshold

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    audio_q.put(indata.copy())

def process_audio():
    speech_buffer = []
    silence_frames = 0
    speaking = False

    silence_frame_limit = int(SILENCE_DURATION / FRAME_DURATION)
    min_speech_frames = int(MIN_SPEECH_DURATION / FRAME_DURATION)
    frame_size = int(SAMPLERATE * FRAME_DURATION)
    leftover = np.zeros((0, CHANNELS), dtype=np.float32)

    while True:
        while not audio_q.empty():
            leftover = np.vstack([leftover, audio_q.get()])

        while len(leftover) >= frame_size:
            frame = leftover[:frame_size]
            leftover = leftover[frame_size:]
            frame_mono = frame.mean(axis=1)

            if is_speech(frame_mono, SILENCE_THRESHOLD):
                if not speaking:
                    speaking = True
                    print("[Listening...]")
                speech_buffer.append(frame_mono)
                silence_frames = 0
            else:
                if speaking:
                    silence_frames += 1
                    speech_buffer.append(frame_mono)

                    if silence_frames >= silence_frame_limit:
                        if len(speech_buffer) >= min_speech_frames:
                            audio_segment = np.concatenate(speech_buffer)
                            transcription_q.put(audio_segment)

                        speech_buffer = []
                        silence_frames = 0
                        speaking = False

        time.sleep(0.01)

def transcribe_audio():
    while True:
        audio_segment = transcription_q.get()
        result = model.transcribe(audio_segment, fp16=False, language="en")
        text = result['text'].strip()
        if text:
            print(f"[{time.strftime('%H:%M:%S')}] {text}")

            print(any(trigger in text.lower() for trigger in chat_triggers))
            if any(trigger in text.lower() for trigger in chat_triggers):
                if any(trigger in text.lower() for trigger in glasses_triggers):
                    threading.Thread(target=toggle_glasses, daemon=True).start()
                else:
                    print("Querying GPT")
                    threading.Thread(target=query_gpt, args=(text,), daemon=True).start()

def toggle_glasses():
    if HAT_ATTATCHED:
        global glasses

        # Connect once at the start

        # Use anywhere in your code
        servo_set_angle(0)
        time.sleep(1)
        servo_set_angle(90)
        time.sleep(1)

        # Close when done
        servo_close()

        if glasses:
            success = servo_set_angle(GLASSES_DOWN)
        else:
            success = servo_set_angle(GLASSES_UP)
        glasses = not glasses

def query_gpt(text):

    detected_objs = []
    if HAT_ATTATCHED:
        detected_objs = run_detection()

    print("Sight: " + str(detected_objs))

    sight = "If you are asked if you can see, you cannot. "
    if len(detected_objs) > 0:
        sight = "If you are asked what you see, you see "
        for obj in detected_objs:
            sight += "a " + obj + " "
        sight += ". "

    upcoming_events = []
    if G_CAL:
        upcoming_events = get_upcoming_events(3)

    calender = "If you are asked about upcoming events, you do not have access"
    if len(upcoming_events) > 0:
        calender = "If you are asked about upcoming events, the user has "
        for event in upcoming_events:
            calender += event + ", "

    final_prompt = PROMPT + sight + calender + PROMPT_END + text
    print("Prompt: " + final_prompt)
    response = client.responses.create(
        model="gpt-3.5-turbo",
        input=final_prompt
    )
    print(response.output_text)
    tts_q.put(response.output_text)

def tts_worker():
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id)
    engine.setProperty('rate', 200)

    engine.connect('started-utterance', lambda name: print("Speaking..."))
    engine.connect('finished-utterance', lambda name, completed: print("Done"))

    engine.startLoop(False)
    while True:
        if not tts_q.empty():
            text = tts_q.get()
            engine.say(text)
        engine.iterate()
        time.sleep(0.05)

def run_detection():
    print("Grabbing frame...")
    frame = grab_frame()

    if frame is None:
        print("Failed to grab frame")
        return []

    annotated, labels = detect(frame)
    print("Detected:", labels)

    return labels

# --- Start threads ---
process_thread = threading.Thread(target=process_audio, daemon=True)
process_thread.start()

transcribe_thread = threading.Thread(target=transcribe_audio, daemon=True)
transcribe_thread.start()

tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()

# --- Start audio stream ---

if HAT_ATTATCHED:
    stream = sd.InputStream(
        samplerate=SAMPLERATE,
        channels=CHANNELS,
        callback=audio_callback
    )
else:
        stream = sd.InputStream(
        samplerate=SAMPLERATE,
        channels=CHANNELS,
        callback=audio_callback,
        device=device_index,
    )

with stream:
    print("Recording... Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        if HAT_ATTATCHED:
            servo_close()  # Guaranteed even on crash