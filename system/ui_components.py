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
    """现代化可折叠面板组件 - 针对滑块组件特别优化"""

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
        self.style = ttk.Style()

        # 判断当前主题是否是深色主题
        current_theme = self.style.theme_use()
        self.is_dark_mode = (current_theme == "dark" or current_theme == "sun-valley-dark" or
                             getattr(parent, 'is_dark_mode', False))

        # 根据深色模式设置默认颜色
        if self.is_dark_mode:
            self.bg_color = "#2b2b2b"
            self.header_bg = "#333333"
            self.text_color = "#ffffff"
            self.hover_color = "#3a3a3a"
            self.trough_color = "#505050"  # 深色模式滑槽颜色
        else:
            self.bg_color = "#f5f5f5"
            self.header_bg = "#e5e5e5"
            self.text_color = "#000000"
            self.hover_color = "#e0e0e0"
            self.trough_color = "#d0d0d0"  # 浅色模式滑槽颜色

        # 尝试从父窗口递归获取背景色，确保与应用程序整体风格一致
        self._inherit_background_color()

        # 生成唯一ID作为样式前缀，避免样式冲突
        self.uid = str(id(self))[-6:]

        # 配置整个面板的样式
        panel_style = f"Panel_{self.uid}.TFrame"
        self.style.configure(panel_style, background=self.bg_color)
        self.configure(style=panel_style)

        # 创建并应用基于当前背景色的样式
        self._configure_widget_styles()

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

        # 内容区域 - 使用自定义样式
        self.content_frame = ttk.Frame(self, style=f"Content_{self.uid}.TFrame")
        self.content_frame.pack_forget()  # 初始隐藏

        # 内容区域的内边距容器 - 使用同样的样式
        self.content_padding = ttk.Frame(self.content_frame, style=f"Content_{self.uid}.TFrame")
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

    def _inherit_background_color(self):
        """递归从父窗口获取背景色"""
        try:
            # 先检查是否有is_dark_mode属性，确定整体模式
            parent = self.parent
            while parent:
                if hasattr(parent, 'is_dark_mode'):
                    self.is_dark_mode = parent.is_dark_mode
                    break
                if hasattr(parent, 'master') and parent.master:
                    parent = parent.master
                else:
                    break

            # 尝试获取实际的背景颜色
            parent = self.parent
            while parent:
                try:
                    # 尝试直接获取背景色
                    if hasattr(parent, 'cget'):
                        bg = parent.cget('background')
                        if bg and bg not in ('', 'SystemButtonFace'):
                            self.bg_color = bg
                            return

                    # 检查特殊属性
                    for attr_name in ['bg_color', 'background', 'bg', 'sidebar_bg']:
                        if hasattr(parent, attr_name):
                            attr_val = getattr(parent, attr_name)
                            if isinstance(attr_val, str):
                                self.bg_color = attr_val
                                return

                    # 特别处理高级设置中的字段
                    advanced_fields = [
                        'advanced_page', 'model_params_tab', 'params_content_frame',
                        'threshold_panel', 'accel_panel', 'advanced_detect_panel'
                    ]

                    for field_name in advanced_fields:
                        if hasattr(parent, field_name):
                            field = getattr(parent, field_name)
                            if hasattr(field, 'cget'):
                                bg = field.cget('background')
                                if bg and bg not in ('', 'SystemButtonFace'):
                                    self.bg_color = bg
                                    return
                except Exception:
                    pass

                # 继续向上查找
                if hasattr(parent, 'master') and parent.master:
                    parent = parent.master
                else:
                    break

            # 根据深色模式使用默认背景色
            if self.is_dark_mode:
                self.bg_color = "#2b2b2b"
            else:
                self.bg_color = "#f5f5f5"
        except Exception:
            pass  # 如果获取失败，使用默认背景色

    def _configure_widget_styles(self):
        """为各种组件配置基于当前背景色的样式"""
        # Frame样式
        self.style.configure(f"Content_{self.uid}.TFrame", background=self.bg_color)

        # Label样式
        self.style.configure(f"Label_{self.uid}.TLabel",
                             background=self.bg_color,
                             foreground=self.text_color)

        # 参数标签专用样式
        self.style.configure(f"ParamLabel_{self.uid}.TLabel",
                             background=self.bg_color,
                             foreground=self.text_color)

        # 复选框样式
        self.style.configure(f"Check_{self.uid}.TCheckbutton",
                             background=self.bg_color,
                             foreground=self.text_color)

        self.style.map(f"Check_{self.uid}.TCheckbutton",
                       background=[('active', self.bg_color),
                                   ('disabled', self.bg_color),
                                   ('selected', self.bg_color),
                                   ('!disabled', self.bg_color)],
                       foreground=[('active', self.text_color),
                                   ('disabled', self.text_color),
                                   ('selected', self.text_color)])

        # 单选框样式
        self.style.configure(f"Radio_{self.uid}.TRadiobutton",
                             background=self.bg_color,
                             foreground=self.text_color)

        self.style.map(f"Radio_{self.uid}.TRadiobutton",
                       background=[('active', self.bg_color),
                                   ('disabled', self.bg_color),
                                   ('selected', self.bg_color),
                                   ('!disabled', self.bg_color)],
                       foreground=[('active', self.text_color),
                                   ('disabled', self.text_color),
                                   ('selected', self.text_color)])

        # 滑块样式 - 特别处理
        try:
            # 先删除所有同名样式，避免样式累积叠加问题
            for state in ['', 'active', 'disabled', 'selected', 'focus', 'pressed', 'alternate']:
                try:
                    self.style.map(f"Scale_{self.uid}.Horizontal.TScale",
                                   background=[(state, None)])
                except:
                    pass

            # 重新创建样式
            self.style.configure(f"Scale_{self.uid}.Horizontal.TScale",
                                 background=self.bg_color,
                                 troughcolor=self.trough_color)

            # 确保在所有状态下背景一致
            states = ['active', 'disabled', 'selected', 'focus', '!disabled', 'pressed', 'alternate']
            for state in states:
                self.style.map(f"Scale_{self.uid}.Horizontal.TScale",
                               background=[(state, self.bg_color)])

            # 重写滑块的element布局，尝试更精确控制
            self.style.layout(f"Scale_{self.uid}.Horizontal.TScale", [
                ('Horizontal.Scale.trough', {
                    'sticky': 'nswe',
                    'children': [
                        ('Horizontal.Scale.track', {'sticky': 'nswe'}),
                        ('Horizontal.Scale.slider', {'side': 'left', 'sticky': ''})
                    ]
                })
            ])

            # 直接配置滑块中的实际元素
            self.style.element_create(f"SliderBg_{self.uid}", "from", "default")
            self.style.configure(f"Scale_{self.uid}.Horizontal.TScale",
                                 troughcolor=self.trough_color)

            # 重写垂直滑块样式
            self.style.configure(f"Scale_{self.uid}.Vertical.TScale",
                                 background=self.bg_color,
                                 troughcolor=self.trough_color)
            for state in states:
                self.style.map(f"Scale_{self.uid}.Vertical.TScale",
                               background=[(state, self.bg_color)])
        except Exception as e:
            logger.debug(f"滑块样式配置失败: {str(e)}")

        # 下拉框样式
        self.style.configure(f"Combo_{self.uid}.TCombobox",
                             background=self.bg_color,
                             fieldbackground=self.bg_color,
                             foreground=self.text_color)

    def toggle(self, event=None):
        """切换展开/折叠状态"""
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

        # 使用多段延迟确保UI组件完全渲染后应用样式
        self.master.update_idletasks()

        # 立即应用一次样式
        self._apply_styles_to_all_children()

        # 然后用延迟序列确保完全应用
        self.after(50, self._apply_styles_to_all_children)
        self.after(100, self._apply_styles_to_all_children)
        # 最后一次延迟较长，处理可能的动画完成后
        self.after(300, self._apply_styles_to_all_children)

    def collapse(self):
        """折叠面板"""
        if not self.is_expanded:
            return  # 如果已经折叠，不做任何操作

        self.content_frame.pack_forget()
        self.toggle_button.configure(text="▼")
        self.is_expanded = False

    def add_widget(self, widget):
        """向内容区添加控件并设置背景色"""
        widget.pack(in_=self.content_padding, fill="x", pady=5)
        # 立即应用样式到新添加的组件
        self._apply_style_to_widget(widget)

    def _apply_styles_to_all_children(self):
        """递归应用样式到所有子控件"""
        # 应用到内容框架本身
        self._force_set_background(self.content_frame, self.bg_color)
        self._force_set_background(self.content_padding, self.bg_color)

        # 特别处理 - 寻找并修复面板中的所有滑块组件及其容器框架
        self._find_and_fix_all_scales(self.content_padding)

        # 应用到所有子控件
        for child in self.content_padding.winfo_children():
            self._apply_style_to_widget(child, force_bg=True)

    def _find_and_fix_all_scales(self, parent_widget):
        """特别寻找并修复所有滑块组件及其相关组件"""
        try:
            # 查找所有ttk.Scale组件
            scales = []

            def _find_scales(widget):
                try:
                    if hasattr(widget, 'winfo_children'):
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Scale) or (
                                    hasattr(child, 'winfo_class') and 'Scale' in child.winfo_class()):
                                scales.append(child)
                            _find_scales(child)
                except:
                    pass

            # 开始递归查找
            _find_scales(parent_widget)

            # 对找到的每个滑块应用专用样式
            for scale in scales:
                try:
                    # 获取组件类型
                    widget_class = scale.winfo_class()

                    # 应用水平或垂直滑块样式
                    if "Horizontal" in widget_class:
                        scale.configure(style=f"Scale_{self.uid}.Horizontal.TScale")
                    else:
                        scale.configure(style=f"Scale_{self.uid}.Vertical.TScale")

                    # 强制设置背景色
                    self._force_set_background(scale, self.bg_color)

                    # 特别处理滑块的父容器
                    parent = scale.master
                    if parent:
                        self._force_set_background(parent, self.bg_color)

                        # 处理同级组件（特别是标签）
                        for sibling in parent.winfo_children():
                            if isinstance(sibling, ttk.Label) or (
                                    hasattr(sibling, 'winfo_class') and sibling.winfo_class() == "TLabel"):
                                sibling.configure(style=f"ParamLabel_{self.uid}.TLabel")
                                self._force_set_background(sibling, self.bg_color)
                            elif isinstance(sibling, tk.Label):
                                sibling.configure(bg=self.bg_color, fg=self.text_color)
                except Exception as e:
                    logger.debug(f"修复滑块样式失败: {str(e)}")
        except Exception as e:
            logger.debug(f"查找滑块组件失败: {str(e)}")

    def _force_set_background(self, widget, color):
        """强制设置组件背景色，无视组件类型"""
        try:
            # 尝试各种可能的背景色设置方法
            if hasattr(widget, 'configure'):
                try:
                    if 'background' in widget.config():
                        widget.configure(background=color)
                    if 'bg' in widget.config():
                        widget.configure(bg=color)
                except:
                    pass

            # 对于ttk.Frame特别处理
            if isinstance(widget, ttk.Frame):
                style_name = f"Custom_{id(widget)}.TFrame"
                self.style.configure(style_name, background=color)
                try:
                    widget.configure(style=style_name)
                except:
                    pass

            # 对于ttk.Scale特别处理
            if isinstance(widget, ttk.Scale):
                try:
                    # 获取组件类型
                    widget_class = widget.winfo_class()

                    # 创建并应用自定义样式
                    style_name = f"Custom_{id(widget)}"
                    if "Horizontal" in widget_class:
                        self.style.configure(f"{style_name}.Horizontal.TScale",
                                             background=color,
                                             troughcolor=self.trough_color)
                        widget.configure(style=f"{style_name}.Horizontal.TScale")
                    elif "Vertical" in widget_class:
                        self.style.configure(f"{style_name}.Vertical.TScale",
                                             background=color,
                                             troughcolor=self.trough_color)
                        widget.configure(style=f"{style_name}.Vertical.TScale")
                except:
                    pass
        except:
            pass

    def _apply_style_to_widget(self, widget, force_bg=False):
        """为单个组件应用正确的样式"""
        try:
            # 处理tk原生组件
            if not isinstance(widget, ttk.Widget):
                if hasattr(widget, 'configure'):
                    # 强制设置背景色
                    if 'background' in widget.config():
                        widget.configure(background=self.bg_color)
                    elif 'bg' in widget.config():
                        widget.configure(bg=self.bg_color)

                    # 对于tk.Label和相似组件，同时设置文字颜色
                    if widget.__class__.__name__ in ['Label', 'Message', 'Text'] and 'fg' in widget.config():
                        widget.configure(fg=self.text_color)

                    # 对于tk.Frame特殊处理
                    if widget.__class__.__name__ == 'Frame':
                        # 强制将Frame的所有子控件背景设为相同颜色
                        for child in widget.winfo_children():
                            self._apply_style_to_widget(child, force_bg=True)

            # 特别处理ttk组件
            else:
                # 获取具体的widget类名
                widget_class = widget.winfo_class()

                # 特殊处理框架容器
                if widget_class == "TFrame" or widget_class == "TLabelframe":
                    widget.configure(style=f"Content_{self.uid}.TFrame")

                    # 对于Frame，特别检查是否包含滑块和标签
                    self._find_and_fix_all_scales(widget)

                    # 递归处理所有子组件
                    for child in widget.winfo_children():
                        self._apply_style_to_widget(child, force_bg=True)

                # 特殊处理标签组件，应用专用样式
                elif widget_class == "TLabel":
                    widget.configure(style=f"ParamLabel_{self.uid}.TLabel")

                # 特殊处理滑块组件
                elif widget_class == "TScale" or "Scale" in widget_class:
                    # 水平滑块
                    if "Horizontal" in widget_class:
                        style_name = f"Scale_{self.uid}.Horizontal.TScale"
                        widget.configure(style=style_name)
                    # 垂直滑块
                    elif "Vertical" in widget_class:
                        style_name = f"Scale_{self.uid}.Vertical.TScale"
                        widget.configure(style=style_name)
                    # 默认水平滑块
                    else:
                        style_name = f"Scale_{self.uid}.Horizontal.TScale"
                        widget.configure(style=style_name)

                # 处理其他ttk组件
                elif widget_class == "TCheckbutton":
                    widget.configure(style=f"Check_{self.uid}.TCheckbutton")
                elif widget_class == "TRadiobutton":
                    widget.configure(style=f"Radio_{self.uid}.TRadiobutton")
                elif widget_class == "TCombobox":
                    widget.configure(style=f"Combo_{self.uid}.TCombobox")

                # 强制设置背景色（如果需要）
                if force_bg:
                    self._force_set_background(widget, self.bg_color)

            # 递归处理子组件
            for child in widget.winfo_children():
                self._apply_style_to_widget(child, force_bg=force_bg)

        except Exception as e:
            logger.debug(f"应用样式失败: {str(e)}")

    def bind_toggle_callback(self, callback):
        """绑定切换状态的回调函数"""
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
