"""
物种信息检测应用程序
支持图像物种识别、探测图片保存、Excel输出和图像分类功能
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime
from shutil import copy
from collections import Counter
from typing import Dict, List, Optional, Tuple, Any, Union

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd
import openpyxl
from PIL import Image
from PIL.ExifTags import TAGS
from ultralytics import YOLO

# 配置常量
APP_TITLE = "物种信息检测 v2.5"
DEFAULT_EXCEL_FILENAME = "物种检测信息.xlsx"
SUPPORTED_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
DATE_FORMATS = ['%Y:%m:%d %H:%M:%S', '%Y:%d:%m %H:%M:%S', '%Y-%m-%d %H:%M:%S']
INDEPENDENT_DETECTION_THRESHOLD = 30 * 60  # 30分钟，单位：秒

# 禁用不必要的日志
logging.basicConfig(level=logging.ERROR)

def resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径，支持PyInstaller打包"""
    if getattr(sys, 'frozen', False):  # 是否使用PyInstaller打包
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


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
            return YOLO(model_path)
        except Exception as e:
            logging.error(f"加载模型失败: {e}")
            return None
            
    def detect_species(self, img_path: str) -> Dict[str, Any]:
        """使用YOLO模型识别图片中的物种
        
        Args:
            img_path: 图片文件路径
            
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
            # 使用高级参数提高检测质量
            results = self.model(img_path, augment=True, agnostic_nms=True, 
                                imgsz=1024, half=True, iou=0.3)
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
            logging.error(f"物种检测失败: {e}")
            
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
            logging.error(f"保存检测结果图片失败: {e}")
    
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
            logging.error(f"获取物种名称失败: {e}")
        return "unknown"


class ImageMetadataExtractor:
    """图像元数据提取器，用于获取图像的EXIF信息"""
    
    @staticmethod
    def extract_metadata(img_path: str, filename: str) -> Dict[str, Any]:
        """提取图像元数据
        
        Args:
            img_path: 图像文件路径
            filename: 图像文件名
            
        Returns:
            包含元数据的字典
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
            logging.error(f"提取图像元数据失败 ({filename}): {e}")
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
                
        logging.warning(f"无法解析图片 '{filename}' 的日期格式: '{date_str}'")
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
            logging.warning("无法计算工作天数：未找到任何有效拍摄日期")
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
            logging.warning("没有数据可导出到Excel")
            return False
            
        try:
            # 创建工作簿和工作表
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.title = "物种检测信息"
            
            # 写入表头
            headers = ['文件名', '格式', '拍摄日期', '拍摄时间', '工作天数', 
                       '物种名称', '物种数量', '最低置信度', '独立探测首只']
            sheet.append(headers)
            
            # 写入数据行
            for info in image_info_list:
                row_data = [
                    info.get('文件名', ''),
                    info.get('格式', ''),
                    info.get('拍摄日期', ''),
                    info.get('拍摄时间', ''),
                    info.get('工作天数', ''),
                    info.get('物种名称', ''),
                    info.get('物种数量', ''),
                    info.get('最低置信度', ''),
                    info.get('独立探测首只', '')
                ]
                sheet.append(row_data)
                
            # 保存文件
            workbook.save(output_path)
            return True
        except Exception as e:
            logging.error(f"导出Excel失败: {e}")
            return False


