import requests
from config import global_config
from logger import logger


def process_stt(audio_queue, text_queue, interrupt_event):
    """
    Get audio from audio_queue, convert to text and put into text_queue.
    """
    logger.info("[STT] Process starting...")

    # Get STT parameters from configuration
    stt_config = global_config.stt
    url = stt_config["url"]
    model = stt_config["model"]
    api_key = stt_config["api_key"]

    headers = {"Authorization": f"Bearer {api_key}"}

    while True:
        # Get audio, timeout to periodically check interrupt
        command_mp3_data = audio_queue.get()

        files = {"file": ("example.mp3", command_mp3_data)}
        payload = {"model": model}

        response = requests.post(url, data=payload, files=files, headers=headers)

        command_txt = response.json().get("text")
        logger.info(f"[STT] Transcription result: {response.json()}")
        if command_txt:
            text_queue.put(command_txt)
