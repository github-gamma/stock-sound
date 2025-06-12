import akshare as ak
import numpy as np
import pyaudio
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

# 音频参数
SAMPLE_RATE = 44100  # 采样率 (Hz)
CHUNK = 1024  # 每次处理的音频块大小
AMPLITUDE = 0.3  # 音量 (0.0 到 1.0)
BASE_FREQ = 220.0  # 基础频率 (Hz)


class StockAudioSynth:
    def __init__(self):
        self.running = False
        self.thread = None
        self.current_freq = BASE_FREQ
        self.phase = 0.0
        self.playback_speed = 1.0  # 默认播放速度
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
            # 获取当前日期
            if date_str.lower() == 'today':
                date_str = datetime.now().strftime("%Y%m%d")

            # 获取分时数据
            df = ak.stock_zh_a_hist_min_em(symbol=stock_code, start_date=date_str, end_date=date_str, period="1")

            if df.empty:
                return False, "未获取到数据，请检查股票代码和日期"

            # 提取时间和价格数据
            self.price_data = df[['时间', '收盘']].values.tolist()
            self.current_index = 0
            return True, "数据加载成功"
        except Exception as e:
            return False, f"数据加载失败: {str(e)}"

    def start_playback(self):
        """启动音频播放线程"""
        if not self.running and self.price_data:
            self.running = True
            self.thread = threading.Thread(target=self._generate_audio)
            self.thread.daemon = True
            self.thread.start()

    def stop_playback(self):
        """停止音频播放"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.1)

    def set_playback_speed(self, speed):
        """设置播放速度 (0.1-5.0)"""
        self.playback_speed = float(speed)

    def _calculate_current_freq(self, idx):
        """根据指定索引的价格计算频率"""
        if not self.price_data or idx >= len(self.price_data):
            return BASE_FREQ

        # 获取当前价格
        _, current_price = self.price_data[idx]

        # 计算价格变化百分比 (相对于第一个价格)
        if len(self.price_data) > 1:
            first_price = self.price_data[0][1]
            price_change = (current_price - first_price) / first_price  # 涨跌幅百分比
            freq = BASE_FREQ * (1.0 + price_change * 2)  # 涨跌影响频率
            return max(50.0, min(2000.0, freq))  # 限制在50-2000Hz范围内
        return BASE_FREQ

    def _generate_audio(self):
        """生成音频数据的线程函数"""
        while self.running and self.price_data:
            # 更新当前索引 (根据播放速度)
            now = time.time()
            elapsed = now - self.last_update_time
            self.last_update_time = now

            # 计算应该前进多少数据点
            advance = elapsed * self.playback_speed * 2  # 调整这个系数可以改变数据点更新速度
            self.current_index = min(len(self.price_data) - 1, self.current_index + advance)

            # 确保索引是整数
            current_idx = int(self.current_index)

            # 如果到达数据末尾，停止或循环
            if current_idx >= len(self.price_data) - 1:
                current_idx = len(self.price_data) - 1
                self.current_index = current_idx  # 重置为整数

            # 计算当前频率
            self.current_freq = self._calculate_current_freq(current_idx)

            # 生成正弦波
            t = np.arange(CHUNK) / SAMPLE_RATE
            samples = AMPLITUDE * np.sin(2 * np.pi * self.current_freq * t + self.phase)

            # 更新相位以保持连续性
            self.phase = (self.phase + 2 * np.pi * self.current_freq * CHUNK / SAMPLE_RATE) % (2 * np.pi)

            # 播放音频
            self.stream.write(samples.astype(np.float32).tobytes())

    def close(self):
        """清理资源"""
        self.stop_playback()
        if self.stream.is_active():
            self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()


class StockAudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("股票分时数据音频可视化")
        self.root.geometry("700x500")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 创建音频合成器
        self.synth = StockAudioSynth()

        # 创建UI
        self.create_widgets()

    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title = ttk.Label(main_frame, text="股票分时数据音频可视化", font=("Arial", 16, "bold"))
        title.pack(pady=(0, 20))

        # 控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding=15)
        control_frame.pack(fill=tk.X, pady=10)

        # 股票代码输入
        stock_frame = ttk.Frame(control_frame)
        stock_frame.pack(fill=tk.X, pady=5)
        ttk.Label(stock_frame, text="股票代码:", width=10).pack(side=tk.LEFT)
        self.stock_entry = ttk.Entry(stock_frame)
        self.stock_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.stock_entry.insert(0, "000001")  # 默认平安银行

        # 日期输入
        date_frame = ttk.Frame(control_frame)
        date_frame.pack(fill=tk.X, pady=5)
        ttk.Label(date_frame, text="日期:", width=10).pack(side=tk.LEFT)
        self.date_entry = ttk.Entry(date_frame)
        self.date_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.date_entry.insert(0, "today")  # 默认今天

        # 加载数据按钮
        load_btn = ttk.Button(control_frame, text="加载股票数据", command=self.load_data)
        load_btn.pack(pady=10)

        # 状态信息
        self.status_label = ttk.Label(control_frame, text="准备加载数据...", foreground="blue")
        self.status_label.pack(pady=5)

        # 播放控制
        play_frame = ttk.Frame(control_frame)
        play_frame.pack(fill=tk.X, pady=10)
        self.play_btn = ttk.Button(play_frame, text="开始播放", command=self.toggle_playback)
        self.play_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(play_frame, text="停止", command=self.stop_playback, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # 播放速度控制
        speed_frame = ttk.Frame(control_frame)
        speed_frame.pack(fill=tk.X, pady=10)
        ttk.Label(speed_frame, text="播放速度:").pack(side=tk.LEFT)
        self.speed_slider = ttk.Scale(
            speed_frame,
            from_=0.1,
            to=5.0,
            value=1.0,
            command=self.update_speed,
            length=200
        )
        self.speed_slider.pack(side=tk.LEFT, padx=10)
        self.speed_label = ttk.Label(speed_frame, text="1.0x")
        self.speed_label.pack(side=tk.LEFT)

        # 信息显示
        info_frame = ttk.LabelFrame(main_frame, text="实时信息", padding=15)
        info_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # 当前数据点信息
        self.data_info = ttk.Label(info_frame, text="未加载数据", font=("Arial", 10))
        self.data_info.pack(anchor=tk.W, pady=5)

        # 当前频率信息
        self.freq_info = ttk.Label(info_frame, text="当前频率: - Hz", font=("Arial", 10))
        self.freq_info.pack(anchor=tk.W, pady=5)

        # 价格变化信息
        self.price_info = ttk.Label(info_frame, text="价格变化: -", font=("Arial", 10))
        self.price_info.pack(anchor=tk.W, pady=5)

        # 启动UI更新线程
        self.update_ui_thread()

    def load_data(self):
        """加载股票数据"""
        stock_code = self.stock_entry.get().strip()
        date_str = self.date_entry.get().strip()

        if not stock_code:
            messagebox.showerror("错误", "请输入股票代码")
            return

        self.status_label.config(text="正在加载数据...", foreground="blue")
        self.root.update()

        success, message = self.synth.load_stock_data(stock_code, date_str)

        if success:
            self.status_label.config(text=f"数据加载成功: {len(self.synth.price_data)}个数据点", foreground="green")
            self.play_btn.config(state=tk.NORMAL)
            self.update_data_display()
        else:
            self.status_label.config(text=message, foreground="red")

    def toggle_playback(self):
        """切换播放状态"""
        if not self.synth.running:
            self.synth.start_playback()
            self.play_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.status_label.config(text="正在播放...", foreground="green")
        else:
            self.stop_playback()

    def stop_playback(self):
        """停止播放"""
        self.synth.stop_playback()
        self.play_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="播放已停止", foreground="blue")

    def update_speed(self, value):
        """更新播放速度"""
        speed = float(value)
        self.synth.set_playback_speed(speed)
        self.speed_label.config(text=f"{speed:.1f}x")

    def update_data_display(self):
        """更新数据显示"""
        if self.synth.price_data and int(self.synth.current_index) < len(self.synth.price_data):
            current_idx = int(self.synth.current_index)
            time_str, price = self.synth.price_data[current_idx]
            self.data_info.config(text=f"时间: {time_str}  价格: {price:.2f}")

            # 计算价格变化
            if len(self.synth.price_data) > 1:
                first_price = self.synth.price_data[0][1]
                change = (price - first_price) / first_price * 100
                self.price_info.config(text=f"价格变化: {change:+.2f}% (相对于第一个数据点)")

            # 显示当前频率
            self.freq_info.config(text=f"当前频率: {self.synth.current_freq:.1f} Hz")

    def update_ui_thread(self):
        """定期更新UI的线程函数"""
        if self.synth.running:
            self.update_data_display()

        # 每100毫秒更新一次
        self.root.after(100, self.update_ui_thread)

    def on_close(self):
        """关闭窗口时的清理工作"""
        self.synth.close()
        self.root.destroy()


if __name__ == "__main__":
    # 检查依赖库
    try:
        import akshare as ak
        import pyaudio
        import numpy as np
    except ImportError:
        print("请先安装依赖库: pip install akshare pyaudio numpy")
        exit(1)

    # 启动应用
    root = tk.Tk()
    app = StockAudioApp(root)
    root.mainloop()