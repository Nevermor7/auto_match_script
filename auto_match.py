import threading
import time
import os
import random
from datetime import datetime
import pygetwindow
import cv2
import numpy as np
import pyautogui
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Windows 专用库
try:
    import win32api, win32con
except ImportError:
    win32api = None

# 全局热键库优先使用 pynput,这个包需要手动导入
try:
    from pynput import keyboard as kb
except ImportError:
    kb = None

TEMPLATE_DIR = 'templates'

class CFAotuGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        random.seed(datetime.now().timestamp())
        self.title("Ack")
        self.geometry("580x600-0+0")
        self.templates = {}
        self.running = False
        self.start_hotkey = tk.StringVar(value="F6")
        self.stop_hotkey = tk.StringVar(value="F7")
        self.worker_thread = None
        self.hotkey_listener = None
        self.last_action_time = time.time()
        self.emergency_enabled = tk.BooleanVar(value=False)
        self.interval_seconds_min = 180
        self.interval_seconds_max = 780
        self.interval_seconds = random.randint(self.interval_seconds_min, self.interval_seconds_max)
        self.interval_minutes_min = tk.StringVar(value=str(self.interval_seconds_min // 60))
        self.interval_minutes_max = tk.StringVar(value=str(self.interval_seconds_max // 60))
        self.log_enabled = tk.BooleanVar(value=True)
        self.f11_enabled = tk.BooleanVar(value=True)
        self.scale_value = tk.DoubleVar(value=0.8)
        self.window_region = True
        self.window_region_left = tk.IntVar(value=0)
        self.window_region_top = tk.IntVar(value=0)
        self.window_region_width = tk.IntVar(value=0)
        self.window_region_height = tk.IntVar(value=0)

        os.makedirs(TEMPLATE_DIR, exist_ok=True)

        self._build_ui()
        self._load_templates()
        self._load_hotkey_listener()

    def _build_ui(self):
        scale_frame = ttk.Frame(self)
        scale_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(scale_frame, text="识别模板的匹配度阈值,默认80%").pack(side=tk.LEFT, padx=5)
        ttk.Scale(scale_frame, value=self.scale_value.get(), command=self.set_scale_value, to=1, length=260).pack(side=tk.LEFT, padx=(20, 15))
        ttk.Label(scale_frame, textvariable=self.scale_value, width=5).pack(side=tk.LEFT)

        region_frame = ttk.Frame(self)
        region_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(region_frame, text="游戏窗口坐标").pack(side=tk.LEFT, padx=(5, 20))
        ttk.Label(region_frame, text="左").pack(side=tk.LEFT)
        ttk.Entry(region_frame, textvariable=self.window_region_left, width=5, justify='center').pack(side=tk.LEFT, padx=5)
        ttk.Label(region_frame, text="上").pack(side=tk.LEFT)
        ttk.Entry(region_frame, textvariable=self.window_region_top, width=5, justify='center').pack(side=tk.LEFT, padx=5)
        ttk.Label(region_frame, text="宽").pack(side=tk.LEFT)
        ttk.Entry(region_frame, textvariable=self.window_region_width, width=5, justify='center').pack(side=tk.LEFT, padx=5)
        ttk.Label(region_frame, text="高").pack(side=tk.LEFT)
        ttk.Entry(region_frame, textvariable=self.window_region_height, width=5, justify='center').pack(side=tk.LEFT, padx=5)
        ttk.Button(region_frame, text="刷新窗口位置", command=self.reload_window_region).pack(side=tk.LEFT, padx=(20, 0))

        setting_frame = ttk.Frame(self)
        setting_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Checkbutton(setting_frame, text="开启反挂机,触发频率(分钟)", variable=self.emergency_enabled).pack(side=tk.LEFT,padx=5)
        ttk.Entry(setting_frame, textvariable=self.interval_minutes_min, width=3, justify='center').pack(side=tk.LEFT)
        ttk.Label(setting_frame, text="~").pack(side=tk.LEFT)
        ttk.Entry(setting_frame, textvariable=self.interval_minutes_max, width=3, justify='center').pack(side=tk.LEFT)
        ttk.Checkbutton(setting_frame, text=" 开启自动F11踢狗",variable=self.f11_enabled).pack(side=tk.LEFT, padx=(21, 15))
        ttk.Checkbutton(setting_frame, text="开启日志", variable=self.log_enabled).pack(side=tk.LEFT)

        hot_frame = ttk.Frame(self)
        hot_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(hot_frame, text="开始热键").pack(side=tk.LEFT, padx=5)
        ttk.Entry(hot_frame, textvariable=self.start_hotkey, width=15, justify='center').pack(side=tk.LEFT)
        ttk.Label(hot_frame, text="停止热键").pack(side=tk.LEFT, padx=(15, 5))
        ttk.Entry(hot_frame, textvariable=self.stop_hotkey, width=15, justify='center').pack(side=tk.LEFT)
        ttk.Button(hot_frame, text="刷新热键", command=self._load_hotkey_listener).pack(side=tk.LEFT, padx=(20, 0))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="开始挂机", command=self.start).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="停止挂机", command=self.stop).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新模板", command=self._load_templates).pack(side=tk.LEFT, padx=5)

        self.listbox = tk.Listbox(self, height=6)
        self.listbox.pack(fill=tk.BOTH, padx=5, pady=5)

        log_frame = ttk.Frame(self)
        log_frame.pack(fill=tk.X, padx=5)
        ttk.Button(log_frame, text="清空日志", command=self.clear_log).pack(side=tk.LEFT, padx=5)

        self.log = tk.Text(self, height=13)
        self.log.pack(fill=tk.BOTH, padx=5, pady=5)
        self.log.insert(tk.END, "日志信息...\n")
        self.log.configure(state=tk.DISABLED)

    def set_scale_value(self, change_value):
        self.scale_value.set(round(float(change_value), 2))

    def log_message(self, msg):
        if not self.log_enabled.get():
            return
        self.log.configure(state=tk.NORMAL)
        log_message = f"{time.strftime('%m-%d %H:%M:%S')} - {msg}\n"
        self.log.insert(tk.END, log_message)
        self.log.configure(state=tk.DISABLED)
        self.log.see(tk.END)

    def clear_log(self):
        if not self.log_enabled.get():
            return
        self.log.configure(state=tk.NORMAL)
        self.log.delete('1.0', tk.END)
        self.log.configure(state=tk.DISABLED)

    def _load_templates(self):
        self.templates.clear()
        self.listbox.delete(0, tk.END)
        for filename in os.listdir(TEMPLATE_DIR):
            path = os.path.join(TEMPLATE_DIR, filename)
            if os.path.isfile(path) and path.lower().endswith(('.png', '.jpg', '.bmp')):
                tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self.templates[path] = tpl
                    self.listbox.insert(tk.END, os.path.basename(path))

    def _load_hotkey_listener(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        if kb:
            hk = {f'<{self.start_hotkey.get()}>': self.start, f'<{self.stop_hotkey.get()}>': self.stop}
            self.hotkey_listener = kb.GlobalHotKeys(hk)
            self.hotkey_listener.start()
            self.log_message(f"绑定全局热键 ===> {self.start_hotkey.get()}-开始挂机  {self.stop_hotkey.get()}-停止挂机")
        else:
            self.log_message('绑定热键失败！请手动点击开始挂机！')

    def click_at(self, x, y):
        try:
            if win32api:
                win32api.SetCursorPos((int(x), int(y)))
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            else:
                pyautogui.moveTo(x, y)
                pyautogui.mouseDown(button='left')
                time.sleep(0.05)
                pyautogui.mouseUp(button='left')
        except Exception as e:
            self.log_message(f"点击时发生错误: {e}")

    def start(self):
        if self.running:
            return
        if not self.templates:
            messagebox.showwarning('警告', '请先添加模板')
            return
        try:
            self.interval_seconds = random.randint(int(float(self.interval_minutes_min.get()) * 60), int(float(self.interval_minutes_max.get()) * 60))
        except:
            pass
        self.running = True
        self.last_action_time = time.time()
        self.worker_thread = threading.Thread(target=self._loop, daemon=True)
        self.worker_thread.start()
        self.log_message('挂机开始')

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2)
        self.log_message('挂机停止')

    def reload_window_region(self):
        # 获取窗口的位置和大小
        windows = pygetwindow.getWindowsWithTitle('穿越火线')
        if windows:
            window = windows[0]
            self.window_region_left.set(window.left)
            self.window_region_top.set(window.top)
            self.window_region_width.set(window.width)
            self.window_region_height.set(window.height)
        else:
            self.log_message("未检测到游戏窗口,无法进行精准识别")
            self.window_region = False

    def _loop(self):  # 识别匹配点击
        while self.running:
            # 开始匹配
            left = self.window_region_left.get()
            top = self.window_region_top.get()
            width = self.window_region_width.get()
            height = self.window_region_height.get()
            if self.window_region and left > 0 and top > 0 and width > 0 and height > 0:
                screenshot = pyautogui.screenshot(region=(left, top, width, height))
            else:
                screenshot = pyautogui.screenshot()
            screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
            found = False
            for path, tpl in self.templates.items():
                if not self.running:
                    return
                res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val >= self.scale_value.get():
                    file_name = os.path.basename(path)
                    if file_name.find("wait") >= 0:
                        break
                    th, tw = tpl.shape
                    x = max_loc[0] + tw // 2
                    y = max_loc[1] + th // 2
                    self.click_at(self.window_region_left.get() + x, self.window_region_top.get() + y)
                    self.last_action_time = time.time()
                    self.log_message(f"点击了 {file_name}@({x},{y})conf={max_val:.2f}")
                    time.sleep(0.5)
                    found = True
                    # 把F11移到这里
                    if self.f11_enabled.get() and file_name.find("f11") >= 0:
                        time.sleep(0.5)
                        pyautogui.press('f11')
                        self.log_message(f"检测到t狗:{os.path.basename(path)},已按下F11上票")
                        break
            # 反挂机检测
            if not found and self.emergency_enabled.get() and self.running:
                current_interval_seconds = time.time() - self.last_action_time
                if current_interval_seconds > self.interval_seconds:
                    pyautogui.mouseDown(button='left')
                    time.sleep(random.uniform(1, 3))
                    pyautogui.mouseUp(button='left')
                    self.log_message(f"{round(current_interval_seconds)}秒未点击模板,执行反挂机检测")
                    self.last_action_time = time.time()
                    try:
                        self.interval_seconds = random.randint(int(float(self.interval_minutes_min.get()) * 60),
                                                               int(float(self.interval_minutes_max.get()) * 60))
                    except:
                        self.interval_seconds = random.randint(self.interval_seconds_min, self.interval_seconds_max)
            time.sleep(1)


if __name__ == '__main__':
    app = CFAotuGUI()
    app.mainloop()
