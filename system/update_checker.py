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
from system.config import APP_VERSION

# GitHub仓库信息
GITHUB_USER = "wakin721"
GITHUB_REPO = "animal_detect"
CONFIG_FILE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/system/config.py"
SOURCE_ZIP_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/archive/refs/heads/main.zip"


def get_icon_path():
    """获取图标文件的绝对路径。"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "res", "ico.ico")


def _show_messagebox(parent, title, message, msg_type):
    """内部辅助函数，用于显示带图标的消息框。"""
    transient_parent = tk.Toplevel(parent)
    transient_parent.withdraw()
    icon_path = get_icon_path()
    if os.path.exists(icon_path):
        try:
            transient_parent.iconbitmap(icon_path)
        except tk.TclError:
            pass

    result = None
    if msg_type == "info":
        messagebox.showinfo(title, message, parent=transient_parent)
    elif msg_type == "error":
        messagebox.showerror(title, message, parent=transient_parent)
    elif msg_type == "askyesno":
        result = messagebox.askyesno(title, message, parent=transient_parent)

    transient_parent.destroy()
    return result


def check_for_updates(parent, silent=False):
    """检查GitHub上是否有新版本。"""
    try:
        response = requests.get(CONFIG_FILE_URL)
        response.raise_for_status()
        remote_config_content = response.text

        match = re.search(r"APP_VERSION\s*=\s*\"(.*?)\"", remote_config_content)
        if not match:
            if not silent:
                _show_messagebox(parent, "更新错误", "无法在远程仓库中找到版本信息。", "error")
            return

        remote_version = match.group(1)
        current_parts = list(map(int, APP_VERSION.split('-')[0].split('.')))
        remote_parts = list(map(int, remote_version.split('-')[0].split('.')))

        if remote_parts > current_parts:
            if _show_messagebox(parent, "发现新版本", f"新版本 ({remote_version}) 可用，您想现在更新吗？", "askyesno"):
                download_and_install_update(parent)
        else:
            if not silent:
                _show_messagebox(parent, "无更新", "您目前使用的是最新版本。", "info")

    except requests.RequestException as e:
        if not silent:
            _show_messagebox(parent, "更新错误", f"检查更新失败: {e}", "error")


def download_and_install_update(parent):
    """创建带进度条的更新窗口。"""
    progress_window = tk.Toplevel(parent)
    progress_window.title("正在更新...")
    progress_window.geometry("350x120") # 调整窗口大小以容纳进度条
    
    icon_path = get_icon_path()
    if os.path.exists(icon_path):
        try:
            progress_window.iconbitmap(icon_path)
        except tk.TclError:
            pass
            
    progress_window.transient(parent)
    progress_window.grab_set()

    label = ttk.Label(progress_window, text="正在连接到服务器...")
    label.pack(padx=20, pady=10)

    # 创建进度条
    progress_bar = ttk.Progressbar(progress_window, orient="horizontal", length=300, mode='determinate')
    progress_bar.pack(padx=20, pady=5)
    
    # 使用 after 以确保窗口先显示
    parent.after(100, lambda: perform_download(progress_window, label, progress_bar, parent))


def perform_download(progress_window, label, progress_bar, parent_window):
    """执行下载、解压、安装和重启的完整流程。"""
    try:
        label.config(text="正在从GitHub下载更新...")
        progress_window.update_idletasks()

        response = requests.get(SOURCE_ZIP_URL, stream=True)
        response.raise_for_status()

        # 获取文件总大小，用于计算进度
        total_size = int(response.headers.get('content-length', 0))
        progress_bar['maximum'] = total_size
        
        downloaded_size = 0
        file_buffer = io.BytesIO()

        # 分块下载
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file_buffer.write(chunk)
                downloaded_size += len(chunk)
                # 更新进度条
                progress_bar['value'] = downloaded_size
                progress_window.update_idletasks() # 刷新UI

        label.config(text="下载完成，正在解压并安装...")
        progress_bar['mode'] = 'indeterminate' # 解压时使用不确定模式
        progress_bar.start(10)
        progress_window.update_idletasks()
        
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 从内存中的BytesIO对象解压
        file_buffer.seek(0)
        with zipfile.ZipFile(file_buffer) as z:
            root_folder_in_zip = z.namelist()[0]
            for member in z.infolist():
                path_in_zip = member.filename.replace(root_folder_in_zip, '', 1)
                if not path_in_zip:
                    continue

                target_path = os.path.join(app_root, path_in_zip)
                
                if ".git" in target_path:
                    continue

                if member.is_dir():
                    if not os.path.exists(target_path):
                        os.makedirs(target_path)
                else:
                    target_dir = os.path.dirname(target_path)
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir)
                    with z.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
        
        progress_bar.stop()
        progress_window.destroy()
        
        if _show_messagebox(parent_window, "更新成功", "程序已成功更新！\n是否立即重启应用程序以应用更改？", "askyesno"):
            python_console_executable = sys.executable
            
            if os.name == 'nt' and python_console_executable.endswith('pythonw.exe'):
                python_exe_path = os.path.join(os.path.dirname(python_console_executable), 'python.exe')
                if os.path.exists(python_exe_path):
                    python_console_executable = python_exe_path

            main_script_path = os.path.join(app_root, 'main.py')
            subprocess.Popen([python_console_executable, main_script_path])
            
            parent_window.destroy()
            sys.exit(0)

    except Exception as e:
        progress_window.destroy()
        _show_messagebox(parent_window, "更新失败", f"更新过程中发生错误: {e}", "error")
