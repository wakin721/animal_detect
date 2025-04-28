"""
物种信息检测应用程序
支持图像物种识别、探测图片保存、Excel输出和图像分类功能
Windows 11 风格界面 - 优化版本
"""
import sys
import os
import logging
import subprocess

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