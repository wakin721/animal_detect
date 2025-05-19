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


class CollapsibleFrame(ttk.Frame):
    """可折叠卡片组件"""

    def __init__(self, parent, title, **kwargs):
        """初始化可折叠卡片

        Args:
            parent: 父级控件
            title: 卡片标题
            **kwargs: 传递给Frame的其他参数
        """
        super().__init__(parent, **kwargs)
        self.parent = parent

        # 标题框架
        self.title_frame = ttk.Frame(self)
        self.title_frame.pack(fill="x", expand=False)

        # 折叠状态图标
        self.is_collapsed = True
        self.collapse_icon = ttk.Label(self.title_frame, text="►", width=2)
        self.collapse_icon.pack(side="left", padx=(5, 0))

        # 标题标签
        self.title_label = ttk.Label(self.title_frame, text=title, font=("Segoe UI", 10, "bold"))
        self.title_label.pack(side="left", padx=(5, 0))

        # 内容框架 - 初始隐藏
        self.content_frame = ttk.Frame(self, padding=(15, 5, 5, 5))

        # 绑定点击事件
        self.title_frame.bind("<Button-1>", self._toggle_collapse)
        self.title_label.bind("<Button-1>", self._toggle_collapse)
        self.collapse_icon.bind("<Button-1>", self._toggle_collapse)

    def _toggle_collapse(self, event=None):
        """切换折叠状态"""
        if self.is_collapsed:
            self.expand()
        else:
            self.collapse()

    def expand(self):
        """展开内容"""
        self.collapse_icon.config(text="▼")
        self.content_frame.pack(fill="x", expand=True, pady=(5, 0))
        self.is_collapsed = False

    def collapse(self):
        """折叠内容"""
        self.collapse_icon.config(text="►")
        self.content_frame.pack_forget()
        self.is_collapsed = True

    def add_content(self, widget):
        """添加内容至卡片

        Args:
            widget: 要添加的控件
        """
        widget.pack(in_=self.content_frame, fill="x", expand=True, pady=2)


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
        """向内容区添加控件

        Args:
            widget: 要添加的控件
        """
        widget.pack(in_=self.content_padding, fill="x", pady=5)

    def _on_header_enter(self, event):
        """鼠标进入标题区域时的效果"""
        self.header_frame.config(bg=self.hover_color)
        self.title_label.config(bg=self.hover_color)
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.config(bg=self.hover_color)
        if self.icon_label:
            self.icon_label.config(bg=self.hover_color)
        # 更新折叠按钮背景色
        self.toggle_button.config(bg=self.hover_color)

    def _on_header_leave(self, event):
        """鼠标离开标题区域时的效果"""
        self.header_frame.config(bg=self.header_bg)
        self.title_label.config(bg=self.header_bg)
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.config(bg=self.header_bg)
        if self.icon_label:
            self.icon_label.config(bg=self.header_bg)
        # 更新折叠按钮背景色
        self.toggle_button.config(bg=self.header_bg)

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