# system/update_checker.py

import requests
import re
import os
import zipfile
import io
import shutil
import tkinter as tk
from tkinter import ttk, messagebox
import sys
import subprocess
import threading  # 导入threading模块
from system.config import APP_VERSION

# GitHub仓库信息
GITHUB_USER = "wakin721"
GITHUB_REPO = "animal_detect"
CONFIG_FILE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/system/config.py"
SOURCE_ZIP_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/archive/refs/heads/main.zip"


def parse_version(version_str):
    """
    解析版本字符串为可比较的组件。
    
    Args:
        version_str: 版本字符串，如 "2.2.3-beta" 或 "2.2.3-alpha.1"
        
    Returns:
        tuple: (major, minor, patch, prerelease_type, prerelease_num)
        其中 prerelease_type 为 None (稳定版), 'alpha', 'beta', 'rc' 之一
        prerelease_num 为预发布版本的数字后缀，默认为 0
    """
    # 分割主版本号和预发布标识
    if '-' in version_str:
        main_version, prerelease = version_str.split('-', 1)
    else:
        main_version, prerelease = version_str, None
    
    # 解析主版本号
    try:
        major, minor, patch = map(int, main_version.split('.'))
    except ValueError:
        raise ValueError(f"无效的版本格式: {version_str}")
    
    # 解析预发布标识
    prerelease_type = None
    prerelease_num = 0
    
    if prerelease:
        # 处理预发布标识，如 "alpha", "beta.1", "rc.2" 等
        if '.' in prerelease:
            prerelease_type, num_str = prerelease.split('.', 1)
            try:
                prerelease_num = int(num_str)
            except ValueError:
                prerelease_num = 0
        else:
            prerelease_type = prerelease
    
    return (major, minor, patch, prerelease_type, prerelease_num)


def compare_versions(current_version, remote_version):
    """
    比较两个版本字符串，遵循语义化版本规则。
    
    Args:
        current_version: 当前版本字符串
        remote_version: 远程版本字符串
        
    Returns:
        bool: 如果远程版本更新则返回 True，否则返回 False
    """
    try:
        current = parse_version(current_version)
        remote = parse_version(remote_version)
        
        # 比较主版本号 (major, minor, patch)
        current_main = current[:3]
        remote_main = remote[:3]
        
        if remote_main > current_main:
            return True
        elif remote_main < current_main:
            return False
        
        # 主版本号相同，比较预发布标识
        current_prerelease = current[3]
        remote_prerelease = remote[3]
        
        # 稳定版 > 任何预发布版
        if current_prerelease is None and remote_prerelease is not None:
            return False  # 当前是稳定版，远程是预发布版，不更新
        if current_prerelease is not None and remote_prerelease is None:
            return True   # 当前是预发布版，远程是稳定版，需要更新
        
        # 都是稳定版或都是预发布版
        if current_prerelease is None and remote_prerelease is None:
            return False  # 主版本号相同的稳定版，不更新
        
        # 都是预发布版，比较预发布类型
        prerelease_order = {'alpha': 1, 'beta': 2, 'rc': 3}
        
        current_order = prerelease_order.get(current_prerelease, 0)
        remote_order = prerelease_order.get(remote_prerelease, 0)
        
        if remote_order > current_order:
            return True
        elif remote_order < current_order:
            return False
        
        # 预发布类型相同，比较数字后缀
        current_num = current[4]
        remote_num = remote[4]
        
        return remote_num > current_num
        
    except ValueError as e:
        # 如果版本解析失败，回退到原来的简单比较
        try:
            current_parts = list(map(int, current_version.split('-')[0].split('.')))
            remote_parts = list(map(int, remote_version.split('-')[0].split('.')))
            return remote_parts > current_parts
        except:
            return False


def get_icon_path():
    """获取图标文件的绝对路径。"""
    try:
        # 适应PyInstaller打包后的路径
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except Exception:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "res", "ico.ico")


