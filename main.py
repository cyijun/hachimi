import multiprocessing
import time

from tts import process_tts
from stt import process_stt
from voice_listener import process_kws_vad
from llm_mcp_host import process_llm_host
from config import config

if __name__ == "__main__":
    # 1. 设置通信管道
    # 上下文：Spawn 是最安全的启动方式 (兼容 Windows/Mac/Linux)
    multiprocessing.set_start_method("spawn", force=True)

    # 从配置获取队列大小（如果配置中有）
    queue_size = config.process.get("queue_size", 0)  # 0表示无限大小

    # 创建队列，如果配置了大小则使用配置的大小
    if queue_size > 0:
        audio_queue = multiprocessing.Queue(maxsize=queue_size)  # KWS -> STT
        text_queue = multiprocessing.Queue(maxsize=queue_size)  # STT -> LLM
        tts_queue = multiprocessing.Queue(maxsize=queue_size)  # LLM -> TTS
    else:
        audio_queue = multiprocessing.Queue()  # KWS -> STT
        text_queue = multiprocessing.Queue()  # STT -> LLM
        tts_queue = multiprocessing.Queue()  # LLM -> TTS

    # 全局控制信号
    interrupt_event = multiprocessing.Event()
    mic_running_event = multiprocessing.Event()
    mic_running_event.set()

    # 2. 初始化进程
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

    # 3. 启动所有进程
    processes = [p_kws, p_stt, p_llm, p_tts]
    for p in processes:
        p.start()

    print("=== 语音助手框架已运行（使用配置版本）。按 Ctrl+C 退出 ===")
    print(f"配置队列大小: {queue_size if queue_size > 0 else '无限'}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止系统...")
        mic_running_event.clear()
        for p in processes:
            p.terminate()
            p.join()
        print("系统已退出。")
