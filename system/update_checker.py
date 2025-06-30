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


def check_for_updates(parent, silent=False):
    """
    检查GitHub上是否有新版本。

    Args:
        parent: 父窗口，用于显示消息框。
        silent: 是否为静默检查。如果是，只在有更新时显示消息。
    """
    try:
        response = requests.get(CONFIG_FILE_URL)
        response.raise_for_status()
        remote_config_content = response.text

        match = re.search(r"APP_VERSION\s*=\s*\"(.*?)\"", remote_config_content)
        if not match:
            if not silent:
                messagebox.showerror("更新错误", "无法在远程仓库中找到版本信息。")
            return

        remote_version = match.group(1)

        # 版本比较逻辑，确保 '2.1.10' > '2.1.9'
        current_parts = list(map(int, APP_VERSION.split('-')[0].split('.')))
        remote_parts = list(map(int, remote_version.split('-')[0].split('.')))

        if remote_parts > current_parts:
            if messagebox.askyesno("发现新版本", f"新版本 ({remote_version}) 可用，您想现在更新吗？"):
                download_and_install_update(parent)
        else:
            if not silent:
                messagebox.showinfo("无更新", "您目前使用的是最新版本。")

    except requests.RequestException as e:
        if not silent:
            messagebox.showerror("更新错误", f"检查更新失败: {e}")


def download_and_install_update(parent):
    """下载并安装更新。"""
    progress_window = tk.Toplevel(parent)
    progress_window.title("正在更新...")
    progress_window.geometry("300x100")
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
                # 从压缩包成员路径中移除顶层目录
                path_in_zip = member.filename.replace(root_folder_in_zip, '', 1)
                if not path_in_zip:
                    continue

                target_path = os.path.join(app_root, path_in_zip)

                # 排除 .gitattributes, .gitignore 等Git相关文件
                if ".git" in target_path:
                    continue

                # 如果是目录，则创建
                if member.is_dir():
                    if not os.path.exists(target_path):
                        os.makedirs(target_path)
                # 如果是文件，则写入
                else:
                    # 确保目标目录存在
                    target_dir = os.path.dirname(target_path)
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir)
                    with z.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)

        progress_window.destroy()

        # 询问用户是否立即重启
        if messagebox.askyesno("更新成功", "程序已成功更新！\n是否立即重启应用程序以应用更改？"):
            # 获取当前虚拟环境的Python解释器路径
            python_executable = sys.executable
            # 获取主脚本 'main.py' 的路径
            main_script_path = os.path.join(app_root, 'main.py')

            # 使用 Popen 启动一个新进程来运行主脚本
            subprocess.Popen([python_executable, main_script_path])

            # 退出当前应用
            parent_window.destroy()
            sys.exit(0)

    except Exception as e:
        progress_window.destroy()
        messagebox.showerror("更新失败", f"更新过程中发生错误: {e}")
