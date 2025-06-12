import akshare as ak
import numpy as np
import pyaudio
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

# 音频参数
SAMPLE_RATE = 44100  # 采样率 (Hz)
CHUNK = 1024  # 每次处理的音频块大小
AMPLITUDE = 0.3  # 音量 (0.0 到 1.0)
BASE_NOTE = 440.0  # A4 音符频率 (Hz)


# 十二平均律计算
def get_note_frequency(base_freq, semitones):
    """根据半音数计算频率"""
    return base_freq * (2 ** (semitones / 12))


# 创建音阶映射 (-12到+12个半音，对应-100%到+100%价格变化)
NOTE_RANGE = 12  # 上下各12个半音（一个八度）
NOTE_MAPPING = [get_note_frequency(BASE_NOTE, i) for i in range(-NOTE_RANGE, NOTE_RANGE + 1)]


class StockAudioSynth:
    def __init__(self):
        self.running = False
        self.thread = None
        self.current_freq = BASE_NOTE
        self.phase = 0.0
        self.playback_speed = 1.0
        self.price_data = []
        self.current_index = 0
        self.last_update_time = time.time()

        # 初始化 PyAudio
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=SAMPLE_RATE,
            output=True,
            frames_per_buffer=CHUNK
        )


    def load_stock_data(self, stock_code, date_str):
        """从AKShare加载股票分时数据"""
        try:
            if date_str.lower() == 'today':
                date_str = datetime.now().strftime("%Y%m%d")

            df = ak.stock_zh_a_hist_min_em(symbol=stock_code, start_date=date_str, end_date=date_str, period="1")

            if df.empty:
                return False, "未获取到数据，请检查股票代码和日期"

            self.price_data = df[['时间', '收盘']].values.tolist()

            # 计算价格范围用于归一化
            prices = [p[1] for p in self.price_data]
            self.min_price = min(prices)
            self.max_price = max(prices)
            self.price_range = self.max_price - self.min_price

            self.current_index = 0
            return True, f"数据加载成功: {len(self.price_data)}个数据点"
        except Exception as e:
            return False, f"数据加载失败: {str(e)}"

    def start_playback(self):
        if not self.running and self.price_data:
            self.running = True
            self.thread = threading.Thread(target=self._generate_audio)
            self.thread.daemon = True
            self.thread.start()

    def stop_playback(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.1)

    def set_playback_speed(self, speed):
        self.playback_speed = float(speed)

    def _map_price_to_note(self, price):
        """将价格映射到音阶"""
        if self.price_range == 0:
            return BASE_NOTE

        # 归一化价格到[-1, 1]范围
        normalized = 2 * (price - self.min_price) / self.price_range - 1

        # 映射到半音索引 (-12到+12)
        semitone = int(round(normalized * NOTE_RANGE))
        semitone = max(-NOTE_RANGE, min(NOTE_RANGE, semitone))

        return NOTE_MAPPING[semitone + NOTE_RANGE]  # 列表索引从0开始

    def _generate_audio(self):
        """生成音频数据的线程函数"""
        while self.running and self.price_data:
            # 更新当前索引
            now = time.time()
            elapsed = now - self.last_update_time
            self.last_update_time = now

            advance = elapsed * self.playback_speed * 2
            self.current_index = min(len(self.price_data) - 1, self.current_index + advance)

            current_idx = int(self.current_index)
            if current_idx >= len(self.price_data) - 1:
                current_idx = len(self.price_data) - 1
                self.current_index = current_idx

            # 获取当前价格并映射到音阶
            _, current_price = self.price_data[current_idx]
            self.current_freq = self._map_price_to_note(current_price)

            # 生成正弦波
            t = np.arange(CHUNK) / SAMPLE_RATE
            samples = AMPLITUDE * np.sin(2 * np.pi * self.current_freq * t + self.phase)

            # 更新相位
            self.phase = (self.phase + 2 * np.pi * self.current_freq * CHUNK / SAMPLE_RATE) % (2 * np.pi)

            # 播放音频
            self.stream.write(samples.astype(np.float32).tobytes())

    def close(self):
        self.stop_playback()
        if self.stream.is_active():
            self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()


class StockAudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("股票音乐化 - 十二平均律版")
        self.root.geometry("700x500")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.synth = StockAudioSynth()
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题和说明
        title = ttk.Label(main_frame, text="股票价格音乐化系统", font=("Arial", 16, "bold"))
        title.pack(pady=(0, 10))

        desc = ttk.Label(main_frame, text="将股票分时数据转换为十二平均律音阶，价格变化听起来像音乐!", wraplength=600)
        desc.pack(pady=(0, 20))

        # 控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding=15)
        control_frame.pack(fill=tk.X, pady=10)

        # 股票代码输入
        stock_frame = ttk.Frame(control_frame)
        stock_frame.pack(fill=tk.X, pady=5)
        ttk.Label(stock_frame, text="股票代码:").pack(side=tk.LEFT)
        self.stock_entry = ttk.Entry(stock_frame)
        self.stock_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.stock_entry.insert(0, "000001")

        # 日期输入
        date_frame = ttk.Frame(control_frame)
        date_frame.pack(fill=tk.X, pady=5)
        ttk.Label(date_frame, text="日期:").pack(side=tk.LEFT)
        self.date_entry = ttk.Entry(date_frame)
        self.date_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.date_entry.insert(0, "today")

        # 按钮区域
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        self.load_btn = ttk.Button(btn_frame, text="加载数据", command=self.load_data)
        self.load_btn.pack(side=tk.LEFT, padx=5)

        self.play_btn = ttk.Button(btn_frame, text="开始播放", command=self.start_playback, state=tk.DISABLED)
        self.play_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self.stop_playback, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # 播放速度控制
        speed_frame = ttk.Frame(control_frame)
        speed_frame.pack(fill=tk.X, pady=10)
        ttk.Label(speed_frame, text="播放速度:").pack(side=tk.LEFT)
        self.speed_slider = ttk.Scale(speed_frame, from_=0.1, to=5.0, value=1.0, command=self.update_speed, length=200)
        self.speed_slider.pack(side=tk.LEFT, padx=10)
        self.speed_label = ttk.Label(speed_frame, text="1.0x")
        self.speed_label.pack(side=tk.LEFT)

        # 状态和信息显示
        self.status_label = ttk.Label(control_frame, text="准备加载数据...", foreground="blue")
        self.status_label.pack(pady=5)

        # 信息显示区域
        info_frame = ttk.LabelFrame(main_frame, text="实时信息", padding=15)
        info_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.data_info = ttk.Label(info_frame, text="未加载数据", font=("Arial", 10))
        self.data_info.pack(anchor=tk.W, pady=5)

        self.freq_info = ttk.Label(info_frame, text="当前频率: - Hz", font=("Arial", 10))
        self.freq_info.pack(anchor=tk.W, pady=5)

        self.note_info = ttk.Label(info_frame, text="当前音符: -", font=("Arial", 10))
        self.note_info.pack(anchor=tk.W, pady=5)

        self.price_info = ttk.Label(info_frame, text="价格变化: -", font=("Arial", 10))
        self.price_info.pack(anchor=tk.W, pady=5)

        # 启动UI更新
        self.update_ui()

    def load_data(self):
        stock_code = self.stock_entry.get().strip()
        date_str = self.date_entry.get().strip()

        if not stock_code:
            messagebox.showerror("错误", "请输入股票代码")
            return

        self.status_label.config(text="正在加载数据...", foreground="blue")
        self.root.update()

        success, message = self.synth.load_stock_data(stock_code, date_str)

        if success:
            self.status_label.config(text=message, foreground="green")
            self.play_btn.config(state=tk.NORMAL)
        else:
            self.status_label.config(text=message, foreground="red")

    def start_playback(self):
        self.synth.start_playback()
        self.play_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="正在播放...", foreground="green")

    def stop_playback(self):
        self.synth.stop_playback()
        self.play_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="播放已停止", foreground="blue")

    def update_speed(self, value):
        speed = float(value)
        self.synth.set_playback_speed(speed)
        self.speed_label.config(text=f"{speed:.1f}x")

    def get_note_name(self, freq):
        """获取最接近的音符名称"""
        if not hasattr(self, 'note_names'):
            # 创建音符名称列表 (A0到A8)
            notes = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']
            self.note_names = []
            for octave in range(0, 9):
                for i, note in enumerate(notes):
                    if note == 'B' and i == 2 and octave < 8:
                        self.note_names.append(f"{note}{octave}")
                    elif note.startswith('C') and i == 3 and octave < 8:
                        self.note_names.append(f"{note}{octave}")
                    elif octave < 8:
                        self.note_names.append(f"{note}{octave}")

        # 找到最接近的音符
        closest_note = min(self.note_names,
                           key=lambda x: abs(get_note_frequency(27.5, self.note_names.index(x)) - freq))
        return closest_note

    def update_ui(self):
        if hasattr(self.synth, 'price_data') and self.synth.price_data:
            current_idx = int(self.synth.current_index)
            if current_idx < len(self.synth.price_data):
                time_str, price = self.synth.price_data[current_idx]
                self.data_info.config(text=f"时间: {time_str}  价格: {price:.2f}")

                # 计算价格变化百分比
                price_change = (price - self.synth.min_price) / self.synth.price_range * 100
                self.price_info.config(
                    text=f"价格位置: {price_change:.1f}% (最低{self.synth.min_price:.2f}, 最高{self.synth.max_price:.2f})")

                # 显示频率和音符
                self.freq_info.config(text=f"当前频率: {self.synth.current_freq:.1f} Hz")
                note_name = self.get_note_name(self.synth.current_freq)
                self.note_info.config(text=f"当前音符: {note_name}")

        self.root.after(100, self.update_ui)

    def on_close(self):
        self.synth.close()
        self.root.destroy()


if __name__ == "__main__":
    try:
        import akshare as ak
        import pyaudio
        import numpy as np
    except ImportError:
        print("请先安装依赖库: pip install akshare pyaudio numpy")
        exit(1)

    root = tk.Tk()
    app = StockAudioApp(root)
    root.mainloop()