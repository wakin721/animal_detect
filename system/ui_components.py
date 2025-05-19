import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)


class RoundedButton(tk.Canvas):
    """圆角按钮实现"""

    def __init__(self, parent, text="", command=None, radius=10, bg="#0078d7", fg="#ffffff",
                 hover_bg=None, hover_fg=None, width=120, height=40, **kwargs):
        """初始化圆角按钮"""
        self.width = width
        self.height = height
        self.radius = radius
        self.bg = bg
        self.fg = fg
        self.hover_bg = hover_bg if hover_bg else self._calculate_hover_color(bg)
        self.hover_fg = hover_fg if hover_fg else fg
        self.command = command
        self.text = text
        self.is_active = False

        # 获取父组件背景色
        parent_bg = None
        try:
            # 尝试使用cget获取ttk组件的背景色
            parent_bg = parent.cget("background")
        except Exception:
            # 如果失败，使用父组件的主题色或默认色
            parent_bg = bg

        # 创建画布
        super().__init__(
            parent,
            width=self.width,
            height=self.height,
            highlightthickness=0,
            bg=parent_bg,
            **kwargs
        )

        # 绘制按钮
        self._draw_button()

        # 绑定事件
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _calculate_hover_color(self, color):
        """计算悬停颜色"""
        try:
            # 将十六进制颜色转换为RGB
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)

            # 计算亮度
            brightness = (r * 299 + g * 587 + b * 114) / 1000

            if brightness > 128:
                # 使颜色变暗
                factor = 0.8
                r = max(0, int(r * factor))
                g = max(0, int(g * factor))
                b = max(0, int(b * factor))
            else:
                # 使颜色变亮
                factor = 1.2
                r = min(255, int(r * factor))
                g = min(255, int(g * factor))
                b = min(255, int(b * factor))

            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception as e:
            logger.warning(f"计算悬停颜色失败: {e}")
            return "#3d6a99"  # 默认悬停色

    def _draw_button(self):
        """绘制按钮"""
        # 清除画布
        self.delete("all")

        # 确定当前颜色
        current_bg = self.hover_bg if self.is_active else self.bg
        current_fg = self.hover_fg if self.is_active else self.fg

        # 绘制圆角矩形
        self.create_rounded_rect(0, 0, self.width, self.height, self.radius, fill=current_bg)

        # 绘制文字
        self.create_text(
            self.width // 2,
            self.height // 2,
            text=self.text,
            fill=current_fg,
            font=("Segoe UI", 11),
            anchor="center"
        )

    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """绘制圆角矩形"""
        points = [
            # 左上角圆弧
            x1 + radius, y1,
            x2 - radius, y1,
            # 右上角圆弧
            x2, y1,
            x2, y1 + radius,
            # 右下角圆弧
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            # 左下角圆弧
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            # 左上角圆弧完成
            x1, y1 + radius,
            x1, y1
        ]
        return self.create_polygon(points, **kwargs, smooth=True)

    def _on_enter(self, event):
        """鼠标进入事件"""
        self.is_active = True
        self._draw_button()

    def _on_leave(self, event):
        """鼠标离开事件"""
        self.is_active = False
        self._draw_button()

    def _on_click(self, event):
        """鼠标点击事件"""
        pass

    def _on_release(self, event):
        """鼠标释放事件"""
        if self.command:
            self.command()

    def set_active(self, active):
        """设置按钮的活动状态"""
        if self.is_active != active:
            self.is_active = active
            self._draw_button()

class ModernFrame(ttk.Frame):
    """现代风格框架"""
    pass

class InfoBar(ttk.Frame):
    """信息栏"""

    def __init__(self, parent, **kwargs):
        """初始化信息栏"""
        super().__init__(parent, **kwargs)

        self.status_label = ttk.Label(self, text="就绪", padding=(10, 5))
        self.status_label.pack(side="left")

class SpeedProgressBar(ttk.Frame):
    """带速度显示的进度条"""

    def __init__(self, parent, **kwargs):
        """初始化进度条"""
        super().__init__(parent, **kwargs)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self, orient="horizontal", length=300, mode="determinate", variable=self.progress_var)
        self.progress_bar.pack(side="left", fill="x", expand=True)

        self.info_frame = ttk.Frame(self)
        self.info_frame.pack(side="right", padx=(10, 0))

        self.speed_label = ttk.Label(self.info_frame, text="", width=15)
        self.speed_label.pack(side="top", anchor="e")

        self.time_label = ttk.Label(self.info_frame, text="", width=15)
        self.time_label.pack(side="bottom", anchor="e")