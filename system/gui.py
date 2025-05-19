"""
GUI模块 - 提供现代化桌面应用程序界面 (清晰的侧边栏菜单和主工作区)
"""

import os
import time
import logging
import threading
import platform  # 添加这一行以导入platform模块
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import cv2
from shutil import copy
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import Counter

import sv_ttk  # Sun Valley ttk theme for Windows 11 style

from system.config import (
    APP_TITLE, APP_VERSION, PADDING, BUTTON_WIDTH,
    LARGE_FONT, NORMAL_FONT, SMALL_FONT, SUPPORTED_IMAGE_EXTENSIONS
)
from system.utils import resource_path
from system.image_processor import ImageProcessor
from system.metadata_extractor import ImageMetadataExtractor
from system.data_processor import DataProcessor
from system.ui_components import ModernFrame, InfoBar, SpeedProgressBar
from system.settings_manager import SettingsManager
from system.ui_components import CollapsiblePanel

logger = logging.getLogger(__name__)

class ObjectDetectionGUI:
    """物种检测GUI应用程序 - Windows 11风格界面"""

    def __init__(self, master: tk.Tk, settings_manager: Optional[SettingsManager] = None,
                 settings: Optional[Dict[str, Any]] = None, cache_data: Optional[Dict[str, Any]] = None,
                 resume_processing: bool = False):
        """初始化GUI应用

        Args:
            master: Tkinter主窗口
            settings_manager: 设置管理器实例
            settings: 加载的设置数据
            cache_data: 处理缓存数据
            resume_processing: 是否继续上次的处理
        """
        self.master = master
        master.title(APP_TITLE)

        import torch
        # 检查CUDA可用性
        self.cuda_available = torch.cuda.is_available()

        # 保存设置管理器
        self.settings_manager = settings_manager

        # 缓存数据和恢复标志
        self.cache_data = cache_data
        self.resume_processing = resume_processing

        self._apply_system_theme()

        # 设置窗口尺寸和位置
        width, height = 900, 700  # 增加窗口宽度以适应侧边栏
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        master.geometry(f"{width}x{height}+{x}+{y}")
        master.minsize(width, height)  # 设置最小窗口尺寸

        # 设置窗口图标
        try:
            ico_path = resource_path(os.path.join("res", "ico.ico"))
            master.iconbitmap(ico_path)
        except Exception as e:
            logger.warning(f"无法加载窗口图标: {e}")

        # 初始化模型
        model_path = resource_path(os.path.join("res", "predict.pt"))
        self.image_processor = ImageProcessor(model_path)
        # 保存当前使用的模型路径和名称
        self.image_processor.model_path = model_path

        # 状态变量
        self.is_processing = False
        self.processing_stop_flag = threading.Event()
        self.preview_image = None
        self.current_detection_results = None
        self.original_image = None  # 保存原始图像
        self.current_image_path = None  # 保存当前图像路径
        self.current_page = "settings"  # 当前显示的页面

        # 处理进度缓存相关变量
        self.cache_interval = 10  # 每处理10张图片保存一次缓存
        self.excel_data = []  # 保存处理结果数据

        # 创建GUI元素
        self._create_ui_elements()
        self._setup_styles()

        # 加载设置到UI
        if settings:
            self._load_settings_to_ui(settings)

        # 绑定事件
        self._bind_events()

        # 检查模型是否加载成功
        if not self.image_processor.model:
            messagebox.showerror("错误", "模型文件未找到。请检查应用程序目录中的模型文件。")
            self.start_stop_button["state"] = "disabled"

        # 如果需要继续上次处理，自动开始处理
        if self.resume_processing and self.cache_data:
            # 设置延迟，确保UI已完全加载
            self.master.after(1000, self._resume_processing)

        self.setup_theme_monitoring()


    def _resume_processing(self) -> None:
        """继续上次未完成的处理任务"""
        if not self.cache_data:
            return

        # 从缓存中恢复数据
        file_path = self.cache_data.get('file_path', '')
        save_path = self.cache_data.get('save_path', '')
        save_detect_image = self.cache_data.get('save_detect_image', True)
        output_excel = self.cache_data.get('output_excel', True)
        copy_img = self.cache_data.get('copy_img', False)
        use_fp16 = self.cache_data.get('use_fp16', False)
        processed_files = self.cache_data.get('processed_files', 0)
        self.excel_data = self.cache_data.get('excel_data', [])

        # 检查路径是否有效
        if not self._validate_inputs(file_path, save_path):
            return

        # 更新UI
        self.file_path_entry.delete(0, tk.END)
        self.file_path_entry.insert(0, file_path)
        self.save_path_entry.delete(0, tk.END)
        self.save_path_entry.insert(0, save_path)
        self.save_detect_image_var.set(save_detect_image)
        self.output_excel_var.set(output_excel)
        self.copy_img_var.set(copy_img)
        self.use_fp16_var.set(use_fp16)

        # 更新文件列表
        self.update_file_list(file_path)

        # 显示继续处理的消息
        self.status_bar.status_label.config(text=f"准备继续处理，已处理: {processed_files} 张")

        # 自动开始处理
        self.start_processing(resume_from=processed_files)

    def _apply_system_theme(self) -> None:
        """应用与系统匹配的主题"""
        try:
            # 尝试获取系统主题颜色
            import darkdetect
            system_theme = darkdetect.theme().lower()  # 返回 'Dark' 或 'Light'

            if system_theme == 'dark':
                sv_ttk.set_theme("dark")
                self.is_dark_mode = True
            else:
                sv_ttk.set_theme("light")
                self.is_dark_mode = False

            logger.info(f"已应用系统主题: {system_theme}")

            # 获取系统强调色
            self._detect_system_accent_color()

        except Exception as e:
            # 如果无法检测系统主题，默认使用亮色主题
            sv_ttk.set_theme("light")
            self.is_dark_mode = False
            logger.warning(f"无法检测系统主题，使用默认亮色主题: {e}")

    def _detect_system_accent_color(self) -> None:
        """检测系统强调色并应用"""
        try:
            # 根据操作系统类型检测系统强调色
            system = platform.system()

            if system == "Windows":
                import winreg
                registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\DWM")
                # 获取十六进制的颜色值并转换
                color_dword = winreg.QueryValueEx(key, "AccentColor")[0]
                # Windows存储AABBGGRR格式，转换为RRGGBB格式
                color_hex = f"#{color_dword & 0xFF:02x}{(color_dword >> 8) & 0xFF:02x}{(color_dword >> 16) & 0xFF:02x}"
                self.accent_color = color_hex

            elif system == "Darwin":  # macOS
                # macOS获取强调色较复杂，需要使用Apple Script或其他方法
                # 这里使用默认的系统蓝色
                self.accent_color = "#0078d7"

            else:  # Linux等其他系统
                # 使用默认蓝色
                self.accent_color = "#0078d7"

            logger.info(f"获取到系统强调色: {self.accent_color}")

        except Exception as e:
            # 如果无法获取系统强调色，使用默认的蓝色
            self.accent_color = "#0078d7"
            logger.warning(f"无法获取系统强调色，使用默认颜色: {e}")

    def setup_theme_monitoring(self):
        """设置主题监控，每隔一段时间检查系统主题是否变化"""
        if platform.system() == "Windows" or platform.system() == "Darwin":  # Windows或macOS
            # 每10秒检查一次主题变化
            self._check_theme_change()

    def _check_theme_change(self):
        """检查系统主题是否发生变化"""
        try:
            import darkdetect
            current_theme = darkdetect.theme().lower()

            if (current_theme == 'dark' and not self.is_dark_mode) or \
                    (current_theme == 'light' and self.is_dark_mode):
                # 主题已经改变，需要更新
                self._apply_system_theme()
                self._setup_styles()  # 重新应用样式

                # 更新UI组件的样式
                self._update_ui_theme()

                logger.info(f"系统主题已变更为: {current_theme}")
        except Exception as e:
            logger.warning(f"检查主题变化失败: {e}")

        # 10秒后再次检查
        self.master.after(10000, self._check_theme_change)

    def _update_ui_theme(self):
        """更新UI组件的主题样式"""
        # 更新侧边栏的背景色
        if hasattr(self, 'sidebar'):
            sidebar_bg = "#1e1e1e" if self.is_dark_mode else "#2c3e50"
            for widget in self.sidebar.winfo_children():
                if hasattr(widget, 'configure'):
                    try:
                        if isinstance(widget, ttk.Label) or isinstance(widget, ttk.Frame):
                            widget.configure(background=sidebar_bg)
                    except:
                        pass

        # 更新当前选中的导航按钮
        self._show_page(self.current_page)

    def _setup_styles(self):
        """设置自定义样式"""
        style = ttk.Style()

        # 使用系统强调色作为侧边栏颜色
        if not hasattr(self, 'accent_color'):
            self.accent_color = "#0078d7"  # 默认值

        sidebar_bg = self.accent_color  # 使用系统强调色作为侧边栏背景

        # 计算适合的文字颜色 (根据背景色亮度)
        # 将十六进制颜色转换为RGB
        r = int(sidebar_bg[1:3], 16)
        g = int(sidebar_bg[3:5], 16)
        b = int(sidebar_bg[5:7], 16)

        # 计算亮度
        brightness = (r * 299 + g * 587 + b * 114) / 1000

        # 亮度高于128使用黑色文字，否则使用白色文字
        sidebar_fg = "#000000" if brightness > 128 else "#ffffff"

        # 计算更深/更浅的背景色用于悬停和选中效果
        # 如果背景色较亮，为了悬停效果更明显，使其变暗
        # 如果背景色较暗，则使其变亮
        if brightness > 128:
            # 使颜色变暗
            factor = 0.8
            r_hover = max(0, int(r * factor))
            g_hover = max(0, int(g * factor))
            b_hover = max(0, int(b * factor))

            # 使选中色更暗
            factor_selected = 0.7
            r_selected = max(0, int(r * factor_selected))
            g_selected = max(0, int(g * factor_selected))
            b_selected = max(0, int(b * factor_selected))
        else:
            # 使颜色变亮
            factor = 1.2
            r_hover = min(255, int(r * factor))
            g_hover = min(255, int(g * factor))
            b_hover = min(255, int(b * factor))

            # 使选中色更亮
            factor_selected = 1.3
            r_selected = min(255, int(r * factor_selected))
            g_selected = min(255, int(g * factor_selected))
            b_selected = min(255, int(b * factor_selected))

        sidebar_hover_bg = f"#{r_hover:02x}{g_hover:02x}{b_hover:02x}"
        sidebar_selected_bg = f"#{r_selected:02x}{g_selected:02x}{b_selected:02x}"

        # 侧边栏样式
        style.configure("Sidebar.TFrame", background=sidebar_bg)

        # 创建圆角按钮样式 - 由于ttk不直接支持圆角，需要使用Canvas或自定义Frame实现
        # 这里我们先设置好基本样式，然后在创建按钮时额外处理
        style.configure("Sidebar.TButton",
                        font=("Segoe UI", 11),
                        background=sidebar_bg,
                        foreground=sidebar_fg,
                        borderwidth=0,
                        focusthickness=0,
                        relief="flat",
                        padding=(10, 15),
                        anchor="w")

        # 侧边栏按钮激活/悬停样式
        style.map("Sidebar.TButton",
                  background=[("active", sidebar_hover_bg), ("pressed", sidebar_selected_bg)],
                  foreground=[("active", sidebar_fg), ("pressed", sidebar_fg)])

        # 侧边栏选中按钮样式
        style.configure("SidebarSelected.TButton",
                        background=sidebar_selected_bg,
                        foreground=sidebar_fg,
                        font=("Segoe UI", 11, "bold"),
                        borderwidth=0,
                        focusthickness=0,
                        relief="flat",
                        padding=(10, 15),
                        anchor="w")

        # 内容区标题样式
        style.configure("Title.TLabel",
                        font=("Segoe UI", 14, "bold"),
                        padding=(0, 10, 0, 10))

        # 开始处理按钮样式
        style.configure("Process.TButton",
                        font=("Segoe UI", 11),
                        padding=(10, 5))

    def _create_ui_elements(self) -> None:
        """创建GUI界面元素"""
        # 主布局 - 使用网格布局
        self.master.columnconfigure(1, weight=1)
        self.master.rowconfigure(0, weight=1)

        # 创建侧边栏
        self._create_sidebar()

        # 创建主要内容区域
        self.content_frame = ttk.Frame(self.master)
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        # 创建各个页面
        self._create_settings_page()
        self._create_preview_page()
        self._create_advanced_page()
        self._create_about_page()

        # 默认显示基本设置页面
        self._show_page("settings")

        # 底部状态栏
        self.status_bar = InfoBar(self.master)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

        # 初始化模型列表（如果高级页面已创建）
        if hasattr(self, 'model_listbox'):
            self.refresh_model_list()

    def _create_sidebar(self) -> None:
        """创建侧边栏菜单"""
        # 使用系统强调色作为侧边栏背景
        sidebar_bg = self.accent_color if hasattr(self, 'accent_color') else "#0078d7"

        # 计算适合的文字颜色
        # 将十六进制颜色转换为RGB
        r = int(sidebar_bg[1:3], 16)
        g = int(sidebar_bg[3:5], 16)
        b = int(sidebar_bg[5:7], 16)

        # 计算亮度
        brightness = (r * 299 + g * 587 + b * 114) / 1000

        # 亮度高于128使用黑色文字，否则使用白色文字
        sidebar_fg = "#000000" if brightness > 128 else "#ffffff"

        # 创建侧边栏框架
        self.sidebar = ttk.Frame(self.master, style="Sidebar.TFrame", width=180)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)  # 防止框架大小随内容变化

        # 创建应用标题/Logo
        logo_frame = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        logo_frame.pack(fill="x", pady=(20, 30))

        # 尝试加载Logo
        try:
            logo_path = resource_path(os.path.join("res", "logo.png"))
            logo_img = Image.open(logo_path)
            logo_img = logo_img.resize((50, 50), Image.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_img)
            logo_label = ttk.Label(logo_frame, image=logo_photo, background=sidebar_bg)
            logo_label.image = logo_photo  # 保持引用
            logo_label.pack(pady=(0, 5))
        except Exception:
            pass

        # 应用名称标签
        app_name = ttk.Label(
            logo_frame,
            text="动物检测系统",
            font=("Segoe UI", 12, "bold"),
            foreground=sidebar_fg,
            background=sidebar_bg
        )
        app_name.pack()

        # 创建分隔线
        sep = ttk.Separator(self.sidebar, orient="horizontal")
        sep.pack(fill="x", padx=15, pady=10)

        # 创建侧边栏按钮
        self.nav_buttons = {}

        # 定义菜单项
        menu_items = [
            ("settings", "基本设置"),
            ("preview", "图像预览"),
            ("advanced", "高级设置"),
            ("about", "关于")
        ]

        # 创建按钮容器 - 使用普通的tk.Frame以便能设置背景色
        buttons_frame = tk.Frame(self.sidebar, bg=sidebar_bg)
        buttons_frame.pack(fill="x", padx=10, pady=5)

        # 计算更深/更浅的背景色用于悬停和选中效果
        if brightness > 128:
            # 使颜色变暗
            factor_selected = 0.7
            r_selected = max(0, int(r * factor_selected))
            g_selected = max(0, int(g * factor_selected))
            b_selected = max(0, int(b * factor_selected))
        else:
            # 使颜色变亮
            factor_selected = 1.3
            r_selected = min(255, int(r * factor_selected))
            g_selected = min(255, int(g * factor_selected))
            b_selected = min(255, int(b * factor_selected))

        sidebar_selected_bg = f"#{r_selected:02x}{g_selected:02x}{b_selected:02x}"

        # 创建圆角按钮
        from system.ui_components import RoundedButton

        for page_id, page_name in menu_items:
            button = RoundedButton(
                buttons_frame,
                text=page_name,
                command=lambda p=page_id: self._show_page(p),
                bg=sidebar_bg,
                fg=sidebar_fg,
                width=160,
                height=40,
                radius=15  # 圆角半径
            )
            button.pack(fill="x", pady=3)
            self.nav_buttons[page_id] = button

        # 为了填充空间，添加一个空的Frame
        spacer = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        spacer.pack(fill="both", expand=True)

        # 添加版本信息
        version_label = ttk.Label(
            self.sidebar,
            text=f"V{APP_VERSION}",
            foreground=sidebar_fg,
            background=sidebar_bg,
            font=("Segoe UI", 8)
        )
        version_label.pack(pady=(0, 10))

    def _show_page(self, page_id: str) -> None:
        """显示指定页面并隐藏其他页面"""
        # 更新侧边栏按钮状态
        for pid, button in self.nav_buttons.items():
            if pid == page_id:
                button.set_active(True)
            else:
                button.set_active(False)

        # 隐藏所有页面
        self.settings_page.pack_forget()
        self.preview_page.pack_forget()
        self.advanced_page.pack_forget()
        self.about_page.pack_forget()

        # 显示选中的页面
        if page_id == "settings":
            self.settings_page.pack(fill="both", expand=True)
        elif page_id == "preview":
            self.preview_page.pack(fill="both", expand=True)
            # 如果有文件路径，更新文件列表
            file_path = self.file_path_entry.get()
            if file_path and os.path.isdir(file_path):
                if self.file_listbox.size() == 0:
                    self.update_file_list(file_path)
                # 如果有文件且没有选择，则选择第一个
                if self.file_listbox.size() > 0 and not self.file_listbox.curselection():
                    self.file_listbox.selection_set(0)
                    self.on_file_selected(None)
        elif page_id == "advanced":
            self.advanced_page.pack(fill="both", expand=True)
        elif page_id == "about":
            self.about_page.pack(fill="both", expand=True)

        # 保存当前页面ID
        self.current_page = page_id

    def _create_settings_page(self) -> None:
        """创建基本设置页面"""
        self.settings_page = ttk.Frame(self.content_frame)

        # 页面标题
        title_frame = ttk.Frame(self.settings_page)
        title_frame.pack(fill="x", padx=20, pady=(20, 10))

        title = ttk.Label(title_frame, text="基本设置", style="Title.TLabel")
        title.pack(side="left")

        # 路径设置区域
        paths_frame = ttk.LabelFrame(self.settings_page, text="路径设置")
        paths_frame.pack(fill="x", padx=20, pady=10)

        # 文件路径
        file_path_frame = ttk.Frame(paths_frame)
        file_path_frame.pack(fill="x", padx=10, pady=10)

        file_path_label = ttk.Label(file_path_frame, text="图像文件路径:")
        file_path_label.pack(side="top", anchor="w")

        file_path_entry_frame = ttk.Frame(file_path_frame)
        file_path_entry_frame.pack(fill="x", pady=5)

        self.file_path_entry = ttk.Entry(file_path_entry_frame)
        self.file_path_entry.pack(side="left", fill="x", expand=True)

        self.file_path_button = ttk.Button(
            file_path_entry_frame, text="浏览", command=self.browse_file_path, width=8)
        self.file_path_button.pack(side="right", padx=(5, 0))

        # 保存路径
        save_path_frame = ttk.Frame(paths_frame)
        save_path_frame.pack(fill="x", padx=10, pady=10)

        save_path_label = ttk.Label(save_path_frame, text="结果保存路径:")
        save_path_label.pack(side="top", anchor="w")

        save_path_entry_frame = ttk.Frame(save_path_frame)
        save_path_entry_frame.pack(fill="x", pady=5)

        self.save_path_entry = ttk.Entry(save_path_entry_frame)
        self.save_path_entry.pack(side="left", fill="x", expand=True)

        self.save_path_button = ttk.Button(
            save_path_entry_frame, text="浏览", command=self.browse_save_path, width=8)
        self.save_path_button.pack(side="right", padx=(5, 0))

        # 功能选项区域
        options_frame = ttk.LabelFrame(self.settings_page, text="功能选项")
        options_frame.pack(fill="x", padx=20, pady=10)

        # 创建选项
        self.save_detect_image_var = tk.BooleanVar(value=True)
        self.output_excel_var = tk.BooleanVar(value=True)
        self.copy_img_var = tk.BooleanVar(value=False)
        self.use_fp16_var = tk.BooleanVar(value=False)

        options_container = ttk.Frame(options_frame)
        options_container.pack(fill="x", padx=10, pady=10)

        # 使用网格布局来组织选项
        save_detect_switch = ttk.Checkbutton(
            options_container, text="保存探测结果图片", variable=self.save_detect_image_var)
        save_detect_switch.grid(row=0, column=0, sticky="w", pady=5, padx=10)

        output_excel_switch = ttk.Checkbutton(
            options_container, text="输出为Excel表格", variable=self.output_excel_var)
        output_excel_switch.grid(row=1, column=0, sticky="w", pady=5, padx=10)

        copy_img_switch = ttk.Checkbutton(
            options_container, text="按物种分类图片", variable=self.copy_img_var)
        copy_img_switch.grid(row=2, column=0, sticky="w", pady=5, padx=10)

        # 处理控制区域 - 只在基本设置页面显示
        process_frame = ttk.Frame(self.settings_page)
        process_frame.pack(fill="x", padx=20, pady=20)

        # 进度条和信息
        self.progress_frame = SpeedProgressBar(process_frame)
        self.progress_frame.pack(fill="x", pady=10)

        # 开始处理按钮
        self.start_stop_button = ttk.Button(
            process_frame,
            text="▶ 开始处理",
            command=self.toggle_processing_state,
            style="Process.TButton",
            width=15)
        self.start_stop_button.pack(side="right", pady=0)

    def _create_preview_page(self) -> None:
        """创建图像预览页面"""
        self.preview_page = ttk.Frame(self.content_frame)

        # 页面标题
        title_frame = ttk.Frame(self.preview_page)
        title_frame.pack(fill="x", padx=20, pady=(20, 10))

        title = ttk.Label(title_frame, text="图像预览", style="Title.TLabel")
        title.pack(side="left")

        # 创建预览区域
        preview_content = ttk.Frame(self.preview_page)
        preview_content.pack(fill="both", expand=True, padx=20, pady=10)

        # 左侧文件列表
        list_frame = ttk.LabelFrame(preview_content, text="图像文件")
        list_frame.pack(side="left", fill="y", padx=(0, 10))

        self.file_listbox = tk.Listbox(list_frame, width=25, font=NORMAL_FONT)
        self.file_listbox.pack(side="left", fill="both", expand=True)

        file_list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        file_list_scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=file_list_scrollbar.set)

        # 右侧预览区域
        preview_right = ttk.Frame(preview_content)
        preview_right.pack(side="right", fill="both", expand=True)

        # 预览图像区域
        image_frame = ttk.LabelFrame(preview_right, text="图像预览")
        image_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.image_label = ttk.Label(image_frame, text="请从左侧列表选择图像", anchor="center")
        self.image_label.pack(fill="both", expand=True, padx=10, pady=10)

        # 添加图像信息区域
        info_frame = ttk.LabelFrame(preview_right, text="图像信息")
        info_frame.pack(fill="x", pady=(0, 10))

        self.info_text = tk.Text(info_frame, height=3, font=NORMAL_FONT, wrap="word")
        self.info_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.info_text.config(state="disabled")

        # 预览控制区域
        control_frame = ttk.Frame(preview_right)
        control_frame.pack(fill="x")

        # 显示检测结果开关
        self.show_detection_var = tk.BooleanVar(value=False)
        show_detection_switch = ttk.Checkbutton(
            control_frame, text="显示检测结果", variable=self.show_detection_var,
            command=self.toggle_detection_preview)
        show_detection_switch.pack(side="left")

        # 检测按钮
        self.detect_button = ttk.Button(
            control_frame, text="检测当前图像", command=self.detect_current_image, width=12)
        self.detect_button.pack(side="right")

    def _create_advanced_page(self) -> None:
        """创建高级设置页面，使用标签页分隔功能"""
        self.advanced_page = ttk.Frame(self.content_frame)

        # 页面标题
        title_frame = ttk.Frame(self.advanced_page)
        title_frame.pack(fill="x", padx=20, pady=(20, 10))

        title = ttk.Label(title_frame, text="高级设置", style="Title.TLabel")
        title.pack(side="left")

        # 创建标签页控件
        self.advanced_notebook = ttk.Notebook(self.advanced_page)
        self.advanced_notebook.pack(fill="both", expand=True, padx=20, pady=10)

        # 创建模型参数设置标签页
        self.model_params_tab = ttk.Frame(self.advanced_notebook)
        self.advanced_notebook.add(self.model_params_tab, text="模型参数设置")

        # 创建环境维护标签页
        self.env_maintenance_tab = ttk.Frame(self.advanced_notebook)
        self.advanced_notebook.add(self.env_maintenance_tab, text="环境维护")

        # 绑定标签页切换事件
        self.advanced_notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # 填充模型参数设置标签页内容
        self._create_model_params_content()

        # 填充环境维护标签页内容
        self._create_env_maintenance_content()

        # 按钮区域 (共享区域，位于标签页下方)
        buttons_frame = ttk.Frame(self.advanced_page)
        buttons_frame.pack(fill="x", padx=20, pady=10)

        # 查看参数说明按钮
        help_button = ttk.Button(
            buttons_frame, text="查看参数说明", command=self.show_params_help, width=12)
        help_button.pack(side="left")

        # 恢复默认参数按钮
        reset_button = ttk.Button(
            buttons_frame, text="恢复默认参数", command=self._reset_model_params, width=12)
        reset_button.pack(side="right")

        # 确保在初始化后面板能正确显示
        self.advanced_notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # 初次显示页面时，确保环境维护标签页内容正确加载
        self.master.after(500, lambda: self._ensure_env_maintenance_visible())

    def _ensure_env_maintenance_visible(self):
        """确保环境维护标签页在初始加载时内容可见"""
        if hasattr(self, 'env_content_frame') and hasattr(self, 'env_canvas'):
            self.env_content_frame.update_idletasks()
            self.env_canvas.configure(scrollregion=self.env_canvas.bbox("all"))


    def _create_model_params_content(self) -> None:
        """创建模型参数设置标签页内容"""
        # 模型参数设置
        params_frame = ttk.LabelFrame(self.model_params_tab, text="模型参数设置")
        params_frame.pack(fill="x", pady=10)

        # 参数内容框架
        params_content = ttk.Frame(params_frame)
        params_content.pack(fill="x", padx=10, pady=10)

        # 初始化模型参数变量
        self.iou_var = tk.DoubleVar(value=0.3)  # IOU阈值，默认0.3
        self.conf_var = tk.DoubleVar(value=0.25)  # 置信度阈值，默认0.25
        self.use_augment_var = tk.BooleanVar(value=True)  # 数据增强，默认开启
        self.use_agnostic_nms_var = tk.BooleanVar(value=True)  # 类别无关NMS，默认开启
        self.current_path = None

        # IOU阈值滑动条
        ttk.Label(params_content, text="IOU阈值:").grid(row=0, column=0, sticky="w", pady=(10, 0))

        iou_frame = ttk.Frame(params_content)
        iou_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        iou_scale = ttk.Scale(iou_frame, from_=0.1, to=0.9, orient="horizontal",
                              variable=self.iou_var, command=self._update_iou_label)
        iou_scale.pack(side="left", fill="x", expand=True)

        self.iou_label = ttk.Label(iou_frame, text="0.30", width=4)
        self.iou_label.pack(side="right", padx=(10, 0))

        # 置信度阈值滑动条
        ttk.Label(params_content, text="置信度阈值:").grid(row=2, column=0, sticky="w", pady=(10, 0))

        conf_frame = ttk.Frame(params_content)
        conf_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        conf_scale = ttk.Scale(conf_frame, from_=0.05, to=0.95, orient="horizontal",
                               variable=self.conf_var, command=self._update_conf_label)
        conf_scale.pack(side="left", fill="x", expand=True)

        self.conf_label = ttk.Label(conf_frame, text="0.25", width=4)
        self.conf_label.pack(side="right", padx=(10, 0))

        # 模型优化选项
        options_frame = ttk.LabelFrame(self.model_params_tab, text="模型优化选项")
        options_frame.pack(fill="x", pady=10)

        options_content = ttk.Frame(options_frame)
        options_content.pack(fill="x", padx=10, pady=10)

        # FP16加速
        fp16_frame = ttk.Frame(options_content)
        fp16_frame.pack(fill="x", pady=5)

        fp16_switch = ttk.Checkbutton(
            fp16_frame, text="使用FP16加速推理", variable=self.use_fp16_var)
        fp16_switch.pack(anchor="w")

        # 如果CUDA不可用，禁用FP16开关
        if not self.cuda_available:
            fp16_switch["state"] = "disabled"
            self.use_fp16_var.set(False)

        fp16_desc = ttk.Label(
            fp16_frame,
            text="减少内存使用并提高速度，可能略微降低精度",
            font=SMALL_FONT,
            foreground="gray")
        fp16_desc.pack(anchor="w", padx=25, pady=(0, 5))

        # 数据增强
        augment_frame = ttk.Frame(options_content)
        augment_frame.pack(fill="x", pady=5)

        augment_switch = ttk.Checkbutton(
            augment_frame, text="使用数据增强", variable=self.use_augment_var)
        augment_switch.pack(anchor="w")

        augment_desc = ttk.Label(
            augment_frame,
            text="通过测试时增强提高检测准确性，但会降低速度",
            font=SMALL_FONT,
            foreground="gray")
        augment_desc.pack(anchor="w", padx=25, pady=(0, 5))

        # 类别无关NMS
        nms_frame = ttk.Frame(options_content)
        nms_frame.pack(fill="x", pady=5)

        agnostic_nms_switch = ttk.Checkbutton(
            nms_frame, text="使用类别无关NMS", variable=self.use_agnostic_nms_var)
        agnostic_nms_switch.pack(anchor="w")

        agnostic_nms_desc = ttk.Label(
            nms_frame,
            text="忽略类别信息进行非极大值抑制，对多类别场景有优势",
            font=SMALL_FONT,
            foreground="gray")
        agnostic_nms_desc.pack(anchor="w", padx=25, pady=(0, 5))

    def _create_model_selection_card(self, parent) -> None:
        """创建模型选择折叠卡片 - 与PyTorch安装卡片风格一致"""
        # 创建折叠卡片框架
        card_frame = ttk.Frame(parent)
        card_frame.pack(fill="x", pady=5)

        # 创建标题栏
        header_frame = ttk.Frame(card_frame)
        header_frame.pack(fill="x")

        # 使用系统强调色的变体作为卡片标题背景
        if hasattr(self, 'accent_color'):
            r = int(self.accent_color[1:3], 16)
            g = int(self.accent_color[3:5], 16)
            b = int(self.accent_color[5:7], 16)

            # 计算亮度
            brightness = (r * 299 + g * 587 + b * 114) / 1000

            # 根据亮度选择文字颜色
            text_color = "#000000" if brightness > 128 else "#ffffff"

            # 创建标题标签
            header_style = ttk.Style()
            header_style.configure("CardHeader.TLabel",
                                   background=self.accent_color,
                                   foreground=text_color,
                                   font=("Segoe UI", 11, "bold"),
                                   padding=(10, 5))

            header = ttk.Label(header_frame, text="模型选择", style="CardHeader.TLabel")
        else:
            header = ttk.Label(header_frame, text="模型选择", font=("Segoe UI", 11, "bold"))

        header.pack(side="left", fill="x", expand=True)

        # 添加展开/折叠按钮
        self.model_expanded = tk.BooleanVar(value=False)  # 默认折叠
        toggle_btn = ttk.Button(header_frame, text="▼", width=3,
                                command=lambda: self._toggle_card("model"))
        toggle_btn.pack(side="right", padx=5)

        # 添加内容区域
        content_frame = ttk.Frame(card_frame, padding=(15, 10))
        content_frame.pack(fill="x", expand=True)

        # 初始隐藏内容
        content_frame.pack_forget()

        # 存储卡片信息
        self.advanced_cards["model"] = {
            "content": content_frame,
            "toggle_btn": toggle_btn,
            "expanded": self.model_expanded
        }

        # 显示当前模型
        current_model_frame = ttk.Frame(content_frame)
        current_model_frame.pack(fill="x", pady=5)

        ttk.Label(current_model_frame, text="当前模型:").pack(side="left", padx=(0, 10))

        current_model_name = os.path.basename(self.image_processor.model_path) if hasattr(self.image_processor,
                                                                                          'model_path') else "未知"
        self.current_model_var = tk.StringVar(value=current_model_name)
        current_model_label = ttk.Label(current_model_frame, textvariable=self.current_model_var,
                                        font=("Segoe UI", 9, "bold"))
        current_model_label.pack(side="left")

        # 添加模型选择
        model_select_frame = ttk.Frame(content_frame)
        model_select_frame.pack(fill="x", pady=(10, 5))

        ttk.Label(model_select_frame, text="选择模型:").pack(side="left", padx=(0, 10))

        # 创建模型下拉菜单
        self.model_selection_var = tk.StringVar()
        self.model_combobox = ttk.Combobox(
            model_select_frame,
            textvariable=self.model_selection_var,
            state="readonly",
            width=30
        )
        self.model_combobox.pack(side="left", padx=(0, 5), fill="x", expand=True)

        # 刷新按钮
        refresh_btn = ttk.Button(
            model_select_frame,
            text="刷新",
            command=self._refresh_model_list,
            width=6
        )
        refresh_btn.pack(side="left")

        # 添加加载按钮
        load_frame = ttk.Frame(content_frame)
        load_frame.pack(fill="x", pady=(10, 5))

        self.load_model_btn = ttk.Button(
            load_frame,
            text="加载选中模型",
            command=self._apply_selected_model,
            width=15
        )
        self.load_model_btn.pack(side="right")

        # 模型状态框架
        status_frame = ttk.Frame(content_frame)
        status_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(status_frame, text="状态:").pack(side="left", padx=(0, 5))

        self.model_status_var = tk.StringVar(value="就绪")
        model_status = ttk.Label(status_frame, textvariable=self.model_status_var)
        model_status.pack(side="left")

        # 初始化加载模型列表
        self._refresh_model_list()

    def _create_env_maintenance_content(self) -> None:
        """创建环境维护标签页内容 - 简化版本"""
        # 清除旧内容
        for widget in self.env_maintenance_tab.winfo_children():
            widget.destroy()

        # 创建滚动视图容器
        self.env_scrollable = ttk.Frame(self.env_maintenance_tab)
        self.env_scrollable.pack(fill="both", expand=True)

        # 创建Canvas和滚动条
        self.env_canvas = tk.Canvas(self.env_scrollable, highlightthickness=0)
        self.env_canvas.pack(side="left", fill="both", expand=True)

        self.env_scrollbar = ttk.Scrollbar(self.env_scrollable, orient="vertical", command=self.env_canvas.yview)
        self.env_scrollbar.pack(side="right", fill="y")
        self.env_canvas.configure(yscrollcommand=self.env_scrollbar.set)

        # 创建内容框架
        self.env_content_frame = ttk.Frame(self.env_canvas)
        self.env_canvas_window = self.env_canvas.create_window(
            (0, 0),
            window=self.env_content_frame,
            anchor="nw",
            width=self.env_canvas.winfo_reqwidth()
        )

        # 确保系统变量已初始化
        if not hasattr(self, 'is_dark_mode'):
            self.is_dark_mode = False

        # 创建PyTorch安装面板
        self.pytorch_panel = CollapsiblePanel(
            self.env_content_frame,
            "安装 PyTorch",
            subtitle="安装 PyTorch 与 xFormers",
            icon="📦"
        )
        self.pytorch_panel.pack(fill="x", expand=False)

        # 版本选择下拉框
        version_frame = ttk.Frame(self.pytorch_panel.content_padding)
        version_frame.pack(fill="x", pady=5)

        version_label = ttk.Label(version_frame, text="选择版本")
        version_label.pack(side="top", anchor="w", pady=(0, 5))

        # PyTorch版本选择下拉框
        self.pytorch_version_var = tk.StringVar()
        versions = [
            "2.7.0 (CUDA 12.8)",
            "2.7.0 (CUDA 12.6)",
            "2.7.0 (CUDA 11.8)",
            "2.7.0 (CPU Only)",
        ]

        # 设置下拉框样式
        style = ttk.Style()
        style.configure("Dropdown.TCombobox", padding=(10, 5))

        version_combo = ttk.Combobox(
            version_frame,
            textvariable=self.pytorch_version_var,
            values=versions,
            state="readonly",
            style="Dropdown.TCombobox"
        )
        version_combo.pack(fill="x", expand=True)
        version_combo.current(0)  # 默认选择第一项

        # 仅安装必要组件选项
        options_frame = ttk.Frame(self.pytorch_panel.content_padding)
        options_frame.pack(fill="x", pady=10)

        self.minimal_install_var = tk.BooleanVar(value=False)
        minimal_switch = ttk.Checkbutton(
            options_frame,
            text="仅安装基础组件",
            variable=self.minimal_install_var
        )
        minimal_switch.pack(anchor="w")

        # 安装按钮和状态显示
        bottom_frame = ttk.Frame(self.pytorch_panel.content_padding)
        bottom_frame.pack(fill="x", pady=(10, 0))

        self.pytorch_status_var = tk.StringVar(value="")
        status_label = ttk.Label(bottom_frame, textvariable=self.pytorch_status_var)
        status_label.pack(side="left")

        self.install_button = ttk.Button(
            bottom_frame,
            text="安装",
            command=self._install_pytorch,
            style="Action.TButton"
        )
        style.configure("Action.TButton", font=("Segoe UI", 9))
        self.install_button.pack(side="right")

        # 创建模型管理面板
        self.model_panel = CollapsiblePanel(
            self.env_content_frame,
            "模型管理",
            subtitle="管理用于识别的模型",
            icon="🔧"
        )
        self.model_panel.pack(fill="x", expand=False, pady=(0, 1))

        # 添加模型列表和选择功能
        model_selection_frame = ttk.Frame(self.model_panel.content_padding)
        model_selection_frame.pack(fill="x", pady=5)

        model_label = ttk.Label(model_selection_frame, text="当前使用的模型")
        model_label.pack(anchor="w", pady=(0, 5))

        # 当前模型显示
        model_name = os.path.basename(self.image_processor.model_path) if hasattr(self.image_processor,
                                                                                  'model_path') else "未知"
        self.current_model_var = tk.StringVar(value=model_name)

        # 设置只读输入框样式
        style.configure("ReadOnly.TEntry", fieldbackground="#f0f0f0" if not self.is_dark_mode else "#3a3a3a")

        current_model_entry = ttk.Entry(
            model_selection_frame,
            textvariable=self.current_model_var,
            state="readonly",
            style="ReadOnly.TEntry"
        )
        current_model_entry.pack(fill="x", expand=True, pady=(0, 10))

        # 模型选择
        model_select_label = ttk.Label(model_selection_frame, text="选择可用模型")
        model_select_label.pack(anchor="w", pady=(0, 5))

        # 模型下拉框
        self.model_selection_var = tk.StringVar()
        self.model_combobox = ttk.Combobox(
            model_selection_frame,
            textvariable=self.model_selection_var,
            state="readonly",
            style="Dropdown.TCombobox"
        )
        self.model_combobox.pack(fill="x", expand=True)

        # 模型操作按钮
        model_buttons_frame = ttk.Frame(self.model_panel.content_padding)
        model_buttons_frame.pack(fill="x", pady=10)

        self.model_status_var = tk.StringVar(value="")
        model_status = ttk.Label(model_buttons_frame, textvariable=self.model_status_var)
        model_status.pack(side="left")

        # 添加刷新按钮
        refresh_btn = ttk.Button(
            model_buttons_frame,
            text="刷新列表",
            command=self._refresh_model_list,
            style="Secondary.TButton"
        )
        style.configure("Secondary.TButton", font=("Segoe UI", 9))
        refresh_btn.pack(side="right", padx=(0, 5))

        # 添加应用按钮
        apply_btn = ttk.Button(
            model_buttons_frame,
            text="应用模型",
            command=self._apply_selected_model,
            style="Action.TButton"
        )
        apply_btn.pack(side="right")

        # 创建Python组件管理面板
        self.python_panel = CollapsiblePanel(
            self.env_content_frame,
            "重装单个 Python 组件",
            subtitle="重新安装单个 Pip 软件包",
            icon="🐍"
        )
        self.python_panel.pack(fill="x", expand=False, pady=(0, 1))

        # 添加组件安装内容
        package_frame = ttk.Frame(self.python_panel.content_padding)
        package_frame.pack(fill="x", pady=5)

        package_label = ttk.Label(package_frame, text="输入包名称")
        package_label.pack(anchor="w", pady=(0, 5))

        self.package_var = tk.StringVar()
        package_entry = ttk.Entry(package_frame, textvariable=self.package_var)
        package_entry.pack(fill="x", expand=True)

        # 版本约束选项
        version_constraint_frame = ttk.Frame(self.python_panel.content_padding)
        version_constraint_frame.pack(fill="x", pady=10)

        version_label = ttk.Label(version_constraint_frame, text="版本约束 (可选)")
        version_label.pack(anchor="w", pady=(0, 5))

        self.version_constraint_var = tk.StringVar()
        version_entry = ttk.Entry(version_constraint_frame, textvariable=self.version_constraint_var)
        version_entry.pack(fill="x", expand=True)

        # 示例提示
        example_label = ttk.Label(
            version_constraint_frame,
            text="示例: ==1.0.0, >=2.0.0, <3.0.0",
            font=("Segoe UI", 8),
            foreground="#888888"
        )
        example_label.pack(anchor="w", pady=(2, 0))

        # 安装按钮
        package_buttons_frame = ttk.Frame(self.python_panel.content_padding)
        package_buttons_frame.pack(fill="x", pady=(10, 0))

        self.package_status_var = tk.StringVar(value="")
        package_status = ttk.Label(package_buttons_frame, textvariable=self.package_status_var)
        package_status.pack(side="left")

        install_package_btn = ttk.Button(
            package_buttons_frame,
            text="安装",
            command=self._install_python_package,
            style="Action.TButton"
        )
        install_package_btn.pack(side="right")

        # 初始化刷新模型列表
        self._refresh_model_list()

        # 初始检查PyTorch安装状态
        self._check_pytorch_status()

        # 设置面板折叠/展开事件处理
        for panel in [self.pytorch_panel, self.model_panel, self.python_panel]:
            panel.bind_toggle_callback(self._on_panel_toggle)

        # 配置滚动
        self._configure_env_scrolling()

        # 初始化显示
        self._refresh_model_list()
        self._check_pytorch_status()

    def _bind_scrollwheel(self):
        """绑定鼠标滚轮事件"""

        def _on_mousewheel(event):
            # 根据不同平台处理鼠标滚轮事件
            if event.state & 0x4:  # 在 Windows/Linux 上的 Control 键
                # 按住 Ctrl 滚动速度更快
                delta = 3
            else:
                delta = 1

            # 计算滚动方向和距离
            if platform.system() == "Windows":
                scroll_direction = -1 if event.delta > 0 else 1
            elif platform.system() == "Darwin":  # macOS
                scroll_direction = -1 if event.delta > 0 else 1
            else:  # Linux
                if event.num == 4:
                    scroll_direction = -1
                elif event.num == 5:
                    scroll_direction = 1
                else:
                    scroll_direction = 0

            # 移动所有可见内容，模拟滚动效果
            y_move = scroll_direction * delta * 20  # 调整滚动速度
            for widget in self.env_content_frame.winfo_children():
                widget.place(y=widget.winfo_y() - y_move)

            # 防止过度滚动导致顶部空白
            self._ensure_no_empty_space()

        # 根据不同平台绑定滚轮事件
        if platform.system() == "Windows":
            self.env_content_frame.bind_all("<MouseWheel>", _on_mousewheel)
        elif platform.system() == "Darwin":  # macOS
            self.env_content_frame.bind_all("<MouseWheel>", _on_mousewheel)
        else:  # Linux
            self.env_content_frame.bind_all("<Button-4>", _on_mousewheel)
            self.env_content_frame.bind_all("<Button-5>", _on_mousewheel)

    def _configure_env_scrolling(self):
        """配置环境维护标签页的滚动功能 - 简化版本"""

        # 更新滚动区域尺寸
        def _update_scrollregion(event=None):
            self.env_canvas.configure(scrollregion=self.env_canvas.bbox("all"))

        # 当Canvas大小改变时，调整窗口宽度
        def _configure_canvas(event):
            # 设置内容框架宽度与Canvas相同
            canvas_width = event.width
            self.env_canvas.itemconfigure(self.env_canvas_window, width=canvas_width)

        # 处理面板展开/折叠事件
        def _on_panel_toggle(panel, is_expanded):
            # 更新滚动区域
            self.env_content_frame.update_idletasks()
            _update_scrollregion()

        # 处理鼠标滚轮事件
        def _on_mousewheel(event):
            # 检查鼠标是否在canvas上
            x, y = self.env_canvas.winfo_pointerxy()
            canvas_x = self.env_canvas.winfo_rootx()
            canvas_y = self.env_canvas.winfo_rooty()
            canvas_width = self.env_canvas.winfo_width()
            canvas_height = self.env_canvas.winfo_height()

            if (x >= canvas_x and x <= canvas_x + canvas_width and
                    y >= canvas_y and y <= canvas_y + canvas_height):

                # Windows系统
                if hasattr(event, 'delta'):
                    self.env_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                # Linux系统
                elif hasattr(event, 'num'):
                    if event.num == 4:  # 向上滚动
                        self.env_canvas.yview_scroll(-1, "units")
                    elif event.num == 5:  # 向下滚动
                        self.env_canvas.yview_scroll(1, "units")

        # 绑定事件
        self.env_content_frame.bind("<Configure>", _update_scrollregion)
        self.env_canvas.bind("<Configure>", _configure_canvas)

        # 绑定面板切换事件
        for panel in [self.pytorch_panel, self.model_panel, self.python_panel]:
            panel.bind_toggle_callback(_on_panel_toggle)

        # 绑定鼠标滚轮事件，根据不同平台
        import platform
        if platform.system() == "Windows":
            self.env_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        else:  # Linux和macOS
            self.env_canvas.bind_all("<Button-4>", _on_mousewheel)
            self.env_canvas.bind_all("<Button-5>", _on_mousewheel)

        # 初始更新滚动区域
        self.env_content_frame.update_idletasks()
        self.env_canvas.configure(scrollregion=self.env_canvas.bbox("all"))

    def _ensure_no_empty_space(self):
        """确保没有顶部空白区域"""
        # 找到最顶部的元素
        top_y = float('inf')
        for widget in self.env_content_frame.winfo_children():
            widget_y = widget.winfo_y()
            if widget_y < top_y:
                top_y = widget_y

        # 如果顶部有空白，移动所有元素以消除空白
        if top_y > 0:
            for widget in self.env_content_frame.winfo_children():
                widget.place(y=widget.winfo_y() - top_y)

    def _on_panel_toggle(self, panel, is_expanded):
        """处理面板展开/折叠事件"""
        # 更新布局，确保所有面板正确显示
        self.env_content_frame.update_idletasks()

        # 如果折叠了面板，确保没有顶部空白
        if not is_expanded:
            self._ensure_no_empty_space()

        # 将面板置于正确的位置
        self._update_panels_position()

    def _update_panels_position(self):
        """更新所有面板的位置，确保它们正确排列"""
        # 当前y坐标位置
        y_pos = 0

        # 按照原始顺序重排面板
        for panel in [self.pytorch_panel, self.model_panel, self.python_panel]:
            panel.place(x=0, y=y_pos, relwidth=1)
            y_pos += panel.winfo_height() + 1  # 加1作为面板间间隔

    def _toggle_card(self, card_id: str) -> None:
        """切换折叠卡片的展开/收起状态"""
        if card_id in self.advanced_cards:
            card = self.advanced_cards[card_id]
            expanded = card["expanded"].get()

            if expanded:
                # 收起内容
                card["content"].pack_forget()
                card["toggle_btn"].configure(text="▼")
                card["expanded"].set(False)
            else:
                # 展开内容
                card["content"].pack(fill="x", expand=True)
                card["toggle_btn"].configure(text="▲")
                card["expanded"].set(True)

    def _browse_model(self) -> None:
        """浏览并选择模型文件"""
        # 尝试使用当前模型所在目录作为初始目录
        initial_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'res')
        if not os.path.exists(initial_dir):
            initial_dir = os.getcwd()

        model_path = filedialog.askopenfilename(
            title="选择模型文件",
            initialdir=initial_dir,
            filetypes=[("模型文件", "*.pt"), ("所有文件", "*.*")]
        )

        if model_path:
            self.model_path_var.set(model_path)
            # 保存到设置
            if self.settings_manager:
                self.settings_manager.set_setting("model_path", model_path)
                self.settings_manager.save_settings()

    def _refresh_model_list(self) -> None:
        """刷新模型下拉列表"""
        # 获取res目录
        res_dir = resource_path(os.path.join("res"))

        try:
            # 清空下拉列表
            self.model_combobox["values"] = []

            # 查找所有.pt模型文件
            if os.path.exists(res_dir):
                model_files = [f for f in os.listdir(res_dir) if f.lower().endswith('.pt')]

                if model_files:
                    # 排序并设置为下拉列表的值
                    model_files.sort()
                    self.model_combobox["values"] = model_files

                    # 选择第一个值
                    self.model_combobox.current(0)

                    # 尝试选择当前正在使用的模型
                    current_model = os.path.basename(self.image_processor.model_path) if hasattr(self.image_processor,
                                                                                                 'model_path') else None

                    if current_model in model_files:
                        self.model_combobox.set(current_model)

                    # 更新状态
                    self.model_status_var.set(f"找到 {len(model_files)} 个模型文件")
                else:
                    self.model_status_var.set("未找到任何模型文件")
            else:
                self.model_status_var.set("模型目录不存在")

        except Exception as e:
            logger.error(f"刷新模型列表失败: {e}")
            self.model_status_var.set(f"刷新失败: {str(e)}")

    def _apply_selected_model(self) -> None:
        """应用选中的模型"""
        # 获取选中的模型
        model_name = self.model_selection_var.get()

        if not model_name:
            messagebox.showinfo("提示", "请先选择一个模型")
            return

        # 构建完整路径
        model_path = resource_path(os.path.join("res", model_name))

        # 检查文件是否存在
        if not os.path.exists(model_path):
            messagebox.showerror("错误", f"模型文件不存在: {model_path}")
            return

        # 如果选中的就是当前使用的模型，无需再次加载
        current_model = os.path.basename(self.image_processor.model_path) if hasattr(self.image_processor,
                                                                                     'model_path') else None
        if model_name == current_model:
            messagebox.showinfo("提示", f"模型 {model_name} 已经加载")
            return

        # 确认切换模型
        if not messagebox.askyesno("确认", f"确定要切换到模型 {model_name} 吗？"):
            return

        # 更新状态
        self.model_status_var.set("正在加载...")
        self.master.update_idletasks()

        try:
            # 在独立线程中加载模型
            def load_model_thread():
                try:
                    # 加载模型
                    self.image_processor.load_model(model_path)

                    # 更新UI显示
                    self.master.after(0, lambda: self.current_model_var.set(model_name))
                    self.master.after(0, lambda: self.model_status_var.set("已加载"))
                    self.master.after(0, lambda: messagebox.showinfo("成功", f"模型 {model_name} 已成功加载"))

                except Exception as e:
                    logger.error(f"加载模型失败: {e}")
                    self.master.after(0, lambda: self.model_status_var.set(f"加载失败: {str(e)}"))
                    self.master.after(0, lambda: messagebox.showerror("错误", f"加载模型失败: {e}"))

            # 启动线程
            threading.Thread(target=load_model_thread, daemon=True).start()

        except Exception as e:
            logger.error(f"应用模型失败: {e}")
            self.model_status_var.set(f"加载失败: {str(e)}")
            messagebox.showerror("错误", f"应用模型失败: {e}")

    def _apply_model(self, model_path: str) -> None:
        """应用选择的模型"""
        if not model_path or not os.path.exists(model_path):
            messagebox.showerror("错误", "请先选择有效的模型文件")
            return

        # 确认切换模型
        if not messagebox.askyesno("确认",
                                   f"确定要切换到模型:\n{os.path.basename(model_path)}吗？\n\n"
                                   "这将重新加载模型，可能需要几秒钟时间。"):
            return

        # 显示加载中状态
        self.status_bar.status_label.config(text=f"正在加载模型...")
        self.master.update_idletasks()

        try:
            # 在单独线程中加载模型
            def load_model_thread():
                try:
                    # 加载模型
                    self.image_processor.load_model(model_path)

                    # 更新UI
                    self.master.after(0, lambda: self.status_bar.status_label.config(
                        text=f"模型已加载: {os.path.basename(model_path)}"))
                    self.master.after(0, lambda: messagebox.showinfo("成功", "模型已成功加载！"))
                except Exception as e:
                    logger.error(f"加载模型失败: {e}")
                    self.master.after(0, lambda: self.status_bar.status_label.config(text=f"加载模型失败: {e}"))
                    self.master.after(0, lambda: messagebox.showerror("错误", f"加载模型失败: {e}"))

            threading.Thread(target=load_model_thread, daemon=True).start()
        except Exception as e:
            self.status_bar.status_label.config(text=f"加载模型失败: {e}")
            messagebox.showerror("错误", f"加载模型失败: {e}")

    def _check_pytorch_status(self) -> None:
        """检查PyTorch安装状态"""
        try:
            import torch
            version = torch.__version__
            device = "GPU (CUDA)" if torch.cuda.is_available() else "CPU"
            self.pytorch_status_var.set(f"已安装 v{version} ({device})")
        except ImportError:
            self.pytorch_status_var.set("未安装")
        except Exception as e:
            self.pytorch_status_var.set(f"检查失败: {str(e)}")

    def _install_pytorch(self) -> None:
        """安装PyTorch"""
        # 获取版本
        version = self.pytorch_version_var.get()
        if not version:
            messagebox.showinfo("提示", "请选择PyTorch版本")
            return

        # 确认安装
        message = f"将安装 {version}"
        if self.minimal_install_var.get():
            message += "（仅基础组件）"

        if not messagebox.askyesno("确认安装", message + "\n\n是否继续？"):
            return

        # 解析版本信息
        is_cuda = "CPU" not in version
        cuda_version = None
        if is_cuda:
            if "CUDA 11.7" in version:
                cuda_version = "cu117"
            elif "CUDA 11.8" in version:
                cuda_version = "cu118"
            elif "CUDA 12.1" in version:
                cuda_version = "cu121"

        pytorch_version = re.search(r"PyTorch (\d+\.\d+\.\d+)", version).group(1)

        # 更新状态并禁用按钮
        self.install_button.configure(state="disabled")
        self.pytorch_status_var.set("准备安装...")
        self.master.update_idletasks()

        # 在线程中安装
        def install_thread():
            try:
                # 构建安装命令
                cmd = [sys.executable, "-m", "pip", "install"]

                # 添加PyTorch包和版本
                if is_cuda:
                    cmd.append(f"torch=={pytorch_version}+{cuda_version}")
                    cmd.extend(["-f", f"https://download.pytorch.org/whl/{cuda_version}/torch_stable.html"])
                else:
                    cmd.append(f"torch=={pytorch_version}+cpu")
                    cmd.extend(["-f", "https://download.pytorch.org/whl/cpu/torch_stable.html"])

                # 添加其他包
                if not self.minimal_install_var.get():
                    if is_cuda:
                        cmd.extend([f"torchvision=={pytorch_version}+{cuda_version}",
                                    f"torchaudio=={pytorch_version}+{cuda_version}"])
                    else:
                        cmd.extend([f"torchvision=={pytorch_version}+cpu", f"torchaudio=={pytorch_version}+cpu"])

                # 更新UI
                self.master.after(0, lambda: self.pytorch_status_var.set("正在安装..."))

                # 执行命令
                if platform.system() == "Windows":
                    process = subprocess.Popen(
                        f"start cmd /k \"{' '.join(cmd)} && echo PyTorch安装完成，请关闭此窗口 || echo PyTorch安装失败，请检查错误信息\"",
                        shell=True)
                else:  # Linux/Mac
                    process = subprocess.Popen(
                        f"gnome-terminal -- bash -c \"{' '.join(cmd)}; echo 'PyTorch安装完成，按任意键关闭此窗口'; read -n 1\"",
                        shell=True)

                # 通知用户
                self.master.after(0, lambda: messagebox.showinfo("安装已开始",
                                                                 "PyTorch安装已在命令行窗口启动，\n"
                                                                 "请查看命令行窗口了解进度。\n\n"
                                                                 "安装完成后，您需要重启应用程序以应用更改。"))

                # 还原按钮状态
                self.master.after(0, lambda: self.install_button.configure(state="normal"))
                self.master.after(0, lambda: self.pytorch_status_var.set("安装中..."))

            except Exception as e:
                logger.error(f"安装PyTorch失败: {e}")
                self.master.after(0, lambda: self.pytorch_status_var.set(f"安装失败: {str(e)}"))
                self.master.after(0, lambda: self.install_button.configure(state="normal"))
                self.master.after(0, lambda: messagebox.showerror("错误", f"安装PyTorch失败: {e}"))

        # 启动安装线程
        threading.Thread(target=install_thread, daemon=True).start()

    def _install_python_package(self) -> None:
        """安装Python包"""
        # 获取包名
        package = self.package_var.get().strip()
        if not package:
            messagebox.showinfo("提示", "请输入包名称")
            return

        # 获取版本约束
        version_constraint = self.version_constraint_var.get().strip()

        # 构建完整包规范
        if version_constraint:
            package_spec = f"{package}{version_constraint}"
        else:
            package_spec = package

        # 确认安装
        if not messagebox.askyesno("确认安装", f"将安装 {package_spec}\n\n是否继续？"):
            return

        # 更新状态
        self.package_status_var.set("准备安装...")
        self.master.update_idletasks()

        # 在线程中安装
        def install_thread():
            try:
                # 构建安装命令
                cmd = [sys.executable, "-m", "pip", "install", "--upgrade", package_spec]

                # 更新UI
                self.master.after(0, lambda: self.package_status_var.set("正在安装..."))

                # 执行命令
                if platform.system() == "Windows":
                    process = subprocess.Popen(
                        f"start cmd /k \"{' '.join(cmd)} && echo 包安装完成，请关闭此窗口 || echo 包安装失败，请检查错误信息\"",
                        shell=True)
                else:  # Linux/Mac
                    process = subprocess.Popen(
                        f"gnome-terminal -- bash -c \"{' '.join(cmd)}; echo '包安装完成，按任意键关闭此窗口'; read -n 1\"",
                        shell=True)

                # 通知用户
                self.master.after(0, lambda: messagebox.showinfo("安装已开始",
                                                                 f"{package} 安装已在命令行窗口启动，\n"
                                                                 "请查看命令行窗口了解进度。"))

                # 还原状态
                self.master.after(0, lambda: self.package_status_var.set("安装中..."))

            except Exception as e:
                logger.error(f"安装包失败: {e}")
                self.master.after(0, lambda: self.package_status_var.set(f"安装失败: {str(e)}"))
                self.master.after(0, lambda: messagebox.showerror("错误", f"安装包失败: {e}"))

        # 启动安装线程
        threading.Thread(target=install_thread, daemon=True).start()

    def _run_pytorch_install(self, version: str, cuda_version: str) -> None:
        """在后台线程中运行PyTorch安装"""
        self.pytorch_status_var.set("正在安装...")
        self.pytorch_progress_var.set(0)

        try:
            # 构建安装命令
            cmd = [sys.executable, "-m", "pip", "install"]

            # 基于版本和CUDA版本构建PyTorch安装URL
            if "CPU Only" in cuda_version:
                cmd.append(f"torch=={version}+cpu")
                cmd.extend(["-f", "https://download.pytorch.org/whl/cpu/torch_stable.html"])
            elif "CUDA" in cuda_version:
                cuda_ver = cuda_version.split(" ")[1].replace(".", "")  # 例如将CUDA 11.8转换为cu118
                cmd.append(f"torch=={version}+{cuda_ver}")
                cmd.extend(["-f", f"https://download.pytorch.org/whl/{cuda_ver}/torch_stable.html"])
            else:
                cmd.append(f"torch=={version}")

            # 设置进度更新
            def update_progress(line):
                if "%" in line:
                    try:
                        percent = float(line.split("%")[0].split(" ")[-1].strip())
                        self.pytorch_progress_var.set(percent)

                        # 更新UI
                        self.master.update_idletasks()
                    except:
                        pass

            # 执行命令并捕获输出
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # 读取输出
            for line in process.stdout:
                update_progress(line)

            process.wait()

            if process.returncode == 0:
                self.master.after(0, lambda: self.pytorch_status_var.set("安装成功"))
                self.master.after(0, lambda: self.pytorch_progress_var.set(100))
                self.master.after(1000, self._check_pytorch_status)
            else:
                self.master.after(0, lambda: self.pytorch_status_var.set("安装失败"))

        except Exception as e:
            self.master.after(0, lambda: self.pytorch_status_var.set(f"安装错误: {str(e)}"))

        finally:
            # 启用安装按钮
            self.master.after(0, lambda: self._enable_pytorch_buttons())

    def _enable_pytorch_buttons(self) -> None:
        """重新启用PyTorch安装按钮"""
        for widget in self.advanced_cards["pytorch"]["content"].winfo_children():
            if isinstance(widget, ttk.Frame):
                for w in widget.winfo_children():
                    if isinstance(w, ttk.Button):
                        w.configure(state="normal")

    def _update_iou_label(self, value) -> None:
        """更新IOU标签显示"""
        self.iou_label.config(text=f"{float(value):.2f}")

    def _update_conf_label(self, value) -> None:
        """更新置信度标签显示"""
        self.conf_label.config(text=f"{float(value):.2f}")

    def _create_about_page(self) -> None:
        """创建关于页面"""
        self.about_page = ttk.Frame(self.content_frame)

        # 页面标题
        title_frame = ttk.Frame(self.about_page)
        title_frame.pack(fill="x", padx=20, pady=(20, 10))

        title = ttk.Label(title_frame, text="关于", style="Title.TLabel")
        title.pack(side="left")

        # 关于内容
        about_content = ttk.Frame(self.about_page)
        about_content.pack(fill="both", expand=True, padx=20, pady=20)

        # 应用Logo
        try:
            logo_path = resource_path(os.path.join("res", "logo.png"))
            logo_img = Image.open(logo_path)
            logo_img = logo_img.resize((120, 120), Image.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_img)
            logo_label = ttk.Label(about_content, image=logo_photo)
            logo_label.image = logo_photo  # 保持引用
            logo_label.pack(pady=(20, 10))
        except Exception:
            # 如果没有图标，显示文本标题
            logo_label = ttk.Label(about_content, text=APP_TITLE, font=('Segoe UI', 18, 'bold'))
            logo_label.pack(pady=(20, 10))

        # 应用名称
        app_name = ttk.Label(about_content, text="物种信息检测系统", font=("Segoe UI", 16, "bold"))
        app_name.pack(pady=5)

        # 版本信息
        version_label = ttk.Label(about_content, text=f"版本: {APP_VERSION}", font=NORMAL_FONT)
        version_label.pack(pady=5)

        # 应用描述
        desc_label = ttk.Label(
            about_content,
            text="一款高效的物种信息检测应用程序，支持图像物种识别、探测图片保存、Excel输出和图像分类功能。",
            font=NORMAL_FONT,
            wraplength=500,
            justify="center"
        )
        desc_label.pack(pady=15)

        # 作者信息
        author_label = ttk.Label(about_content, text="作者：和錦わきん", font=NORMAL_FONT)
        author_label.pack(pady=5)

        # 版权信息
        copyright_label = ttk.Label(about_content, text="© 2024 版权所有", font=SMALL_FONT)
        copyright_label.pack(pady=(20, 0))

    def show_params_help(self) -> None:
        """显示参数说明弹窗"""
        # 创建一个顶层窗口
        help_window = tk.Toplevel(self.master)
        help_window.title("参数说明")

        # 设置窗口尺寸
        width, height = 500, 400
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        help_window.geometry(f"{width}x{height}+{x}+{y}")

        # 设置窗口为模态，用户必须关闭此窗口才能继续操作主窗口
        help_window.transient(self.master)
        help_window.grab_set()

        # 尝试设置相同的图标
        try:
            ico_path = resource_path(os.path.join("res", "ico.ico"))
            help_window.iconbitmap(ico_path)
        except Exception:
            pass

        # 创建一个框架容器
        content_frame = ttk.Frame(help_window, padding=PADDING)
        content_frame.pack(fill="both", expand=True)

        # 创建带滚动条的文本区域
        text_frame = ttk.Frame(content_frame)
        text_frame.pack(fill="both", expand=True, pady=(0, PADDING))

        help_text = tk.Text(text_frame, wrap="word", font=NORMAL_FONT)
        help_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=help_text.yview)
        help_text.configure(yscrollcommand=help_scroll.set)

        help_scroll.pack(side="right", fill="y")
        help_text.pack(side="left", fill="both", expand=True)

        # 设置参数说明文本
        param_help_text = """
IOU阈值 (Intersection Over Union)

说明：控制对象检测中边界框的重叠程度判定。
作用：用于消除冗余边界框，只保留得分最高的那个。
调节建议：
  - 较低值 (0.1-0.3)：检出更多目标，但可能有重复框
  - 中等值 (0.3-0.5)：平衡检出率和重复率
  - 较高值 (0.5-0.9)：减少重复框，但可能漏检部分目标
适用场景：当目标物体互相重叠时，提高IOU阈值可避免多重检测

置信度阈值 (Confidence Threshold)

说明：决定检测结果是否被保留的可信度标准。
作用：过滤掉低置信度的检测结果，减少误检。
调节建议：
  - 较低值 (0.05-0.2)：检出更多潜在目标，但可能增加误检率
  - 中等值 (0.2-0.4)：平衡检出率和误检率
  - 较高值 (0.4-0.95)：仅保留高置信度目标，减少误检但可能增加漏检
适用场景：检测难度大的场景可适当降低，简单明显的目标可提高

FP16加速 (半精度浮点数加速)

说明：使用16位浮点数而非32位浮点数进行计算。
优势：
  - 减少内存使用量约50%
  - 提高推理速度20-50%
  - 适合资源受限设备
潜在问题：
  - 对某些复杂场景可能略微降低精度
  - 在某些旧硬件上可能不支持或无加速效果
建议：大多数情况下建议开启，只有在发现明显精度下降时才考虑关闭
注意：在未检测到CUDA/Rocm时会禁用FP16加速！！！

数据增强 (Test-Time Augmentation)

说明：在检测过程中对图像应用多种变换，综合多个结果。
优势：
  - 提高检测准确性和稳定性
  - 减少因视角、光照等因素导致的漏检
缺点：
  - 会显著降低处理速度（通常慢2-4倍）
  - 增加内存占用
适用场景：对精度要求高且不赶时间的场景；对处理速度有要求时建议关闭

类别无关NMS (Class-Agnostic NMS)

说明：在应用非极大值抑制时忽略类别信息。
优势：
  - 对可能同时出现多种类别的场景有帮助
  - 避免不同类别目标因重叠而被错误抑制
缺点：
  - 在某些情况下可能导致错误分类的检测结果被保留
适用场景：当单个物体可能被错误分类为多个类别时；当多个不同类别物体密集分布时
"""

        help_text.insert("1.0", param_help_text.strip())
        help_text.configure(state="disabled")  # 设置为只读

        # 添加关闭按钮
        close_button = ttk.Button(content_frame, text="关闭", command=help_window.destroy, width=BUTTON_WIDTH)
        close_button.pack(side="right")

        # 确保弹窗在最前
        help_window.focus_set()

        # 防止窗口被调整大小
        help_window.resizable(False, False)

    def _bind_events(self) -> None:
        """绑定事件处理函数"""
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.file_path_entry.bind("<Return>", self.save_file_path_by_enter)
        self.save_path_entry.bind("<Return>", self.save_save_path_by_enter)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_selected)

        # 绑定图像标签的双击事件
        self.image_label.bind("<Double-1>", self.on_image_double_click)

        # 添加显示检测结果开关的变量跟踪
        self.show_detection_var.trace("w", self._detection_switch_changed)

        # 添加设置保存事件
        self.file_path_entry.bind("<FocusOut>", lambda e: self._save_current_settings())
        self.save_path_entry.bind("<FocusOut>", lambda e: self._save_current_settings())

        # 选项变量的追踪
        self.save_detect_image_var.trace("w", lambda *args: self._save_current_settings())
        self.output_excel_var.trace("w", lambda *args: self._save_current_settings())
        self.copy_img_var.trace("w", lambda *args: self._save_current_settings())
        self.use_fp16_var.trace("w", lambda *args: self._save_current_settings())
        self.iou_var.trace("w", lambda *args: self._save_current_settings())
        self.conf_var.trace("w", lambda *args: self._save_current_settings())
        self.use_augment_var.trace("w", lambda *args: self._save_current_settings())
        self.use_agnostic_nms_var.trace("w", lambda *args: self._save_current_settings())

    def _detection_switch_changed(self, *args) -> None:
        """处理显示检测结果开关变化"""
        # 如果正在处理且用户试图关闭显示，则强制保持打开
        if self.is_processing and not self.show_detection_var.get():
            self.show_detection_var.set(True)

    def on_image_double_click(self, event) -> None:
        """处理图像双击事件，放大显示图像"""
        # 检查是否有图像显示
        if not self.original_image or not self.current_image_path:
            return

        # 创建一个新窗口显示大图
        zoom_window = tk.Toplevel(self.master)
        zoom_window.title("图像放大查看")

        # 设置窗口图标
        try:
            ico_path = resource_path(os.path.join("res", "ico.ico"))
            zoom_window.iconbitmap(ico_path)
        except Exception:
            pass

        # 准备图像 - 根据是否显示检测结果决定显示原图或检测结果图
        if self.show_detection_var.get() and hasattr(self,
                                                     'current_detection_results') and self.current_detection_results is not None:
            # 显示检测结果图像
            for result in self.current_detection_results:
                result_img = result.plot()
                result_img_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
                display_img = Image.fromarray(result_img_rgb)
                break  # 只使用第一个结果
        else:
            # 显示原始图像
            display_img = self.original_image

        # 保存原始图像尺寸比例
        orig_width, orig_height = display_img.size
        aspect_ratio = orig_width / orig_height

        # 计算窗口初始大小 - 屏幕尺寸的80%
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        max_width = int(screen_width * 0.8)
        max_height = int(screen_height * 0.8)

        # 按比例计算初始窗口大小
        if aspect_ratio > 1:  # 宽图
            window_width = min(max_width, orig_width)
            window_height = int(window_width / aspect_ratio)
            if window_height > max_height:
                window_height = max_height
                window_width = int(window_height * aspect_ratio)
        else:  # 高图
            window_height = min(max_height, orig_height)
            window_width = int(window_height * aspect_ratio)
            if window_width > max_width:
                window_width = max_width
                window_height = int(window_width / aspect_ratio)

        # 设置窗口大小和位置
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        zoom_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 允许窗口大小调整
        zoom_window.resizable(True, True)

        # 创建Canvas以实现完美居中和拖动功能
        canvas = tk.Canvas(zoom_window, highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        # 初始显示图像
        resized_img = display_img.resize((window_width, window_height), Image.LANCZOS)
        photo = ImageTk.PhotoImage(resized_img)

        # 保存原始图像和必要的引用
        canvas.original_img = display_img
        canvas.aspect_ratio = aspect_ratio
        canvas.current_img = resized_img  # 保存当前显示的图像
        canvas.image = photo
        canvas.zoom_level = 1.0  # 初始缩放级别

        # 用于图像拖动的变量
        canvas.drag_data = {"x": 0, "y": 0, "dragging": False}
        canvas.offset_x = 0  # 图像X偏移量
        canvas.offset_y = 0  # 图像Y偏移量

        # 在Canvas中心创建图像
        canvas.img_id = canvas.create_image(window_width // 2, window_height // 2, image=photo)

        # 窗口大小变化事件处理
        def on_window_resize(event):
            # 只处理窗口大小变化事件
            if event.widget == zoom_window:
                # 确保窗口已完全初始化
                zoom_window.update_idletasks()

                # 获取当前窗口可用空间
                available_width = canvas.winfo_width()
                available_height = canvas.winfo_height()

                if available_width <= 10 or available_height <= 10:
                    return  # 避免无效的尺寸

                # 重设缩放级别为1.0（适应窗口）
                canvas.zoom_level = 1.0

                # 重置偏移量
                canvas.offset_x = 0
                canvas.offset_y = 0

                # 根据宽高比计算实际使用的尺寸
                ar = canvas.aspect_ratio

                # 确定哪个维度是限制因素
                if available_width / ar <= available_height:
                    # 宽度是限制因素
                    new_width = available_width
                    new_height = int(new_width / ar)
                else:
                    # 高度是限制因素
                    new_height = available_height
                    new_width = int(new_height * ar)

                # 重新调整图像大小以适应窗口，保持宽高比
                resized = canvas.original_img.resize((new_width, new_height), Image.LANCZOS)
                canvas.current_img = resized  # 更新当前图像
                new_photo = ImageTk.PhotoImage(resized)
                canvas.itemconfig(canvas.img_id, image=new_photo)
                canvas.image = new_photo  # 保持引用

                # 重新定位图像到Canvas中心
                canvas.coords(canvas.img_id, available_width // 2, available_height // 2)

        # 鼠标滚轮事件处理，用于缩放图像
        def on_mousewheel(event):
            # 确定缩放方向
            if event.delta > 0:
                # 放大图像
                zoom_factor = 1.1
                canvas.zoom_level *= zoom_factor
            else:
                # 缩小图像
                zoom_factor = 0.9
                canvas.zoom_level *= zoom_factor

            # 限制缩放级别范围，防止过度缩放
            if canvas.zoom_level < 0.1:
                canvas.zoom_level = 0.1
            elif canvas.zoom_level > 5.0:
                canvas.zoom_level = 5.0

            # 获取当前窗口大小
            available_width = canvas.winfo_width()
            available_height = canvas.winfo_height()

            # 根据窗口大小和宽高比计算基础大小
            ar = canvas.aspect_ratio
            if available_width / ar <= available_height:
                base_width = available_width
                base_height = int(base_width / ar)
            else:
                base_height = available_height
                base_width = int(base_height * ar)

            # 应用缩放系数计算新大小
            new_width = int(base_width * canvas.zoom_level)
            new_height = int(base_height * canvas.zoom_level)

            # 重新调整图像大小
            resized = canvas.original_img.resize((new_width, new_height), Image.LANCZOS)
            canvas.current_img = resized
            new_photo = ImageTk.PhotoImage(resized)
            canvas.itemconfig(canvas.img_id, image=new_photo)
            canvas.image = new_photo  # 保持引用

            # 确保偏移量在缩小时不超出图像边界
            if canvas.zoom_level <= 1.0:
                # 如果缩放级别小于等于1.0，则重置偏移量
                canvas.offset_x = 0
                canvas.offset_y = 0
            else:
                # 当缩放时，限制偏移量以防止图像超出可见区域
                max_offset_x = (new_width - base_width) // 2
                max_offset_y = (new_height - base_height) // 2

                # 限制偏移量在允许范围内
                canvas.offset_x = max(-max_offset_x, min(max_offset_x, canvas.offset_x))
                canvas.offset_y = max(-max_offset_y, min(max_offset_y, canvas.offset_y))

            # 计算图像位置，应用偏移量
            x_pos = available_width // 2 - canvas.offset_x
            y_pos = available_height // 2 - canvas.offset_y
            canvas.coords(canvas.img_id, x_pos, y_pos)

            # 显示当前缩放级别在标题栏
            zoom_window.title(f"图像放大查看 - 缩放: {canvas.zoom_level:.1f}x")

            # 更新光标样式
            update_cursor_style()

        # 鼠标拖动相关函数
        def on_drag_start(event):
            # 当开始拖动时记录鼠标位置
            if canvas.zoom_level > 1.0:  # 只在放大状态下允许拖动
                canvas.drag_data["x"] = event.x
                canvas.drag_data["y"] = event.y
                canvas.drag_data["dragging"] = True
                # 改变光标样式为抓手
                canvas.config(cursor="fleur")  # 抓手光标

        def on_drag_motion(event):
            # 拖动过程中移动图像
            if canvas.drag_data["dragging"] and canvas.zoom_level > 1.0:
                # 计算鼠标移动的距离
                dx = event.x - canvas.drag_data["x"]
                dy = event.y - canvas.drag_data["y"]

                # 更新鼠标位置
                canvas.drag_data["x"] = event.x
                canvas.drag_data["y"] = event.y

                # 更新偏移量
                canvas.offset_x -= dx
                canvas.offset_y -= dy

                # 获取当前窗口大小
                available_width = canvas.winfo_width()
                available_height = canvas.winfo_height()

                # 获取当前图像尺寸
                img_width = canvas.current_img.width
                img_height = canvas.current_img.height

                # 计算最大允许偏移量
                max_offset_x = max(0, (img_width - available_width) // 2)
                max_offset_y = max(0, (img_height - available_height) // 2)

                # 限制偏移量在允许范围内
                canvas.offset_x = max(-max_offset_x, min(max_offset_x, canvas.offset_x))
                canvas.offset_y = max(-max_offset_y, min(max_offset_y, canvas.offset_y))

                # 应用偏移量更新图像位置
                x_pos = available_width // 2 - canvas.offset_x
                y_pos = available_height // 2 - canvas.offset_y
                canvas.coords(canvas.img_id, x_pos, y_pos)

        def on_drag_stop(event):
            # 停止拖动
            canvas.drag_data["dragging"] = False
            # 恢复正常光标或根据缩放状态设置光标
            update_cursor_style()

        def update_cursor_style():
            # 根据缩放状态更新光标样式
            if canvas.zoom_level > 1.0:
                # 缩放大于1.0时使用移动光标提示可拖动
                canvas.config(cursor="hand2")  # 或使用"fleur"作为抓手光标
            else:
                # 缩放小于等于1.0时使用默认光标
                canvas.config(cursor="")

        # 绑定事件
        canvas.bind("<MouseWheel>", on_mousewheel)  # Windows系统滚轮事件
        canvas.bind("<Button-4>", lambda e: on_mousewheel(type('Event', (), {'delta': 120})))  # Linux上滚
        canvas.bind("<Button-5>", lambda e: on_mousewheel(type('Event', (), {'delta': -120})))  # Linux下滚
        canvas.bind("<ButtonPress-1>", on_drag_start)  # 鼠标左键按下开始拖动
        canvas.bind("<B1-Motion>", on_drag_motion)  # 按住左键移动进行拖动
        canvas.bind("<ButtonRelease-1>", on_drag_stop)  # 释放左键停止拖动
        zoom_window.bind("<Configure>", on_window_resize)

        # 添加ESC键关闭窗口的功能
        def close_on_escape(event):
            if event.keysym == 'Escape':
                zoom_window.destroy()

        zoom_window.bind('<Key>', close_on_escape)

        # 初始化光标样式
        update_cursor_style()

        # 确保窗口在最前
        zoom_window.focus_set()
        zoom_window.transient(self.master)  # 设置为主窗口的临时窗口

    def on_tab_changed(self, event) -> None:
        """处理选项卡切换事件 - 修改为适应新的布局"""
        # 这里应该获取当前显示的是哪个标签页
        current_tab = event.widget.select()
        tab_id = event.widget.index(current_tab)

        # 如果当前是图像预览标签页
        if current_tab == self.image_preview_tab:
            # 确保文件列表已更新
            file_path = self.file_path_entry.get()
            if file_path and os.path.isdir(file_path):
                # 如果文件列表为空，则更新
                if self.file_listbox.size() == 0:
                    self.update_file_list(file_path)

                # 如果有文件且没有选择，则选择第一个
                if self.file_listbox.size() > 0 and not self.file_listbox.curselection():
                    self.file_listbox.selection_set(0)
                    self.on_file_selected(None)

    def _on_tab_changed(self, event):
        """处理标签页切换事件 - 更新版本"""
        # 获取当前选中的标签页
        current_tab = self.advanced_notebook.select()
        tab_text = self.advanced_notebook.tab(current_tab, "text")

        # 如果切换到了环境维护标签页，更新滚动区域
        if tab_text == "环境维护" and hasattr(self, 'env_canvas'):
            # 延迟执行以确保界面已完全渲染
            self.master.after(100, lambda: self.env_canvas.configure(scrollregion=self.env_canvas.bbox("all")))

    def _get_current_settings(self) -> Dict[str, Any]:
        """获取当前UI中的所有设置

        Returns:
            设置字典
        """
        settings = {
            "file_path": self.file_path_entry.get(),
            "save_path": self.save_path_entry.get(),
            "save_detect_image": self.save_detect_image_var.get(),
            "output_excel": self.output_excel_var.get(),
            "copy_img": self.copy_img_var.get(),
            "use_fp16": self.use_fp16_var.get(),
            "iou": self.iou_var.get(),
            "conf": self.conf_var.get(),
            "use_augment": self.use_augment_var.get(),
            "use_agnostic_nms": self.use_agnostic_nms_var.get()
        }
        return settings

    def _save_current_settings(self) -> None:
        """保存当前设置到JSON文件"""
        if not self.settings_manager or not hasattr(self.settings_manager, 'save_settings'):
            logger.warning("设置管理器未正确初始化，无法保存设置")
            return

        settings = self._get_current_settings()
        success = self.settings_manager.save_settings(settings)

        if success:
            logger.info("设置已保存")
            # 可选: 在状态栏显示保存成功信息
            self.status_bar.status_label.config(text="设置已保存")

    def _load_settings_to_ui(self, settings: Dict[str, Any]) -> None:
        """将设置应用到UI元素

        Args:
            settings: 设置字典
        """
        try:
            # 设置路径
            if "file_path" in settings and settings["file_path"] and os.path.exists(settings["file_path"]):
                self.file_path_entry.delete(0, tk.END)
                self.file_path_entry.insert(0, settings["file_path"])
                self.current_path = settings["file_path"]
                # 如果是目录，更新文件列表
                if os.path.isdir(settings["file_path"]):
                    self.update_file_list(settings["file_path"])

            if "save_path" in settings and settings["save_path"]:
                self.save_path_entry.delete(0, tk.END)
                self.save_path_entry.insert(0, settings["save_path"])

            # 设置功能选项
            if "save_detect_image" in settings:
                self.save_detect_image_var.set(settings["save_detect_image"])

            if "output_excel" in settings:
                self.output_excel_var.set(settings["output_excel"])

            if "copy_img" in settings:
                self.copy_img_var.set(settings["copy_img"])

            # 设置高级选项
            if "use_fp16" in settings:
                self.use_fp16_var.set(settings["use_fp16"])

            if "iou" in settings:
                self.iou_var.set(settings["iou"])
                self._update_iou_label(settings["iou"])

            if "conf" in settings:
                self.conf_var.set(settings["conf"])
                self._update_conf_label(settings["conf"])

            if "use_augment" in settings:
                self.use_augment_var.set(settings["use_augment"])

            if "use_agnostic_nms" in settings:
                self.use_agnostic_nms_var.set(settings["use_agnostic_nms"])

            logger.info("设置已加载到UI")
        except Exception as e:
            logger.error(f"加载设置到UI失败: {e}")

    def on_closing(self) -> None:
        """窗口关闭事件处理"""
        if self.is_processing:
            if not messagebox.askyesno("警告",
                                       "处理正在进行中，确定要退出程序吗？\n处理进度将会保存，下次启动时可以继续。"):
                return

            # 停止处理但不删除缓存
            self.processing_stop_flag.set()

        # 释放图像资源
        if hasattr(self, 'preview_image'):
            self.preview_image = None
        if hasattr(self, 'original_image'):
            self.original_image = None
        if hasattr(self, 'current_detection_results'):
            self.current_detection_results = None

        # 强制垃圾回收
        import gc
        gc.collect()

        # 保存当前设置，添加防错处理
        try:
            if hasattr(self, '_save_current_settings'):
                self._save_current_settings()
        except Exception as e:
            logger.error(f"保存设置时出错: {e}")

        self.master.destroy()

    def browse_file_path(self) -> None:
        """浏览文件路径"""
        folder_selected = filedialog.askdirectory(title="选择图像文件所在文件夹")
        if folder_selected:
            # 如果选择了新的文件夹，则清空临时图像目录
            if self.current_path != folder_selected:
                self._clean_temp_photo_directory()

            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, folder_selected)
            self.update_file_list(folder_selected)

    def browse_save_path(self) -> None:
        """浏览保存路径"""
        folder_selected = filedialog.askdirectory(title="选择结果保存文件夹")
        if folder_selected:
            self.save_path_entry.delete(0, tk.END)
            self.save_path_entry.insert(0, folder_selected)

    def update_file_list(self, directory: str) -> None:
        """更新文件列表"""
        if not os.path.isdir(directory):
            return

        self.file_listbox.delete(0, tk.END)

        # 重置检测相关变量（但不复位显示检测结果开关，让它根据选择的图片自动决定）
        self.current_detection_results = None
        self.current_image_path = None

        try:
            image_files = [
                item for item in os.listdir(directory)
                if os.path.isfile(os.path.join(directory, item)) and
                   item.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS)
            ]

            for file in sorted(image_files):
                self.file_listbox.insert(tk.END, file)

            if image_files:
                self.status_bar.status_label.config(text=f"找到 {len(image_files)} 个图像文件")
            else:
                self.status_bar.status_label.config(text="未找到图像文件")
        except Exception as e:
            logger.error(f"更新文件列表失败: {e}")
            self.status_bar.status_label.config(text="读取文件列表失败")

    def on_file_selected(self, event) -> None:
        """文件选择事件处理"""
        selection = self.file_listbox.curselection()
        if not selection:
            return

        # 清除之前的图像引用
        if hasattr(self, 'preview_image'):
            self.preview_image = None
        if hasattr(self, 'original_image'):
            self.original_image = None

        file_name = self.file_listbox.get(selection[0])
        file_path = os.path.join(self.file_path_entry.get(), file_name)

        # 保存当前图像路径
        self.current_image_path = file_path

        # 重置检测结果变量
        self.current_detection_results = None

        # 检查是否已有检测结果（在temp/photo目录中）
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")
        photo_path = os.path.join(temp_dir, "photo")
        temp_result_path = os.path.join(photo_path, file_name)

        # 检查是否有对应的 JSON 文件（用于确认是否已检测）
        base_name, _ = os.path.splitext(file_name)
        json_path = os.path.join(photo_path, f"{base_name}.json")

        # 如果已经检测过（存在检测结果图像和JSON），自动显示检测结果
        if os.path.exists(temp_result_path) and os.path.exists(json_path):
            # 打开显示检测结果开关
            self.show_detection_var.set(True)

            # 显示检测结果图像
            self.update_image_preview(temp_result_path, is_temp_result=True)

            # 显示检测信息
            try:
                import json
                with open(json_path, 'r', encoding='utf-8') as f:
                    detection_info = json.load(f)

                # 构建检测信息并更新显示
                species_info = {
                    '物种名称': detection_info.get('物种名称', ''),
                    '物种数量': detection_info.get('物种数量', ''),
                    '最低置信度': detection_info.get('最低置信度', ''),
                    '检测时间': detection_info.get('检测时间', '')
                }

                # 更新图像信息和检测信息
                self.update_image_info(file_path, file_name)
                self._update_detection_info_from_json(species_info)
            except Exception as e:
                logger.error(f"读取检测信息JSON失败: {e}")
                # 如果读取JSON失败，仍然更新图像信息但不显示检测信息
                self.update_image_info(file_path, file_name)
        else:
            # 没有检测结果，关闭显示检测结果开关
            self.show_detection_var.set(False)

            # 更新预览图像（显示原图）
            self.update_image_preview(file_path)

            # 更新图像信息
            self.update_image_info(file_path, file_name)

    def update_image_preview(self, file_path: str, show_detection: bool = False, detection_results=None,
                             is_temp_result: bool = False) -> None:
        """更新图像预览

        Args:
            file_path: 图像文件路径
            show_detection: 是否显示检测结果
            detection_results: YOLO检测结果对象
            is_temp_result: 是否为临时结果图像
        """
        try:
            # 先清除可能的旧引用
            if hasattr(self, 'preview_image'):
                self.preview_image = None
            if hasattr(self, 'image_label') and hasattr(self.image_label, 'image'):
                self.image_label.image = None

            if is_temp_result:
                # 直接加载临时结果图像
                img = Image.open(file_path)
            elif show_detection and detection_results is not None:
                # 获取YOLO绘制的检测结果图像
                for result in detection_results:
                    # 使用plots功能获取绘制了检测框的图像
                    result_img = result.plot()
                    # 将OpenCV的BGR格式转换为RGB格式
                    result_img_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(result_img_rgb)
                    break  # 只使用第一个结果
            else:
                # 显示原始图像
                img = Image.open(file_path)

            # 保存原始图像，用于双击放大
            self.original_image = img

            # 计算调整大小的比例，以适应预览区域
            max_width = 400
            max_height = 300
            img_width, img_height = img.size

            ratio = min(max_width / img_width, max_height / img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)

            img = img.resize((new_width, new_height), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            # 更新图像标签
            self.image_label.config(image=photo)
            self.image_label.image = photo  # 保持引用

            # 将预览图像设置为当前图像
            self.preview_image = img
        except Exception as e:
            logger.error(f"更新图像预览失败: {e}")
            self.image_label.config(image='', text="无法加载图像")
            self.original_image = None
            self.preview_image = None

    def update_image_info(self, file_path: str, file_name: str) -> None:
        """更新图像信息"""
        try:
            # 提取元数据
            image_info, _ = ImageMetadataExtractor.extract_metadata(file_path, file_name)

            # 更新信息文本
            self.info_text.config(state="normal")
            self.info_text.delete(1.0, tk.END)

            # 第一行信息
            info_text = f"文件名: {image_info.get('文件名', '')}    格式: {image_info.get('格式', '')}"

            # 第二行信息
            info_text2 = ""
            if image_info.get('拍摄日期'):
                info_text2 += f"拍摄日期: {image_info.get('拍摄日期')} {image_info.get('拍摄时间', '')}    "
            else:
                info_text2 += "拍摄日期: 未知    "

            # 添加图像尺寸信息
            try:
                with Image.open(file_path) as img:
                    info_text2 += f"尺寸: {img.width} x {img.height} 像素    "
                    info_text2 += f"文件大小: {os.path.getsize(file_path) / 1024:.1f} KB"
            except:
                pass

            # 插入文本内容（两行）
            self.info_text.insert(tk.END, info_text + "\n" + info_text2)
            self.info_text.config(state="disabled")
        except Exception as e:
            logger.error(f"更新图像信息失败: {e}")
            self.info_text.config(state="normal")
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, f"加载图像信息失败: {e}")
            self.info_text.config(state="disabled")

    def save_file_path_by_enter(self, event) -> None:
        """处理文件路径输入框的回车键事件"""
        folder_selected = self.file_path_entry.get()
        if os.path.isdir(folder_selected):
            # 如果选择了新的文件夹，则清空临时图像目录
            if folder_selected != self.current_path:
                self._clean_temp_photo_directory()

            self.current_path = folder_selected
            self.update_file_list(folder_selected)
            self.status_bar.status_label.config(text=f"已设置文件路径: {folder_selected}")

        else:
            messagebox.showerror("错误", "输入的文件路径无效，请检查。\n请确保路径指向一个文件夹。")

    def save_save_path_by_enter(self, event) -> None:
        """处理保存路径输入框的回车键事件"""
        save_path = self.save_path_entry.get()
        if os.path.isdir(save_path):
            self.status_bar.status_label.config(text=f"已设置保存路径: {save_path}")
        else:
            try:
                os.makedirs(save_path)
                self.status_bar.status_label.config(text=f"已创建并设置保存路径: {save_path}")
            except Exception as e:
                messagebox.showerror("错误", f"输入的保存路径无效或无法创建: {e}")

    def toggle_processing_state(self) -> None:
        """切换处理状态：开始处理或停止处理"""
        if not self.is_processing:
            # 检查是否存在缓存文件
            self.check_for_cache_and_process()
        else:
            self.stop_processing()

    def check_for_cache_and_process(self) -> None:
        """检查是否存在缓存文件，并询问是否继续处理"""
        # 获取temp目录路径
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")
        cache_file = os.path.join(temp_dir, "cache.json")

        # 检查是否存在缓存文件
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)

                if 'processed_files' in cache_data and 'total_files' in cache_data:
                    # 创建提示信息
                    processed = cache_data.get('processed_files', 0)
                    total = cache_data.get('total_files', 0)
                    file_path = cache_data.get('file_path', '')

                    # 显示询问对话框
                    if messagebox.askyesno(
                            "发现未完成任务",
                            f"检测到上次有未完成的处理任务，是否从上次进度继续处理？\n\n"
                            f"已处理：{processed} 张\n"
                            f"总计：{total} 张\n"
                            f"路径：{file_path}"
                    ):
                        # 从缓存恢复设置并开始处理
                        self._load_cache_data_from_file(cache_data)
                        self.start_processing(resume_from=processed)
                        return
            except Exception as e:
                logger.error(f"读取缓存文件失败: {e}")

        # 如果没有缓存或用户选择不继续，则正常开始处理
        self.start_processing()

    def _load_cache_data_from_file(self, cache_data: Dict[str, Any]) -> None:
        """从缓存数据加载设置

        Args:
            cache_data: 缓存数据字典
        """
        try:
            # 从缓存中恢复数据
            file_path = cache_data.get('file_path', '')
            save_path = cache_data.get('save_path', '')
            save_detect_image = cache_data.get('save_detect_image', True)
            output_excel = cache_data.get('output_excel', True)
            copy_img = cache_data.get('copy_img', False)
            use_fp16 = cache_data.get('use_fp16', False)

            # 加载Excel数据
            excel_data = cache_data.get('excel_data', [])

            # 处理Excel数据中的日期时间字符串
            for item in excel_data:
                # 转换"拍摄日期对象"字段
                if '拍摄日期对象' in item and isinstance(item['拍摄日期对象'], str):
                    try:
                        item['拍摄日期对象'] = datetime.fromisoformat(item['拍摄日期对象'])
                    except ValueError:
                        pass

                # 转换任何其他日期时间字符串字段
                for key, value in list(item.items()):
                    if isinstance(value, str) and 'T' in value and value.count('-') >= 2:
                        try:
                            item[key] = datetime.fromisoformat(value)
                        except ValueError:
                            pass

            # 更新类属性
            self.excel_data = excel_data

            # 更新UI
            if file_path and os.path.exists(file_path):
                self.file_path_entry.delete(0, tk.END)
                self.file_path_entry.insert(0, file_path)
                self.update_file_list(file_path)

            if save_path:
                self.save_path_entry.delete(0, tk.END)
                self.save_path_entry.insert(0, save_path)

            self.save_detect_image_var.set(save_detect_image)
            self.output_excel_var.set(output_excel)
            self.copy_img_var.set(copy_img)
            self.use_fp16_var.set(use_fp16)

            logger.info("从缓存加载设置和数据成功")

        except Exception as e:
            logger.error(f"从缓存加载设置失败: {e}")

    def start_processing(self, resume_from=0):
        """开始处理图像

        Args:
            resume_from: 从第几张图片开始处理，用于继续上次未完成的处理
        """
        # 获取配置
        file_path = self.file_path_entry.get()
        save_path = self.save_path_entry.get()
        save_detect_image = self.save_detect_image_var.get()
        output_excel = self.output_excel_var.get()
        copy_img = self.copy_img_var.get()
        use_fp16 = self.use_fp16_var.get()

        # 验证输入
        if not self._validate_inputs(file_path, save_path):
            return

        # 检查是否选择了至少一个功能
        if not save_detect_image and not output_excel and not copy_img:
            messagebox.showerror("错误", "请至少选择一个处理功能。")
            return

        # 更新UI状态
        self._set_processing_state(True)

        # 切换到图像预览选项卡
        self.notebook.select(1)

        # 如果不是继续处理，则清空excel_data
        if resume_from == 0:
            self.excel_data = []

        # 启动处理线程
        threading.Thread(
            target=self._process_images_thread,
            args=(file_path, save_path, save_detect_image, output_excel, copy_img, use_fp16, resume_from),
            daemon=True
        ).start()

    def stop_processing(self):
        """停止处理图像"""
        if messagebox.askyesno("停止确认", "确定要停止图像处理吗？\n处理进度将被保存，下次可以继续。"):
            self.processing_stop_flag.set()
            self.status_bar.status_label.config(text="正在停止处理...")
        else:
            messagebox.showinfo("信息", "处理继续进行。")

    def _validate_inputs(self, file_path: str, save_path: str) -> bool:
        """验证输入参数

        Args:
            file_path: 文件路径
            save_path: 保存路径

        Returns:
            输入是否有效
        """
        if not file_path or not save_path:
            messagebox.showerror("错误", "请填写文件路径和保存路径。")
            return False

        if not os.path.isdir(file_path):
            messagebox.showerror("错误", "无效的文件路径。")
            return False

        if not os.path.isdir(save_path):
            try:
                os.makedirs(save_path)
                messagebox.showinfo("信息", "保存路径目录已创建。")
            except Exception as e:
                messagebox.showerror("错误", f"无效的保存路径或无法创建目录: {e}")
                return False

        return True

    def _set_processing_state(self, is_processing: bool) -> None:
        """设置处理状态

        Args:
            is_processing: 是否正在处理
        """
        self.is_processing = is_processing

        # 更新UI状态
        if is_processing:
            self.start_stop_button.config(text="停止处理")
            self.status_bar.status_label.config(text="正在处理图像...")
            self.progress_frame.progress_var.set(0)
            self.progress_frame.speed_label.config(text="")
            self.progress_frame.time_label.config(text="")
            self.processing_stop_flag.clear()

            # 禁用配置选项
            for widget in (self.file_path_entry, self.file_path_button,
                           self.save_path_entry, self.save_path_button):
                widget["state"] = "disabled"

            # 当前不在预览页面，则切换到预览页面
            if self.current_page != "preview":
                self._show_page("preview")

            # 禁用侧边栏按钮（除了预览页面）
            for page_id, button in self.nav_buttons.items():
                if page_id != "preview":
                    button["state"] = "disabled"

            # 禁用检测按钮
            self.detect_button["state"] = "disabled"

            # 自动打开显示检测结果开关
            self.show_detection_var.set(True)
        else:
            self.start_stop_button.config(text="开始处理")
            self.progress_frame.speed_label.config(text="")
            self.progress_frame.time_label.config(text="")

            # 更新状态栏文本
            if self.processing_stop_flag.is_set():
                self.status_bar.status_label.config(text="处理已停止")
            else:
                self.status_bar.status_label.config(text="就绪")

            # 启用配置选项
            for widget in (self.file_path_entry, self.file_path_button,
                           self.save_path_entry, self.save_path_button):
                widget["state"] = "normal"

            # 启用侧边栏按钮
            for button in self.nav_buttons.values():
                button["state"] = "normal"

            # 启用检测按钮
            self.detect_button["state"] = "normal"

    def _process_images_thread(self, file_path: str, save_path: str,
                               save_detect_image: bool, output_excel: bool,
                               copy_img: bool, use_fp16: bool, resume_from: int = 0) -> None:
        """图像处理线程

        Args:
            file_path: 源文件路径
            save_path: 保存路径
            save_detect_image: 是否保存探测图片
            output_excel: 是否输出Excel表格
            copy_img: 是否按物种分类复制图片
            use_fp16: 是否使用FP16加速推理
            resume_from: 从第几张图片开始处理，用于继续上次未完成的处理
        """
        # 计算合适的开始时间，考虑已处理的图片
        if resume_from > 0:
            # 如果是继续处理，根据平均处理时间估算之前处理所花费的时间
            # 假设每张图片的处理时间为0.5秒（可根据实际情况调整）
            estimated_previous_time = resume_from * 0.5  # 估算之前处理所花的时间
            start_time = time.time() - estimated_previous_time  # 调整开始时间点
        else:
            start_time = time.time()  # 新任务直接使用当前时间

        excel_data = [] if resume_from == 0 else getattr(self, 'excel_data', [])
        processed_files = resume_from
        stopped_manually = False
        earliest_date = None
        cache_interval = 10  # 每处理10张图片保存一次缓存
        timeout_error_occurred = False  # 新增标志，用于跟踪是否出现超时错误

        try:
            # 获取高级设置参数
            iou = self.iou_var.get()
            conf = self.conf_var.get()
            augment = self.use_augment_var.get()
            agnostic_nms = self.use_agnostic_nms_var.get()

            # 显示当前使用的设置
            fp16_status = "启用" if use_fp16 else "禁用"
            self.master.after(0, lambda: self.status_bar.status_label.config(
                text=f"正在处理图像... FP16加速: {fp16_status}, IOU: {iou:.2f}, 置信度: {conf:.2f}"))

            # 获取所有图片文件
            image_files = self._get_image_files(file_path)

            total_files = len(image_files)
            self.progress_frame.progress_bar["maximum"] = total_files

            if not image_files:
                self.status_bar.status_label.config(text="未找到任何图片文件。")
                messagebox.showinfo("提示", "在指定路径下未找到任何图片文件。")
                return

            # 如果是继续处理，从上次处理的位置开始
            if resume_from > 0 and resume_from < total_files:
                image_files = image_files[resume_from:]

                # 如果有已处理的数据，找出最早的日期
                if excel_data:
                    for item in excel_data:
                        if item.get('拍摄日期对象'):
                            if earliest_date is None or item['拍摄日期对象'] < earliest_date:
                                earliest_date = item['拍摄日期对象']

                # 立即更新进度显示，显示已加载的进度
                self._update_progress(processed_files, total_files, start_time)

            # 处理每张图片
            for filename in image_files:
                if self.processing_stop_flag.is_set():
                    stopped_manually = True
                    break

                try:
                    # 更新UI显示当前处理的文件
                    self.master.after(0, lambda f=filename: self.status_bar.status_label.config(
                        text=f"正在处理: {f} (FP16加速: {fp16_status})"))

                    # 选中当前文件并滚动到可见处
                    try:
                        idx = self.file_listbox.get(0, tk.END).index(filename)
                        self.file_listbox.selection_clear(0, tk.END)
                        self.file_listbox.selection_set(idx)
                        self.file_listbox.see(idx)

                        # 更新预览
                        img_path = os.path.join(file_path, filename)
                        self.master.after(0, lambda p=img_path: self.update_image_preview(p))
                    except (ValueError, Exception) as e:
                        logger.debug(f"更新列表选择失败: {e}")

                    # 处理单张图片
                    img_path = os.path.join(file_path, filename)
                    image_info, img = ImageMetadataExtractor.extract_metadata(img_path, filename)

                    # 检测物种 - 使用高级设置参数，添加超时参数
                    species_info = self.image_processor.detect_species(
                        img_path,
                        use_fp16=self.use_fp16_var.get() and self.cuda_available,  # 只有CUDA可用时才使用FP16
                        iou=self.iou_var.get(),
                        conf=self.conf_var.get(),
                        augment=self.use_augment_var.get(),
                        agnostic_nms=self.use_agnostic_nms_var.get(),
                        timeout=10.0  # 设置超时
                    )

                    # 如果是不会超时错误外的异常，处理照常进行
                    # 更新图像信息
                    image_info.update(species_info)

                    # 更新预览图像 - 显示检测结果
                    detect_results = species_info['detect_results']
                    self.current_detection_results = detect_results  # 保存当前检测结果
                    self.master.after(0, lambda p=img_path, d=detect_results:
                    self.update_image_preview(p, True, d))

                    # 保存临时检测结果图片
                    if self.current_detection_results:
                        self.image_processor.save_detection_temp(detect_results, filename)
                        # 添加检测时间
                        from datetime import datetime
                        species_info['检测时间'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # 保存检测结果JSON
                        self.image_processor.save_detection_info_json(detect_results, filename, species_info)

                    # 保存检测结果到临时目录
                    if detect_results:
                        self.image_processor.save_detection_temp(detect_results, filename)

                    # 更新最早日期
                    if image_info.get('拍摄日期对象'):
                        if earliest_date is None or image_info['拍摄日期对象'] < earliest_date:
                            earliest_date = image_info['拍摄日期对象']

                    # 保存检测结果图片
                    if save_detect_image:
                        self.image_processor.save_detection_result(
                            species_info['detect_results'], filename, save_path)

                    # 按物种分类复制图片
                    if copy_img and img:
                        self._copy_image_by_species(
                            img_path, save_path, species_info['物种名称'].split(','))

                    excel_data.append(image_info)

                except Exception as e:
                    logger.error(f"处理文件 {filename} 失败: {e}")

                # 更新进度
                processed_files += 1
                self._update_progress(processed_files, total_files, start_time)

                # 每处理cache_interval张图片保存一次缓存
                if processed_files % cache_interval == 0:
                    try:
                        # 确保temp目录存在
                        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")
                        if not os.path.exists(temp_dir):
                            os.makedirs(temp_dir)

                        cache_file = os.path.join(temp_dir, "cache.json")

                        # 处理excel_data中的不可序列化对象
                        serializable_excel_data = []
                        for item in excel_data:
                            serializable_item = {}
                            for key, value in item.items():
                                # 处理datetime对象
                                if isinstance(value, datetime):
                                    serializable_item[key] = value.isoformat()
                                # 处理Results对象 - 不保存它们，因为它们不需要用于恢复处理
                                elif key == 'detect_results':
                                    # 跳过Results对象，不保存到缓存中
                                    continue
                                # 其他基本类型可以直接保存
                                elif isinstance(value, (str, int, float, bool, type(None))):
                                    serializable_item[key] = value
                                # 如果是列表或字典，尝试保存，但不保存其中的复杂对象
                                elif isinstance(value, (list, dict)):
                                    try:
                                        # 测试是否可以序列化
                                        json.dumps(value)
                                        serializable_item[key] = value
                                    except TypeError:
                                        # 如果无法序列化，则跳过
                                        continue
                                else:
                                    # 对于其他无法序列化的对象，转换为字符串
                                    try:
                                        serializable_item[key] = str(value)
                                    except:
                                        continue
                            serializable_excel_data.append(serializable_item)

                        cache_data = {
                            'file_path': file_path,
                            'save_path': save_path,
                            'save_detect_image': save_detect_image,
                            'output_excel': output_excel,
                            'copy_img': copy_img,
                            'use_fp16': use_fp16,
                            'processed_files': processed_files,
                            'total_files': total_files,
                            'excel_data': serializable_excel_data,
                            'timestamp': time.time()
                        }

                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=4)

                        logger.info(f"处理进度已缓存: {processed_files}/{total_files}")
                    except Exception as e:
                        logger.error(f"保存处理缓存失败: {e}")

            # 保存用于后续处理的Excel数据
            self.excel_data = excel_data

            # 如果发生了超时错误，显示中断信息
            if timeout_error_occurred:
                self.status_bar.status_label.config(text="处理因超时而中断！")
                return

            # 处理独立探测首只
            excel_data = DataProcessor.process_independent_detection(excel_data)

            # 计算工作天数
            if earliest_date:
                excel_data = DataProcessor.calculate_working_days(excel_data, earliest_date)

            # 输出Excel
            if excel_data and output_excel:
                self._export_and_open_excel(excel_data, save_path)

            # 删除缓存文件
            try:
                temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")
                cache_file = os.path.join(temp_dir, "cache.json")
                if os.path.exists(cache_file) and not stopped_manually and not timeout_error_occurred:
                    os.remove(cache_file)
                    logger.info("处理完成，缓存文件已删除")
            except Exception as e:
                logger.error(f"删除缓存文件失败: {e}")

            # 完成处理
            if not stopped_manually and not timeout_error_occurred:
                self.status_bar.status_label.config(text="处理完成！")
                messagebox.showinfo("成功", "图像处理完成！")

        except Exception as e:
            logger.error(f"处理过程中发生错误: {e}")
            self.status_bar.status_label.config(text="处理过程中出错。")
            messagebox.showerror("错误", f"处理过程中发生错误: {e}")

        finally:
            # 恢复UI状态
            self._set_processing_state(False)

    def toggle_detection_preview(self) -> None:
        """切换是否显示检测结果"""
        # 如果正在批量处理，则强制显示检测结果
        if self.is_processing:
            self.show_detection_var.set(True)
            return

        selection = self.file_listbox.curselection()
        if not selection:
            self.show_detection_var.set(False)  # 如果没有选中图片，关闭开关
            return

        file_name = self.file_listbox.get(selection[0])
        file_path = os.path.join(self.file_path_entry.get(), file_name)

        # 检查是否有检测结果
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")
        photo_path = os.path.join(temp_dir, "photo")
        temp_result_path = os.path.join(photo_path, file_name)

        # 检查是否有对应的 JSON 文件
        base_name, _ = os.path.splitext(file_name)
        json_path = os.path.join(photo_path, f"{base_name}.json")

        # 如果显示结果开关打开
        if self.show_detection_var.get():
            if os.path.exists(temp_result_path):
                # 存在检测结果图像，显示它
                self.update_image_preview(temp_result_path, is_temp_result=True)

                # 如果存在JSON文件，读取并显示检测信息
                if os.path.exists(json_path):
                    try:
                        import json
                        with open(json_path, 'r', encoding='utf-8') as f:
                            detection_info = json.load(f)

                        # 构建检测信息并更新显示
                        species_info = {
                            '物种名称': detection_info.get('物种名称', ''),
                            '物种数量': detection_info.get('物种数量', ''),
                            '最低置信度': detection_info.get('最低置信度', ''),
                            '检测时间': detection_info.get('检测时间', '')
                        }
                        self._update_detection_info_from_json(species_info)
                    except Exception as e:
                        logger.error(f"读取检测信息JSON失败: {e}")
            elif hasattr(self, 'current_detection_results') and self.current_detection_results is not None:
                # 有当前检测结果但没有临时保存的图像，使用当前结果
                self.update_image_preview(file_path, True, self.current_detection_results)
            else:
                # 没有检测结果，显示原始图像并提示用户
                self.update_image_preview(file_path, False)
                messagebox.showinfo("提示", '当前图像尚未检测，请点击"检测当前图像"按钮。')
                self.show_detection_var.set(False)  # 自动关闭开关
        else:
            # 显示原始图像
            self.update_image_preview(file_path, False)

    def detect_current_image(self) -> None:
        """检测当前选中的图像"""
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一张图像。")
            return

        file_name = self.file_listbox.get(selection[0])
        file_path = os.path.join(self.file_path_entry.get(), file_name)

        # 显示处理状态
        self.status_bar.status_label.config(text="正在检测图像...")
        self.detect_button.config(state="disabled")

        # 在单独的线程中执行检测，避免界面卡顿
        threading.Thread(
            target=self._detect_image_thread,
            args=(file_path, file_name),
            daemon=True
        ).start()

    def _detect_image_thread(self, img_path: str, filename: str) -> None:
        """在单独线程中执行图像检测
        Args:
            img_path: 图像文件路径
            filename: 图像文件名
        """
        try:
            # 导入需要的依赖
            from collections import Counter
            from datetime import datetime

            # 使用现有代码模式进行检测
            if not self.image_processor.model:
                raise Exception("模型未加载")

            # 设置模型参数
            use_fp16 = self.use_fp16_var.get() and self.cuda_available
            iou = self.iou_var.get()
            conf = self.conf_var.get()
            augment = self.use_augment_var.get()
            agnostic_nms = self.use_agnostic_nms_var.get()

            # 进行检测
            results = self.image_processor.model(
                img_path,
                augment=augment,
                agnostic_nms=agnostic_nms,
                imgsz=1024,
                half=use_fp16,
                iou=iou,
                conf=conf
            )

            # 处理检测结果
            species_names = ""
            species_counts = ""
            n = 0
            min_confidence = None

            for r in results:
                data_list = r.boxes.cls.tolist()
                counts = Counter(data_list)
                species_dict = r.names
                confidences = r.boxes.conf.tolist()

                if confidences:
                    current_min_confidence = min(confidences)
                    if min_confidence is None or current_min_confidence < min_confidence:
                        min_confidence = "%.3f" % current_min_confidence

                for element, count in counts.items():
                    n += 1
                    species_name = species_dict[int(element)]
                    if n == 1:
                        species_names += species_name
                        species_counts += str(count)
                    else:
                        species_names += f",{species_name}"
                        species_counts += f",{count}"

            # 添加检测时间
            detection_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 构建结果字典
            species_info = {
                '物种名称': species_names,
                '物种数量': species_counts,
                'detect_results': results,
                '最低置信度': min_confidence,
                '检测时间': detection_time
            }

            # 保存检测结果以便在预览中使用
            self.current_detection_results = results

            # 保存检测结果到临时目录中
            if self.current_detection_results:
                # 保存图像
                self.image_processor.save_detection_temp(self.current_detection_results, filename)
                # 保存JSON
                self.image_processor.save_detection_info_json(self.current_detection_results, filename, species_info)

            # 切换到显示检测结果
            self.master.after(0, lambda: self.show_detection_var.set(True))

            # 更新预览图像
            self.master.after(0, lambda: self.update_image_preview(
                img_path, True, self.current_detection_results))

            # 更新信息文本
            self.master.after(0, lambda: self._update_detection_info(species_info))

        except Exception as err:
            error_msg = str(err)
            logger.error(f"检测图像失败: {error_msg}")
            self.master.after(0, lambda msg=error_msg: messagebox.showerror("错误", f"检测图像失败: {msg}"))
        finally:
            # 恢复按钮状态
            self.master.after(0, lambda: self.detect_button.config(state="normal"))
            self.master.after(0, lambda: self.status_bar.status_label.config(text="检测完成"))

    def _update_detection_info(self, species_info: Dict) -> None:
        """更新检测信息文本

        Args:
            species_info: 物种检测信息
        """
        self.info_text.config(state="normal")

        # 获取当前文本
        current_text = self.info_text.get(1.0, tk.END).strip()

        # 在文本末尾添加检测信息
        detection_parts = ["检测结果:"]
        if species_info['物种名称']:
            species_names = species_info['物种名称'].split(',')
            species_counts = species_info['物种数量'].split(',')

            species_info_parts = []
            for i, (name, count) in enumerate(zip(species_names, species_counts)):
                species_info_parts.append(f"{name}: {count}只")
            detection_parts.append(", ".join(species_info_parts))

            if species_info['最低置信度']:
                detection_parts.append(f"最低置信度: {species_info['最低置信度']}")
        else:
            detection_parts.append("未检测到已知物种")

        # 创建新的文本内容
        detection_info = " | ".join(detection_parts)
        new_text = current_text + "\n" + detection_info

        # 设置新的文本内容
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, new_text)
        self.info_text.config(state="disabled")

    def _update_iou_label(self, value) -> None:
        """更新IOU标签显示"""
        iou_value = float(value)
        self.iou_label.config(text=f"{iou_value:.2f}")

    def _update_conf_label(self, value) -> None:
        """更新置信度标签显示"""
        conf_value = float(value)
        self.conf_label.config(text=f"{conf_value:.2f}")

    def _reset_model_params(self) -> None:
        """重置模型参数到默认值"""
        self.iou_var.set(0.3)
        self.conf_var.set(0.25)
        self.use_fp16_var.set(False)
        self.use_augment_var.set(True)
        self.use_agnostic_nms_var.set(True)

        # 更新标签
        self._update_iou_label(0.3)
        self._update_conf_label(0.25)

        messagebox.showinfo("参数重置", "模型参数已恢复为默认值")

    def _get_image_files(self, directory: str) -> List[str]:
        """获取目录中的所有图片文件

        Args:
            directory: 目录路径

        Returns:
            图片文件名列表
        """
        return [
            item for item in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, item)) and
               item.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS)
        ]

    def _copy_image_by_species(self, img_path: str, save_path: str, species_names: List[str]) -> None:
        """按物种分类复制图片

        Args:
            img_path: 图片路径
            save_path: 保存路径
            species_names: 物种名称列表
        """
        try:
            for name in species_names:
                if name:
                    to_path = os.path.join(save_path, name)
                else:
                    to_path = os.path.join(save_path, "None")

                os.makedirs(to_path, exist_ok=True)
                copy(img_path, to_path)
        except Exception as e:
            logger.error(f"复制图片失败: {e}")

    def _update_progress(self, processed: int, total: int, start_time: float) -> None:
        """更新进度显示

        Args:
            processed: 已处理文件数
            total: 总文件数
            start_time: 开始时间
        """
        # 更新进度条
        self.progress_frame.progress_var.set(processed)

        # 计算速度和剩余时间
        elapsed_time = time.time() - start_time
        if processed > 0:
            # 计算处理速度
            speed = processed / elapsed_time
            speed_text = f"速度: {speed:.2f} 张/秒"

            # 计算剩余时间
            time_per_file = elapsed_time / processed
            remaining_files = total - processed
            estimated_time = time_per_file * remaining_files

            if estimated_time > 60:
                minutes = int(estimated_time // 60)
                seconds = int(estimated_time % 60)
                time_text = f"剩余时间: {minutes}分{seconds}秒"
            else:
                time_text = f"剩余时间: {int(estimated_time)}秒"

            # 更新标签
            self.progress_frame.speed_label.config(text=speed_text)
            self.progress_frame.time_label.config(text=time_text)

        # 刷新UI
        self.master.update_idletasks()

    def _export_and_open_excel(self, excel_data: List[Dict], save_path: str) -> None:
        """导出Excel并询问是否打开

        Args:
            excel_data: Excel数据
            save_path: 保存路径
        """
        from system.config import DEFAULT_EXCEL_FILENAME

        output_file_path = os.path.join(save_path, DEFAULT_EXCEL_FILENAME)
        if DataProcessor.export_to_excel(excel_data, output_file_path):
            messagebox.showinfo("成功", f"物种检测信息已成功导出到Excel文件:\n{output_file_path}")

            # 询问是否打开文件
            if messagebox.askyesno("打开文件", "是否立即打开Excel文件?"):
                try:
                    os.startfile(output_file_path)
                except Exception as e:
                    logger.error(f"打开Excel文件失败: {e}")
                    messagebox.showerror("错误", f"无法打开Excel文件: {e}")

    def json_serial(obj):
        """用于JSON序列化处理datetime对象的函数"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    def _update_detection_info_from_json(self, species_info: Dict) -> None:
        """从JSON更新检测信息文本

        Args:
            species_info: 物种检测信息
        """
        self.info_text.config(state="normal")

        # 获取当前文本（保留文件基本信息）
        current_text = self.info_text.get(1.0, "2.end")  # 只保留前两行基本信息

        # 在文本末尾添加检测信息
        detection_parts = ["检测结果:"]
        if species_info['物种名称']:
            species_names = species_info['物种名称'].split(',')
            species_counts = species_info['物种数量'].split(',')

            species_info_parts = []
            for i, (name, count) in enumerate(zip(species_names, species_counts)):
                species_info_parts.append(f"{name}: {count}只")
            detection_parts.append(", ".join(species_info_parts))

            if species_info['最低置信度']:
                detection_parts.append(f"最低置信度: {species_info['最低置信度']}")

            if species_info['检测时间']:
                detection_parts.append(f"检测时间: {species_info['检测时间']}")
        else:
            detection_parts.append("未检测到已知物种")

        # 创建新的文本内容
        detection_info = " | ".join(detection_parts)
        new_text = current_text + "\n" + detection_info

        # 设置新的文本内容
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, new_text)
        self.info_text.config(state="disabled")

    def _clean_temp_photo_directory(self) -> None:
        """清空临时图像文件目录"""
        try:
            import os
            import shutil
            import gc

            # 先释放所有可能的图像引用
            self.image_label.config(image='')  # 清除图像标签显示
            if hasattr(self, 'preview_image'):
                self.preview_image = None
            if hasattr(self, 'original_image'):
                self.original_image = None
            if hasattr(self, 'current_detection_results'):
                self.current_detection_results = None

            # 强制垃圾回收以确保释放所有图像引用
            gc.collect()

            # 获取临时图像目录路径
            temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")
            photo_path = os.path.join(temp_dir, "photo")

            # 如果目录存在，清空其中的所有文件
            if os.path.exists(photo_path):
                # 记录清理操作
                logger.info(f"正在清空临时图像目录: {photo_path}")

                # 尝试多次删除，有时文件可能会被延迟释放
                attempts = 3
                for attempt in range(attempts):
                    failed_files = []

                    for file in os.listdir(photo_path):
                        file_path = os.path.join(photo_path, file)
                        try:
                            if os.path.isfile(file_path):
                                # 使用try-except捕获权限和锁定文件的错误
                                try:
                                    os.unlink(file_path)
                                except PermissionError:
                                    # 可能是Windows文件锁定，使用标记删除文件的方法
                                    try:
                                        import stat
                                        # 修改文件权限
                                        os.chmod(file_path, stat.S_IWRITE)
                                        os.unlink(file_path)
                                    except:
                                        failed_files.append(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path, ignore_errors=True)
                        except Exception as e:
                            logger.error(f"清除临时文件失败 {file_path}: {e}")
                            failed_files.append(file_path)

                    # 如果所有文件都已成功删除，跳出重试循环
                    if not failed_files:
                        break

                    # 如果不是最后一次尝试，等待一段时间再重试
                    if attempt < attempts - 1 and failed_files:
                        import time
                        time.sleep(0.5)  # 等待500毫秒
                        gc.collect()  # 再次强制垃圾回收

                        # 记录哪些文件无法删除
                        if failed_files:
                            logger.warning(f"第 {attempt + 1} 次尝试后，仍有 {len(failed_files)} 个文件无法删除")

                # 如果仍有无法删除的文件，记录它们
                if failed_files:
                    logger.error(f"无法删除以下文件: {failed_files}")
                    # 可以考虑给用户显示警告信息
                    self.master.after(0, lambda: messagebox.showwarning("警告",
                                                                        f"有 {len(failed_files)} 个临时文件无法删除。这些文件可能正在被系统占用。"))
                else:
                    logger.info("临时图像目录清空完成")
            else:
                # 目录不存在，创建它
                os.makedirs(photo_path, exist_ok=True)
                logger.info(f"创建临时图像目录: {photo_path}")

        except Exception as e:
            logger.error(f"清空临时图像目录失败: {e}")
            self.master.after(0, lambda err=str(e): messagebox.showerror("错误", f"清空临时图像目录失败: {err}"))

    def _has_detection_result(self, file_name: str) -> bool:
        """检查图像是否有检测结果

        Args:
            file_name: 图像文件名

        Returns:
            bool: 是否存在检测结果
        """
        try:
            temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")
            photo_path = os.path.join(temp_dir, "photo")
            temp_result_path = os.path.join(photo_path, file_name)

            # 检查是否有对应的 JSON 文件
            base_name, _ = os.path.splitext(file_name)
            json_path = os.path.join(photo_path, f"{base_name}.json")

            return os.path.exists(temp_result_path) and os.path.exists(json_path)
        except Exception as e:
            logger.error(f"检查检测结果失败: {e}")
            return False
