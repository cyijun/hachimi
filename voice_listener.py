import io
import multiprocessing
import queue
import time

import numpy as np
import pyaudio
import webrtcvad
from openwakeword.model import Model
from pydub import AudioSegment

from config import config


class VoiceAssistantListener:
    def __init__(
        self,
        model_path=None,
        mic_running_event=multiprocessing.Event(),
        inturrupt_event=multiprocessing.Event(),
        audio_queue=multiprocessing.Queue(),
    ):
        # 从配置获取参数
        listener_config = config.voice_listener

        # 如果未提供model_path，使用配置中的路径
        if model_path is None:
            model_path = listener_config["wake_word_model_path"]

        # 音频参数
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = listener_config["channels"]
        self.RATE = listener_config["rate"]
        self.CHUNK = listener_config["chunk"]
        self.VAD_FRAME_MS = listener_config["vad_frame_ms"]
        self.VAD_FRAME_SAMPLES = int(self.RATE * self.VAD_FRAME_MS / 1000)

        # 逻辑阈值
        self.WAKE_WORD_THRESHOLD = listener_config["wake_word_threshold"]
        self.SILENCE_LIMIT_SECONDS = listener_config["silence_limit_seconds"]
        self.MIN_RECORD_SECONDS = listener_config["min_record_seconds"]

        self.oww_model = Model(
            wakeword_models=[model_path], inference_framework="tflite"
        )

        # 2. 初始化 VAD
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(3)  # 0-3, 3 最激进(过滤噪音强但可能切掉语音)，1 比较保守

        # 3. 初始化 PyAudio
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

        print("--- 系统就绪 ---")
        print(f"唤醒词模型: {model_path}")
        print(f"采样率: {self.RATE}Hz")

    def record_command(self):
        """
        唤醒后调用此函数录制语音指令
        """
        print(">>> 正在聆听指令 (VAD检测中)...")
        frames = []
        silence_chunks = 0
        # 计算多少个连续的静音 VAD 块等于设定的静音时间限制
        max_silence_chunks = int(self.SILENCE_LIMIT_SECONDS * 1000 / self.VAD_FRAME_MS)

        recording = True

        while recording:
            # 读取适合 VAD 的小块数据
            data = self.stream.read(self.VAD_FRAME_SAMPLES, exception_on_overflow=False)
            frames.append(data)

            # VAD 检测
            is_speech = self.vad.is_speech(data, self.RATE)

            if is_speech:
                silence_chunks = 0  # 重置静音计数
            else:
                silence_chunks += 1

            # 检查是否结束录制
            # 条件1: 静音时间超过阈值 且 录制总时长超过最小限制
            current_duration = (len(frames) * self.VAD_FRAME_MS) / 1000
            if (
                silence_chunks > max_silence_chunks
                and current_duration > self.MIN_RECORD_SECONDS
            ):
                print(">>> 检测到语音结束")
                recording = False

        return b"".join(frames)

    def pcm_to_mp3(self, audio_data):
        """将原始 PCM 数据保存为 MP3"""
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
        print("等待唤醒中... 请说 'Hey Jarvis'")

        try:
            while self.mic_running_event.is_set():
                # 1. 获取音频块 (用于唤醒检测)
                audio_data = self.stream.read(self.CHUNK, exception_on_overflow=False)

                # 转换格式供 openwakeword 使用 (numpy int16)
                audio_np = np.frombuffer(audio_data, dtype=np.int16)

                # 2. 喂入唤醒模型
                prediction = self.oww_model.predict(audio_np)

                # 3. 检查是否唤醒
                # openwakeword 返回字典，key是模型名
                for model_name, score in prediction.items():
                    if score > self.WAKE_WORD_THRESHOLD:
                        print("\n>>> [KWS] 检测到唤醒词！触发打断机制！ <<<")
                        print(f"\n!!! 唤醒成功 (分数: {score:.4f}) !!!")
                        # --- 核心打断逻辑 ---
                        self.interrupt_event.set()  # 发送打断信号

                        # 清空之前的音频队列，防止 STT 处理旧语音
                        while not self.audio_queue.empty():
                            try:
                                self.audio_queue.get_nowait()
                            except queue.Empty:
                                break

                        # 给其他进程一点时间响应打断
                        time.sleep(0.1)
                        print("[KWS] 打断完成，开始监听新指令...")

                        # 4. 开始录制指令 (B -> C)
                        command_audio = self.record_command()

                        mp3_data = self.pcm_to_mp3(command_audio)

                        # 5. 保存文件 (用于测试/后续传给STT)
                        self.audio_queue.put(mp3_data)

                        # 清空 openwakeword 的内部缓冲，防止连续触发
                        self.oww_model.reset()
                        self.interrupt_event.clear()  # 重置信号，准备接收新指令

        except KeyboardInterrupt:
            print("停止监听")
        finally:
            self.stream.stop_stream()
            self.stream.close()
            self.pa.terminate()


def process_kws_vad(audio_queue, interrupt_event, mic_running_event):
    """
    负责监听麦克风，检测唤醒词，并裁切有效语音发送给 STT。
    它是整个系统的'指挥官'，拥有触发打断的权限。
    """
    print("[KWS] 进程启动...")
    listener = VoiceAssistantListener(
        None, mic_running_event, interrupt_event, audio_queue
    )
    listener.start()
