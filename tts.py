import pyaudio
import queue
from openai import OpenAI
from config import config


def process_tts(tts_queue, interrupt_event):
    """
    接收文本片段，合成音频并播放。
    这是打断机制最直观体现的地方：必须立即停止播放。
    """
    print("[TTS] 进程启动...")

    # 从配置获取TTS参数
    tts_config = config.tts
    api_key = tts_config["api_key"]
    base_url = tts_config["base_url"]
    model = tts_config["model"]
    voice = tts_config["voice"]
    sample_rate = tts_config["sample_rate"]

    # 初始化pyaudio
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
        print(f"[TTS] 正在播放: {assistant_answer_text}")

        with client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            extra_body={"sample_rate": sample_rate},
            # 用户输入信息
            input=assistant_answer_text,
            response_format="pcm",  # 支持 mp3, wav, pcm, opus 格式
        ) as response:
            for chunk in response.iter_bytes(chunk_size=4096):
                if interrupt_event.is_set():
                    while not tts_queue.empty():
                        try:
                            tts_queue.get_nowait()
                        except queue.Empty:
                            break
                    break  # 停止当前播放
                if chunk:
                    stream.write(chunk)
