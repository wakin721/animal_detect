"""
物种信息检测应用程序
支持图像物种识别、探测图片保存、Excel输出和图像分类功能
Windows 11 风格界面 - 优化版本
"""

import os
import sys
import time
import logging
import threading
import webbrowser
from datetime import datetime
from shutil import copy
from collections import Counter
from typing import Dict, List, Optional, Tuple, Any, Union
from functools import partial
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sv_ttk  # Sun Valley ttk theme for Windows 11 style
import cv2

import pandas as pd
import numpy as np
from PIL import Image, ImageTk
from PIL.ExifTags import TAGS
from ultralytics import YOLO

# 配置日志
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 配置常量
APP_TITLE = "物种信息检测 v4.5"
APP_VERSION = "4.5.1"
DEFAULT_EXCEL_FILENAME = "物种检测信息.xlsx"
SUPPORTED_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
DATE_FORMATS = ['%Y:%m:%d %H:%M:%S', '%Y:%d:%m %H:%M:%S', '%Y-%m-%d %H:%M:%S']
INDEPENDENT_DETECTION_THRESHOLD = 30 * 60  # 30分钟，单位：秒

# 界面相关常量
PADDING = 10
BUTTON_WIDTH = 14
LARGE_FONT = ('Segoe UI', 11)
NORMAL_FONT = ('Segoe UI', 10)
SMALL_FONT = ('Segoe UI', 9)


def resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径，支持PyInstaller打包"""
    try:
        if getattr(sys, 'frozen', False):  # 是否使用PyInstaller打包
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)
    except Exception as e:
        logger.error(f"获取资源路径失败: {e}")
        return os.path.join(os.path.abspath("."), relative_path)


class ImageProcessor:
    """处理图像、检测物种的核心类"""

    def __init__(self, model_path: str):
        """初始化图像处理器

        Args:
            model_path: YOLO模型文件路径
        """
        self.model = self._load_model(model_path)

    def _load_model(self, model_path: str) -> Optional[YOLO]:
        """加载YOLO模型

        Args:
            model_path: 模型文件路径

        Returns:
            加载的YOLO模型或None（如果加载失败）
        """
        try:
            logger.info(f"正在加载模型: {model_path}")
            return YOLO(model_path)
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return None

    def detect_species(self, img_path: str, use_fp16: bool = True,
                       iou: float = 0.3, conf: float = 0.25,
                       augment: bool = True, agnostic_nms: bool = True) -> Dict[str, Any]:
        """使用YOLO模型识别图片中的物种

        Args:
            img_path: 图片文件路径
            use_fp16: 是否使用FP16加速推理
            iou: IOU阈值
            conf: 置信度阈值
            augment: 是否使用数据增强
            agnostic_nms: 是否使用类别无关NMS

        Returns:
            包含物种信息的字典
        """
        species_names = ""
        species_counts = ""
        n = 0
        detect_results = None
        min_confidence = None

        if not self.model:
            return {
                '物种名称': species_names,
                '物种数量': species_counts,
                'detect_results': detect_results,
                '最低置信度': min_confidence
            }

        try:
            # 使用参数进行检测
            results = self.model(
                img_path,
                augment=augment,
                agnostic_nms=agnostic_nms,
                imgsz=1024,
                half=use_fp16,
                iou=iou,
                conf=conf
            )
            detect_results = results

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
        except Exception as e:
            logger.error(f"物种检测失败: {e}")

        return {
            '物种名称': species_names,
            '物种数量': species_counts,
            'detect_results': detect_results,
            '最低置信度': min_confidence
        }

    def save_detection_result(self, results: Any, image_name: str, save_path: str) -> None:
        """保存探测结果图片

        Args:
            results: YOLO检测结果
            image_name: 原始图片名称
            save_path: 保存路径
        """
        if not results:
            return

        try:
            # 创建结果保存目录
            result_path = os.path.join(save_path, "result")
            os.makedirs(result_path, exist_ok=True)

            for c, h in enumerate(results):
                # 获取第一个检测到的物种名称
                species_name = self._get_first_detected_species(results)
                result_file = os.path.join(result_path, f"{image_name}_result_{species_name}.jpg")
                h.save(filename=result_file)
        except Exception as e:
            logger.error(f"保存检测结果图片失败: {e}")

    def _get_first_detected_species(self, results: Any) -> str:
        """从检测结果中获取第一个物种的名称

        Args:
            results: YOLO检测结果

        Returns:
            物种名称或空字符串
        """
        try:
            for r in results:
                if r.boxes and len(r.boxes.cls) > 0:
                    return r.names[int(r.boxes.cls[0].item())]
        except Exception as e:
            logger.error(f"获取物种名称失败: {e}")
        return "unknown"


class ImageMetadataExtractor:
    """图像元数据提取器，用于获取图像的EXIF信息"""

    @staticmethod
    def extract_metadata(img_path: str, filename: str) -> Tuple[Dict[str, Any], Optional[Image.Image]]:
        """提取图像元数据

        Args:
            img_path: 图像文件路径
            filename: 图像文件名

        Returns:
            包含元数据的字典和PIL图像对象
        """
        try:
            img = Image.open(img_path)
            file_type = filename.split('.')[-1].lower()

            image_info = {
                '文件名': filename,
                '格式': file_type,
                '拍摄日期': None,
                '拍摄时间': None,
                '拍摄日期对象': None,
                '工作天数': None,
                '物种名称': '',
                '物种数量': '',
                'detect_results': None,
                '最低置信度': None,
                '独立探测首只': '',
            }

            # 提取EXIF数据
            exif = img._getexif()
            if exif:
                date_taken = ImageMetadataExtractor._get_date_from_exif(exif, filename)
                if date_taken:
                    image_info['拍摄日期'] = date_taken.strftime('%Y-%m-%d')
                    image_info['拍摄时间'] = date_taken.strftime('%H:%M')
                    image_info['拍摄日期对象'] = date_taken

            return image_info, img
        except Exception as e:
            logger.error(f"提取图像元数据失败 ({filename}): {e}")
            return {
                '文件名': filename,
                '格式': filename.split('.')[-1].lower(),
            }, None

    @staticmethod
    def _get_date_from_exif(exif: Dict, filename: str) -> Optional[datetime]:
        """从EXIF数据中提取拍摄日期

        Args:
            exif: EXIF数据字典
            filename: 文件名（用于日志记录）

        Returns:
            日期时间对象或None
        """
        # 尝试从两个可能的EXIF标签中获取日期
        date_str = exif.get(36867) or exif.get(306)
        if not date_str:
            return None

        # 尝试不同的日期格式
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.warning(f"无法解析图片 '{filename}' 的日期格式: '{date_str}'")
        return None


class DataProcessor:
    """数据处理类，处理图像信息集合"""

    @staticmethod
    def calculate_working_days(image_info_list: List[Dict], earliest_date: Optional[datetime]) -> List[Dict]:
        """计算每张图片的工作天数

        Args:
            image_info_list: 图像信息列表
            earliest_date: 最早的拍摄日期

        Returns:
            更新后的图像信息列表
        """
        if not earliest_date:
            logger.warning("无法计算工作天数：未找到任何有效拍摄日期")
            return image_info_list

        for info in image_info_list:
            date_taken = info.get('拍摄日期对象')
            if date_taken:
                working_days = (date_taken.date() - earliest_date.date()).days + 1
                info['工作天数'] = working_days

        return image_info_list

    @staticmethod
    def process_independent_detection(image_info_list: List[Dict]) -> List[Dict]:
        """处理独立探测首只标记

        Args:
            image_info_list: 图像信息列表

        Returns:
            更新后的图像信息列表
        """
        # 按拍摄日期排序
        sorted_images = sorted(
            [img for img in image_info_list if img.get('拍摄日期对象')],
            key=lambda x: x['拍摄日期对象']
        )

        species_last_detected = {}  # 记录每个物种的最后探测时间

        for img_info in sorted_images:
            species_names = img_info['物种名称'].split(',')
            current_time = img_info.get('拍摄日期对象')

            if not current_time or not species_names or species_names == ['']:
                img_info['独立探测首只'] = ''
                continue

            is_independent = False

            for species in species_names:
                if species in species_last_detected:
                    # 检查时间差是否超过阈值
                    time_diff = (current_time - species_last_detected[species]).total_seconds()
                    if time_diff > INDEPENDENT_DETECTION_THRESHOLD:
                        is_independent = True
                else:
                    # 首次探测该物种
                    is_independent = True

                # 更新最后探测时间
                species_last_detected[species] = current_time

            img_info['独立探测首只'] = '是' if is_independent else ''

        return image_info_list

    @staticmethod
    def export_to_excel(image_info_list: List[Dict], output_path: str) -> bool:
        """将图像信息导出为Excel文件

        Args:
            image_info_list: 图像信息列表
            output_path: 输出文件路径

        Returns:
            是否成功导出
        """
        if not image_info_list:
            logger.warning("没有数据可导出到Excel")
            return False

        try:
            # 使用pandas创建DataFrame更高效
            df = pd.DataFrame(image_info_list)

            # 选择需要的列并按顺序排列
            columns = ['文件名', '格式', '拍摄日期', '拍摄时间', '工作天数',
                       '物种名称', '物种数量', '最低置信度', '独立探测首只']

            # 确保所有列都存在，不存在的列填充空值
            for col in columns:
                if col not in df.columns:
                    df[col] = ''

            # 只保留需要的列并排序
            df = df[columns]

            # 导出到Excel
            df.to_excel(output_path, sheet_name="物种检测信息", index=False)

            return True
        except Exception as e:
            logger.error(f"导出Excel失败: {e}")
            return False


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
            self.ico_path = resource_path(os.path.join("res", "ico.ico"))
            master.iconbitmap(self.ico_path)
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
        self.use_fp16_var = tk.BooleanVar(value=True)  # 新增FP16加速选项

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
            options_container, text="按物种分类复制图片", variable=self.copy_img_var,
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

        # 添加底部信息框
        info_frame = ttk.LabelFrame(self.preview_frame, text="图像信息")
        info_frame.pack(fill="x", padx=PADDING, pady=(0, PADDING))

        self.info_text = tk.Text(info_frame, height=5, font=NORMAL_FONT, wrap="word")
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
        self.detect_button.pack(side="right", padx=PADDING)

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
        self.use_fp16_var = tk.BooleanVar(value=True)  # FP16加速，默认开启
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

        # 创建按钮框架，将参数说明按钮和重置按钮放在同一行
        buttons_frame = ttk.Frame(self.advanced_frame)
        buttons_frame.pack(fill="x", padx=PADDING, pady=PADDING)

        # 添加查看参数说明按钮
        help_button = ttk.Button(
            buttons_frame, text="查看参数说明", command=self.show_param_explanation, width=BUTTON_WIDTH)
        help_button.pack(side="left", padx=PADDING)

        # 添加恢复默认参数按钮
        reset_button = ttk.Button(
            buttons_frame, text="恢复默认参数", command=self._reset_model_params, width=BUTTON_WIDTH)
        reset_button.pack(side="right", padx=PADDING)

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
            text="作者:和錦わきん",
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

    def _bind_events(self) -> None:
        """绑定事件处理函数"""
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.file_path_entry.bind("<Return>", self.save_file_path_by_enter)
        self.save_path_entry.bind("<Return>", self.save_save_path_by_enter)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_selected)

        # 添加选项卡切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

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

    def update_image_info(self, file_path: str, file_name: str) -> None:
        """更新图像信息"""
        try:
            # 提取元数据
            image_info, _ = ImageMetadataExtractor.extract_metadata(file_path, file_name)

            # 更新信息文本
            self.info_text.config(state="normal")
            self.info_text.delete(1.0, tk.END)

            info_text = f"文件名: {image_info.get('文件名', '')}\n"
            info_text += f"格式: {image_info.get('格式', '')}\n"

            if image_info.get('拍摄日期'):
                info_text += f"拍摄日期: {image_info.get('拍摄日期')} {image_info.get('拍摄时间', '')}\n"
            else:
                info_text += "拍摄日期: 未知\n"

            # 添加图像尺寸信息
            try:
                with Image.open(file_path) as img:
                    info_text += f"尺寸: {img.width} x {img.height} 像素\n"
                    info_text += f"文件大小: {os.path.getsize(file_path) / 1024:.1f} KB"
            except:
                pass

            self.info_text.insert(tk.END, info_text)
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
            self._set_processing_state(False)
            if stopped_manually:
                self.status_bar.status_label.config(text="处理已停止。")

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

        # 保留原始信息，添加检测结果
        current_text = self.info_text.get(1.0, tk.END)

        # 在文本末尾添加检测信息
        detection_info = "\n\n检测结果:\n"
        if species_info['物种名称']:
            species_names = species_info['物种名称'].split(',')
            species_counts = species_info['物种数量'].split(',')

            for i, (name, count) in enumerate(zip(species_names, species_counts)):
                detection_info += f"- {name}: {count}只\n"

            if species_info['最低置信度']:
                detection_info += f"\n最低置信度: {species_info['最低置信度']}"
        else:
            detection_info += "未检测到已知物种"

        # 设置新的文本内容
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, current_text.strip() + detection_info)
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
        self.use_fp16_var.set(True)
        self.use_augment_var.set(True)
        self.use_agnostic_nms_var.set(True)

        # 更新标签
        self._update_iou_label(0.3)
        self._update_conf_label(0.25)

        messagebox.showinfo("参数重置", "模型参数已恢复为默认值")

    def show_param_explanation(self) -> None:
        """显示参数说明弹窗"""
        explanation_text = """
        IOU阈值：控制边界框的重叠程度，值越低检出的框越多，可能导致重复检测；值越高检出的框越少，可能导致漏检。

        置信度阈值：控制检测结果的可信度，值越低检出更多低置信度目标，可能增加误检；值越高仅保留高置信度目标，可能导致漏检。

        FP16加速：使用半精度浮点数进行计算，可提高20-50%的速度，但在某些场景可能略微减少精度。

        数据增强：在检测过程中应用多种变换以提高准确性，但会减慢处理速度，对复杂场景有帮助。

        类别无关NMS：在消除重复边界框时忽略类别信息，对同一位置可能出现多种类别的场景有帮助。
        """

        # 创建弹窗
        explanation_window = tk.Toplevel(self.master)
        explanation_window.title("参数说明")
        explanation_window.iconbitmap(self.ico_path)

        # 设置模态窗口（阻止与其他窗口的交互，直到此窗口关闭）
        explanation_window.grab_set()

        # 窗口大小和位置
        window_width, window_height = 500, 350
        screen_width = explanation_window.winfo_screenwidth()
        screen_height = explanation_window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        explanation_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 创建一个框架来容纳文本区域和滚动条
        frame = tk.Frame(explanation_window)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 创建说明文本区域
        text_area = tk.Text(frame, wrap="word", font=NORMAL_FONT, padx=15, pady=15)

        # 添加滚动条 - 注意滚动条现在是frame的子组件，而不是text_area的子组件
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text_area.yview)

        # 设置滚动条和文本区域的位置关系
        scrollbar.pack(side="right", fill="y")
        text_area.pack(side="left", fill="both", expand=True)

        # 连接滚动条和文本区域
        text_area.config(yscrollcommand=scrollbar.set)

        # 插入说明文本
        text_area.insert("1.0", explanation_text.strip())
        text_area.config(state="disabled")  # 使文本只读

        # 底部关闭按钮
        close_button = ttk.Button(explanation_window, text="关闭",
                                  command=explanation_window.destroy,
                                  width=BUTTON_WIDTH)
        close_button.pack(pady=(0, 15))

def main():
    """程序入口点"""
    root = tk.Tk()
    root.resizable(False, False)
    app = ObjectDetectionGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
