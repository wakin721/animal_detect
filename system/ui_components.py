import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)


class RoundedButton(tk.Canvas):
    """圆角按钮实现 - 选中时在左侧显示高亮指示条"""

    def __init__(self, parent, text="", command=None, bg="#2c3e50", fg="#ffffff",
                 width=160, height=40, radius=10, highlight_color="#ffffff", **kwargs):
        """初始化圆角按钮

        Args:
            parent: 父级窗口
            text: 按钮文本
            command: 点击回调函数
            bg: 背景色
            fg: 文字颜色
            width: 按钮宽度
            height: 按钮高度
            radius: 圆角半径
            highlight_color: 高亮指示条颜色
        """
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=bg,
            highlightthickness=0,
            **kwargs
        )

        self.bg = bg
        self.fg = fg
        self.command = command
        self.radius = radius
        self.text = text
        self.width = width
        self.height = height
        self.active = False  # 默认非激活状态
        self.highlight_color = highlight_color

        # 计算悬停状态的颜色
        r, g, b = [int(self.bg[i:i + 2], 16) for i in (1, 3, 5)]
        brightness = (r * 299 + g * 587 + b * 114) / 1000

        if brightness < 128:  # 深色背景
            # 变亮
            self.hover_bg = f"#{min(255, int(r * 1.3)):02x}{min(255, int(g * 1.3)):02x}{min(255, int(b * 1.3)):02x}"
        else:
            # 变暗
            self.hover_bg = f"#{max(0, int(r * 0.9)):02x}{max(0, int(g * 0.9)):02x}{max(0, int(b * 0.9)):02x}"

        # 绘制初始状态
        self._draw_button("normal")

        # 绑定事件
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _draw_button(self, state="normal"):
        """绘制按钮，根据状态使用不同的背景色

        Args:
            state: 按钮状态，可选值为 "normal", "hover", "active"
        """
        # 清除所有内容
        self.delete("all")

        # 根据状态选择背景色
        if state == "active":
            bg_color = self.bg  # 选中时使用原始背景色
            font_style = ("Segoe UI", 11, "bold")  # 选中时文字加粗
        elif state == "hover":
            bg_color = self.hover_bg
            font_style = ("Segoe UI", 11)
        else:  # normal
            bg_color = self.bg
            font_style = ("Segoe UI", 11)

        # 绘制圆角矩形
        radius = self.radius
        width = self.width
        height = self.height

        # 绘制主体矩形
        self.create_rectangle(
            radius, 0,
            width - radius, height,
            fill=bg_color, outline="", tags="body"
        )

        # 绘制左右侧矩形
        self.create_rectangle(
            0, radius,
            radius, height - radius,
            fill=bg_color, outline="", tags="body"
        )

        self.create_rectangle(
            width - radius, radius,
            width, height - radius,
            fill=bg_color, outline="", tags="body"
        )

        # 绘制四个角的圆弧
        self.create_arc(
            0, 0, radius * 2, radius * 2,
            start=90, extent=90, fill=bg_color, outline=""
        )

        self.create_arc(
            width - radius * 2, 0, width, radius * 2,
            start=0, extent=90, fill=bg_color, outline=""
        )

        self.create_arc(
            width - radius * 2, height - radius * 2, width, height,
            start=270, extent=90, fill=bg_color, outline=""
        )

        self.create_arc(
            0, height - radius * 2, radius * 2, height,
            start=180, extent=90, fill=bg_color, outline=""
        )

        # 如果是激活状态，添加左侧高亮指示条
        if state == "active":
            # 设置缩短的高亮指示条参数
            indicator_width = 2  # 指示条宽度
            indicator_height = height * 0.6  # 指示条高度为按钮高度的60%
            indicator_y_offset = (height - indicator_height) / 2  # 垂直居中

            # 使用固定坐标确保上下半圆对齐
            x_left = 0
            x_right = indicator_width

            # 计算半圆直径
            circle_diameter = indicator_width * 2

            # 计算矩形的上下边界
            rect_top = indicator_y_offset + circle_diameter / 2
            rect_bottom = indicator_y_offset + indicator_height - circle_diameter / 2

            # 绘制主体矩形部分
            if rect_bottom > rect_top:  # 确保有中间部分
                self.create_rectangle(
                    x_left,
                    rect_top,
                    x_right * 2,
                    rect_bottom,
                    fill=self.highlight_color,
                    outline="",
                    tags="highlight"
                )

            # 绘制上半圆 - 确保位置精确对齐
            self.create_arc(
                x_left,
                indicator_y_offset,
                circle_diameter,
                indicator_y_offset + circle_diameter,
                start=0,
                extent=180,  # 180度弧，形成半圆
                fill=self.highlight_color,
                outline="",
                tags="highlight"
            )

            # 绘制下半圆 - 确保与上半圆完全对齐
            self.create_arc(
                x_left,  # 与上半圆使用完全相同的x坐标
                indicator_y_offset + indicator_height - circle_diameter,
                circle_diameter*0.75,  # 与上半圆使用完全相同的宽度
                indicator_y_offset + indicator_height,
                start=180,
                extent=180,  # 180度弧，形成半圆
                fill=self.highlight_color,
                outline="",
                tags="highlight"
            )

            # 绘制文本
        self.text_id = self.create_text(
            width // 2,
            height // 2,
            text=self.text,
            fill=self.fg,
            font=font_style,
            anchor="center",
            tags="text"
        )

    def set_active(self, active):
        """设置按钮是否处于激活状态"""
        self.active = active
        self._draw_button("active" if active else "normal")

    def _on_press(self, event):
        """按下按钮事件处理"""
        # 执行命令
        if self.command:
            self.command()

    def _on_release(self, event):
        """释放按钮事件处理"""
        pass

    def _on_enter(self, event):
        """鼠标进入事件处理"""
        # 如果不是激活状态，显示悬停效果
        if not self.active:
            self._draw_button("hover")

    def _on_leave(self, event):
        """鼠标离开事件处理"""
        # 恢复正常或激活状态
        self._draw_button("active" if self.active else "normal")

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


