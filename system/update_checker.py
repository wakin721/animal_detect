# system/update_checker.py

import requests
import re
import os
import zipfile
import io
import shutil
import tkinter as tk
from tkinter import messagebox
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
    """下载并安装更新。"""
    progress_window = tk.Toplevel(parent)
    progress_window.title("正在更新...")
    progress_window.geometry("300x100")
    
    icon_path = get_icon_path()
    if os.path.exists(icon_path):
        try:
            progress_window.iconbitmap(icon_path)
        except tk.TclError:
            pass
            
    progress_window.transient(parent)
    progress_window.grab_set()

    label = tk.Label(progress_window, text="正在从GitHub下载更新...")
    label.pack(padx=20, pady=20)
    
    parent.after(100, lambda: perform_download(progress_window, label, parent))


def perform_download(progress_window, label, parent_window):
    """执行下载、解压、安装和重启的完整流程。"""
    try:
        response = requests.get(SOURCE_ZIP_URL, stream=True)
        response.raise_for_status()

        label.config(text="下载完成，正在解压并安装...")
        progress_window.update()
        
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
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
        
        progress_window.destroy()
        
        if _show_messagebox(parent_window, "更新成功", "程序已成功更新！\n是否立即重启应用程序以应用更改？", "askyesno"):
            # 获取当前虚拟环境的Python解释器路径
            python_console_executable = sys.executable
            
            # 在Windows上, sys.executable可能是'pythonw.exe'。我们需要'python.exe'来显示命令行窗口。
            if os.name == 'nt' and python_console_executable.endswith('pythonw.exe'):
                # 'python.exe'通常和'pythonw.exe'在同一个目录下
                python_exe_path = os.path.join(os.path.dirname(python_console_executable), 'python.exe')
                if os.path.exists(python_exe_path):
                    python_console_executable = python_exe_path

            # 获取主脚本'main.py'的路径
            main_script_path = os.path.join(app_root, 'main.py')

            # 使用Popen启动一个新进程来运行主脚本。
            # 这个新进程会显示一个命令行窗口来执行main.py中的依赖检查,
            # 然后main.py内部的逻辑会再次以无窗口模式启动GUI并退出, 从而关闭命令行。
            subprocess.Popen([python_console_executable, main_script_path])
            
            # 退出当前(旧的)应用程序
            parent_window.destroy()
            sys.exit(0)

    except Exception as e:
        progress_window.destroy()
        _show_messagebox(parent_window, "更新失败", f"更新过程中发生错误: {e}", "error")
