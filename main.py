import multiprocessing
import time

from src.tts import process_tts
from src.stt import process_stt
from src.voice_listener import process_kws_vad
from src.llm_mcp_host import process_llm_host
from src.config import global_config
from src.logger import logger

if __name__ == "__main__":
    # 1. Set up communication pipes
    # Context: Spawn is the safest startup method (compatible with Windows/Mac/Linux)
    multiprocessing.set_start_method("spawn", force=True)

    # Get queue size from configuration (if configured)
    queue_size = global_config.process.get("queue_size", 0)  # 0 means unlimited size

    # Create queues, use configured size if specified
    if queue_size > 0:
        audio_queue = multiprocessing.Queue(maxsize=queue_size)  # KWS -> STT
        text_queue = multiprocessing.Queue(maxsize=queue_size)  # STT -> LLM
        tts_queue = multiprocessing.Queue(maxsize=queue_size)  # LLM -> TTS
    else:
        audio_queue = multiprocessing.Queue()  # KWS -> STT
        text_queue = multiprocessing.Queue()  # STT -> LLM
        tts_queue = multiprocessing.Queue()  # LLM -> TTS

    # Global control signals
    interrupt_event = multiprocessing.Event()
    mic_running_event = multiprocessing.Event()
    mic_running_event.set()

    # 2. Initialize processes
    p_kws = multiprocessing.Process(
        target=process_kws_vad,
        args=(audio_queue, interrupt_event, mic_running_event),
        name="KWS_Process",
    )

    p_stt = multiprocessing.Process(
        target=process_stt,
        args=(audio_queue, text_queue, interrupt_event),
        name="STT_Process",
    )

    p_llm = multiprocessing.Process(
        target=process_llm_host,
        args=(text_queue, tts_queue, interrupt_event),
        name="LLM_Process",
    )

    p_tts = multiprocessing.Process(
        target=process_tts, args=(tts_queue, interrupt_event), name="TTS_Process"
    )

    # 3. Start all processes
    processes = [p_kws, p_stt, p_llm, p_tts]
    for p in processes:
        p.start()

    logger.info("=== Voice assistant framework running (configuration version). Press Ctrl+C to exit ===")
    logger.info(f"Configured queue size: {queue_size if queue_size > 0 else 'unlimited'}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping system...")
        mic_running_event.clear()
        for p in processes:
            p.terminate()
            p.join()
        logger.info("System exited.")
