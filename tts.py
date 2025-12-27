import pyaudio
import queue
from openai import OpenAI
from config import config
from logger import logger


def process_tts(tts_queue, interrupt_event):
    """
    Receive text fragments, synthesize audio and play.
    This is where the interrupt mechanism is most intuitively reflected: must stop playback immediately.
    """
    logger.info("[TTS] Process starting...")

    # Get TTS parameters from configuration
    tts_config = config.tts
    api_key = tts_config["api_key"]
    base_url = tts_config["base_url"]
    model = tts_config["model"]
    voice = tts_config["voice"]
    sample_rate = tts_config["sample_rate"]

    # Initialize pyaudio
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        output=True,
    )

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    while True:
        assistant_answer_text = tts_queue.get()
        logger.info(f"[TTS] Playing: {assistant_answer_text}")

        with client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            extra_body={"sample_rate": sample_rate},
            # User input information
            input=assistant_answer_text,
            response_format="pcm",  # Supports mp3, wav, pcm, opus formats
        ) as response:
            for chunk in response.iter_bytes(chunk_size=4096):
                if interrupt_event.is_set():
                    while not tts_queue.empty():
                        try:
                            tts_queue.get_nowait()
                        except queue.Empty:
                            break
                    break  # Stop current playback
                if chunk:
                    stream.write(chunk)
