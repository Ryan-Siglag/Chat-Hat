import sounddevice as sd
import numpy as np
import whisper
import queue
import threading
import time
import pyttsx3
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

PROMPT = "Ignore any odd words, especially chat and or hat. Answer quickly with a reponse no more than 20 words. "

# --- Settings ---
DEVICE_NAME = "USB"
SAMPLERATE = 16000
CHANNELS = 1

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

# --- Load Whisper model ---
print("Loading Whisper model...")
model = whisper.load_model("tiny.en")

# --- Find the right input device ---
device_info = None
for i, dev in enumerate(sd.query_devices()):
    if DEVICE_NAME.lower() in dev['name'].lower() and dev['max_input_channels'] > 0:
        device_info = dev
        device_index = i
        print(f"Using input device: {dev['name']}")
        break
if device_info is None:
    raise RuntimeError(f"Could not find audio input device containing '{DEVICE_NAME}'")

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
            if any(trigger in text.lower() for trigger in chat_triggers):
                print("GPT")
                # Run GPT in its own thread so transcription keeps moving
                threading.Thread(target=query_gpt, args=(text,), daemon=True).start()

def query_gpt(text):
    response = client.responses.create(
        # model="gpt-5-nano-2025-08-07",
        model="gpt-3.5-turbo",
        input=PROMPT + text
    )
    print(response.output_text)
    tts_q.put(response.output_text)

def tts_worker():
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id)
    engine.setProperty('rate', 200)

    def process_queue(name, completed):
        if not tts_q.empty():
            text = tts_q.get()
            engine.say(text)
        else:
            time.sleep(0.1)

    engine.connect('started-utterance', lambda name: print("Speaking..."))
    engine.connect('finished-utterance', lambda name, completed: print("Done"))

    engine.startLoop(False)  # False = we drive the loop manually
    while True:
        if not tts_q.empty():
            text = tts_q.get()
            engine.say(text)
        engine.iterate()
        time.sleep(0.05)

# --- Start threads ---
process_thread = threading.Thread(target=process_audio, daemon=True)
process_thread.start()

transcribe_thread = threading.Thread(target=transcribe_audio, daemon=True)
transcribe_thread.start()

tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()

# --- Start audio stream ---
stream = sd.InputStream(
    samplerate=SAMPLERATE,
    device=device_index,
    channels=CHANNELS,
    callback=audio_callback
)

with stream:
    print("Recording... Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")