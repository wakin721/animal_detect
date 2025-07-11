import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
import json
import logging
import cv2
import threading
import re

from system.config import NORMAL_FONT, SUPPORTED_IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)


# In system/gui/preview_page.py

class PreviewPage(ttk.Frame):
    """图像预览和校验页面"""

    def __init__(self, parent, controller, **kwargs):
        super().__init__(parent, **kwargs)
        self.controller = controller
        self.validation_data = {}
        self.original_image = None
        self.validation_original_image = None
        self.current_image_path = None
        self.current_detection_results = None
        self.active_keybinds = []
        self._is_navigating = False  

        self._create_widgets()
        self.rebind_keys()

    def _create_widgets(self):
        self.preview_notebook = ttk.Notebook(self)
        self.preview_notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.image_preview_tab = ttk.Frame(self.preview_notebook)
        self.validation_tab = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(self.image_preview_tab, text="图像预览")
        self.preview_notebook.add(self.validation_tab, text="检查校验")
        self.preview_notebook.bind("<<NotebookTabChanged>>", self._on_preview_tab_changed)

        self._create_image_preview_content(self.image_preview_tab)
        self._create_validation_content(self.validation_tab)

    def clear_previews(self):
        """Clears content from all preview tabs to reset the state."""
        # Clear image preview tab
        self.file_listbox.delete(0, tk.END)
        self.image_label.config(image='', text="请从左侧列表选择图像")
        if hasattr(self.image_label, 'image'):
            self.image_label.image = None
        self.info_text.config(state="normal")
        self.info_text.delete(1.0, tk.END)
        self.info_text.config(state="disabled")
        self.current_image_path = None
        self.current_detection_results = None
        self.show_detection_var.set(False)

        # Clear validation check tab
        self.validation_listbox.delete(0, tk.END)
        self.validation_image_label.config(image='', text="请从左侧列表选择处理后的图像")
        if hasattr(self.validation_image_label, 'image'):
            self.validation_image_label.image = None
        self.validation_info_text.config(state="normal")
        self.validation_info_text.delete(1.0, tk.END)
        self.validation_info_text.config(state="disabled")
        self.validation_status_label.config(text="未校验")
        self.validation_progress_var.set("0/0")
        self.validation_data.clear()

    def _create_image_preview_content(self, parent):
        preview_content = ttk.Frame(parent)
        preview_content.pack(fill="both", expand=True)
        preview_content.columnconfigure(1, weight=1) # 让右侧列扩展
        preview_content.rowconfigure(0, weight=1) # 让第一行扩展

        list_frame = ttk.LabelFrame(preview_content, text="图像文件")
        list_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.file_listbox = tk.Listbox(list_frame, width=25, font=NORMAL_FONT,
                                       selectbackground=self.controller.sidebar_bg,
                                       selectforeground=self.controller.sidebar_fg)
        self.file_listbox.pack(side="left", fill="both", expand=True)
        file_list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        file_list_scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=file_list_scrollbar.set)

        preview_right = ttk.Frame(preview_content)
        preview_right.grid(row=0, column=1, sticky="nsew")
        preview_right.columnconfigure(0, weight=1)
        preview_right.rowconfigure(0, weight=1) # 图片行将扩展

        image_frame = ttk.LabelFrame(preview_right, text="图像预览")
        image_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(0, weight=1)

        self.image_label = ttk.Label(image_frame, text="请从左侧列表选择图像", anchor="center")
        self.image_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.image_label.bind('<Configure>', self._on_resize)


        info_frame = ttk.LabelFrame(preview_right, text="图像信息")
        info_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.info_text = tk.Text(info_frame, height=4, font=NORMAL_FONT, wrap="word")
        self.info_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.info_text.config(state="disabled")

        control_frame = ttk.Frame(preview_right)
        control_frame.grid(row=2, column=0, sticky="ew")
        self.show_detection_var = tk.BooleanVar(value=False)
        show_detection_switch = ttk.Checkbutton(
            control_frame,
            text="显示检测结果",
            variable=self.show_detection_var,
            command=self.toggle_detection_preview
        )
        show_detection_switch.pack(side="left")
        self.detect_button = ttk.Button(
            control_frame,
            text="检测当前图像",
            command=self.detect_current_image,
            width=12
        )
        self.detect_button.pack(side="right")

    def _create_validation_content(self, parent):
        validation_content = ttk.Frame(parent)
        validation_content.pack(fill="both", expand=True)
        validation_content.columnconfigure(1, weight=1)
        validation_content.rowconfigure(0, weight=1)

        list_frame = ttk.LabelFrame(validation_content, text="处理后图像")
        list_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.validation_listbox = tk.Listbox(list_frame, width=25, font=NORMAL_FONT,
                                             selectbackground=self.controller.sidebar_bg,
                                             selectforeground=self.controller.sidebar_fg)
        self.validation_listbox.pack(side="left", fill="both", expand=True)
        validation_list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.validation_listbox.yview)
        validation_list_scrollbar.pack(side="right", fill="y")
        self.validation_listbox.config(yscrollcommand=validation_list_scrollbar.set)

        preview_right = ttk.Frame(validation_content)
        preview_right.grid(row=0, column=1, sticky="nsew")
        preview_right.columnconfigure(0, weight=1)
        preview_right.rowconfigure(0, weight=1) # 图片行将扩展

        image_frame = ttk.LabelFrame(preview_right, text="图像校验")
        image_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(0, weight=1)

        self.validation_image_label = ttk.Label(image_frame, text="请从左侧列表选择处理后的图像", anchor="center")
        self.validation_image_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.validation_image_label.bind("<Double-1>", self.on_image_double_click)
        self.validation_image_label.bind('<Configure>', self._on_resize)

        info_frame = ttk.LabelFrame(preview_right, text="检测信息")
        info_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.validation_info_text = tk.Text(info_frame, height=3, font=NORMAL_FONT, wrap="word")
        self.validation_info_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.validation_info_text.config(state="disabled")

        validation_control_frame = ttk.Frame(preview_right)
        validation_control_frame.grid(row=2, column=0, sticky="ew", pady=5)
        self.validation_status_label = ttk.Label(validation_control_frame, text="未校验", font=NORMAL_FONT)
        self.validation_status_label.pack(side="left", padx=5)
        ttk.Label(validation_control_frame, text="进度:").pack(side="left", padx=(20, 5))
        self.validation_progress_var = tk.StringVar(value="0/0")
        ttk.Label(validation_control_frame, textvariable=self.validation_progress_var).pack(side="left")

        buttons_frame = ttk.Frame(preview_right)
        buttons_frame.grid(row=3, column=0, sticky="ew", pady=10)
        self.correct_button = ttk.Button(buttons_frame, text="正确 ✅", command=lambda: self._mark_validation(True),
                                         width=10)
        self.correct_button.pack(side="left", padx=(0, 5))
        self.incorrect_button = ttk.Button(buttons_frame, text="错误 ❌", command=lambda: self._mark_validation(False),
                                           width=10)
        self.incorrect_button.pack(side="left", padx=5)
        self.export_excel_button = ttk.Button(buttons_frame, text="导出为Excel", command=self._export_validation_excel,
                                              width=12, state="disabled")
        self.export_excel_button.pack(side="right", padx=(5, 0))
        self.export_error_button = ttk.Button(buttons_frame, text="导出错误图片", command=self._export_error_images,
                                              width=12)
        self.export_error_button.pack(side="right", padx=5)

        self.validation_listbox.bind("<<ListboxSelect>>", self._on_validation_file_selected)

    def rebind_keys(self):
        """Unbinds old keys and binds new, case-insensitive keys."""
        # 1. 解绑所有先前绑定的按键
        for key_sequence in self.active_keybinds:
            self.controller.master.unbind(key_sequence)
            self.validation_listbox.unbind(key_sequence) # 同时解绑列表框上的按键
        self.active_keybinds = []

        # 2. 获取新的按键定义
        key_map = {
            "up": (self.controller.advanced_page.key_up_var.get(), self._select_prev_image),
            "down": (self.controller.advanced_page.key_down_var.get(), self._select_next_image),
            "correct": (self.controller.advanced_page.key_correct_var.get(), lambda e: self._mark_validation(True)),
            "incorrect": (
            self.controller.advanced_page.key_incorrect_var.get(), lambda e: self._mark_validation(False)),
        }

        # 3. 根据按键功能，在不同层级上进行绑定
        for action, (key_def, command) in key_map.items():
            sequences_to_bind = []
            # (处理大小写和特殊按键的逻辑保持不变)
            match = re.fullmatch(r"<Key-([a-zA-Z0-9])>", key_def)
            if match:
                key_char = match.group(1)
                if key_char.isalpha():
                    sequences_to_bind.append(f"<Key-{key_char.lower()}>")
                    sequences_to_bind.append(f"<Key-{key_char.upper()}>")
                else:
                    sequences_to_bind.append(key_def)
            elif len(key_def) == 1 and key_def.isalpha():
                sequences_to_bind.append(f"<Key-{key_def.lower()}>")
                sequences_to_bind.append(f"<Key-{key_def.upper()}>")
            else:
                sequences_to_bind.append(key_def)

            for seq in sequences_to_bind:
                if seq not in self.active_keybinds:
                    # **核心修改：根据功能决定绑定目标**
                    if action in ["up", "down"]:
                        # 导航键绑定在列表框上
                        self.validation_listbox.bind(seq, command)
                    else:
                        # 功能键绑定在全局窗口上
                        self.controller.master.bind(seq, command)
                    self.active_keybinds.append(seq)

    def _select_prev_image(self, event=None):
        """Selects the previous image in the validation listbox."""
        if self._is_navigating:
            return "break"

        if not self.validation_listbox.curselection():
            return "break"

        current_index = self.validation_listbox.curselection()[0]
        if current_index > 0:
            self._is_navigating = True
            next_index = current_index - 1
            self.validation_listbox.selection_clear(0, tk.END)
            self.validation_listbox.selection_set(next_index)
            self.validation_listbox.see(next_index)
            self.validation_listbox.event_generate("<<ListboxSelect>>")
            self.master.after(100, lambda: setattr(self, '_is_navigating', False))

        return "break"  # <-- 确保此行存在

    def _select_next_image(self, event=None):
        """Selects the next image in the validation listbox."""
        if self._is_navigating:
            return "break"

        if not self.validation_listbox.curselection():
            return "break"

        current_index = self.validation_listbox.curselection()[0]
        if current_index < self.validation_listbox.size() - 1:
            self._is_navigating = True
            next_index = current_index + 1
            self.validation_listbox.selection_clear(0, tk.END)
            self.validation_listbox.selection_set(next_index)
            self.validation_listbox.see(next_index)
            self.validation_listbox.event_generate("<<ListboxSelect>>")
            self.master.after(100, lambda: setattr(self, '_is_navigating', False))

        return "break"  # <-- 确保此行存在

    def _on_preview_tab_changed(self, event):
        selected_tab = self.preview_notebook.select()
        tab_text = self.preview_notebook.tab(selected_tab, "text")
        if tab_text == "检查校验":
            self._load_processed_images()
            self.validation_listbox.focus_set()  # <-- 将焦点直接设置在列表框上
            self.rebind_keys()

    def update_file_list(self, directory: str):
        # The clearing is now done in clear_previews, called from main_window
        if not os.path.isdir(directory):
            return

        try:
            image_files = [f for f in os.listdir(directory) if f.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS)]
            image_files.sort()
            for file in image_files:
                self.file_listbox.insert(tk.END, file)
        except Exception as e:
            logger.error(f"更新文件列表失败: {e}")

    def on_file_selected(self, event):
        selection = self.file_listbox.curselection()
        if not selection:
            return

        self.controller.master.update_idletasks()

        file_name = self.file_listbox.get(selection[0])
        file_path = os.path.join(self.controller.start_page.file_path_entry.get(), file_name)
        self.current_image_path = file_path
        self.current_detection_results = None

        self.update_image_info(file_path, file_name)

        photo_path = self.controller.get_temp_photo_dir()
        if not photo_path: return

        temp_result_path = os.path.join(photo_path, file_name)
        base_name, _ = os.path.splitext(file_name)
        json_path = os.path.join(photo_path, f"{base_name}.json")

        if os.path.exists(temp_result_path) and os.path.exists(json_path):
            self.show_detection_var.set(True)
            self.update_image_preview(temp_result_path, is_temp_result=True)
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    detection_info = json.load(f)
                self._update_detection_info(detection_info)
            except Exception as e:
                logger.error(f"读取检测JSON失败: {e}")
        else:
            self.show_detection_var.set(False)
            self.update_image_preview(file_path)

    def update_image_preview(self, file_path: str, show_detection: bool = False, detection_results=None,
                             is_temp_result: bool = False):
        if hasattr(self.image_label, 'image'):
            self.image_label.image = None

        try:
            if is_temp_result:
                img = Image.open(file_path)
            elif show_detection and detection_results:
                result_img = detection_results[0].plot()
                img = Image.fromarray(cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB))
            else:
                img = Image.open(file_path)
            self.original_image = img
            resized_img = self._resize_image_to_fit(img, self.image_label.winfo_width(),
                                                    self.image_label.winfo_height())
            photo = ImageTk.PhotoImage(resized_img)
            self.image_label.config(image=photo)
            self.image_label.image = photo
        except Exception as e:
            logger.error(f"更新图像预览失败: {e}")
            self.image_label.config(image='', text="无法加载图像")
            self.original_image = None

    def update_image_info(self, file_path: str, file_name: str):
        from system.metadata_extractor import ImageMetadataExtractor
        image_info, _ = ImageMetadataExtractor.extract_metadata(file_path, file_name)
        self.info_text.config(state="normal")
        self.info_text.delete(1.0, tk.END)
        info1 = f"文件名: {image_info.get('文件名', '')}    格式: {image_info.get('格式', '')}"
        info2 = f"拍摄日期: {image_info.get('拍摄日期', '未知')} {image_info.get('拍摄时间', '')}    "
        try:
            with Image.open(file_path) as img:
                info2 += f"尺寸: {img.width}x{img.height}px    文件大小: {os.path.getsize(file_path) / 1024:.1f} KB"
        except:
            pass
        self.info_text.insert(tk.END, info1 + "\n" + info2)
        # Keep the text box disabled for user interaction, but allow code to modify it.
        # self.info_text.config(state="disabled")

    def toggle_detection_preview(self, *args):
        if self.controller.is_processing:
            self.show_detection_var.set(True)
            return
        selection = self.file_listbox.curselection()
        if not selection:
            self.show_detection_var.set(False)
            return

        file_name = self.file_listbox.get(selection[0])
        file_path = os.path.join(self.controller.start_page.file_path_entry.get(), file_name)

        if self.show_detection_var.get():
            photo_path = self.controller.get_temp_photo_dir()
            if not photo_path: return
            temp_result_path = os.path.join(photo_path, file_name)
            if os.path.exists(temp_result_path):
                self.update_image_preview(temp_result_path, is_temp_result=True)
            elif self.current_detection_results:
                self.update_image_preview(file_path, True, self.current_detection_results)
            else:
                messagebox.showinfo("提示", '当前图像尚未检测，请点击"检测当前图像"按钮。')
                self.show_detection_var.set(False)
        else:
            self.update_image_preview(file_path)

    def detect_current_image(self):
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一张图像。")
            return
        file_name = self.file_listbox.get(selection[0])
        file_path = os.path.join(self.controller.start_page.file_path_entry.get(), file_name)
        # self.controller.status_bar.status_label.config(text="正在检测图像...")
        self.detect_button.config(state="disabled")
        threading.Thread(target=self._detect_image_thread, args=(file_path, file_name), daemon=True).start()

    def _detect_image_thread(self, img_path, filename):
        try:
            from datetime import datetime
            results = self.controller.image_processor.detect_species(img_path,
                                                                     self.controller.advanced_page.controller.use_fp16_var.get(),
                                                                     self.controller.advanced_page.controller.iou_var.get(),
                                                                     self.controller.advanced_page.controller.conf_var.get(),
                                                                     self.controller.advanced_page.controller.use_augment_var.get(),
                                                                     self.controller.advanced_page.controller.use_agnostic_nms_var.get())
            self.current_detection_results = results['detect_results']
            species_info = {k: v for k, v in results.items() if k != 'detect_results'}
            species_info['检测时间'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if self.current_detection_results:
                temp_photo_dir = self.controller.get_temp_photo_dir()
                self.controller.image_processor.save_detection_temp(self.current_detection_results, filename,
                                                                    temp_photo_dir)
                self.controller.image_processor.save_detection_info_json(self.current_detection_results, filename,
                                                                         species_info, temp_photo_dir)

            self.master.after(0, lambda: self.show_detection_var.set(True))
            self.master.after(0, lambda: self.update_image_preview(img_path, True, self.current_detection_results))
            self.master.after(0, lambda: self._update_detection_info(species_info))
        except Exception as err:
            logger.error(f"检测图像失败: {err}")
            self.master.after(0, lambda msg=str(err): messagebox.showerror("错误", f"检测图像失败: {msg}"))
        finally:
            self.master.after(0, lambda: self.detect_button.config(state="normal"))
            # self.master.after(0, lambda: self.controller.status_bar.status_label.config(text="检测完成"))

    def _update_detection_info(self, species_info):
        self.info_text.config(state="normal")
        current_text_lines = self.info_text.get(1.0, tk.END).strip().split('\n')
        basic_info = "\n".join(current_text_lines[:2])

        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, basic_info)

        detection_parts = ["检测结果:"]
        if species_info and species_info.get('物种名称'):
            names = species_info['物种名称'].split(',')
            counts = species_info.get('物种数量', '').split(',')
            info_parts = [f"{n}: {c}只" for n, c in zip(names, counts)]
            detection_parts.append(", ".join(info_parts))
            if species_info.get('最低置信度'):
                detection_parts.append(f"最低置信度: {species_info['最低置信度']}")
            if species_info.get('检测时间'):
                detection_parts.append(f"检测于: {species_info['检测时间']}")
        else:
            detection_parts.append("未检测到已知物种")

        self.info_text.insert(tk.END, "\n" + " | ".join(detection_parts))
        self.info_text.config(state="disabled")

    def _resize_image_to_fit(self, img, max_width, max_height):
        if not all([max_width > 0, max_height > 0]):
            max_width, max_height = 400, 300
        w, h = img.size
        if w == 0 or h == 0: return img
        scale = min(max_width / w, max_height / h)
        if scale >= 1: return img
        new_width = max(1, int(w * scale))
        new_height = max(1, int(h * scale))
        return img.resize((new_width, new_height), Image.LANCZOS)

    def on_image_double_click(self, event):
        pass

    def _load_processed_images(self):
        photo_dir = self.controller.get_temp_photo_dir()
        if not photo_dir or not os.path.exists(photo_dir):
            return
        self.validation_listbox.delete(0, tk.END)
        processed_images = sorted([f for f in os.listdir(photo_dir) if f.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS)])
        for file in processed_images:
            self.validation_listbox.insert(tk.END, file)
        self._update_validation_progress()
        if processed_images:
            unvalidated_index = next((i for i, f in enumerate(processed_images) if f not in self.validation_data), -1)
            if unvalidated_index != -1:
                self.validation_listbox.selection_set(unvalidated_index)
                self.validation_listbox.see(unvalidated_index)
            else:
                self.validation_listbox.selection_set(0)
            self._on_validation_file_selected(None)

    def _on_validation_file_selected(self, event):
        selection = self.validation_listbox.curselection()
        if not selection:
            return
        file_name = self.validation_listbox.get(selection[0])
        photo_dir = self.controller.get_temp_photo_dir()
        if not photo_dir: return
        file_path = os.path.join(photo_dir, file_name)
        try:
            img = Image.open(file_path)
            self.validation_original_image = img  # 保存原始图像
            resized_img = self._resize_image_to_fit(img, self.validation_image_label.winfo_width(),
                                                    self.validation_image_label.winfo_height())
            photo = ImageTk.PhotoImage(resized_img)
            self.validation_image_label.config(image=photo)
            self.validation_image_label.image = photo
        except Exception as e:
            logger.error(f"加载校验图像失败: {e}")
            self.validation_original_image = None  # 加载失败时清除

        json_path = os.path.join(photo_dir, f"{os.path.splitext(file_name)[0]}.json")
        self.validation_info_text.config(state="normal")
        self.validation_info_text.delete(1.0, tk.END)
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                info_text = f"物种: {info.get('物种名称', 'N/A')}\n数量: {info.get('物种数量', 'N/A')}\n置信度: {info.get('最低置信度', 'N/A')}"
                self.validation_info_text.insert(tk.END, info_text)
            except:
                pass
        self.validation_info_text.config(state="disabled")
        status = self.validation_data.get(file_name)
        self.validation_status_label.config(
            text=f"已标记: {'正确 ✅' if status is True else '错误 ❌' if status is False else '未校验'}")
        
    def _mark_validation(self, is_correct):
        selection = self.validation_listbox.curselection()
        if not selection:
            return
        file_name = self.validation_listbox.get(selection[0])
        self.validation_data[file_name] = is_correct
        self.validation_status_label.config(text=f"已标记: {'正确 ✅' if is_correct else '错误 ❌'}")
        self._save_validation_data()
        self._update_validation_progress()

        # 自动跳转到下一张图片
        self._select_next_image()

        # 在所有操作完成后，将焦点交还给列表框
        self.validation_listbox.focus_set()

    def _update_validation_progress(self):
        total = self.validation_listbox.size()
        validated = len(self.validation_data)
        self.validation_progress_var.set(f"{validated}/{total}")

    def _save_validation_data(self):
        temp_dir = self.controller.get_temp_photo_dir()
        if not temp_dir: return
        with open(os.path.join(temp_dir, "validation.json"), 'w', encoding='utf-8') as f:
            json.dump(self.validation_data, f, indent=2)

    def _load_validation_data(self):
        temp_dir = self.controller.get_temp_photo_dir()
        if not temp_dir: return
        path = os.path.join(temp_dir, "validation.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.validation_data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load validation data: {e}")
                self.validation_data = {}
        else:
            self.validation_data = {}

    def _export_error_images(self):
        error_files = [f for f, v in self.validation_data.items() if v is False]
        if not error_files:
            messagebox.showinfo("提示", "没有标记为错误的图片")
            return
        source_dir = self.controller.start_page.file_path_entry.get()
        save_dir = self.controller.start_page.save_path_entry.get()
        if not all([source_dir, save_dir]):
            messagebox.showerror("错误", "请设置源路径和保存路径")
            return
        error_folder = os.path.join(save_dir, "error")
        os.makedirs(error_folder, exist_ok=True)
        from shutil import copy
        for file in error_files:
            try:
                copy(os.path.join(source_dir, file), error_folder)
            except Exception as e:
                logger.error(f"复制错误图片失败: {e}")
        messagebox.showinfo("成功", f"成功导出 {len(error_files)} 张错误图片到 {error_folder}")

    def _export_validation_excel(self):
        messagebox.showinfo("提示", "此功能尚未实现。")

    def _on_resize(self, event):
        # 确定是哪个标签触发了事件
        if event.widget == self.image_label:
            image_to_resize = self.original_image
            label_widget = self.image_label
        elif event.widget == self.validation_image_label:
            image_to_resize = self.validation_original_image
            label_widget = self.validation_image_label
        else:
            return

        # 如果有原始图片，则根据新大小重新缩放
        if image_to_resize:
            # 获取标签的新尺寸
            width, height = event.width, event.height
            if width < 2 or height < 2: return  # 避免尺寸过小时出错

            # 重新缩放并更新图片
            resized_img = self._resize_image_to_fit(image_to_resize, width, height)
            photo = ImageTk.PhotoImage(resized_img)
            label_widget.config(image=photo)
            label_widget.image = photo