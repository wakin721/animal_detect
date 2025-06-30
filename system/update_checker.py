# system/update_checker.py

import requests
import re
import os
import zipfile
import io
import shutil
import tkinter as tk
from tkinter import messagebox
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

        if remote_version > APP_VERSION:
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
    
    # 使用 after 以确保窗口先显示
    parent.after(100, lambda: perform_download(progress_window, label, parent))

def perform_download(progress_window, label, parent_window):
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
                
                # 排除 .gitattributes, .gitignore 等文件
                if ".git" in target_path:
                    continue

                if member.is_dir():
                    if not os.path.exists(target_path):
                        os.makedirs(target_path)
                else:
                    with z.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
        
        progress_window.destroy()
        messagebox.showinfo("更新成功", "程序已成功更新！请重启应用程序以应用更改。")
        parent_window.destroy()

    except Exception as e:
        progress_window.destroy()
        messagebox.showerror("更新失败", f"更新过程中发生错误: {e}")