def _show_messagebox(parent, title, message, msg_type):
    """
    内部辅助函数，用于显示居中的、带图标的消息框。
    使用 after() 方法确保在主线程中调用messagebox。
    """

    def show_message():
        # 创建一个临时的Toplevel窗口
        transient_parent = tk.Toplevel(parent)
        transient_parent.withdraw()
        transient_parent.title(title)

        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            try:
                transient_parent.iconbitmap(icon_path)
            except tk.TclError:
                pass

        parent.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        win_width = 350
        win_height = 150

        x = parent_x + (parent_width // 2) - (win_width // 2)
        y = parent_y + (parent_height // 2) - (win_height // 2)

        transient_parent.geometry(f'+{x}+{y}')
        transient_parent.deiconify()
        transient_parent.withdraw()

        result = None
        if msg_type == "info":
            messagebox.showinfo(title, message, parent=transient_parent)
        elif msg_type == "error":
            messagebox.showerror(title, message, parent=transient_parent)
        elif msg_type == "askyesno":
            result = messagebox.askyesno(title, message, parent=transient_parent)

        transient_parent.destroy()
        # 如果需要返回结果，需要更复杂的处理，例如使用回调或事件
        # 这里我们假设askyesno的结果需要在UI线程中直接处理
        if msg_type == "askyesno" and result:
            # 如果用户点击“是”，启动下载
            start_download_thread(parent)

    # 确保在主线程中执行
    parent.after(0, show_message)


def check_for_updates(parent, silent=False):
    """在后台线程中检查GitHub上是否有新版本。"""
    try:
        response = requests.get(CONFIG_FILE_URL, timeout=10)  # 设置超时
        response.raise_for_status()
        remote_config_content = response.text

        match = re.search(r"APP_VERSION\s*=\s*\"(.*?)\"", remote_config_content)
        if not match:
            if not silent:
                _show_messagebox(parent, "更新错误", "无法在远程仓库中找到版本信息。", "error")
            return

        remote_version = match.group(1)
        
        if compare_versions(APP_VERSION, remote_version):
            # 在主GUI的侧边栏显示更新通知 (通过after调度)
            if hasattr(parent, 'show_update_notification'):
                parent.after(0, parent.show_update_notification)

            # 显示更新对话框 (通过after调度)
            _show_messagebox(parent, "发现新版本", f"新版本 ({remote_version}) 可用，您想现在更新吗？", "askyesno")
        else:
            if not silent:
                _show_messagebox(parent, "无更新", "您目前使用的是最新版本。", "info")

    except requests.RequestException as e:
        if not silent:
            _show_messagebox(parent, "更新错误", f"检查更新失败: {e}", "error")


def start_download_thread(parent):
    """启动下载更新的线程。"""
    download_thread = threading.Thread(target=download_and_install_update, args=(parent,), daemon=True)
    download_thread.start()


def download_and_install_update(parent):
    """创建带进度条的更新窗口。此函数现在在自己的线程中运行。"""

    # 因为此函数在后台线程中，所有UI操作都需要通过 parent.after() 来调度
    def create_progress_window():
        global progress_window, label, progress_bar  # 使用全局变量以便其他函数可以访问
        progress_window = tk.Toplevel(parent)
        progress_window.title("正在更新...")
        progress_window.geometry("350x120")

        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            try:
                progress_window.iconbitmap(icon_path)
            except tk.TclError:
                pass

        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (350 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (120 // 2)
        progress_window.geometry(f'+{x}+{y}')

        progress_window.transient(parent)
        progress_window.grab_set()

        label = ttk.Label(progress_window, text="正在连接到服务器...")
        label.pack(padx=20, pady=10)

        progress_bar = ttk.Progressbar(progress_window, orient="horizontal", length=300, mode='determinate')
        progress_bar.pack(padx=20, pady=5)

        # 下载和安装逻辑
        perform_download(parent)

    parent.after(0, create_progress_window)


def perform_download(parent_window):
    """执行下载、解压、安装和重启的完整流程。"""

    def update_ui(text=None, p_value=None, p_mode=None, start=False, stop=False):
        """安全更新UI的辅助函数"""
        if text:
            label.config(text=text)
        if p_value is not None:
            progress_bar['value'] = p_value
        if p_mode:
            progress_bar['mode'] = p_mode
        if start:
            progress_bar.start(10)
        if stop:
            progress_bar.stop()
        progress_window.update_idletasks()

    try:
        parent_window.after(0, lambda: update_ui(text="正在从GitHub下载更新..."))

        response = requests.get(SOURCE_ZIP_URL, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        parent_window.after(0, lambda: progress_bar.config(maximum=total_size))

        downloaded_size = 0
        file_buffer = io.BytesIO()

        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file_buffer.write(chunk)
                downloaded_size += len(chunk)
                parent_window.after(0, lambda v=downloaded_size: update_ui(p_value=v))

        parent_window.after(0, lambda: update_ui(text="下载完成，正在解压并安装...", p_mode='indeterminate', start=True))

        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        file_buffer.seek(0)
        with zipfile.ZipFile(file_buffer) as z:
            root_folder_in_zip = z.namelist()[0]
            for member in z.infolist():
                path_in_zip = member.filename.replace(root_folder_in_zip, '', 1)
                if not path_in_zip or ".git" in path_in_zip:
                    continue

                target_path = os.path.join(app_root, path_in_zip)

                if member.is_dir():
                    os.makedirs(target_path, exist_ok=True)
                else:
                    target_dir = os.path.dirname(target_path)
                    os.makedirs(target_dir, exist_ok=True)
                    with z.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)

        parent_window.after(0, lambda: update_ui(stop=True))
        parent_window.after(0, progress_window.destroy)

        # 重启逻辑也需要调度
        def ask_restart():
            if messagebox.askyesno("更新成功", "程序已成功更新！\n是否立即重启应用程序以应用更改？",
                                   parent=parent_window):
                python_executable = sys.executable
                # 确保使用控制台python.exe而非pythonw.exe来避免问题
                if os.name == 'nt' and python_executable.endswith('pythonw.exe'):
                    python_exe_path = os.path.join(os.path.dirname(python_executable), 'python.exe')
                    if os.path.exists(python_exe_path):
                        python_executable = python_exe_path

                main_script_path = os.path.join(os.path.dirname(app_root), 'main.py')  # 假设main.py在animal_detect目录下
                subprocess.Popen([python_executable, main_script_path])
                parent_window.destroy()
                sys.exit(0)

        parent_window.after(0, ask_restart)

    except Exception as e:
        parent_window.after(0, progress_window.destroy)
        _show_messagebox(parent_window, "更新失败", f"更新过程中发生错误: {e}", "error")