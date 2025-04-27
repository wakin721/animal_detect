"""
UI组件模块 - 提供应用程序界面组件
"""

import tkinter as tk
from tkinter import ttk

from system.config import PADDING, LARGE_FONT, NORMAL_FONT, SMALL_FONT, APP_VERSION

class ModernFrame(ttk.Frame):
    """现代风格的框架组件，带有圆角和标题"""

    def __init__(self, master, title=None, **kwargs):
        super().__init__(master, **kwargs)

        if title:
            self.title_label = ttk.Label(self, text=title, font=LARGE_FONT)
            self.title_label.pack(anchor="w", padx=PADDING, pady=(PADDING, 5))

            # 添加分隔线
            separator = ttk.Separator(self, orient="horizontal")
            separator.pack(fill="x", padx=PADDING, pady=(0, PADDING))


class InfoBar(ttk.Frame):
    """信息栏组件，显示状态和版本信息"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.status_label = ttk.Label(self, text="准备就绪", font=SMALL_FONT)
        self.status_label.pack(side="left", padx=PADDING)

        self.version_label = ttk.Label(self, text=f"版本 {APP_VERSION}", font=SMALL_FONT)
        self.version_label.pack(side="right", padx=PADDING)


class SpeedProgressBar(ttk.Frame):
    """速度进度条组件，包含进度条和速度/时间信息"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self, orient="horizontal", variable=self.progress_var, mode="determinate")
        self.progress_bar.pack(fill="x", padx=PADDING, pady=(PADDING, 5))

        info_frame = ttk.Frame(self)
        info_frame.pack(fill="x", padx=PADDING)

        self.speed_label = ttk.Label(info_frame, text="", font=SMALL_FONT)
        self.speed_label.pack(side="left")

        self.time_label = ttk.Label(info_frame, text="", font=SMALL_FONT)
        self.time_label.pack(side="right")