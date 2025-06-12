import pyaudio
import numpy as np
import threading
import time
import tkinter as tk
from tkinter import ttk

# 音频参数
SAMPLE_RATE = 44100  # 采样率 (Hz)
CHUNK = 1024  # 每次处理的音频块大小
AMPLITUDE = 0.5  # 音量 (0.0 到 1.0)


class AudioSynth:
    def __init__(self):
        self.running = False
        self.thread = None
        self.frequency = 440.0  # 初始频率 (A4)
        self.phase = 0.0

        # 初始化 PyAudio
        self.p = pyaudio.PyAudio()

        # 打开音频流
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=SAMPLE_RATE,
            output=True,
            frames_per_buffer=CHUNK
        )

    def start(self):
        """启动音频合成线程"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._generate_audio)
            self.thread.daemon = True
            self.thread.start()

    def stop(self):
        """停止音频合成"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.1)

    def set_frequency(self, freq):
        """设置新的频率"""
        self.frequency = float(freq)

    def _generate_audio(self):
        """生成音频数据的线程函数"""
        while self.running:
            # 计算时间向量
            t = np.arange(CHUNK) / SAMPLE_RATE

            # 生成正弦波
            samples = AMPLITUDE * np.sin(2 * np.pi * self.frequency * t + self.phase)

            # 更新相位以保持连续性
            self.phase = (self.phase + 2 * np.pi * self.frequency * CHUNK / SAMPLE_RATE) % (2 * np.pi)

            # 转换为32位浮点数并播放
            self.stream.write(samples.astype(np.float32).tobytes())

    def close(self):
        """清理资源"""
        self.stop()
        if self.stream.is_active():
            self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()


class AudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("实时音频合成器")
        self.root.geometry("500x300")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 创建音频合成器
        self.synth = AudioSynth()

        # 创建UI
        self.create_widgets()

        # 启动音频合成
        self.synth.start()

    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title = ttk.Label(main_frame, text="实时音频合成器", font=("Arial", 16, "bold"))
        title.pack(pady=(0, 20))

        # 频率显示
        self.freq_label = ttk.Label(main_frame, text=f"频率: {self.synth.frequency:.1f} Hz", font=("Arial", 12))
        self.freq_label.pack(pady=5)

        # 频率滑块
        freq_frame = ttk.Frame(main_frame)
        freq_frame.pack(fill=tk.X, pady=10)

        ttk.Label(freq_frame, text="低", font=("Arial", 10)).pack(side=tk.LEFT)

        self.freq_slider = ttk.Scale(
            freq_frame,
            from_=50,
            to=2000,
            value=self.synth.frequency,
            command=self.update_frequency,
            length=400
        )
        self.freq_slider.pack(side=tk.LEFT, padx=10)

        ttk.Label(freq_frame, text="高", font=("Arial", 10)).pack(side=tk.LEFT)

        # 音符参考
        notes_frame = ttk.LabelFrame(main_frame, text="音符参考", padding=10)
        notes_frame.pack(fill=tk.X, pady=20)

        notes = [
            ("C4 (中音Do)", 261.63),
            ("D4 (Re)", 293.66),
            ("E4 (Mi)", 329.63),
            ("F4 (Fa)", 349.23),
            ("G4 (Sol)", 392.00),
            ("A4 (La)", 440.00),
            ("B4 (Si)", 493.88),
            ("C5 (高音Do)", 523.25)
        ]

        for i, (name, freq) in enumerate(notes):
            btn = ttk.Button(
                notes_frame,
                text=name,
                width=10,
                command=lambda f=freq: self.set_frequency(f)
            )
            btn.grid(row=i // 4, column=i % 4, padx=5, pady=5)

    def update_frequency(self, value):
        """滑块值变化时更新频率"""
        freq = float(value)
        self.synth.set_frequency(freq)
        self.freq_label.config(text=f"频率: {freq:.1f} Hz")

    def set_frequency(self, freq):
        """设置特定频率"""
        self.freq_slider.set(freq)
        self.synth.set_frequency(freq)
        self.freq_label.config(text=f"频率: {freq:.1f} Hz")

    def on_close(self):
        """关闭窗口时的清理工作"""
        self.synth.close()
        self.root.destroy()


if __name__ == "__main__":
    # 检查依赖库
    try:
        import pyaudio
        import numpy as np
    except ImportError:
        print("请先安装依赖库: pip install pyaudio numpy")
        exit(1)

    # 启动应用
    root = tk.Tk()
    app = AudioApp(root)
    root.mainloop()