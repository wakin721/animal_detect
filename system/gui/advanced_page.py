import tkinter as tk
from tkinter import ttk, messagebox
import os
import platform
import re
import subprocess
import logging
import threading
import sys

from system.gui.ui_components import CollapsiblePanel
from system.utils import resource_path

logger = logging.getLogger(__name__)


class AdvancedPage(ttk.Frame):
    """高级设置页面"""

    def __init__(self, parent, controller, **kwargs):
        super().__init__(parent, **kwargs)
        self.controller = controller
        self.is_dark_mode = self.controller.is_dark_mode

        self.controller.iou_var = tk.DoubleVar(value=0.3)
        self.controller.conf_var = tk.DoubleVar(value=0.25)
        self.controller.use_fp16_var = tk.BooleanVar(value=self.controller.cuda_available)
        self.controller.use_augment_var = tk.BooleanVar(value=True)
        self.controller.use_agnostic_nms_var = tk.BooleanVar(value=True)

        self._create_widgets()

    def _create_widgets(self) -> None:
        """创建高级设置页面的控件"""
        self.advanced_notebook = ttk.Notebook(self)
        self.advanced_notebook.pack(fill="both", expand=True, padx=20, pady=10)

        self.model_params_tab = ttk.Frame(self.advanced_notebook)
        self.advanced_notebook.add(self.model_params_tab, text="模型参数设置")

        self.env_maintenance_tab = ttk.Frame(self.advanced_notebook)
        self.advanced_notebook.add(self.env_maintenance_tab, text="环境维护")

        self.advanced_notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._create_model_params_content()
        self._create_env_maintenance_content()

    def _create_model_params_content(self) -> None:
        """创建模型参数设置内容"""
        main_frame = ttk.Frame(self.model_params_tab)
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        style = ttk.Style()
        bg_color = style.lookup('TFrame', 'background') or 'SystemButtonFace'
        self.params_canvas = tk.Canvas(main_frame, bg=bg_color, highlightthickness=0)

        self.params_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.params_canvas.yview)
        self.params_canvas.configure(yscrollcommand=self.params_scrollbar.set)
        self.params_scrollbar.grid(row=0, column=1, sticky="ns")
        self.params_canvas.grid(row=0, column=0, sticky="nsew")

        self.params_content_frame = ttk.Frame(self.params_canvas)
        self.params_content_frame.configure(style='TFrame')

        self.params_canvas_window = self.params_canvas.create_window(
            (0, 0),
            window=self.params_content_frame,
            anchor="nw"
        )

        self.threshold_panel = CollapsiblePanel(
            self.params_content_frame,
            title="检测阈值设置",
            subtitle="调整目标检测的置信度和重叠度阈值",
            icon="🎯"
        )
        self.threshold_panel.pack(fill="x", expand=False, pady=(0, 1))

        iou_frame = ttk.Frame(self.threshold_panel.content_padding)
        iou_frame.pack(fill="x", pady=5)
        iou_label_frame = ttk.Frame(iou_frame)
        iou_label_frame.pack(fill="x", pady=(0, 5))
        ttk.Label(iou_label_frame, text="IOU阈值").pack(side="left")
        self.iou_label = ttk.Label(iou_label_frame, text="0.30")
        self.iou_label.pack(side="right")
        iou_scale = ttk.Scale(
            iou_frame,
            from_=0.1,
            to=0.9,
            orient="horizontal",
            variable=self.controller.iou_var,
            command=self._update_iou_label
        )
        iou_scale.pack(fill="x")

        conf_frame = ttk.Frame(self.threshold_panel.content_padding)
        conf_frame.pack(fill="x", pady=10)
        conf_label_frame = ttk.Frame(conf_frame)
        conf_label_frame.pack(fill="x", pady=(0, 5))
        ttk.Label(conf_label_frame, text="置信度阈值").pack(side="left")
        self.conf_label = ttk.Label(conf_label_frame, text="0.25")
        self.conf_label.pack(side="right")
        conf_scale = ttk.Scale(
            conf_frame,
            from_=0.05,
            to=0.95,
            orient="horizontal",
            variable=self.controller.conf_var,
            command=self._update_conf_label
        )
        conf_scale.pack(fill="x")

        self.accel_panel = CollapsiblePanel(
            self.params_content_frame,
            title="模型加速选项",
            subtitle="控制推理速度与精度的平衡",
            icon="⚡"
        )
        self.accel_panel.pack(fill="x", expand=False, pady=(0, 1))

        fp16_frame = ttk.Frame(self.accel_panel.content_padding)
        fp16_frame.pack(fill="x", pady=5)
        fp16_check = ttk.Checkbutton(
            fp16_frame,
            text="使用FP16加速 (需要支持CUDA)",
            variable=self.controller.use_fp16_var,
            state="normal" if self.controller.cuda_available else "disabled"
        )
        fp16_check.pack(anchor="w")
        if not self.controller.cuda_available:
            cuda_warning = ttk.Label(
                fp16_frame,
                text="未检测到CUDA，FP16加速已禁用",
                foreground="red"
            )
            cuda_warning.pack(anchor="w", pady=(5, 0))

        self.advanced_detect_panel = CollapsiblePanel(
            self.params_content_frame,
            title="高级检测选项",
            subtitle="配置增强检测功能和特殊选项",
            icon="🔍"
        )
        self.advanced_detect_panel.pack(fill="x", expand=False, pady=(0, 1))

        augment_frame = ttk.Frame(self.advanced_detect_panel.content_padding)
        augment_frame.pack(fill="x", pady=5)
        augment_check = ttk.Checkbutton(
            augment_frame,
            text="使用数据增强 (Test-Time Augmentation)",
            variable=self.controller.use_augment_var
        )
        augment_check.pack(anchor="w")

        agnostic_frame = ttk.Frame(self.advanced_detect_panel.content_padding)
        agnostic_frame.pack(fill="x", pady=5)
        agnostic_check = ttk.Checkbutton(
            agnostic_frame,
            text="使用类别无关NMS (Class-Agnostic NMS)",
            variable=self.controller.use_agnostic_nms_var
        )
        agnostic_check.pack(anchor="w")

        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
        separator = ttk.Separator(bottom_frame, orient="horizontal")
        separator.pack(fill="x", pady=10)
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(fill="x", padx=10)
        help_button = ttk.Button(
            button_frame,
            text="参数说明",
            command=self.controller.show_params_help,
            width=14
        )
        help_button.pack(side="left", padx=5)
        reset_button = ttk.Button(
            button_frame,
            text="重置为默认值",
            command=self._reset_model_params,
            width=14
        )
        reset_button.pack(side="right", padx=5)

        for panel in [self.threshold_panel, self.accel_panel, self.advanced_detect_panel]:
            panel.bind_toggle_callback(self._on_panel_toggle)
        self._configure_params_scrolling()
        self.master.after(100, lambda: self.params_canvas.yview_moveto(0.0))

    def _create_env_maintenance_content(self) -> None:
        """创建环境维护标签页内容"""
        for widget in self.env_maintenance_tab.winfo_children():
            widget.destroy()

        self.env_scrollable = ttk.Frame(self.env_maintenance_tab)
        self.env_scrollable.pack(fill="both", expand=True)

        style = ttk.Style()
        bg_color = style.lookup('TFrame', 'background') or 'SystemButtonFace'
        self.env_canvas = tk.Canvas(self.env_scrollable, bg=bg_color, highlightthickness=0)

        self.env_canvas.pack(side="left", fill="both", expand=True)
        self.env_scrollbar = ttk.Scrollbar(self.env_scrollable, orient="vertical", command=self.env_canvas.yview)
        self.env_scrollbar.pack(side="right", fill="y")
        self.env_canvas.configure(yscrollcommand=self.env_scrollbar.set)
        self.env_content_frame = ttk.Frame(self.env_canvas)
        self.env_canvas_window = self.env_canvas.create_window(
            (0, 0),
            window=self.env_content_frame,
            anchor="nw"
        )

        self.pytorch_panel = CollapsiblePanel(
            self.env_content_frame,
            "安装 PyTorch",
            subtitle="安装或修复 PyTorch",
            icon="📦"
        )
        self.pytorch_panel.pack(fill="x", expand=False, pady=(0, 1))

        version_frame = ttk.Frame(self.pytorch_panel.content_padding)
        version_frame.pack(fill="x", pady=5)
        ttk.Label(version_frame, text="选择版本").pack(side="top", anchor="w", pady=(0, 5))
        self.pytorch_version_var = tk.StringVar()
        versions = [
            "2.7.1 (CUDA 12.8)",
            "2.7.1 (CUDA 12.6)",
            "2.7.1 (CUDA 11.8)",
            "2.7.1 (CPU Only)",
        ]
        style.configure("Dropdown.TCombobox", padding=(10, 5))
        version_combo = ttk.Combobox(
            version_frame,
            textvariable=self.pytorch_version_var,
            values=versions,
            state="readonly",
            style="Dropdown.TCombobox"
        )
        version_combo.pack(fill="x", expand=True)
        version_combo.current(0)

        options_frame = ttk.Frame(self.pytorch_panel.content_padding)
        options_frame.pack(fill="x", pady=10)
        self.force_reinstall_var = tk.BooleanVar(value=False)
        force_reinstall_switch = ttk.Checkbutton(
            options_frame,
            text="强制重装PyTorch",
            variable=self.force_reinstall_var
        )
        force_reinstall_switch.pack(anchor="w")
        ttk.Label(
            options_frame,
            text="勾选后将先卸载现有的torch、torchvision、torchaudio模块再重新安装",
            foreground="#666666",
            font=("Segoe UI", 8)
        ).pack(anchor="w", padx=(20, 0))

        bottom_frame = ttk.Frame(self.pytorch_panel.content_padding)
        bottom_frame.pack(fill="x", pady=(10, 0))
        self.pytorch_status_var = tk.StringVar(value="")
        ttk.Label(bottom_frame, textvariable=self.pytorch_status_var).pack(side="left")
        self.install_button = ttk.Button(
            bottom_frame,
            text="安装",
            command=self._install_pytorch,
            style="Action.TButton"
        )
        style.configure("Action.TButton", font=("Segoe UI", 9))
        self.install_button.pack(side="right")

        self.model_panel = CollapsiblePanel(
            self.env_content_frame,
            "模型管理",
            subtitle="管理用于识别的模型",
            icon="🔧"
        )
        self.model_panel.pack(fill="x", expand=False, pady=(0, 1))

        model_selection_frame = ttk.Frame(self.model_panel.content_padding)
        model_selection_frame.pack(fill="x", pady=5)
        ttk.Label(model_selection_frame, text="当前使用的模型").pack(anchor="w", pady=(0, 5))
        model_name = os.path.basename(self.controller.image_processor.model_path) if hasattr(
            self.controller.image_processor, 'model_path') and self.controller.image_processor.model_path else "未知"
        self.current_model_var = tk.StringVar(value=model_name)
        style.configure("ReadOnly.TEntry", fieldbackground="#f0f0f0" if not self.is_dark_mode else "#3a3a3a")
        current_model_entry = ttk.Entry(
            model_selection_frame,
            textvariable=self.current_model_var,
            state="readonly",
            style="ReadOnly.TEntry"
        )
        current_model_entry.pack(fill="x", expand=True, pady=(0, 10))
        ttk.Label(model_selection_frame, text="选择可用模型").pack(anchor="w", pady=(0, 5))
        self.model_selection_var = tk.StringVar()
        self.model_combobox = ttk.Combobox(
            model_selection_frame,
            textvariable=self.model_selection_var,
            state="readonly",
            style="Dropdown.TCombobox"
        )
        self.model_combobox.pack(fill="x", expand=True)
        model_buttons_frame = ttk.Frame(self.model_panel.content_padding)
        model_buttons_frame.pack(fill="x", pady=10)
        self.model_status_var = tk.StringVar(value="")
        ttk.Label(model_buttons_frame, textvariable=self.model_status_var).pack(side="left")
        refresh_btn = ttk.Button(
            model_buttons_frame,
            text="刷新列表",
            command=self._refresh_model_list,
            style="Secondary.TButton"
        )
        style.configure("Secondary.TButton", font=("Segoe UI", 9))
        refresh_btn.pack(side="right", padx=(0, 5))
        apply_btn = ttk.Button(
            model_buttons_frame,
            text="应用模型",
            command=self._apply_selected_model,
            style="Action.TButton"
        )
        apply_btn.pack(side="right")

        self.python_panel = CollapsiblePanel(
            self.env_content_frame,
            "重装单个 Python 组件",
            subtitle="重新安装单个 Pip 软件包",
            icon="🐍"
        )
        self.python_panel.pack(fill="x", expand=False, pady=(0, 1))

        package_frame = ttk.Frame(self.python_panel.content_padding)
        package_frame.pack(fill="x", pady=5)
        ttk.Label(package_frame, text="输入包名称").pack(anchor="w", pady=(0, 5))
        self.package_var = tk.StringVar()
        ttk.Entry(package_frame, textvariable=self.package_var).pack(fill="x", expand=True)

        version_constraint_frame = ttk.Frame(self.python_panel.content_padding)
        version_constraint_frame.pack(fill="x", pady=10)
        ttk.Label(version_constraint_frame, text="版本约束 (可选)").pack(anchor="w", pady=(0, 5))
        self.version_constraint_var = tk.StringVar()
        ttk.Entry(version_constraint_frame, textvariable=self.version_constraint_var).pack(fill="x", expand=True)
        ttk.Label(
            version_constraint_frame,
            text="示例: ==1.0.0, >=2.0.0, <3.0.0",
            font=("Segoe UI", 8),
            foreground="#888888"
        ).pack(anchor="w", pady=(2, 0))

        package_buttons_frame = ttk.Frame(self.python_panel.content_padding)
        package_buttons_frame.pack(fill="x", pady=(10, 0))
        self.package_status_var = tk.StringVar(value="")
        ttk.Label(package_buttons_frame, textvariable=self.package_status_var).pack(side="left")
        self.install_package_btn = ttk.Button(
            package_buttons_frame,
            text="安装",
            command=self._install_python_package,
            style="Action.TButton"
        )
        self.install_package_btn.pack(side="right")

        self._refresh_model_list()
        self._check_pytorch_status()
        self._configure_env_scrolling()
        self.master.after(100, lambda: self.env_canvas.yview_moveto(0.0))

    def _configure_params_scrolling(self):
        def _update_scrollregion(event=None):
            self.params_canvas.configure(scrollregion=self.params_canvas.bbox("all"))

        def _configure_canvas(event):
            canvas_width = event.width
            if self.params_canvas.winfo_exists() and self.params_canvas_window:
                self.params_canvas.itemconfigure(self.params_canvas_window, width=canvas_width)

        def _on_mousewheel(event):
            view_pos = self.params_canvas.yview()
            if platform.system() == "Windows":
                delta = -1 if event.delta > 0 else 1
            else:
                if hasattr(event, 'num'):
                    delta = -1 if event.num == 4 else 1
                else:
                    return

            if delta < 0 and view_pos[0] < 0.1:
                self.params_canvas.yview_moveto(0)
            else:
                self.params_canvas.yview_scroll(delta, "units")

            if self.params_canvas.yview()[0] < 0.001:
                self.params_canvas.yview_moveto(0)
            return "break"

        self.params_canvas.bind("<MouseWheel>", _on_mousewheel)
        self.params_canvas.bind("<Button-4>", _on_mousewheel)
        self.params_canvas.bind("<Button-5>", _on_mousewheel)
        self.params_content_frame.bind("<Configure>", _update_scrollregion)
        self.params_canvas.bind("<Configure>", _configure_canvas)

    def _configure_env_scrolling(self):
        def _update_scrollregion(event=None):
            self.env_canvas.configure(scrollregion=self.env_canvas.bbox("all"))

        def _configure_canvas(event):
            canvas_width = event.width
            if self.env_canvas.winfo_exists() and self.env_canvas_window:
                self.env_canvas.itemconfigure(self.env_canvas_window, width=canvas_width)

        def _on_mousewheel(event):
            view_pos = self.env_canvas.yview()
            if platform.system() == "Windows":
                delta = -1 if event.delta > 0 else 1
            else:
                if hasattr(event, 'num'):
                    delta = -1 if event.num == 4 else 1
                else:
                    return

            if delta < 0 and view_pos[0] < 0.1:
                self.env_canvas.yview_moveto(0)
            else:
                self.env_canvas.yview_scroll(delta, "units")
            if self.env_canvas.yview()[0] < 0.001:
                self.env_canvas.yview_moveto(0)
            return "break"

        self.env_canvas.bind("<MouseWheel>", _on_mousewheel)
        self.env_canvas.bind("<Button-4>", _on_mousewheel)
        self.env_canvas.bind("<Button-5>", _on_mousewheel)
        self.env_content_frame.bind("<Configure>", _update_scrollregion)
        self.env_canvas.bind("<Configure>", _configure_canvas)

    def _on_panel_toggle(self, panel, is_expanded):
        current_pos = self.params_canvas.yview()
        was_at_top = current_pos[0] <= 0.001
        self.params_content_frame.update_idletasks()
        self.params_canvas.configure(scrollregion=self.params_canvas.bbox("all"))
        if was_at_top:
            self.params_canvas.yview_moveto(0.0)
        self.master.after(50, self._force_check_params_top)

    def _force_check_params_top(self):
        current_pos = self.params_canvas.yview()
        if 0 < current_pos[0] < 0.01:
            self.params_canvas.yview_moveto(0.0)

    def _update_iou_label(self, value):
        self.iou_label.config(text=f"{float(value):.2f}")

    def _update_conf_label(self, value):
        self.conf_label.config(text=f"{float(value):.2f}")

    def _reset_model_params(self):
        self.controller.iou_var.set(0.3)
        self._update_iou_label(0.3)
        self.controller.conf_var.set(0.25)
        self._update_conf_label(0.25)
        self.controller.use_fp16_var.set(self.controller.cuda_available)
        self.controller.use_augment_var.set(False)
        self.controller.use_agnostic_nms_var.set(False)
        self.controller.status_bar.show_message("已重置所有参数到默认值", 3000)

    def _check_pytorch_status(self) -> None:
        """检查PyTorch安装状态"""
        try:
            import torch
            version = torch.__version__
            device = "GPU (CUDA)" if torch.cuda.is_available() else "CPU"
            self.pytorch_status_var.set(f"已安装 v{version} ({device})")
        except ImportError:
            self.pytorch_status_var.set("未安装")
        except Exception as e:
            self.pytorch_status_var.set(f"检查失败: {str(e)}")

    # V V V V V V V V V V V V V V V V V V V V
    # MODIFICATION: Refined installation logic for auto-closing terminal and restart prompt.
    # V V V V V V V V V V V V V V V V V V V V
    def _ask_for_restart(self, title="操作完成"):
        """弹窗询问用户是否重启应用"""
        try:
            if messagebox.askyesno(title, "操作已完成，建议重启软件以应用所有更改。\n是否立即重启？"):
                logger.info("用户选择重启应用程序")
                try:
                    python_executable = sys.executable
                    if os.name == 'nt' and 'pythonw.exe' in python_executable.lower():
                        console_executable = os.path.join(os.path.dirname(python_executable), 'python.exe')
                        if os.path.exists(console_executable):
                            python_executable = console_executable
                    
                    main_script = sys.argv[0]
                    logger.info(f"重启命令: {python_executable} {main_script}")
                    
                    subprocess.Popen([python_executable, main_script])
                    self.controller.master.destroy()
                except Exception as e:
                    error_msg = f"无法自动重启应用: {e}"
                    logger.error(error_msg, exc_info=True)
                    messagebox.showerror("重启失败", f"{error_msg}\n请手动重启应用程序。")
            else:
                logger.info("用户选择不重启应用程序")
        except Exception as e:
            logger.error(f"重启询问过程中发生错误: {e}", exc_info=True)

    def _run_install_in_terminal(self, command_args, status_var, success_title):
        """在新终端窗口中运行安装命令，完成后自动关闭并提示重启"""

        def installation_thread():
            try:
                python_executable = sys.executable
                logger.info(f"开始安装过程，Python可执行文件: {python_executable}")
                
                # 强制使用 python.exe 以确保终端窗口弹出
                if os.name == 'nt' and 'pythonw.exe' in python_executable.lower():
                    console_executable = os.path.join(os.path.dirname(python_executable), 'python.exe')
                    if os.path.exists(console_executable):
                        python_executable = console_executable
                        logger.info(f"切换到控制台版本: {python_executable}")

                # 构造基础安装命令 (作为列表，更安全)
                base_cmd = [python_executable, '-m'] + command_args
                logger.info(f"基础安装命令: {base_cmd}")

                # 平台特定的命令构造和执行
                self.master.after(0, lambda: status_var.set("安装已启动..."))

                if platform.system() == "Windows":
                    # Windows: 使用 cmd.exe 特定语法和适当的转义
                    install_cmd_str = subprocess.list2cmdline(base_cmd)
                    success_msg = "echo. && echo Installation successful. This window will close in 5 seconds... && timeout /t 5 /nobreak"
                    final_command = f'cmd /c "({install_cmd_str}) && ({success_msg})"'
                    logger.info(f"Windows命令: {final_command}")
                    
                    # 在Windows上创建新的控制台窗口
                    process = subprocess.Popen(
                        final_command,
                        shell=True,
                        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
                    )
                else:
                    # Linux/macOS: 使用 sh/bash 语法
                    install_cmd_str = ' '.join(f'"{arg}"' if ' ' in str(arg) or any(c in str(arg) for c in ['&', '|', ';', '(', ')', '<', '>']) else str(arg) for arg in base_cmd)
                    success_msg = 'echo "" && echo "Installation successful. This window will close in 5 seconds..." && sleep 5'
                    final_command = f'({install_cmd_str}) && ({success_msg})'
                    logger.info(f"Unix命令: {final_command}")
                    
                    # 尝试在新终端窗口中打开 (如果可能)
                    terminal_cmd = None
                    for terminal in ['gnome-terminal', 'xterm', 'konsole', 'x-terminal-emulator']:
                        if subprocess.run(['which', terminal], capture_output=True).returncode == 0:
                            if terminal == 'gnome-terminal':
                                terminal_cmd = ['gnome-terminal', '--', 'bash', '-c', final_command]
                            elif terminal == 'xterm':
                                terminal_cmd = ['xterm', '-e', 'bash', '-c', final_command]
                            elif terminal == 'konsole':
                                terminal_cmd = ['konsole', '-e', 'bash', '-c', final_command]
                            else:
                                terminal_cmd = [terminal, '-e', 'bash', '-c', final_command]
                            break
                    
                    if terminal_cmd:
                        logger.info(f"使用终端: {terminal_cmd[0]}")
                        process = subprocess.Popen(terminal_cmd)
                    else:
                        # 回退到无终端执行
                        logger.warning("未找到合适的终端，回退到后台执行")
                        process = subprocess.Popen(final_command, shell=True)

                # 等待安装完成
                logger.info("等待安装过程完成...")
                process.communicate()

                # 处理结果
                if process.returncode == 0:
                    logger.info("安装成功完成")
                    self.master.after(0, lambda: status_var.set("安装成功！"))
                    self.master.after(100, lambda: self._ask_for_restart(success_title))
                else:
                    # 安装失败
                    error_message = f"安装失败 (返回码: {process.returncode})。\n请查看终端窗口获取详细错误信息。"
                    logger.error(f"安装失败，返回码: {process.returncode}")
                    self.master.after(0, lambda: status_var.set("安装失败"))
                    self.master.after(0, lambda: messagebox.showerror("安装错误", error_message))

            except subprocess.CalledProcessError as e:
                error_msg = f"安装命令执行失败: {e}"
                logger.error(error_msg)
                self.master.after(0, lambda: status_var.set("执行失败"))
                self.master.after(0, lambda: messagebox.showerror("执行错误", error_msg))
            except FileNotFoundError as e:
                error_msg = f"找不到可执行文件: {e}"
                logger.error(error_msg)
                self.master.after(0, lambda: status_var.set("文件未找到"))
                self.master.after(0, lambda: messagebox.showerror("文件错误", error_msg))
            except Exception as e:
                error_msg = f"执行安装命令时出现未知错误: {e}"
                logger.error(error_msg, exc_info=True)
                self.master.after(0, lambda: status_var.set("未知错误"))
                self.master.after(0, lambda: messagebox.showerror("未知错误", error_msg))
            finally:
                # 确保按钮状态总是被恢复
                logger.info("恢复按钮状态")
                self.master.after(0, self._restore_button_states)

        threading.Thread(target=installation_thread, daemon=True).start()

    def _restore_button_states(self):
        """恢复所有安装按钮的状态"""
        try:
            if hasattr(self, 'install_button') and self.install_button:
                self.install_button.configure(state="normal")
                logger.debug("恢复PyTorch安装按钮状态")
        except Exception as e:
            logger.warning(f"恢复install_button状态失败: {e}")
        
        try:
            if hasattr(self, 'install_package_btn') and self.install_package_btn:
                self.install_package_btn.configure(state="normal")
                logger.debug("恢复包安装按钮状态")
        except Exception as e:
            logger.warning(f"恢复install_package_btn状态失败: {e}")

    def _install_pytorch(self):
        """准备并启动PyTorch安装"""
        try:
            version_str = self.pytorch_version_var.get()
            if not version_str:
                messagebox.showerror("错误", "请选择PyTorch版本")
                return
                
            logger.info(f"开始PyTorch安装流程，版本: {version_str}")
            
            if not messagebox.askyesno("确认安装",
                                       f"将开始安装 PyTorch {version_str}。\n过程可能需要几分钟，请保持网络连接。\n是否继续？"):
                logger.info("用户取消了PyTorch安装")
                return

            # 禁用按钮并显示状态
            self.install_button.configure(state="disabled")
            self.pytorch_status_var.set("正在准备安装...")
            self.master.update_idletasks()

            # 解析版本信息
            pytorch_match = re.search(r"(\d+\.\d+\.\d+)", version_str)
            cuda_match = re.search(r"CUDA (\d+\.\d+)", version_str)
            pytorch_version = pytorch_match.group(1) if pytorch_match else None
            cuda_version = cuda_match.group(1) if cuda_match else None

            if not pytorch_version:
                error_msg = "无法解析PyTorch版本信息"
                logger.error(f"{error_msg}，版本字符串: {version_str}")
                messagebox.showerror("错误", error_msg)
                self.install_button.configure(state="normal")
                self.pytorch_status_var.set("版本解析失败")
                return

            # 构造安装命令
            command_args = ["pip", "install", "--upgrade"]
            if self.force_reinstall_var.get():
                command_args.append("--force-reinstall")
                logger.info("启用强制重装选项")
                
            command_args.extend([f"torch=={pytorch_version}", "torchvision", "torchaudio"])
            
            if cuda_version:
                cuda_str_map = {"11.8": "cu118", "12.1": "cu121", "12.6": "cu126", "12.8": "cu128"}
                cuda_str = cuda_str_map.get(cuda_version, f"cu{cuda_version.replace('.', '')}")
                command_args.extend(["--index-url", f"https://download.pytorch.org/whl/{cuda_str}"])
                logger.info(f"使用CUDA版本: {cuda_version} ({cuda_str})")
            else:
                command_args.extend(["--index-url", "https://download.pytorch.org/whl/cpu"])
                logger.info("使用CPU版本")

            logger.info(f"PyTorch安装命令: {command_args}")
            self._run_install_in_terminal(command_args, self.pytorch_status_var, "PyTorch 安装完成")
            
        except Exception as e:
            error_msg = f"准备PyTorch安装时发生错误: {e}"
            logger.error(error_msg, exc_info=True)
            messagebox.showerror("安装准备错误", error_msg)
            self.pytorch_status_var.set("准备失败")
            # 确保按钮状态恢复
            try:
                self.install_button.configure(state="normal")
            except Exception:
                pass

    def _install_python_package(self):
        """准备并启动单个Python包的安装"""
        try:
            package = self.package_var.get().strip()
            if not package:
                messagebox.showerror("错误", "请输入包名称")
                return
                
            version_constraint = self.version_constraint_var.get().strip()
            package_spec = f"{package}{version_constraint}"
            
            logger.info(f"开始Python包安装流程，包规格: {package_spec}")
            
            if not messagebox.askyesno("确认安装", f"将开始安装 {package_spec}。\n是否继续？"):
                logger.info("用户取消了包安装")
                return

            # 禁用按钮并显示状态
            self.install_package_btn.configure(state="disabled")
            self.package_status_var.set("正在准备安装...")
            self.master.update_idletasks()

            # 验证包名称格式 (基础验证)
            if not package.replace('-', '').replace('_', '').replace('.', '').isalnum():
                error_msg = f"包名称格式无效: {package}"
                logger.warning(error_msg)
                messagebox.showerror("错误", error_msg)
                self.install_package_btn.configure(state="normal")
                self.package_status_var.set("格式错误")
                return

            # 构造安装命令
            command_args = ["pip", "install", "--upgrade", package_spec]
            logger.info(f"包安装命令: {command_args}")
            
            self._run_install_in_terminal(command_args, self.package_status_var, f"安装 {package_spec} 完成")
            
        except Exception as e:
            error_msg = f"准备包安装时发生错误: {e}"
            logger.error(error_msg, exc_info=True)
            messagebox.showerror("安装准备错误", error_msg)
            self.package_status_var.set("准备失败")
            # 确保按钮状态恢复
            try:
                self.install_package_btn.configure(state="normal")
            except Exception:
                pass

    # ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^

    def _refresh_model_list(self):
        res_dir = resource_path("res")
        try:
            self.model_combobox["values"] = []
            if os.path.exists(res_dir):
                model_files = [f for f in os.listdir(res_dir) if f.lower().endswith('.pt')]
                if model_files:
                    model_files.sort()
                    self.model_combobox["values"] = model_files
                    self.model_combobox.current(0)
                    current_model = os.path.basename(self.controller.image_processor.model_path) if hasattr(
                        self.controller.image_processor,
                        'model_path') and self.controller.image_processor.model_path else None
                    if current_model in model_files:
                        self.model_combobox.set(current_model)
                    self.model_status_var.set(f"找到 {len(model_files)} 个模型文件")
                else:
                    self.model_status_var.set("未找到任何模型文件")
            else:
                self.model_status_var.set("模型目录不存在")
        except Exception as e:
            logger.error(f"刷新模型列表失败: {e}")
            self.model_status_var.set(f"刷新失败: {str(e)}")

    def _apply_selected_model(self):
        model_name = self.model_selection_var.get()
        if not model_name:
            messagebox.showinfo("提示", "请先选择一个模型")
            return
        model_path = resource_path(os.path.join("res", model_name))
        if not os.path.exists(model_path):
            messagebox.showerror("错误", f"模型文件不存在: {model_path}")
            return
        current_model = os.path.basename(self.controller.image_processor.model_path) if hasattr(
            self.controller.image_processor, 'model_path') and self.controller.image_processor.model_path else None
        if model_name == current_model:
            messagebox.showinfo("提示", f"模型 {model_name} 已经加载")
            return
        if not messagebox.askyesno("确认", f"确定要切换到模型 {model_name} 吗？"):
            return
        self.model_status_var.set("正在加载...")
        self.master.update_idletasks()
        threading.Thread(target=self._load_model_thread, args=(model_path, model_name), daemon=True).start()

    def _load_model_thread(self, model_path, model_name):
        try:
            self.controller.image_processor.load_model(model_path)
            self.master.after(0, lambda: self.current_model_var.set(model_name))
            self.master.after(0, lambda: self.model_status_var.set("已加载"))
            self.master.after(0, lambda: messagebox.showinfo("成功", f"模型 {model_name} 已成功加载"))
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            self.master.after(0, lambda: self.model_status_var.set(f"加载失败: {str(e)}"))
            self.master.after(0, lambda: messagebox.showerror("错误", f"加载模型失败: {e}"))

    def _on_tab_changed(self, event):
        current_tab = self.advanced_notebook.select()
        tab_text = self.advanced_notebook.tab(current_tab, "text")
        if tab_text == "环境维护" and hasattr(self, 'env_canvas'):
            self.master.after(10, lambda: self.env_canvas.configure(scrollregion=self.env_canvas.bbox("all")))