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
import pydirectinput

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
F11_TEMPLATE_DIR = 'f11_templates'
SCREEN_SHOT = 'screen_shot'


class CFAotuGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        random.seed(datetime.now().timestamp())
        self.title("Ack")
        self.geometry("590x650-180+0")
        self.templates = {}
        self.receive_templates = {}
        self.f11_templates = {}
        self.running = False
        self.start_hotkey = tk.StringVar(value="F6")
        self.stop_hotkey = tk.StringVar(value="F7")
        self.worker_thread = None
        self.hotkey_listener = None
        self.is_topmost = tk.BooleanVar(value=True)
        self.last_action_time = time.time()
        self.emergency_enabled = tk.BooleanVar(value=True)
        self.is_in_game = False
        self.interval_seconds_min = 120
        self.interval_seconds_max = 300
        self.interval_seconds = random.randint(self.interval_seconds_min, self.interval_seconds_max)
        self.interval_minutes_min = tk.StringVar(value=str(self.interval_seconds_min // 60))
        self.interval_minutes_max = tk.StringVar(value=str(self.interval_seconds_max // 60))
        self.log_enabled = tk.BooleanVar(value=True)
        self.f11_enabled = tk.BooleanVar(value=True)
        self.scale_value = tk.DoubleVar(value=0.8)
        self.enable_menu_chose = tk.BooleanVar(value=False)
        self.enable_complex_skill = tk.BooleanVar(value=False)
        self.menu_chose_num = tk.IntVar(value=2)
        self.enable_window_region = True
        self.window_region_left = tk.IntVar(value=0)
        self.window_region_top = tk.IntVar(value=0)
        self.window_region_width = tk.IntVar(value=0)
        self.window_region_height = tk.IntVar(value=0)

        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        os.makedirs(F11_TEMPLATE_DIR, exist_ok=True)
        os.makedirs(SCREEN_SHOT, exist_ok=True)

        self._build_ui()
        self._load_templates()
        self._load_f11_templates()
        self._load_hotkey_listener()

    def _build_ui(self):
        frame = ttk.Frame(self)
        frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(frame, text="添加模板", command=self.add_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="移除模板", command=self.remove_template).pack(side=tk.LEFT)
        ttk.Button(frame, text="刷新模板", command=self._load_templates).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="添加F11模板", command=self.add_f11_template).pack(side=tk.LEFT)
        ttk.Button(frame, text="移除F11模板", command=self.remove_f11_template).pack(side=tk.LEFT, padx=5)
        # ttk.Checkbutton(frame, text="置顶窗口", variable=self.is_topmost, command=self.toggle_topmost).pack(side=tk.LEFT)

        scale_frame = ttk.Frame(self)
        scale_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(scale_frame, text="识别模板的匹配度阈值,默认80%").pack(side=tk.LEFT, padx=5)
        ttk.Scale(scale_frame, value=self.scale_value.get(), command=self.set_scale_value, to=1, length=270).pack(side=tk.LEFT, padx=(20, 15))
        ttk.Label(scale_frame, textvariable=self.scale_value, width=5).pack(side=tk.LEFT)

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
        ttk.Button(btn_frame, text="停止挂机", command=self.stop).pack(side=tk.LEFT)
        ttk.Checkbutton(btn_frame, text="开启自动选择终结者(1~7)", variable=self.enable_menu_chose).pack(side=tk.LEFT, padx=(15, 5))
        ttk.Entry(btn_frame, textvariable=self.menu_chose_num, width=2, justify='center').pack(side=tk.LEFT)
        ttk.Checkbutton(btn_frame, text="复杂技能", variable=self.enable_complex_skill).pack(side=tk.LEFT, padx=6)

        setting_frame = ttk.Frame(self)
        setting_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Checkbutton(setting_frame, text="开启反挂机,触发频率(分钟)", variable=self.emergency_enabled).pack(side=tk.LEFT,padx=5)
        ttk.Entry(setting_frame, textvariable=self.interval_minutes_min, width=3, justify='center').pack(side=tk.LEFT)
        ttk.Label(setting_frame, text="~").pack(side=tk.LEFT)
        ttk.Entry(setting_frame, textvariable=self.interval_minutes_max, width=3, justify='center').pack(side=tk.LEFT)
        ttk.Checkbutton(setting_frame, text=" 开启自动F11踢狗",variable=self.f11_enabled).pack(side=tk.LEFT, padx=(21, 15))
        ttk.Checkbutton(setting_frame, text="开启日志", variable=self.log_enabled).pack(side=tk.LEFT)

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

    def toggle_topmost(self):
        self.attributes('-topmost', self.is_topmost.get())

    def log_message(self, msg):
        if not self.log_enabled.get():
            return
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"{time.strftime('%m-%d %H:%M:%S')} - {msg}\n")
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

    def _load_f11_templates(self):
        self.f11_templates.clear()
        for filename in os.listdir(F11_TEMPLATE_DIR):
            path = os.path.join(F11_TEMPLATE_DIR, filename)
            if os.path.isfile(path) and path.lower().endswith(('.png', '.jpg', '.bmp')):
                tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self.f11_templates[path] = tpl

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
                pydirectinput.moveTo(x, y)
                pydirectinput.mouseDown(button='left')
                time.sleep(0.05)
                pydirectinput.mouseUp(button='left')
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
        pydirectinput.FAILSAFE = False
        self.reload_window_region()
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

    def window_capture(self, file_prefix):
        # 获取窗口的位置和大小
        windows = pygetwindow.getWindowsWithTitle('穿越火线')
        if windows and windows[0].isActive:
            window = windows[0]
            left, top, width, height = window.left, window.top, window.width, window.height
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
        else:
            self.log_message("未检测到游戏窗口,执行全屏截图！")
            screenshot = pyautogui.screenshot()
        # 保存截图
        target_dir = rf'{SCREEN_SHOT}\{time.strftime('%Y-%m-%d')}'
        os.makedirs(target_dir, exist_ok=True)
        file_name = f'{file_prefix}_{time.strftime('%H_%M')}.png'
        file_path = os.path.join(target_dir, file_name)
        screenshot.save(file_path)
        # self.log_message(f"截图已保存至{file_path}")
        self.log_message(f"截图已保存 {file_name}")

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
            self.enable_window_region = False

    def _loop(self):  # 识别匹配点击
        while self.running:
            # 开始匹配
            if self.enable_window_region:
                screenshot = pyautogui.screenshot(region=(self.window_region_left.get(), self.window_region_top.get(), self.window_region_width.get(), self.window_region_height.get()))
            else:
                screenshot = pyautogui.screenshot()
            screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
            for path, tpl in self.templates.items():
                if not self.running:
                    return
                res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val >= self.scale_value.get():
                    file_name = os.path.basename(path)
                    if file_name.find("wait") >= 0:
                        break
                    if file_name.find("loading") >= 0:
                        self.is_in_game = True
                        self.last_action_time = time.time()
                        break
                    if file_name.find("seconds") >= 0:
                        self.is_in_game = True
                        if self.enable_menu_chose.get():
                            pydirectinput.press('f')
                            self.log_message("检测到生化开局读秒,已按下F增加变终结效率")
                        continue
                    if file_name.find("ui") >= 0:
                        if self.enable_menu_chose.get():
                            pydirectinput.press('e')
                            self.log_message("已按下E呼出变身菜单")
                        continue
                    if file_name.find("menu") >= 0:
                        if self.enable_menu_chose.get():
                            pydirectinput.press(str(self.menu_chose_num.get()))
                            self.log_message(f"检测到变身菜单,已按下{self.menu_chose_num.get()}选择指定终结者")
                        continue
                    if file_name.find("skill_g") >= 0:
                        if self.enable_menu_chose.get():
                            pydirectinput.press('g')
                            if self.enable_complex_skill.get():
                                time.sleep(2)
                                pydirectinput.mouseDown(button='left')
                                time.sleep(0.05)
                                pydirectinput.mouseUp(button='left')
                            self.log_message("已使用技能G")
                        continue
                    if file_name.find("skill_f") >= 0:
                        if self.enable_menu_chose.get():
                            pydirectinput.press('f')
                            if self.enable_complex_skill.get():
                                move_x = random.randint(-3000,3000)
                                move_y = random.randint(400,1800)
                                time.sleep(1)
                                pydirectinput.moveRel(move_x, move_y, duration=1, relative=True)
                                pydirectinput.mouseDown(button='left')
                                time.sleep(0.05)
                                pydirectinput.mouseUp(button='left')
                                pydirectinput.moveRel(-move_x, -move_y, duration=1, relative=True)
                            self.log_message("已使用技能F")
                        continue
                    if file_name.find("settle") >= 0:
                        self.is_in_game = False
                        self.window_capture('settle')
                        time.sleep(0.5)
                    th, tw = tpl.shape
                    x = max_loc[0] + tw // 2
                    y = max_loc[1] + th // 2
                    self.click_at(self.window_region_left.get() + x, self.window_region_top.get() + y)
                    self.last_action_time = time.time()
                    self.log_message(f"点击了 {file_name}@({x},{y})conf={max_val:.2f}")
                    time.sleep(0.5)
            # 上票
            if self.f11_enabled.get():  # 检查是否开启 F11 检测
                for path, tpl in self.f11_templates.items():
                    if not self.running:
                        return
                    res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    if max_val >= self.scale_value.get():
                        pydirectinput.press('f11')
                        self.log_message(f"检测到t狗:{os.path.basename(path)},已按下F11上票")
                        break
            # 反挂机检测
            if self.is_in_game and self.emergency_enabled.get() and self.running:
                current_interval_seconds = time.time() - self.last_action_time
                if current_interval_seconds > self.interval_seconds:
                    move_list_1 = ['w', 's']
                    random_move_1 = random.choice(move_list_1)
                    move_list_2 = ['a', 'd', '']
                    random_move_2 = random.choice(move_list_2)
                    pydirectinput.mouseDown(button='left')
                    pydirectinput.keyDown(random_move_1)
                    if len(random_move_2) > 0:
                        pydirectinput.keyDown(random_move_2)
                    pydirectinput.keyDown('space')
                    pydirectinput.keyUp('space')
                    time.sleep(random.uniform(1, 3))
                    if len(random_move_2) > 0:
                        pydirectinput.keyUp(random_move_2)
                    pydirectinput.keyUp(random_move_1)
                    pydirectinput.mouseUp(button='left')
                    self.log_message(f"{round(current_interval_seconds)}秒未点击模板,执行反挂机检测{random_move_1}{random_move_2}")
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
