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
import threading

# --- existing setup_virtual_environment and install_requirements functions ---
# ... (no changes needed in these functions)

def setup_virtual_environment():
    """设置虚拟环境"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(base_dir, ".venv")

    # 检查是否已经在虚拟环境中运行
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("已在虚拟环境中运行...")
        return True

    # 检查虚拟环境是否存在
    if not os.path.exists(venv_dir):
        print("首次运行检测到，正在创建虚拟环境...")

        # 首先尝试使用内置的venv模块
        venv_created = False
        try:
            print("尝试使用内置venv模块创建虚拟环境...")
            subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
            print("使用venv模块创建虚拟环境成功。")
            venv_created = True
        except subprocess.CalledProcessError as e:
            print(f"使用venv模块创建虚拟环境失败：{e}")
        except Exception as e:
            print(f"使用venv模块时发生错误：{e}")

        # 如果venv模块失败，尝试安装并使用virtualenv
        if not venv_created:
            print("正在尝试安装virtualenv...")
            try:
                # 检查virtualenv是否已安装
                try:
                    import virtualenv
                    print("virtualenv已安装。")
                except ImportError:
                    print("virtualenv未安装，正在自动安装...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "virtualenv"])
                    print("virtualenv安装完成。")

                # 使用virtualenv创建虚拟环境
                print("使用virtualenv创建虚拟环境...")
                subprocess.check_call([sys.executable, "-m", "virtualenv", venv_dir])
                print("使用virtualenv创建虚拟环境成功。")
                venv_created = True

            except subprocess.CalledProcessError as e:
                print(f"使用virtualenv创建虚拟环境失败：{e}")
            except Exception as e:
                print(f"安装或使用virtualenv时发生错误：{e}")

        # 如果两种方法都失败了
        if not venv_created:
            print("错误：无法创建虚拟环境！")
            print("请尝试以下解决方案：")
            print("1. 确保Python版本支持venv模块（Python 3.3+）")
            print("2. 手动安装virtualenv：pip install virtualenv")
            print("3. 检查Python安装是否完整")
            print("4. 以管理员权限运行程序")
            input("按任意键退出...")
            sys.exit(1)

    # 确定虚拟环境中Python解释器的路径
    if os.name == 'nt':  # Windows
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        venv_pip = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:  # Linux/Mac
        venv_python = os.path.join(venv_dir, "bin", "python")
        venv_pip = os.path.join(venv_dir, "bin", "pip")

    # 检查虚拟环境是否正确创建
    if not os.path.exists(venv_python):
        print("虚拟环境创建不完整，正在重新创建...")
        try:
            # 删除不完整的虚拟环境
            import shutil
            shutil.rmtree(venv_dir)

            # 重新创建 - 优先使用venv，失败则使用virtualenv
            venv_recreated = False
            try:
                print("重新尝试使用venv模块...")
                subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
                print("使用venv模块重新创建成功。")
                venv_recreated = True
            except:
                print("venv模块重新创建失败，尝试使用virtualenv...")
                try:
                    subprocess.check_call([sys.executable, "-m", "virtualenv", venv_dir])
                    print("使用virtualenv重新创建成功。")
                    venv_recreated = True
                except Exception as e:
                    print(f"virtualenv重新创建也失败：{e}")

            if not venv_recreated:
                print("重新创建虚拟环境失败！")
                input("按任意键退出...")
                sys.exit(1)

        except Exception as e:
            print(f"重新创建虚拟环境失败：{e}")
            input("按任意键退出...")
            sys.exit(1)

    # 如果不在虚拟环境中，重新启动程序在虚拟环境中运行
    print("正在进入虚拟环境...")
    try:
        # 将当前脚本的所有参数传递给虚拟环境中的Python
        args = [venv_python] + sys.argv
        subprocess.check_call(args)
        sys.exit(0)  # 退出当前进程
    except subprocess.CalledProcessError as e:
        print(f"在虚拟环境中启动程序失败：{e}")
        print("请检查虚拟环境是否正确创建。")
        input("按任意键退出...")
        sys.exit(1)
    except Exception as e:
        print(f"启动虚拟环境时发生未知错误：{e}")
        input("按任意键退出...")
        sys.exit(1)

def install_requirements():
    """安装依赖"""
    # 检查是否在虚拟环境中
    if not (hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)):
        print("警告：似乎不在虚拟环境中运行")

    # 升级pip
    print("正在检查pip版本...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        print("pip升级完成。")
    except Exception as e:
        print(f"升级pip失败：{e}，继续执行...")
        # 继续执行，不退出

    # 首先安装setuptools，这是许多其他包的依赖
    print("正在检查基础依赖...")
    try:
        import setuptools
        print("setuptools已安装。")
    except ImportError:
        print("setuptools未安装，正在自动安装...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "setuptools"])
            print("setuptools安装完成。")
        except Exception as e:
            print(f"setuptools安装失败：{e}")
            print("请手动运行：pip install setuptools")
            input("按任意键退出...")
            sys.exit(1)

    # 安装wheel，提高包安装效率
    try:
        import wheel
        print("wheel已安装。")
    except ImportError:
        print("wheel未安装，正在自动安装...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "wheel"])
            print("wheel安装完成。")
        except Exception as e:
            print(f"wheel安装失败：{e}，继续执行...")

    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if not os.path.exists(req_path):
        print("未发现 requirements.txt，跳过依赖检查。")
        return

    try:
        import pkg_resources
        with open(req_path, "r", encoding="utf-8") as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        pkg_resources.require(requirements)
        print("所有依赖已满足。")
    except (ImportError, pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as e:
        print(f"检测到缺少依赖：{e}")
        print("正在自动安装 requirements.txt 中的依赖，请稍候...")
        try:
            # 使用更详细的安装参数
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "-r", req_path,
                "--upgrade",
                "--no-cache-dir"
            ])
            print("依赖安装完成。")
        except subprocess.CalledProcessError as e:
            print(f"依赖安装失败（返回码：{e.returncode}）")
            print("请尝试手动运行：pip install -r requirements.txt")
            input("按任意键退出...")
            sys.exit(1)
        except Exception as e:
            print(f"依赖安装过程中发生未知错误：{e}")
            print("请尝试手动运行：pip install -r requirements.txt")
            input("按任意键退出...")
            sys.exit(1)

    # 如果执行到这里，依赖检查完成
    print("依赖检查完毕，程序即将启动...")

# 首先设置虚拟环境
setup_virtual_environment()

# 然后安装依赖
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
sys.path.append(os.path.join(os.path.dirname(__file__)))


# V V V V V V V V V V V V V V V V
# MODIFICATION: Added import for check_for_updates
# V V V V V V V V V V V V V V V V
from system.gui.main_window import ObjectDetectionGUI
from system.config import APP_TITLE
from system.settings_manager import SettingsManager
from system.update_checker import check_for_updates


def main():
    """程序入口点"""
    def check_cuda_available():
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    cuda_available = check_cuda_available()
    if not cuda_available:
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showwarning("CUDA检测", "未检测到CUDA/Rocm，请检查是否正确安装对应PyTorch版本。")
        temp_root.destroy()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    settings_manager = SettingsManager(base_dir)
    settings = settings_manager.load_settings()

    # Resume logic
    cache_file = os.path.join(settings_manager.settings_dir, "cache.json")
    resume_processing = False
    cache_data = None
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            if cache_data:
                 temp_root = tk.Tk()
                 temp_root.withdraw()
                 resume_processing = messagebox.askyesno(
                    "发现未完成任务",
                    "检测到上次有未完成的处理任务，是否从上次进度继续处理？"
                 )
                 if not resume_processing:
                     os.remove(cache_file)
                     cache_data = None
                 temp_root.destroy()
        except Exception as e:
            logger.error(f"读取缓存文件失败: {e}")
            cache_data = None


    # 创建主窗口
    root = tk.Tk()
    app = ObjectDetectionGUI(
        master=root,
        settings_manager=settings_manager,
        settings=settings,
        resume_processing=resume_processing,
        cache_data=cache_data
        )

    # Startup update check
    update_thread = threading.Thread(target=lambda: check_for_updates(root, silent=True), daemon=True)
    update_thread.start()

    # 启动主循环
    root.mainloop()

if __name__ == "__main__":
    # --- existing GUI launch logic ---
    # ... (no changes needed in this part)
    #main()
    if '--gui-only' in sys.argv:
        main()
    else:
        python_executable = sys.executable
        if os.name == 'nt':
            gui_executable = os.path.join(os.path.dirname(python_executable), 'pythonw.exe')
            if not os.path.exists(gui_executable):
                gui_executable = python_executable
        else:
            gui_executable = python_executable
        args = [gui_executable, __file__] + sys.argv[1:] + ['--gui-only']
        if os.name == 'nt':
            subprocess.Popen(args, creationflags=0x00000008, close_fds=True)
        else:
            subprocess.Popen(args, close_fds=True)
        sys.exit(0)