class CollapsiblePanel(ttk.Frame):
    """现代化可折叠面板组件 - 修复版"""

    def __init__(self, parent, title, subtitle="", icon=None, **kwargs):
        """初始化可折叠面板

        Args:
            parent: 父级容器
            title: 面板标题
            subtitle: 面板副标题
            icon: 图标（可选）
            **kwargs: 传递给Frame的其他参数
        """
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.toggle_callbacks = []  # 用于存储切换状态的回调函数

        # 创建自定义样式
        style = ttk.Style()

        # 确保使用正确的背景颜色
        if style.theme_use() == "sun-valley-dark" or getattr(self, 'is_dark_mode', False):
            self.bg_color = "#2b2b2b"
            self.header_bg = "#333333"
            self.text_color = "#ffffff"
            self.hover_color = "#3a3a3a"
        else:
            self.bg_color = "#f5f5f5"
            self.header_bg = "#e5e5e5"
            self.text_color = "#000000"
            self.hover_color = "#e0e0e0"

        # 配置整个面板
        self.configure(style="Panel.TFrame")
        style.configure("Panel.TFrame", background=self.bg_color)

        # 头部框架
        self.header_frame = tk.Frame(self, bg=self.header_bg, cursor="hand2")
        self.header_frame.pack(fill="x", expand=False, pady=(0, 1))

        # 左侧图标（如果提供）
        self.icon_label = None
        if icon:
            try:
                if isinstance(icon, str):  # 如果是字符串，当作图标代码处理
                    self.icon_label = tk.Label(self.header_frame, text=icon,
                                               font=("Segoe MDL2 Assets", 16),
                                               bg=self.header_bg, fg=self.text_color)
                else:  # 否则当作图像处理
                    self.icon_label = tk.Label(self.header_frame, image=icon,
                                               bg=self.header_bg)
                self.icon_label.pack(side="left", padx=(15, 10), pady=12)
            except Exception as e:
                logger.error(f"加载图标失败: {e}")
                # 如果加载失败，不显示图标

        # 标题框架（含标题和副标题）
        title_container = tk.Frame(self.header_frame, bg=self.header_bg)
        title_container.pack(side="left", fill="both", expand=True, pady=10)

        # 标题
        self.title_label = tk.Label(title_container, text=title,
                                    font=("Segoe UI", 11, "bold"),
                                    bg=self.header_bg, fg=self.text_color)
        self.title_label.pack(side="top", anchor="w")

        # 副标题（如果提供）
        if subtitle:
            self.subtitle_label = tk.Label(title_container, text=subtitle,
                                           font=("Segoe UI", 9),
                                           bg=self.header_bg, fg=self.text_color)
            self.subtitle_label.pack(side="top", anchor="w")

        # 折叠按钮 - 使用 tk.Label 以便更好地控制外观
        self.is_expanded = False
        self.toggle_button = tk.Label(self.header_frame, text="▼",
                                      font=("Segoe UI", 9),
                                      bg=self.header_bg, fg=self.text_color)
        self.toggle_button.pack(side="right", padx=(0, 15), pady=10)

        # 内容区域
        self.content_frame = ttk.Frame(self, style="Content.TFrame")
        style.configure("Content.TFrame", background=self.bg_color, relief="flat")
        self.content_frame.pack_forget()  # 初始隐藏

        # 内容区域的内边距容器
        self.content_padding = ttk.Frame(self.content_frame, style="ContentPadding.TFrame")
        style.configure("ContentPadding.TFrame", background=self.bg_color)
        self.content_padding.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        # 绑定点击事件
        self.header_frame.bind("<Button-1>", self.toggle)
        self.title_label.bind("<Button-1>", self.toggle)
        if self.icon_label:
            self.icon_label.bind("<Button-1>", self.toggle)
        self.toggle_button.bind("<Button-1>", self.toggle)

        # 鼠标悬停效果
        self.header_frame.bind("<Enter>", self._on_header_enter)
        self.header_frame.bind("<Leave>", self._on_header_leave)

    def toggle(self, event=None):
        """切换展开/折叠状态"""
        was_expanded = self.is_expanded

        if self.is_expanded:
            self.collapse()
        else:
            self.expand()

        # 调用所有注册的回调，传递面板自身和展开状态
        for callback in self.toggle_callbacks:
            callback(self, self.is_expanded)

        return "break"  # 防止事件继续传播

    def expand(self):
        """展开面板"""
        if self.is_expanded:
            return  # 如果已经展开，不做任何操作

        self.content_frame.pack(fill="both", expand=True)
        self.toggle_button.configure(text="▲")
        self.is_expanded = True

    def collapse(self):
        """折叠面板"""
        if not self.is_expanded:
            return  # 如果已经折叠，不做任何操作

        self.content_frame.pack_forget()
        self.toggle_button.configure(text="▼")
        self.is_expanded = False

    def add_widget(self, widget):
        """向内容区添加控件并设置背景色

        Args:
            widget: 要添加的控件
        """
        widget.pack(in_=self.content_padding, fill="x", pady=5)

        # 设置添加的组件背景色
        self._set_widget_bg(widget)

    def _set_widget_bg(self, widget):
        """为组件设置正确的背景色

        Args:
            widget: 要设置背景色的组件
        """
        # 检查组件类型并设置合适的背景色
        try:
            # 对于tk.Frame, tk.Label等支持bg属性的组件
            if hasattr(widget, 'configure') and 'bg' in widget.configure():
                widget.configure(bg=self.bg_color)

            # 对于ttk组件，尝试使用style设置
            elif isinstance(widget, ttk.Widget):
                widget_class = widget.winfo_class()
                widget_name = widget.winfo_name()
                style_name = f"{widget_name}.{widget_class}"

                style = ttk.Style()
                try:
                    # 为不同类型的ttk组件创建适当的样式
                    if widget_class == "TFrame" or widget_class == "TLabelframe":
                        style.configure(style_name, background=self.bg_color)
                    elif widget_class == "TLabel":
                        style.configure(style_name, background=self.bg_color)
                    elif widget_class == "TButton" or widget_class == "TCheckbutton" or widget_class == "TRadiobutton":
                        style.map(style_name, background=[('active', self.bg_color)])
                        style.configure(style_name, background=self.bg_color)

                    # 应用样式
                    widget.configure(style=style_name)
                except tk.TclError:
                    # 有些ttk组件可能不支持某些样式选项
                    pass

            # 递归处理子组件
            for child in widget.winfo_children():
                self._set_widget_bg(child)

        except Exception as e:
            # 如果设置背景色失败，记录但不影响程序运行
            logger.debug(f"设置组件背景色失败: {str(e)}")

    def bind_toggle_callback(self, callback):
        """绑定切换状态的回调函数

        Args:
            callback: 回调函数，接收两个参数：面板对象和展开状态(True/False)
        """
        if callback not in self.toggle_callbacks:
            self.toggle_callbacks.append(callback)

    def unbind_toggle_callback(self, callback):
        """解除绑定切换状态的回调函数"""
        if callback in self.toggle_callbacks:
            self.toggle_callbacks.remove(callback)

    def _on_header_enter(self, event):
        """鼠标进入头部区域时的效果"""
        self.header_frame.config(bg=self.hover_color)
        self.title_label.config(bg=self.hover_color)
        self.toggle_button.config(bg=self.hover_color)
        if self.icon_label:
            self.icon_label.config(bg=self.hover_color)
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.config(bg=self.hover_color)

    def _on_header_leave(self, event):
        """鼠标离开头部区域时的效果"""
        self.header_frame.config(bg=self.header_bg)
        self.title_label.config(bg=self.header_bg)
        self.toggle_button.config(bg=self.header_bg)
        if self.icon_label:
            self.icon_label.config(bg=self.header_bg)
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.config(bg=self.header_bg)
