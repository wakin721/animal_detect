"""
GUI模块 - 提供应用程序主界面和交互逻辑
"""

import os
import time
import logging
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import cv2
from shutil import copy
from typing import Dict, List, Optional

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

logger = logging.getLogger(__name__)

class ObjectDetectionGUI:
    """物种检测GUI应用程序 - Windows 11风格界面"""

    def __init__(self, master: tk.Tk):
        """初始化GUI应用

        Args:
            master: Tkinter主窗口
        """
        self.master = master
        master.title(APP_TITLE)

        # 应用Windows 11主题
        sv_ttk.set_theme("light")

        # 设置窗口尺寸和位置
        width, height = 730, 730
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        master.geometry(f"{width}x{height}+{x}+{y}")

        # 设置窗口图标
        try:
            ico_path = resource_path(os.path.join("res", "ico.ico"))
            master.iconbitmap(ico_path)
        except Exception as e:
            logger.warning(f"无法加载窗口图标: {e}")

        # 初始化模型
        model_path = resource_path(os.path.join("res", "predict.pt"))
        self.image_processor = ImageProcessor(model_path)

        # 状态变量
        self.is_processing = False
        self.processing_stop_flag = threading.Event()
        self.preview_image = None
        self.current_detection_results = None
        self.original_image = None  # 保存原始图像
        self.current_image_path = None  # 保存当前图像路径

        # 创建GUI元素
        self._create_ui_elements()

        # 绑定事件
        self._bind_events()

        # 检查模型是否加载成功
        if not self.image_processor.model:
            messagebox.showerror("错误", "模型文件未找到。请检查应用程序目录中的模型文件。")
            self.start_stop_button["state"] = "disabled"

    def _create_ui_elements(self) -> None:
        """创建GUI界面元素"""
        # 配置主窗口
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(1, weight=1)

        # 创建标题栏
        title_frame = ttk.Frame(self.master)
        title_frame.grid(row=0, column=0, sticky="ew", padx=PADDING, pady=(PADDING, 0))

        title_label = ttk.Label(title_frame, text=APP_TITLE.split('v')[0], font=('Segoe UI', 16, 'bold'))
        title_label.pack(side="left", padx=0)

        # 主内容区域 - 使用笔记本控件创建选项卡界面
        self.notebook = ttk.Notebook(self.master)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=PADDING, pady=PADDING)

        # 选项卡1：基本设置
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="基本设置")

        # 路径设置区域
        paths_frame = ModernFrame(self.settings_frame, title="路径设置")
        paths_frame.pack(fill="x", padx=PADDING, pady=PADDING, anchor="n")

        # 文件路径
        file_path_frame = ttk.Frame(paths_frame)
        file_path_frame.pack(fill="x", padx=PADDING, pady=5)

        file_path_label = ttk.Label(file_path_frame, text="图像文件路径:", font=NORMAL_FONT)
        file_path_label.pack(side="top", anchor="w")

        file_path_entry_frame = ttk.Frame(file_path_frame)
        file_path_entry_frame.pack(fill="x", pady=2)

        self.file_path_entry = ttk.Entry(file_path_entry_frame, font=NORMAL_FONT)
        self.file_path_entry.pack(side="left", fill="x", expand=True)

        self.file_path_button = ttk.Button(
            file_path_entry_frame, text="浏览", command=self.browse_file_path, width=BUTTON_WIDTH)
        self.file_path_button.pack(side="right", padx=(5, 0))

        # 保存路径
        save_path_frame = ttk.Frame(paths_frame)
        save_path_frame.pack(fill="x", padx=PADDING, pady=5)

        save_path_label = ttk.Label(save_path_frame, text="结果保存路径:", font=NORMAL_FONT)
        save_path_label.pack(side="top", anchor="w")

        save_path_entry_frame = ttk.Frame(save_path_frame)
        save_path_entry_frame.pack(fill="x", pady=2)

        self.save_path_entry = ttk.Entry(save_path_entry_frame, font=NORMAL_FONT)
        self.save_path_entry.pack(side="left", fill="x", expand=True)

        self.save_path_button = ttk.Button(
            save_path_entry_frame, text="浏览", command=self.browse_save_path, width=BUTTON_WIDTH)
        self.save_path_button.pack(side="right", padx=(5, 0))

        # 功能选项区域
        options_frame = ModernFrame(self.settings_frame, title="功能选项")
        options_frame.pack(fill="x", padx=PADDING, pady=PADDING, anchor="n")

        # 创建选项
        self.save_detect_image_var = tk.BooleanVar(value=True)
        self.output_excel_var = tk.BooleanVar(value=True)
        self.copy_img_var = tk.BooleanVar(value=False)
        self.use_fp16_var = tk.BooleanVar(value=False)  # 新增FP16加速选项

        options_container = ttk.Frame(options_frame)
        options_container.pack(fill="x", padx=PADDING, pady=PADDING)

        # 使用新的开关控件替代复选框
        save_detect_switch = ttk.Checkbutton(
            options_container, text="保存探测结果图片", variable=self.save_detect_image_var,
            style="Switch.TCheckbutton")
        save_detect_switch.grid(row=0, column=0, sticky="w", pady=5)

        output_excel_switch = ttk.Checkbutton(
            options_container, text="输出为Excel表格", variable=self.output_excel_var,
            style="Switch.TCheckbutton")
        output_excel_switch.grid(row=1, column=0, sticky="w", pady=5)

        copy_img_switch = ttk.Checkbutton(
            options_container, text="按物种分类图片", variable=self.copy_img_var,
            style="Switch.TCheckbutton")
        copy_img_switch.grid(row=2, column=0, sticky="w", pady=5)

        # 选项卡2：图像预览
        self.preview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.preview_frame, text="图像预览")

        # 创建预览区域
        preview_content = ttk.Frame(self.preview_frame)
        preview_content.pack(fill="both", expand=True, padx=PADDING, pady=PADDING)

        # 在左侧添加文件列表
        list_frame = ttk.LabelFrame(preview_content, text="图像文件")
        list_frame.pack(side="left", fill="y", padx=(0, PADDING))

        self.file_listbox = tk.Listbox(list_frame, width=25, font=NORMAL_FONT)
        self.file_listbox.pack(side="left", fill="both", expand=True)

        file_list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        file_list_scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=file_list_scrollbar.set)

        # 添加预览图像区域
        image_frame = ttk.LabelFrame(preview_content, text="图像预览")
        image_frame.pack(side="right", fill="both", expand=True)

        self.image_label = ttk.Label(image_frame, text="请从左侧列表选择图像", anchor="center")
        self.image_label.pack(fill="both", expand=True, padx=PADDING, pady=PADDING)

        # 为图像标签添加双击事件提示
        image_hint = ttk.Label(image_frame, text="双击图像可放大查看", font=SMALL_FONT, foreground="gray")
        image_hint.pack(side="bottom", fill="x", padx=PADDING, pady=(0, PADDING))

        # 添加底部信息框
        info_frame = ttk.LabelFrame(self.preview_frame, text="图像信息")
        info_frame.pack(fill="x", padx=PADDING, pady=(0, PADDING))

        self.info_text = tk.Text(info_frame, height=3, font=NORMAL_FONT, wrap="word")
        self.info_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.info_text.config(state="disabled")

        # 添加切换按钮
        preview_controls = ttk.Frame(self.preview_frame)
        preview_controls.pack(fill="x", padx=PADDING, pady=(PADDING, 0))

        self.show_detection_var = tk.BooleanVar(value=False)
        show_detection_switch = ttk.Checkbutton(
            preview_controls, text="显示检测结果", variable=self.show_detection_var,
            style="Switch.TCheckbutton", command=self.toggle_detection_preview)
        show_detection_switch.pack(side="left", padx=PADDING)

        # 添加手动检测按钮
        self.detect_button = ttk.Button(
            preview_controls, text="检测当前图像", command=self.detect_current_image, width=BUTTON_WIDTH)
        self.detect_button.pack(side="right", padx=PADDING, pady=5)

        # 选项卡3：高级设置
        self.advanced_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.advanced_frame, text="高级设置")

        # 创建高级设置内容 - 模型参数设置
        advanced_content = ModernFrame(self.advanced_frame, title="模型参数设置")
        advanced_content.pack(fill="x", padx=PADDING, pady=PADDING)

        # 创建参数设置框架
        params_frame = ttk.Frame(advanced_content)
        params_frame.pack(fill="x", padx=PADDING, pady=PADDING)

        # 初始化模型参数变量
        self.iou_var = tk.DoubleVar(value=0.3)  # IOU阈值，默认0.3
        self.conf_var = tk.DoubleVar(value=0.25)  # 置信度阈值，默认0.25
        self.use_fp16_var = tk.BooleanVar(value=False)  # FP16加速，默认开启
        self.use_augment_var = tk.BooleanVar(value=True)  # 数据增强，默认开启
        self.use_agnostic_nms_var = tk.BooleanVar(value=True)  # 类别无关NMS，默认开启

        # 创建参数控件 - 使用网格布局
        params_frame.columnconfigure(0, weight=1)
        params_frame.columnconfigure(1, weight=1)

        row = 0

        # IOU阈值滑动条
        ttk.Label(params_frame, text="IOU阈值:", font=NORMAL_FONT).grid(row=row, column=0, sticky="w", pady=(10, 0))
        row += 1

        iou_frame = ttk.Frame(params_frame)
        iou_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=(0, 10), pady=(0, 10))

        iou_scale = ttk.Scale(iou_frame, from_=0.1, to=0.9, orient="horizontal",
                              variable=self.iou_var, command=self._update_iou_label)
        iou_scale.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.iou_label = ttk.Label(iou_frame, text="0.30", width=4)
        self.iou_label.pack(side="right")

        row += 1

        # 置信度阈值滑动条
        ttk.Label(params_frame, text="置信度阈值:", font=NORMAL_FONT).grid(row=row, column=0, sticky="w", pady=(10, 0))
        row += 1

        conf_frame = ttk.Frame(params_frame)
        conf_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=(0, 10), pady=(0, 10))

        conf_scale = ttk.Scale(conf_frame, from_=0.05, to=0.95, orient="horizontal",
                               variable=self.conf_var, command=self._update_conf_label)
        conf_scale.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.conf_label = ttk.Label(conf_frame, text="0.25", width=4)
        self.conf_label.pack(side="right")

        row += 1

        # 创建开关组
        switches_frame = ttk.LabelFrame(params_frame, text="模型优化选项")
        switches_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)

        # FP16加速
        fp16_switch = ttk.Checkbutton(
            switches_frame, text="使用FP16加速推理", variable=self.use_fp16_var,
            style="Switch.TCheckbutton")
        fp16_switch.pack(anchor="w", padx=10, pady=(10, 5))

        fp16_desc = ttk.Label(
            switches_frame,
            text="减少内存使用并提高速度，可能略微降低精度",
            font=SMALL_FONT,
            foreground="gray")
        fp16_desc.pack(anchor="w", padx=30, pady=(0, 10))

        # 数据增强
        augment_switch = ttk.Checkbutton(
            switches_frame, text="使用数据增强", variable=self.use_augment_var,
            style="Switch.TCheckbutton")
        augment_switch.pack(anchor="w", padx=10, pady=(5, 5))

        augment_desc = ttk.Label(
            switches_frame,
            text="通过测试时增强提高检测准确性，但会降低速度",
            font=SMALL_FONT,
            foreground="gray")
        augment_desc.pack(anchor="w", padx=30, pady=(0, 10))

        # 类别无关NMS
        agnostic_nms_switch = ttk.Checkbutton(
            switches_frame, text="使用类别无关NMS", variable=self.use_agnostic_nms_var,
            style="Switch.TCheckbutton")
        agnostic_nms_switch.pack(anchor="w", padx=10, pady=(5, 5))

        agnostic_nms_desc = ttk.Label(
            switches_frame,
            text="忽略类别信息进行非极大值抑制，对多类别场景有优势",
            font=SMALL_FONT,
            foreground="gray")
        agnostic_nms_desc.pack(anchor="w", padx=30, pady=(0, 10))

        # 添加按钮框架 - 按钮并排放置
        buttons_frame = ttk.Frame(self.advanced_frame)
        buttons_frame.pack(fill="x", padx=PADDING, pady=PADDING)

        # 查看参数说明按钮 (左侧)
        help_button = ttk.Button(
            buttons_frame, text="查看参数说明", command=self.show_params_help, width=BUTTON_WIDTH)
        help_button.pack(side="left", padx=(0, 5))

        # 恢复默认参数按钮 (右侧)
        reset_button = ttk.Button(
            buttons_frame, text="恢复默认参数", command=self._reset_model_params, width=BUTTON_WIDTH)
        reset_button.pack(side="right")

        # 选项卡4：关于
        self.about_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.about_frame, text="关于")

        about_content = ttk.Frame(self.about_frame)
        about_content.pack(fill="both", expand=True, padx=PADDING*2, pady=PADDING*2)

        # 应用标志
        try:
            logo_path = resource_path(os.path.join("res", "logo.png"))
            logo_img = Image.open(logo_path)
            logo_img = logo_img.resize((100, 100), Image.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_img)
            logo_label = ttk.Label(about_content, image=logo_photo)
            logo_label.image = logo_photo  # 保持引用
            logo_label.pack(pady=(0, PADDING))
        except Exception:
            # 如果没有图标，显示文本标题
            logo_label = ttk.Label(about_content, text=APP_TITLE, font=('Segoe UI', 18, 'bold'))
            logo_label.pack(pady=(0, PADDING))

        # 应用描述
        desc_label = ttk.Label(
            about_content,
            text="一款高效的物种信息检测应用程序，支持图像物种识别、探测图片保存、Excel输出和图像分类功能。",
            font=NORMAL_FONT,
            wraplength=400,
            justify="center"
        )
        desc_label.pack(pady=PADDING)

        # 版本信息
        version_label = ttk.Label(
            about_content,
            text=f"版本: {APP_VERSION}",
            font=NORMAL_FONT
        )
        version_label.pack(pady=(0, PADDING*2))

        # 当前用户
        user_label = ttk.Label(
            about_content,
            text="作者：和錦わきん",
            font=SMALL_FONT
        )
        user_label.pack()

        # 底部控制区域
        control_frame = ttk.Frame(self.master)
        control_frame.grid(row=2, column=0, sticky="ew", padx=PADDING, pady=(0, PADDING))

        # 进度条和信息
        self.progress_frame = SpeedProgressBar(control_frame)
        self.progress_frame.pack(fill="x", pady=(0, PADDING))

        # 控制按钮
        buttons_frame = ttk.Frame(control_frame)
        buttons_frame.pack(fill="x")

        self.start_stop_button = ttk.Button(
            buttons_frame, text="开始处理", command=self.toggle_processing_state, width=BUTTON_WIDTH)
        self.start_stop_button.pack(side="right", padx=(5, 0))

        # 底部状态栏
        self.status_bar = InfoBar(self.master)
        self.status_bar.grid(row=3, column=0, sticky="ew")

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

        # 添加选项卡切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

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
        """处理选项卡切换事件"""
        # 如果切换到预览选项卡
        if self.notebook.index(self.notebook.select()) == 1:
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

    def on_closing(self) -> None:
        """窗口关闭事件处理"""
        if self.is_processing:
            if not messagebox.askyesno("警告", "处理正在进行中，确定要退出程序吗？"):
                return

        self.master.destroy()

    def browse_file_path(self) -> None:
        """浏览文件路径"""
        folder_selected = filedialog.askdirectory(title="选择图像文件所在文件夹")
        if folder_selected:
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, folder_selected)
            self.update_file_list(folder_selected)

            # 如果当前在预览选项卡，自动选择第一个文件
            if self.notebook.index(self.notebook.select()) == 1 and self.file_listbox.size() > 0:
                self.file_listbox.selection_set(0)
                self.on_file_selected(None)

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

        file_name = self.file_listbox.get(selection[0])
        file_path = os.path.join(self.file_path_entry.get(), file_name)

        # 保存当前图像路径
        self.current_image_path = file_path

        # 更新预览图像
        self.update_image_preview(file_path)

        # 更新图像信息
        self.update_image_info(file_path, file_name)

    def update_image_preview(self, file_path: str, show_detection: bool = False, detection_results=None) -> None:
        """更新图像预览

        Args:
            file_path: 图像文件路径
            show_detection: 是否显示检测结果
            detection_results: YOLO检测结果对象
        """
        try:
            if show_detection and detection_results is not None:
                # 获取YOLO绘制的检测结果图像
                # 这里使用YOLO自带的绘制功能获取处理后的图像
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

            self.image_label.config(image=photo)
            self.image_label.image = photo  # 保持引用

            # 将预览图像设置为当前图像
            self.preview_image = img
        except Exception as e:
            logger.error(f"更新图像预览失败: {e}")
            self.image_label.config(image='', text="无法加载图像")
            self.original_image = None

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
        file_path = self.file_path_entry.get()
        if os.path.isdir(file_path):
            self.update_file_list(file_path)
            self.status_bar.status_label.config(text=f"已设置文件路径: {file_path}")
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
            self.start_processing()
        else:
            self.stop_processing()

    def start_processing(self) -> None:
        """开始处理图像"""
        # 获取配置
        file_path = self.file_path_entry.get()
        save_path = self.save_path_entry.get()
        save_detect_image = self.save_detect_image_var.get()
        output_excel = self.output_excel_var.get()
        copy_img = self.copy_img_var.get()
        use_fp16 = self.use_fp16_var.get()  # 从高级设置中获取FP16设置

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

        # 启动处理线程
        threading.Thread(
            target=self._process_images_thread,
            args=(file_path, save_path, save_detect_image, output_excel, copy_img, use_fp16),  # 传递FP16设置
            daemon=True
        ).start()

    def stop_processing(self) -> None:
        """停止处理图像"""
        if messagebox.askyesno("停止确认", "确定要停止图像处理吗？"):
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

            # 禁用选项卡
            self.notebook.tab(0, state="disabled")
            self.notebook.tab(2, state="disabled")
            self.notebook.tab(3, state="disabled")
        else:
            self.start_stop_button.config(text="开始处理")
            self.progress_frame.speed_label.config(text="")
            self.progress_frame.time_label.config(text="")

            # 启用配置选项
            for widget in (self.file_path_entry, self.file_path_button,
                           self.save_path_entry, self.save_path_button):
                widget["state"] = "normal"

            # 启用选项卡
            self.notebook.tab(0, state="normal")
            self.notebook.tab(2, state="normal")
            self.notebook.tab(3, state="normal")

    def _process_images_thread(self, file_path: str, save_path: str,
                               save_detect_image: bool, output_excel: bool,
                               copy_img: bool, use_fp16: bool) -> None:
        """图像处理线程

        Args:
            file_path: 源文件路径
            save_path: 保存路径
            save_detect_image: 是否保存探测图片
            output_excel: 是否输出Excel表格
            copy_img: 是否按物种分类复制图片
            use_fp16: 是否使用FP16加速推理
        """
        start_time = time.time()
        excel_data = []
        processed_files = 0
        stopped_manually = False
        earliest_date = None

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

                    # 检测物种 - 使用高级设置参数
                    species_info = self.image_processor.detect_species(
                        img_path,
                        use_fp16=use_fp16,
                        iou=iou,
                        conf=conf,
                        augment=augment,
                        agnostic_nms=agnostic_nms
                    )

                    # 更新图像信息
                    image_info.update(species_info)

                    # 更新预览图像 - 显示检测结果
                    detect_results = species_info['detect_results']
                    self.master.after(0, lambda p=img_path, d=detect_results:
                    self.update_image_preview(p, True, d))

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

            # 处理独立探测首只
            excel_data = DataProcessor.process_independent_detection(excel_data)

            # 计算工作天数
            if earliest_date:
                excel_data = DataProcessor.calculate_working_days(excel_data, earliest_date)

            # 输出Excel
            if excel_data and output_excel:
                self._export_and_open_excel(excel_data, save_path)

            # 完成处理
            if not stopped_manually:
                self.status_bar.status_label.config(text="处理完成！")
                messagebox.showinfo("成功", "图像处理完成！")

        except Exception as e:
            logger.error(f"处理过程中发生错误: {e}")
            self.status_bar.status_label.config(text="处理过程中出错。")
            messagebox.showerror("错误", f"处理过程中发生错误: {e}")

        finally:
            # 恢复UI状态
            self

    def toggle_detection_preview(self) -> None:
        """切换是否显示检测结果"""
        selection = self.file_listbox.curselection()
        if not selection:
            return

        file_name = self.file_listbox.get(selection[0])
        file_path = os.path.join(self.file_path_entry.get(), file_name)

        # 获取当前选中文件的检测结果
        if hasattr(self, 'current_detection_results') and self.current_detection_results is not None:
            self.update_image_preview(
                file_path,
                self.show_detection_var.get(),
                self.current_detection_results
            )
        else:
            # 如果没有检测结果，显示原始图像
            self.update_image_preview(file_path, False)

            if self.show_detection_var.get():
                messagebox.showinfo("提示", '当前图像尚未检测，请点击"检测当前图像"按钮。')
                self.show_detection_var.set(False)

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
            # 检测物种 - 使用高级设置参数
            species_info = self.image_processor.detect_species(
                img_path,
                use_fp16=self.use_fp16_var.get(),
                iou=self.iou_var.get(),
                conf=self.conf_var.get(),
                augment=self.use_augment_var.get(),
                agnostic_nms=self.use_agnostic_nms_var.get()
            )

            # 保存检测结果以便在预览中使用
            self.current_detection_results = species_info['detect_results']

            # 切换到显示检测结果
            self.master.after(0, lambda: self.show_detection_var.set(True))

            # 更新预览图像
            self.master.after(0, lambda: self.update_image_preview(
                img_path, True, self.current_detection_results))

            # 更新信息文本
            self.master.after(0, lambda: self._update_detection_info(species_info))

        except Exception as e:
            logger.error(f"检测图像失败: {e}")
            self.master.after(0, lambda: messagebox.showerror("错误", f"检测图像失败: {e}"))
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
