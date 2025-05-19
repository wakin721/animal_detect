"""
物种信息检测应用程序
支持图像物种识别、探测图片保存、Excel输出和图像分类功能
现代化桌面应用程序界面 - 优化版本
"""
import sys
import os
import json
import logging
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

# 自动安装依赖
def install_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if not os.path.exists(req_path):
        print("未发现 requirements.txt，跳过依赖检查。")
        return

    try:
        import pkg_resources
        with open(req_path, "r", encoding="utf-8") as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        pkg_resources.require(requirements)
    except (ImportError, pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
        print("检测到缺少依赖，正在自动安装 requirements.txt 中的依赖，请稍候...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_path])
            print("依赖安装完成。")
        except Exception as e:
            print(f"依赖安装失败：{e}\n请手动运行 pip install -r requirements.txt")
            sys.exit(1)

install_requirements()

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

# 确保system文件夹在路径中
sys.path.append(os.path.join(os.path.dirname(__file__), 'system'))

# 导入GUI模块和配置常量
from system.gui import ObjectDetectionGUI
from system.config import APP_TITLE, APP_VERSION  # 添加导入APP_TITLE

def main():
    """程序入口点"""
    # 检查CUDA可用性
    def check_cuda_available():
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            logger.info(f"CUDA可用性检测结果: {cuda_available}")
            return cuda_available
        except ImportError:
            logger.error("无法导入PyTorch，CUDA检测失败")
            return False
        except Exception as e:
            logger.error(f"检测CUDA时出错: {e}")
            return False

    # 确保在程序启动时检测CUDA
    cuda_available = check_cuda_available()

    # 如果CUDA不可用，显示警告消息
    if not cuda_available:
        # 创建一个临时窗口来显示弹窗
        temp_root = tk.Tk()
        temp_root.withdraw()  # 隐藏窗口
        messagebox.showwarning("CUDA检测", "未检测到CUDA/Rocm，请检查是否正确安装对应PyTorch版本。")
        temp_root.destroy()  # 销毁临时窗口

    # 检查是否存在未完成的处理任务
    base_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = os.path.join(base_dir, "temp")
    cache_file = os.path.join(temp_dir, "cache.json")

    # 检查是否有缓存文件
    resume_processing = False
    resume_from = 0
    cache_data = None
    excel_data = []

    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            if cache_data and 'processed_files' in cache_data and 'total_files' in cache_data:
                # 创建临时根窗口用于显示对话框
                temp_root = tk.Tk()
                temp_root.withdraw()  # 隐藏窗口

                # 显示询问对话框
                resume_processing = messagebox.askyesno(
                    "发现未完成任务",
                    "检测到上次有未完成的处理任务，是否从上次进度继续处理？\n\n"
                    f"已处理：{cache_data.get('processed_files', 0)} 张\n"
                    f"总计：{cache_data.get('total_files', 0)} 张\n"
                    f"路径：{cache_data.get('file_path', '')}",
                    parent=temp_root
                )

                if resume_processing:
                    resume_from = cache_data.get('processed_files', 0)
                    excel_data = cache_data.get('excel_data', [])
                else:
                    # 删除缓存文件
                    os.remove(cache_file)

                # 销毁临时根窗口
                temp_root.destroy()
        except Exception as e:
            logger.error(f"读取缓存文件失败: {e}")
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                except:
                    pass

    # 创建settings_manager目录用于保存设置
    settings_dir = os.path.join(base_dir, "temp")
    if not os.path.exists(settings_dir):
        try:
            os.makedirs(settings_dir)
        except Exception as e:
            logger.error(f"创建设置目录失败: {e}")

    # 创建临时图片目录用于保存检测结果
    temp_photo_dir = os.path.join(temp_dir, "photo")
    if not os.path.exists(temp_photo_dir):
        try:
            os.makedirs(temp_photo_dir)
        except Exception as e:
            logger.error(f"创建临时图片目录失败: {e}")

    # 加载设置
    settings_file = os.path.join(settings_dir, "settings.json")
    settings = None
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            # 如果CUDA不可用，禁用fp16设置
            if not cuda_available and settings and "use_fp16" in settings:
                settings["use_fp16"] = False

        except Exception as e:
            logger.error(f"加载设置文件失败: {e}")

    # 创建主窗口
    root = tk.Tk()
    root.title(APP_TITLE)  # 设置窗口标题

    from system.settings_manager import SettingsManager

    # 创建实际的SettingsManager对象
    settings_manager = SettingsManager(base_dir)

    # 创建GUI实例
    app = ObjectDetectionGUI(root, settings_manager=settings_manager, settings=settings)

    # 设置CUDA可用性属性
    app.cuda_available = cuda_available

    # 如果CUDA不可用，禁用FP16选项并设置为False
    if not cuda_available:
        app.use_fp16_var.set(False)

    # 如果需要继续处理，设置excel_data并启动处理
    if resume_processing and resume_from > 0:
        app.excel_data = excel_data

        if excel_data:
            from datetime import datetime
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

        app.excel_data = excel_data

        # 设置加载上次的配置
        if cache_data:
            # 设置文件路径和保存路径
            if 'file_path' in cache_data and cache_data['file_path']:
                app.file_path_entry.delete(0, tk.END)
                app.file_path_entry.insert(0, cache_data['file_path'])
                app.update_file_list(cache_data['file_path'])

            if 'save_path' in cache_data and cache_data['save_path']:
                app.save_path_entry.delete(0, tk.END)
                app.save_path_entry.insert(0, cache_data['save_path'])

            # 设置处理选项
            if 'save_detect_image' in cache_data:
                app.save_detect_image_var.set(cache_data['save_detect_image'])

            if 'output_excel' in cache_data:
                app.output_excel_var.set(cache_data['output_excel'])

            if 'copy_img' in cache_data:
                app.copy_img_var.set(cache_data['copy_img'])

            # 如果CUDA不可用，强制禁用FP16
            if 'use_fp16' in cache_data:
                if cuda_available:
                    app.use_fp16_var.set(cache_data['use_fp16'])
                else:
                    app.use_fp16_var.set(False)

        # 延迟启动处理，确保UI已完全加载
        root.after(1000, lambda: app.start_processing(resume_from=resume_from))

    # 启动主循环
    root.mainloop()

if __name__ == "__main__":
    main()