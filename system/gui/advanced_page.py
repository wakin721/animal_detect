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
from system.config import APP_VERSION

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

        # Keybinding variables
        self.key_up_var = tk.StringVar(value='<Up>')
        self.key_down_var = tk.StringVar(value='<Down>')
        self.key_correct_var = tk.StringVar(value='<Key-1>')
        self.key_incorrect_var = tk.StringVar(value='<Key-2>')

        self.cache_size_var = tk.StringVar(value="正在计算...")

        self._create_widgets()

    def _create_widgets(self) -> None:
        """创建高级设置页面的控件"""
        self.advanced_notebook = ttk.Notebook(self)
        self.advanced_notebook.pack(fill="both", expand=True, padx=20, pady=10)

        self.model_params_tab = ttk.Frame(self.advanced_notebook)
        self.advanced_notebook.add(self.model_params_tab, text="模型参数设置")

        self.env_maintenance_tab = ttk.Frame(self.advanced_notebook)
        self.advanced_notebook.add(self.env_maintenance_tab, text="环境维护")

        self.software_settings_tab = ttk.Frame(self.advanced_notebook)
        self.advanced_notebook.add(self.software_settings_tab, text="软件设置")

        self.advanced_notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._create_model_params_content()
        self._create_env_maintenance_content()
        self._create_software_settings_content()

    def _create_software_settings_content(self) -> None:
        """创建软件设置标签页内容"""
        main_frame = ttk.Frame(self.software_settings_tab)
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        style = ttk.Style()
        bg_color = style.lookup('TFrame', 'background') or 'SystemButtonFace'
        self.software_canvas = tk.Canvas(main_frame, bg=bg_color, highlightthickness=0)
        self.software_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.software_canvas.yview)
        self.software_canvas.configure(yscrollcommand=self.software_scrollbar.set)
        self.software_scrollbar.grid(row=0, column=1, sticky="ns")
        self.software_canvas.grid(row=0, column=0, sticky="nsew")
        self.software_content_frame = ttk.Frame(self.software_canvas)
        self.software_canvas_window = self.software_canvas.create_window(
            (0, 0), window=self.software_content_frame, anchor="nw"
        )

        # --- Keybinding Panel ---
        self.keybinding_panel = CollapsiblePanel(
            self.software_content_frame,
            "按键绑定",
            subtitle="自定义“检查校验”中的快捷键",
            icon="⌨️"
        )
        self.keybinding_panel.pack(fill="x", expand=False, pady=(0, 1))
        keybinding_grid = ttk.Frame(self.keybinding_panel.content_padding)
        keybinding_grid.pack(fill='x', pady=5)
        keybinding_grid.columnconfigure(1, weight=1)

        key_map = {
            "上一张图片:": self.key_up_var,
            "下一张图片:": self.key_down_var,
            "标记为“正确”:": self.key_correct_var,
            "标记为“错误”:": self.key_incorrect_var,
        }

        i = 0
        for i, (text, var) in enumerate(key_map.items()):
            ttk.Label(keybinding_grid, text=text).grid(row=i, column=0, sticky='w', padx=5, pady=5)
            entry = ttk.Entry(keybinding_grid, textvariable=var, width=20)
            entry.grid(row=i, column=1, sticky='we', padx=5, pady=5)

        ttk.Label(keybinding_grid, text="提示: 单个字母的快捷键不区分大小写。", font=("Segoe UI", 8)).grid(row=i + 1,
                                                                                                          columnspan=2,
                                                                                                          sticky='w',
                                                                                                          padx=5,
                                                                                                          pady=5)

        keybinding_buttons_frame = ttk.Frame(self.keybinding_panel.content_padding)
        keybinding_buttons_frame.pack(fill='x', pady=10)
        keybinding_buttons_frame.columnconfigure(0, weight=1)

        help_button = ttk.Button(
            keybinding_buttons_frame,
            text="查看示例",
            command=self._show_keybinding_help,
            style="Secondary.TButton"
        )
        help_button.grid(row=0, column=0, sticky='w')

        save_button = ttk.Button(
            keybinding_buttons_frame,
            text="保存快捷键",
            command=self._save_keybindings,
            style="Action.TButton"
        )
        save_button.grid(row=0, column=1, sticky='e')

        # --- Cache Management Panel ---
        self.cache_panel = CollapsiblePanel(
            self.software_content_frame,
            "缓存管理",
            subtitle="清除应用程序生成的临时文件",
            icon="🗑️"
        )
        self.cache_panel.pack(fill="x", expand=False, pady=(0, 1))

        cache_action_frame = ttk.Frame(self.cache_panel.content_padding)
        cache_action_frame.pack(fill="x", pady=5)
        cache_action_frame.columnconfigure(0, weight=1)

        cache_info_label = ttk.Label(cache_action_frame, textvariable=self.cache_size_var)
        cache_info_label.grid(row=0, column=0, sticky='w', pady=(0, 10))

        buttons_container = ttk.Frame(cache_action_frame)
        buttons_container.grid(row=1, column=0, sticky='e')

        refresh_button = ttk.Button(
            buttons_container,
            text="刷新大小",
            command=self.update_cache_size,
            style="Secondary.TButton"
        )
        refresh_button.pack(side='left', padx=(0, 5))

        clear_cache_button = ttk.Button(
            buttons_container,
            text="清除图片缓存",
            command=self._clear_image_cache_with_refresh,
            style="Action.TButton"
        )
        clear_cache_button.pack(side='left')

        # --- 更新面板 ---
        self.update_panel = CollapsiblePanel(
            self.software_content_frame,
            "软件更新",
            subtitle="检查、更新和管理软件版本",
            icon="🔄"
        )
        self.update_panel.pack(fill="x", expand=False, pady=(0, 1))

        # --- 更新面板内容 ---
        channel_frame = ttk.Frame(self.update_panel.content_padding)
        channel_frame.pack(fill="x", pady=5)
        ttk.Label(channel_frame, text="选择更新通道").pack(side="top", anchor="w", pady=(0, 5))

        self.controller.update_channel_var = tk.StringVar(value="稳定版 (Release)")
        channel_combo = ttk.Combobox(
            channel_frame,
            textvariable=self.controller.update_channel_var,
            values=["稳定版 (Release)", "预览版 (Preview)"],
            state="readonly"
        )
        channel_combo.pack(fill="x", expand=True)

        update_action_frame = ttk.Frame(self.update_panel.content_padding)
        update_action_frame.pack(fill="x", pady=(10, 5), expand=True)

        self.update_status_label = ttk.Label(update_action_frame, text=f"当前版本: {APP_VERSION}")
        self.update_status_label.pack(side="left", anchor='w')

        self.check_update_button = ttk.Button(
            update_action_frame,
            text="检查更新",
            command=self.controller.check_for_updates_from_ui,
            style="Action.TButton"
        )
        self.check_update_button.pack(side="right")

        self._configure_software_scrolling()
        self.master.after(100, lambda: self.software_canvas.yview_moveto(0.0))

    def _show_keybinding_help(self):
        help_text = """
快捷键格式示例

您可以使用以下格式来定义快捷键。

- **普通按键:** - 字母: a, b, c (大小写均可)
  - 数字: 1, 2, 3

- **特殊按键 (需用尖括号):**
  - 功能键: <F1>, <F2>, ... <F12>
  - 方向键: <Up>, <Down>, <Left>, <Right>
  - 其他: <Space>, <Return> (回车), <Escape>, <Tab>
  - 数字键盘: <KP_0>, <KP_1>, ... <KP_Add>, <KP_Enter>

- **修饰键组合 (用连字符连接):**
  - Ctrl: <Control-a>, <Control-Up>
  - Alt: <Alt-a>, <Alt-Left>
  - Shift: <Shift-a> (或直接用大写 A)

- **鼠标按键:**
  - 左键: <Button-1> 或 <1>
  - 中键: <Button-2> 或 <2>
  - 右键: <Button-3> 或 <3>
  - 滚轮: <MouseWheel>

**注意:** 单个字母的快捷键会自动识别大小写。
"""
        messagebox.showinfo("快捷键设置示例", help_text, parent=self.master)

    def _save_keybindings(self):
        """Saves the keybinding settings and re-binds them in the preview page."""
        self.controller._save_current_settings()
        self.controller.preview_page.rebind_keys()
        messagebox.showinfo("成功", "快捷键设置已保存并生效。", parent=self.master)

    def update_cache_size(self):
        """Calculates and updates the cache size display in a separate thread."""
        self.cache_size_var.set("缓存大小: 正在计算...")
        self.master.update_idletasks()

        def get_dir_size(path):
            total_size = 0
            try:
                for dirpath, dirnames, filenames in os.walk(path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        if not os.path.islink(fp):
                            total_size += os.path.getsize(fp)
            except FileNotFoundError:
                return 0  # Path doesn't exist
            return total_size

        def size_thread():
            cache_dir = os.path.join(self.controller.settings_manager.base_dir, "temp", "photo")
            size_in_bytes = get_dir_size(cache_dir)

            if size_in_bytes < 1024:
                size_str = f"{size_in_bytes} Bytes"
            elif size_in_bytes < 1024 ** 2:
                size_str = f"{size_in_bytes / 1024:.2f} KB"
            elif size_in_bytes < 1024 ** 3:
                size_str = f"{size_in_bytes / 1024 ** 2:.2f} MB"
            else:
                size_str = f"{size_in_bytes / 1024 ** 3:.2f} GB"

            if self.winfo_exists():
                self.cache_size_var.set(f"缓存大小: {size_str}")

        # Start the calculation after a short delay to ensure "Calculating..." is visible
        self.master.after(500, lambda: threading.Thread(target=size_thread, daemon=True).start())

    def _clear_image_cache_with_refresh(self):
        self.controller.clear_image_cache()
        self.master.after(500, self.update_cache_size)

    def _configure_software_scrolling(self):
        """配置软件设置页面的滚动"""

        def _update_scrollregion(event=None):
            self.software_canvas.configure(scrollregion=self.software_canvas.bbox("all"))

        def _configure_canvas(event):
            canvas_width = event.width
            if self.software_canvas.winfo_exists() and self.software_canvas_window:
                self.software_canvas.itemconfigure(self.software_canvas_window, width=canvas_width)

        def _on_mousewheel(event):
            if platform.system() == "Windows":
                self.software_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                self.software_canvas.yview_scroll(int(event.delta), "units")

        self.software_canvas.bind("<MouseWheel>", _on_mousewheel)
        self.software_content_frame.bind("<Configure>", _update_scrollregion)
        self.software_canvas.bind("<Configure>", _configure_canvas)

    def _on_tab_changed(self, event):
        current_tab_index = self.advanced_notebook.index(self.advanced_notebook.select())
        if current_tab_index == 1:  # Env Maintenance
            if hasattr(self, 'env_canvas'):
                self.master.after(10, lambda: self.env_canvas.configure(scrollregion=self.env_canvas.bbox("all")))
        elif current_tab_index == 2:  # Software Settings
            if hasattr(self, 'software_canvas'):
                self.master.after(10,
                                  lambda: self.software_canvas.configure(scrollregion=self.software_canvas.bbox("all")))
                self.update_cache_size()

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
        # self.controller.status_bar.show_message("已重置所有参数到默认值", 3000)

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

    def _install_pytorch(self) -> None:
        """安装PyTorch"""
        version = self.pytorch_version_var.get()
        if not version:
            messagebox.showerror("错误", "请选择PyTorch版本")
            return

        message = f"将安装 PyTorch {version}"
        if self.force_reinstall_var.get():
            message += "，将先卸载现有安装"

        if not messagebox.askyesno("确认安装", message + "\n\n是否继续？"):
            return

        is_cuda = "CPU" not in version
        cuda_version = None
        if is_cuda:
            cuda_match = re.search(r"CUDA (\d+\.\d+)", version)
            if cuda_match:
                cuda_version = cuda_match.group(1)

        pytorch_match = re.search(r"(\d+\.\d+\.\d+)", version)
        if pytorch_match:
            pytorch_version = pytorch_match.group(1)
        else:
            messagebox.showerror("错误", "无法解析PyTorch版本")
            return

        self.install_button.configure(state="disabled")
        self.pytorch_status_var.set("准备安装...")
        self.master.update_idletasks()

        def install_thread():
            try:
                self._run_pytorch_install(pytorch_version, cuda_version)
            except Exception as e:
                self.master.after(0, lambda: self.pytorch_status_var.set(f"安装失败: {str(e)}"))
                self.master.after(0, lambda: self.install_button.configure(state="normal"))

        threading.Thread(target=install_thread, daemon=True).start()

    def _run_pytorch_install(self, pytorch_version, cuda_version=None):
        """使用弹出命令行窗口安装PyTorch"""
        try:
            self.master.after(0, lambda: self.pytorch_status_var.set("正在启动安装..."))

            if cuda_version:
                cuda_str_map = {"11.8": "cu118", "12.1": "cu121", "12.6": "cu126", "12.8": "cu128"}
                cuda_str = cuda_str_map.get(cuda_version, f"cu{cuda_version.replace('.', '')}")
                install_cmd = f"pip install torch=={pytorch_version} torchvision torchaudio --index-url https://download.pytorch.org/whl/{cuda_str}"
            else:
                install_cmd = f"pip install torch=={pytorch_version} torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu"

            if self.force_reinstall_var.get():
                command = (
                    f"echo 正在卸载现有PyTorch... && "
                    f"pip uninstall -y torch torchvision torchaudio && "
                    f"echo 卸载完成，开始安装新版本... && "
                    f"{install_cmd} && "
                    f"echo. && echo 安装完成！窗口将在5秒后自动关闭... && "
                    f"timeout /t 5"
                )
            else:
                command = (
                    f"echo 正在安装PyTorch {pytorch_version}... && "
                    f"{install_cmd} && "
                    f"echo. && echo 安装完成！窗口将在5秒后自动关闭... && "
                    f"timeout /t 5"
                )

            self.master.after(0, lambda: self.pytorch_status_var.set("安装已启动，请查看命令行窗口"))

            if platform.system() == "Windows":
                subprocess.Popen(f"start cmd /C \"{command}\"", shell=True)
            else:
                if platform.system() == "Darwin":
                    mac_command = command.replace("timeout /t 5", "sleep 5")
                    subprocess.Popen(["osascript", "-e", f'tell app "Terminal" to do script "{mac_command}"'])
                else:
                    linux_command = command.replace("timeout /t 5", "sleep 5")
                    for terminal in ["gnome-terminal", "konsole", "xterm"]:
                        try:
                            if terminal == "gnome-terminal":
                                subprocess.Popen([terminal, "--", "bash", "-c", f"{linux_command}"])
                            elif terminal == "konsole":
                                subprocess.Popen([terminal, "-e", f"bash -c '{linux_command}'"])
                            elif terminal == "xterm":
                                subprocess.Popen([terminal, "-e", f"bash -c '{linux_command}'"])
                            break
                        except FileNotFoundError:
                            continue

            self.master.after(2000, lambda: self.install_button.configure(state="normal"))
            self.master.after(2000, lambda: messagebox.showinfo("安装已启动",
                                                                "PyTorch安装已在命令行窗口中启动，\n"
                                                                "请查看命令行窗口了解安装进度，\n"
                                                                "安装完成后，重启程序以使更改生效。\n"
                                                                "命令执行完成后窗口将在5秒后自动关闭。"))

            version_text = f"{pytorch_version} {'(CUDA ' + cuda_version + ')' if cuda_version else '(CPU)'}"
            self.master.after(3000, lambda: self.pytorch_status_var.set(f"已完成安装 PyTorch {version_text}"))

        except Exception as e:
            logger.error(f"安装PyTorch出错: {e}")
            self.master.after(0, lambda: self.pytorch_status_var.set(f"安装失败: {str(e)}"))
            self.master.after(0, lambda: self.install_button.configure(state="normal"))
            self.master.after(0, lambda: messagebox.showerror("安装错误", f"安装PyTorch失败：\n{str(e)}"))

    def _install_python_package(self) -> None:
        """安装Python包"""
        package = self.package_var.get().strip()
        if not package:
            messagebox.showerror("错误", "请输入包名称")
            return

        version_constraint = self.version_constraint_var.get().strip()
        package_spec = f"{package}{version_constraint}" if version_constraint else package

        if not messagebox.askyesno("确认安装", f"将安装 {package_spec}\n\n是否继续？"):
            return

        self.package_status_var.set("准备安装...")
        self.master.update_idletasks()

        def install_thread():
            try:
                self._run_pip_install(package_spec)
            except Exception as e:
                logger.error(f"安装Python包出错: {e}")
                self.master.after(0, lambda: self.package_status_var.set(f"安装失败: {str(e)}"))

        threading.Thread(target=install_thread, daemon=True).start()

    def _run_pip_install(self, package_spec):
        """使用弹出命令行窗口安装Python包"""
        try:
            self.master.after(0, lambda: self.package_status_var.set("正在启动安装..."))

            install_cmd = f"pip install {package_spec}"
            command = (
                f"echo 正在安装 {package_spec}... && "
                f"{install_cmd} && "
                f"echo. && echo 安装完成！窗口将在5秒后自动关闭... && "
                f"timeout /t 5"
            )

            self.master.after(0, lambda: self.package_status_var.set("安装已启动，请查看命令行窗口"))

            if platform.system() == "Windows":
                subprocess.Popen(f"start cmd /C \"{command}\"", shell=True)
            else:
                if platform.system() == "Darwin":
                    mac_command = command.replace("timeout /t 5", "sleep 5")
                    subprocess.Popen(["osascript", "-e", f'tell app "Terminal" to do script "{mac_command}"'])
                else:
                    linux_command = command.replace("timeout /t 5", "sleep 5")
                    for terminal in ["gnome-terminal", "konsole", "xterm"]:
                        try:
                            subprocess.Popen([terminal, "-e", f"bash -c '{linux_command}; read -n1'"])
                            break
                        except FileNotFoundError:
                            continue

            self.master.after(3000, lambda: self.package_status_var.set(f"已完成安装 {package_spec}"))

        except Exception as e:
            logger.error(f"安装Python包出错: {e}")
            self.master.after(0, lambda: self.package_status_var.set(f"安装失败: {str(e)}"))
            self.master.after(0, lambda: messagebox.showerror("安装错误", f"安装Python包失败：\n{str(e)}"))

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
            messagebox.showinfo("提示", "请先选择一个模型", parent=self.master)
            return
        model_path = resource_path(os.path.join("res", model_name))
        if not os.path.exists(model_path):
            messagebox.showerror("错误", f"模型文件不存在: {model_path}", parent=self.master)
            return
        current_model = os.path.basename(self.controller.image_processor.model_path) if hasattr(
            self.controller.image_processor, 'model_path') and self.controller.image_processor.model_path else None
        if model_name == current_model:
            messagebox.showinfo("提示", f"模型 {model_name} 已经加载", parent=self.master)
            return
        if not messagebox.askyesno("确认", f"确定要切换到模型 {model_name} 吗？", parent=self.master):
            return
        self.model_status_var.set("正在加载...")
        self.master.update_idletasks()
        threading.Thread(target=self._load_model_thread, args=(model_path, model_name), daemon=True).start()

    def _load_model_thread(self, model_path, model_name):
        try:
            self.controller.image_processor.load_model(model_path)
            self.master.after(0, lambda: self.current_model_var.set(model_name))
            self.master.after(0, lambda: self.model_status_var.set("已加载"))
            self.master.after(0,
                              lambda: messagebox.showinfo("成功", f"模型 {model_name} 已成功加载", parent=self.master))
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            self.master.after(0, lambda: self.model_status_var.set(f"加载失败: {str(e)}"))
            self.master.after(0, lambda: messagebox.showerror("错误", f"加载模型失败: {e}", parent=self.master))

    def _on_tab_changed(self, event):
        current_tab_index = self.advanced_notebook.index(self.advanced_notebook.select())
        if current_tab_index == 1:  # Env Maintenance
            if hasattr(self, 'env_canvas'):
                self.master.after(10, lambda: self.env_canvas.configure(scrollregion=self.env_canvas.bbox("all")))
        elif current_tab_index == 2:  # Software Settings
            if hasattr(self, 'software_canvas'):
                self.master.after(10,
                                  lambda: self.software_canvas.configure(scrollregion=self.software_canvas.bbox("all")))
                self.update_cache_size()