class ObjectDetectionGUI:
    """物种检测GUI应用程序"""
    
    def __init__(self, master: tk.Tk):
        """初始化GUI应用
        
        Args:
            master: Tkinter主窗口
        """
        self.master = master
        master.title(APP_TITLE)
        
        # 加载资源
        ico_path = resource_path(os.path.join("res", "ico.ico"))
        model_path = resource_path(os.path.join("res", "predict.pt"))
        
        # 设置窗口图标
        try:
            master.iconbitmap(ico_path)
        except Exception:
            logging.warning("无法加载窗口图标")
        
        # 初始化处理器
        self.image_processor = ImageProcessor(model_path)
        
        # 状态变量
        self.is_processing = False
        self.processing_stop_flag = threading.Event()
        
        # 创建GUI元素
        self._create_ui_elements()
        
        # 绑定事件
        self._bind_events()
        
    def _create_ui_elements(self) -> None:
        """创建GUI界面元素"""
        # 配置布局
        self.master.grid_columnconfigure(1, weight=1)
        
        # 文件路径选择区域
        self.file_path_label = tk.Label(self.master, text="文件路径:")
        self.file_path_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        
        self.file_path_entry = tk.Entry(self.master, width=60)
        self.file_path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.file_path_button = tk.Button(self.master, text="浏览", command=self.browse_file_path, width=10)
        self.file_path_button.grid(row=0, column=2, columnspan=4, padx=5, pady=5)
        
        # 保存路径选择区域
        self.save_path_label = tk.Label(self.master, text="保存路径:")
        self.save_path_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        
        self.save_path_entry = tk.Entry(self.master, width=60)
        self.save_path_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        self.save_path_button = tk.Button(self.master, text="浏览", command=self.browse_save_path, width=10)
        self.save_path_button.grid(row=1, column=2, columnspan=4, padx=5, pady=5)
        
        # 功能选项区域
        self.save_detect_image_var = tk.BooleanVar(value=False)
        self.save_detect_image_check = tk.Checkbutton(
            self.master, text="保存探测图片", variable=self.save_detect_image_var)
        self.save_detect_image_check.grid(row=2, column=1, pady=5, sticky="w")
        
        self.output_excel_var = tk.BooleanVar(value=False)
        self.output_excel_check = tk.Checkbutton(
            self.master, text="输出为excel表格", variable=self.output_excel_var)
        self.output_excel_check.grid(row=3, column=1, pady=5, sticky="w")
        
        self.copy_img_var = tk.BooleanVar(value=False)
        self.copy_img_check = tk.Checkbutton(
            self.master, text="将图片分类", variable=self.copy_img_var)
        self.copy_img_check.grid(row=4, column=1, pady=5, sticky="w")
        
        # 控制按钮
        self.start_stop_button = tk.Button(
            self.master, text="开始处理", command=self.toggle_processing_state, width=10)
        self.start_stop_button.grid(row=5, column=1, columnspan=2, pady=20)
        
        # 进度显示区域
        self.progress_label = tk.Label(self.master, text="准备就绪")
        self.progress_label.grid(row=6, column=0, columnspan=3, pady=5)
        
        self.progress_bar = ttk.Progressbar(
            self.master, orient="horizontal", length=320, mode="determinate")
        self.progress_bar.grid(row=6, column=0, columnspan=6, pady=10, padx=10, sticky="ew")
        
        self.speed_label = tk.Label(self.master, text="")
        self.speed_label.grid(row=7, column=2, columnspan=4, padx=0, pady=1, sticky="w")
        
        self.remaining_time_label = tk.Label(self.master, text="")
        self.remaining_time_label.grid(row=7, column=1, columnspan=4, padx=70, pady=1, sticky="e")
        
        # 检查模型是否加载成功
        if not self.image_processor.model:
            messagebox.showerror("错误", "模型文件未找到。请检查脚本中的模型路径。")
            self.start_stop_button["state"] = "disabled"
    
    def _bind_events(self) -> None:
        """绑定事件处理函数"""
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.file_path_entry.bind("<Return>", self.save_file_path_by_enter)
        self.save_path_entry.bind("<Return>", self.save_save_path_by_enter)
    
    def on_closing(self) -> None:
        """窗口关闭事件处理"""
        if messagebox.askyesno("退出确认", "确定要退出程序吗？"):
            self.master.destroy()
    
    def browse_file_path(self) -> None:
        """浏览文件路径"""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, folder_selected)
    
    def browse_save_path(self) -> None:
        """浏览保存路径"""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.save_path_entry.delete(0, tk.END)
            self.save_path_entry.insert(0, folder_selected)
    
    def save_file_path_by_enter(self, event) -> None:
        """处理文件路径输入框的回车键事件"""
        file_path = self.file_path_entry.get()
        if os.path.isdir(file_path):
            messagebox.showinfo("信息", f"文件路径已保存: \n{file_path}")
        else:
            messagebox.showerror("错误", "输入的文件路径无效，请检查。\n请确保路径指向一个文件夹。")
    
    def save_save_path_by_enter(self, event) -> None:
        """处理保存路径输入框的回车键事件"""
        save_path = self.save_path_entry.get()
        if os.path.isdir(save_path):
            messagebox.showinfo("信息", f"保存路径已保存: \n{save_path}")
        else:
            messagebox.showerror("错误", "输入的保存路径无效，请检查。\n请确保路径指向一个文件夹。")
    
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
        
        # 验证输入
        if not self._validate_inputs(file_path, save_path):
            return
            
        # 检查是否选择了至少一个功能
        if not save_detect_image and not output_excel and not copy_img:
            messagebox.showerror("错误", "请至少勾选一个功能。")
            return
        
        # 更新UI状态
        self._set_processing_state(True)
        
        # 启动处理线程
        threading.Thread(
            target=self._process_images_thread,
            args=(file_path, save_path, save_detect_image, output_excel, copy_img),
            daemon=True
        ).start()
    
    def stop_processing(self) -> None:
        """停止处理图像"""
        if messagebox.askyesno("停止确认", "确定要停止图像处理吗？"):
            self.processing_stop_flag.set()
            self.progress_label.config(text="正在停止处理...")
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
            self.progress_label.config(text="正在处理图像...")
            self.progress_bar["value"] = 0
            self.speed_label.config(text="")
            self.remaining_time_label.config(text="")
            self.processing_stop_flag.clear()
            
            # 禁用配置选项
            for widget in (self.file_path_entry, self.file_path_button, 
                          self.save_path_entry, self.save_path_button,
                          self.save_detect_image_check, self.output_excel_check,
                          self.copy_img_check):
                widget["state"] = "disabled"
        else:
            self.start_stop_button.config(text="开始处理")
            self.speed_label.config(text="")
            self.remaining_time_label.config(text="")
            
            # 启用配置选项
            for widget in (self.file_path_entry, self.file_path_button, 
                          self.save_path_entry, self.save_path_button,
                          self.save_detect_image_check, self.output_excel_check,
                          self.copy_img_check):
                widget["state"] = "normal"
    
    def _process_images_thread(self, file_path: str, save_path: str, 
                              save_detect_image: bool, output_excel: bool,
                              copy_img: bool) -> None:
        """图像处理线程
        
        Args:
            file_path: 源文件路径
            save_path: 保存路径
            save_detect_image: 是否保存探测图片
            output_excel: 是否输出Excel表格
            copy_img: 是否按物种分类复制图片
        """
        start_time = time.time()
        excel_data = []
        processed_files = 0
        stopped_manually = False
        earliest_date = None
        
        try:
            # 获取所有图片文件
            image_files = self._get_image_files(file_path)
            
            total_files = len(image_files)
            self.progress_bar["maximum"] = total_files
            
            if not image_files:
                self.progress_label.config(text="未找到任何图片文件。")
                messagebox.showinfo("提示", "在指定路径下未找到任何图片文件。")
                return
                
            # 处理每张图片
            for filename in image_files:
                if self.processing_stop_flag.is_set():
                    stopped_manually = True
                    break
                    
                try:
                    # 处理单张图片
                    img_path = os.path.join(file_path, filename)
                    image_info, img = ImageMetadataExtractor.extract_metadata(img_path, filename)
                    
                    # 检测物种
                    species_info = self.image_processor.detect_species(img_path)
                    image_info.update({
                        '物种名称': species_info['物种名称'],
                        '物种数量': species_info['物种数量'],
                        'detect_results': species_info['detect_results'],
                        '最低置信度': species_info['最低置信度']
                    })
                    
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
                    logging.error(f"处理文件 {filename} 失败: {e}")
                
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
                    messagebox.showinfo("成功", f"物种检测信息已成功导出到Excel文件: \n{output_file_path}")
            
            # 完成处理
            if not stopped_manually:
                self.progress_label.config(text="处理完成！")
                messagebox.showinfo("成功", "图像处理完成！")
            
        except Exception as e:
            logging.error(f"处理过程中发生错误: {e}")
            self.progress_label.config(text="处理过程中出错。")
            messagebox.showerror("错误", f"处理过程中发生错误: {e}")
        
        finally:
            # 恢复UI状态
            self._set_processing_state(False)
            if stopped_manually:
                self.progress_label.config(text="处理已停止。")
    
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
            logging.error(f"复制图片失败: {e}")
    
    def _update_progress(self, processed: int, total: int, start_time: float) -> None:
        """更新进度显示
        
        Args:
            processed: 已处理文件数
            total: 总文件数
            start_time: 开始时间
        """
        # 更新进度条和文本
        progress_text = f"处理中: {processed}/{total} 文件"
        self.progress_label.config(text=progress_text)
        self.progress_bar["value"] = processed
        
        # 计算速度和剩余时间
        elapsed_time = time.time() - start_time
        if processed > 0:
            # 计算处理速度
            speed = processed / elapsed_time
            self.speed_label.config(text=f"速度: {speed:.2f} p/s")
            
            # 计算剩余时间
            time_per_file = elapsed_time / processed
            remaining_files = total - processed
            estimated_time = time_per_file * remaining_files
            minutes = int(estimated_time // 60)
            seconds = int(estimated_time % 60)
            self.remaining_time_label.config(text=f"剩余时间: {minutes:02d}:{seconds:02d}")
        
        # 刷新UI
        self.master.update_idletasks()


def main():
    """程序入口点"""
    root = tk.Tk()
    root.resizable(height=False, width=False)
    app = ObjectDetectionGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
