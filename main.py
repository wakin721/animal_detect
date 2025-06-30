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
    print("正在升级pip...")
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

# 导入GUI模块和配置常量
from system.gui import ObjectDetectionGUI
from system.config import APP_TITLE, APP_VERSION

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
    # 检查脚本是否以GUI模式启动。
    # 我们使用 '--gui-only' 标志来区分首次启动（带命令行）和最终的GUI进程。
    if '--gui-only' in sys.argv:
        # 如果是GUI模式，直接运行主程序。
        # 此时环境和依赖已准备就绪。
        main()
    else:
        # 这是从 bat 文件或命令行首次启动。
        # 此脚本顶部的 setup_virtual_environment() 和 install_requirements() 函数已经执行完毕。

        # 获取当前虚拟环境中的Python解释器路径。
        python_executable = sys.executable 
        gui_executable = python_executable  # 默认值，适用于非Windows系统

        # 在Windows上，我们希望使用 pythonw.exe 来运行GUI，以避免显示命令行窗口。
        # pythonw.exe 通常与 python.exe 在同一目录下。
        if os.name == 'nt':
            venv_scripts_dir = os.path.dirname(python_executable)
            win_gui_executable = os.path.join(venv_scripts_dir, 'pythonw.exe')
            
            # 确认 pythonw.exe 存在
            if os.path.exists(win_gui_executable):
                gui_executable = win_gui_executable
        
        # 准备参数以重新启动脚本，并附带 '--gui-only' 标志。
        # 我们传递所有原始参数，并追加我们的特殊标志。
        args = [gui_executable, __file__] + sys.argv[1:] + ['--gui-only']

        # 使用 subprocess.Popen 启动新的GUI进程。
        if os.name == 'nt':
            # 在Windows上，使用 DETACHED_PROCESS 创建标志来使新进程与当前命令行窗口分离。
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(args, creationflags=DETACHED_PROCESS, close_fds=True)
        else:
            # 在Linux或macOS上，直接启动即可，父进程可以退出。
            subprocess.Popen(args, close_fds=True)
        
        # 退出当前脚本，这将关闭命令行窗口。
        sys.exit(0)