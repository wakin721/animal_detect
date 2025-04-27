"""
物种信息检测应用程序
支持图像物种识别、探测图片保存、Excel输出和图像分类功能
Windows 11 风格界面 - 优化版本
"""
import sys
import os
import logging

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

# 导入GUI模块
from system.gui import ObjectDetectionGUI
import tkinter as tk

def main():
    """程序入口点"""
    root = tk.Tk()
    root.resizable(False, False)
    app = ObjectDetectionGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()