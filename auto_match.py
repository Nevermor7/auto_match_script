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
RECEIVE_TEMPLATE_DIR = 'receive_templates'
F11_TEMPLATE_DIR = 'f11_templates'
SCREEN_SHOT = 'screen_shot'


class CFAotuGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        random.seed(datetime.now().timestamp())
        self.title("Ack")
        self.geometry("800x720-130+0")
        self.templates = {}
        self.receive_templates = {}
        self.f11_templates = {}
        self.running = False
        self.start_hotkey = tk.StringVar(value="F6")
        self.stop_hotkey = tk.StringVar(value="F7")
        self.worker_thread = None
        self.hotkey_listener = None
        self.is_topmost = tk.BooleanVar(value=False)
        self.last_action_time = time.time()
        self.emergency_enabled = tk.BooleanVar(value=True)
        self.interval_seconds = random.randint(180, 600)
        self.interval_minutes_min = tk.StringVar(value="3")
        self.interval_minutes_max = tk.StringVar(value="10")
        self.log_enabled = tk.BooleanVar(value=True)
        self.f11_enabled = tk.BooleanVar(value=True)
        self.is_need_receive = False
        self.scale_value = tk.DoubleVar(value=0.9)

        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        os.makedirs(F11_TEMPLATE_DIR, exist_ok=True)
        os.makedirs(RECEIVE_TEMPLATE_DIR, exist_ok=True)
        os.makedirs(SCREEN_SHOT, exist_ok=True)

        self._build_ui()
        self._load_templates()
        self._load_f11_templates()
        self._load_receive_templates()
        self._load_hotkey_listener()

    def _build_ui(self):
        frame = ttk.Frame(self)
        frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(frame, text="添加模板", command=self.add_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="移除模板", command=self.remove_template).pack(side=tk.LEFT)
        ttk.Button(frame, text="刷新模板", command=self._load_templates).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="添加F11模板", command=self.add_f11_template).pack(side=tk.LEFT)
        ttk.Button(frame, text="移除F11模板", command=self.remove_f11_template).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(frame, text="置顶窗口", variable=self.is_topmost, command=self.toggle_topmost).pack(side=tk.LEFT)

        scale_frame = ttk.Frame(self)
        scale_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(scale_frame, text="识别模板的匹配度阈值，默认90%").pack(side=tk.LEFT, padx=5)
        ttk.Scale(scale_frame, value=self.scale_value.get(), command=self.set_scale_value, to=1, length=211).pack(side=tk.LEFT)
        ttk.Label(scale_frame, textvariable=self.scale_value, width=5).pack(side=tk.LEFT, padx=10)

        hot_frame = ttk.Frame(self)
        hot_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(hot_frame, text="开始热键:").pack(side=tk.LEFT)
        ttk.Entry(hot_frame, textvariable=self.start_hotkey, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(hot_frame, text="停止热键:").pack(side=tk.LEFT)
        ttk.Entry(hot_frame, textvariable=self.stop_hotkey, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(hot_frame, text="刷新热键", command=self._load_hotkey_listener).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="开始挂机", command=self.start).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="停止挂机", command=self.stop).pack(side=tk.LEFT)

        setting_frame = ttk.Frame(self)
        setting_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Checkbutton(setting_frame, text="启用反挂机检测", variable=self.emergency_enabled).pack(side=tk.LEFT,padx=5)
        ttk.Label(setting_frame, text="触发区间(分钟):").pack(side=tk.LEFT)
        ttk.Entry(setting_frame, textvariable=self.interval_minutes_min, width=3).pack(side=tk.LEFT)
        ttk.Label(setting_frame, text="~").pack(side=tk.LEFT)
        ttk.Entry(setting_frame, textvariable=self.interval_minutes_max, width=3).pack(side=tk.LEFT)
        ttk.Checkbutton(setting_frame, text=" 启用自动按F11踢狗\n*需添加投票特征模板",variable=self.f11_enabled).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(setting_frame, text="启用日志输出", variable=self.log_enabled).pack(side=tk.LEFT, padx=5)

        self.listbox = tk.Listbox(self, height=8)
        self.listbox.pack(fill=tk.BOTH, padx=5, pady=5)

        self.log = tk.Text(self, height=15)
        self.log.pack(fill=tk.BOTH, padx=5, pady=5)
        self.log.insert(tk.END, "日志信息...\n")
        self.log.configure(state=tk.DISABLED)

    def set_scale_value(self, change_value):
        self.scale_value.set(round(float(change_value), 2))

    def toggle_topmost(self):
        self.attributes('-topmost', self.is_topmost.get())

    def log_message(self, msg):
        if not self.log_enabled.get():
            return
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"{time.strftime('%m-%d %H:%M:%S')} - {msg}\n")
        self.log.configure(state=tk.DISABLED)
        self.log.see(tk.END)

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

    def _load_f11_templates(self):
        self.f11_templates.clear()
        for filename in os.listdir(F11_TEMPLATE_DIR):
            path = os.path.join(F11_TEMPLATE_DIR, filename)
            if os.path.isfile(path) and path.lower().endswith(('.png', '.jpg', '.bmp')):
                tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self.f11_templates[path] = tpl

    def _load_receive_templates(self):
        self.receive_templates.clear()
        for filename in os.listdir(RECEIVE_TEMPLATE_DIR):
            path = os.path.join(RECEIVE_TEMPLATE_DIR, filename)
            if os.path.isfile(path) and path.lower().endswith(('.png', '.jpg', '.bmp')):
                tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self.receive_templates[path] = tpl

    def add_template(self):
        path = filedialog.askopenfilename(title='选择模板', filetypes=[('图片文件', '*.png;*.jpg;*.bmp')])
        if not path:
            return
        tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            messagebox.showerror('错误', '无法读取图像')
            return
        dst_path = os.path.join(TEMPLATE_DIR, os.path.basename(path))
        if not os.path.exists(dst_path):
            cv2.imwrite(dst_path, tpl)
        self._load_templates()
        self.log_message(f"添加模板: {os.path.basename(path)}")

    def remove_template(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        name = self.listbox.get(sel[0])
        path = os.path.join(TEMPLATE_DIR, name)
        if os.path.exists(path):
            os.remove(path)
        self._load_templates()
        self.log_message(f"移除模板: {name}")

    def add_f11_template(self):
        path = filedialog.askopenfilename(title='选择F11模板', filetypes=[('图片文件', '*.png;*.jpg;*.bmp')])
        if not path:
            return
        tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            messagebox.showerror('错误', '无法读取图像')
            return
        dst_path = os.path.join(F11_TEMPLATE_DIR, os.path.basename(path))
        if not os.path.exists(dst_path):
            cv2.imwrite(dst_path, tpl)
        self._load_f11_templates()
        self.log_message(f"添加F11模板: {os.path.basename(path)}")

    def remove_f11_template(self):
        files = os.listdir(F11_TEMPLATE_DIR)
        if not files:
            messagebox.showinfo('提示', '无F11模板可移除')
            return
        name = filedialog.askopenfilename(initialdir=F11_TEMPLATE_DIR, title='移除F11模板',filetypes=[('图片文件', '*.png;*.jpg;*.bmp')])
        if name and os.path.exists(name):
            os.remove(name)
        self._load_f11_templates()
        self.log_message(f"移除F11模板: {os.path.basename(name)}")

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
                pyautogui.mouseDown()
                time.sleep(0.05)
                pyautogui.mouseUp()
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

    def window_capture(self, window_title, file_prefix):
        # 获取窗口的位置和大小
        windows = pygetwindow.getWindowsWithTitle(window_title)
        if windows and windows[0].isActive:
            window = windows[0]
            left, top, width, height = window.left, window.top, window.width, window.height
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
        else:
            self.log_message("未识别到游戏窗口，执行全屏截图！")
            screenshot = pyautogui.screenshot()
        # 保存截图
        target_dir = rf'{SCREEN_SHOT}\{time.strftime('%Y-%m-%d')}'
        os.makedirs(target_dir, exist_ok=True)
        file_name = f'{file_prefix}_{time.strftime('%H_%M')}.png'
        file_path = os.path.join(target_dir, file_name)
        screenshot.save(file_path)
        self.log_message(f"截图已保存至{file_path}")

    def _loop(self):  # 识别匹配点击
        while self.running:
            # 领取每日任务奖励
            if self.is_need_receive:
                for path, tpl in self.receive_templates.items():
                    if not self.running:
                        return
                    screenshot = pyautogui.screenshot()
                    screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
                    res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if max_val >= self.scale_value.get():
                        th, tw = tpl.shape
                        x = max_loc[0] + tw // 2
                        y = max_loc[1] + th // 2
                        self.click_at(x, y)
                        self.log_message(f"点击了 {os.path.basename(path)}@({x},{y})conf={max_val:.2f}")
                        self.is_need_receive = False
                        time.sleep(0.5)

            # 开始匹配
            screenshot = pyautogui.screenshot()
            screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
            found = False
            for path, tpl in self.templates.items():
                if not self.running:
                    return
                file_name = os.path.basename(path)
                res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val >= self.scale_value.get():
                    if file_name.find("settlement") >= 0:
                        self.window_capture('穿越火线', 'settlement')
                    th, tw = tpl.shape
                    x = max_loc[0] + tw // 2
                    y = max_loc[1] + th // 2
                    self.click_at(x, y)
                    self.last_action_time = time.time()
                    self.log_message(f"点击了 {file_name}@({x},{y})conf={max_val:.2f}")
                    time.sleep(0.5)
                    found = True
                    if file_name.find("mission") >= 0:
                        self.is_need_receive = True
                    if file_name.find("match") >= 0:
                        time.sleep(5)

            if not found:
                # 上票
                if self.f11_enabled.get():  # 检查是否开启 F11 检测
                    for path, tpl in self.f11_templates.items():
                        if not self.running:
                            return
                        res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(res)
                        if max_val >= self.scale_value.get():
                            pyautogui.press('f11')
                            self.log_message(f"检测到t人:{os.path.basename(path)}，已按下F11")
                            break
                # 反挂机检测
                if self.emergency_enabled.get() and self.running:
                    current_interval_seconds = time.time() - self.last_action_time
                    if current_interval_seconds > self.interval_seconds:
                        pyautogui.mouseDown(button='left')
                        time.sleep(1)
                        pyautogui.mouseUp(button='left')
                        self.log_message("{}秒未匹配到模板，触发反挂机检测".format(round(current_interval_seconds, 1)))
                        self.last_action_time = time.time()
                        try:
                            self.interval_seconds = random.randint(int(float(self.interval_minutes_min.get()) * 60),
                                                                   int(float(self.interval_minutes_max.get()) * 60))
                        except:
                            self.interval_seconds = random.randint(180, 600)
            time.sleep(1)


if __name__ == '__main__':
    app = CFAotuGUI()
    app.mainloop()
