import requests
from config import config


def process_stt(audio_queue, text_queue, interrupt_event):
    """
    从 audio_queue 获取音频，转换为文本放入 text_queue。
    """
    print("[STT] 进程启动...")

    # 从配置获取STT参数
    stt_config = config.stt
    url = stt_config["url"]
    model = stt_config["model"]
    api_key = stt_config["api_key"]

    headers = {"Authorization": f"Bearer {api_key}"}

    while True:
        # 获取音频，超时为了定期检查 interrupt
        command_mp3_data = audio_queue.get()

        files = {"file": ("example.mp3", command_mp3_data)}
        payload = {"model": model}

        response = requests.post(url, data=payload, files=files, headers=headers)

        command_txt = response.json().get("text")
        print(f"[STT] 转录结果: {response.json()}")
        if command_txt:
            text_queue.put(command_txt)
