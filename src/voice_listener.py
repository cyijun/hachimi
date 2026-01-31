import io
import multiprocessing
import queue
import time

import numpy as np
import pyaudio
import webrtcvad
from openwakeword.model import Model
from pydub import AudioSegment

from config import global_config
from logger import logger


class VoiceAssistantListener:
    def __init__(
        self,
        model_path=None,
        mic_running_event=multiprocessing.Event(),
        inturrupt_event=multiprocessing.Event(),
        audio_queue=multiprocessing.Queue(),
    ):
        # Get parameters from configuration
        listener_config = global_config.voice_listener

        # If model_path is not provided, use the path from configuration
        if model_path is None:
            model_path = listener_config["wake_word_model_path"]

        # Audio parameters
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = listener_config["channels"]
        self.RATE = listener_config["rate"]
        self.CHUNK = listener_config["chunk"]
        self.VAD_FRAME_MS = listener_config["vad_frame_ms"]
        self.VAD_FRAME_SAMPLES = int(self.RATE * self.VAD_FRAME_MS / 1000)

        # Logic thresholds
        self.WAKE_WORD_THRESHOLD = listener_config["wake_word_threshold"]
        self.SILENCE_LIMIT_SECONDS = listener_config["silence_limit_seconds"]
        self.MIN_RECORD_SECONDS = listener_config["min_record_seconds"]

        self.oww_model = Model(
            wakeword_models=[model_path], inference_framework="tflite"
        )

        # 2. Initialize VAD
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(3)  # 0-3, 3 most aggressive (strong noise filtering but may cut speech), 1 more conservative

        # 3. Initialize PyAudio
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )
        self.mic_running_event = mic_running_event
        self.interrupt_event = inturrupt_event
        self.audio_queue = audio_queue

        logger.info("--- System ready ---")
        logger.info(f"Wake word model: {model_path}")
        logger.info(f"Sample rate: {self.RATE}Hz")

    def record_command(self):
        """
        Call this function after wake-up to record voice commands
        """
        logger.info(">>> Listening for command (VAD detecting)...")
        frames = []
        silence_chunks = 0
        # Calculate how many consecutive silent VAD chunks equal the set silence time limit
        max_silence_chunks = int(self.SILENCE_LIMIT_SECONDS * 1000 / self.VAD_FRAME_MS)

        recording = True

        while recording:
            # Read small chunk suitable for VAD
            data = self.stream.read(self.VAD_FRAME_SAMPLES, exception_on_overflow=False)
            frames.append(data)

            # VAD detection
            is_speech = self.vad.is_speech(data, self.RATE)

            if is_speech:
                silence_chunks = 0  # Reset silence count
            else:
                silence_chunks += 1

            # Check if recording should end
            # Condition 1: Silence time exceeds threshold AND total recording duration exceeds minimum limit
            current_duration = (len(frames) * self.VAD_FRAME_MS) / 1000
            if (
                silence_chunks > max_silence_chunks
                and current_duration > self.MIN_RECORD_SECONDS
            ):
                logger.info(">>> Speech end detected")
                recording = False

        return b"".join(frames)

    def pcm_to_mp3(self, audio_data):
        """Convert raw PCM data to MP3"""
        audio_segment = AudioSegment(
            data=audio_data,
            sample_width=self.pa.get_sample_size(self.FORMAT),
            frame_rate=self.RATE,
            channels=self.CHANNELS,
        )
        mp3_buffer = io.BytesIO()
        audio_segment.export(mp3_buffer, format="mp3")
        return mp3_buffer.getvalue()

    def start(self):
        logger.info("Waiting for wake-up... Please say 'Hey Jarvis'")

        try:
            while self.mic_running_event.is_set():
                # 1. Get audio chunk (for wake-up detection)
                audio_data = self.stream.read(self.CHUNK, exception_on_overflow=False)

                # Convert format for openwakeword use (numpy int16)
                audio_np = np.frombuffer(audio_data, dtype=np.int16)

                # 2. Feed into wake-up model
                prediction = self.oww_model.predict(audio_np)

                # 3. Check if wake-up detected
                # openwakeword returns dictionary, key is model name
                for model_name, score in prediction.items():
                    if score > self.WAKE_WORD_THRESHOLD:
                        logger.info(">>> [KWS] Wake word detected! Triggering interrupt mechanism! <<<")
                        logger.info(f"!!! Wake-up successful (score: {score:.4f}) !!!")
                        # --- Core interrupt logic ---
                        self.interrupt_event.set()  # Send interrupt signal

                        # Clear previous audio queue to prevent STT from processing old speech
                        while not self.audio_queue.empty():
                            try:
                                self.audio_queue.get_nowait()
                            except queue.Empty:
                                break

                        # Give other processes some time to respond to interrupt
                        time.sleep(0.1)
                        logger.info("[KWS] Interrupt completed, starting to listen for new command...")

                        # 4. Start recording command (B -> C)
                        command_audio = self.record_command()

                        mp3_data = self.pcm_to_mp3(command_audio)

                        # 5. Save file (for testing/subsequent transmission to STT)
                        self.audio_queue.put(mp3_data)

                        # Clear openwakeword's internal buffer to prevent continuous triggering
                        self.oww_model.reset()
                        self.interrupt_event.clear()  # Reset signal, ready to receive new command

        except KeyboardInterrupt:
            logger.info("Stopping listening")
        finally:
            self.stream.stop_stream()
            self.stream.close()
            self.pa.terminate()


def process_kws_vad(audio_queue, interrupt_event, mic_running_event):
    """
    Responsible for monitoring microphone, detecting wake words, and trimming valid speech for STT.
    It is the 'commander' of the entire system, with the authority to trigger interrupts.
    """
    logger.info("[KWS] Process starting...")
    listener = VoiceAssistantListener(
        None, mic_running_event, interrupt_event, audio_queue
    )
    listener.start()
