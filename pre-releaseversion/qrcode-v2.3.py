import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image, ImageTk, ImageOps, ImageEnhance, ImageChops, ExifTags
import requests
from io import BytesIO
from pyzbar import pyzbar
import numpy as np
import os
import re
import webbrowser
import threading
import math
import binascii
import struct
import datetime
from PIL.PngImagePlugin import PngInfo
import zlib
import concurrent.futures
import json
import natsort  # 用于自然排序
import sys

# 处理资源路径问题
def resource_path(relative_path):
    """获取资源的绝对路径（用于打包）"""
    try:
        base_path = sys._MEIPASS  # PyInstaller临时文件夹
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 设置环境变量（解决某些库的兼容性问题）
os.environ['TK_SILENCE_DEPRECATION'] = '1'
os.environ['PYZBAR_IGNORE_OPTS'] = '1'

class QRScannerApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("高级二维码扫描与分析工具")
        self.geometry("1000x800")
        self.configure(bg="#f0f0f0")
        
        # 加载配置
        self.config = self.load_config()
        
        # 初始化模块数据
        self.scan_module = ScanModule(self, self.config)
        self.analysis_module = AnalysisModule(self)
        self.settings_module = SettingsModule(self, self.config)
        self.binary_tools_module = BinaryToolsModule(self)  # 新增二进制工具模块
        
        # 创建主框架
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 创建选项卡控件
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建扫描选项卡
        scan_tab = ttk.Frame(self.notebook)
        self.notebook.add(scan_tab, text="二维码扫描")
        
        # 创建分析选项卡
        analysis_tab = ttk.Frame(self.notebook)
        self.notebook.add(analysis_tab, text="高级分析")
        
        # 新增二进制工具选项卡
        binary_tab = ttk.Frame(self.notebook)
        self.notebook.add(binary_tab, text="二进制工具")
        
        # 设置选项卡
        settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(settings_tab, text="设置")
        
        # 初始化各模块UI
        self.scan_module.init_ui(scan_tab)
        self.analysis_module.init_ui(analysis_tab)
        self.binary_tools_module.init_ui(binary_tab)  # 初始化二进制工具UI
        self.settings_module.init_ui(settings_tab)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 配置样式
        self.style = ttk.Style()
        self.style.configure("Accent.TButton", foreground="white", background="#4CAF50")
        self.style.configure("Stop.TButton", foreground="white", background="#F44336")
        self.style.configure("TButton", padding=6)
        
        # 设置拖放功能
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.handle_drop)
        
        # 绑定关闭事件以保存配置
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_close(self):
        """窗口关闭时保存配置"""
        self.save_config()
        self.destroy()
    
    def load_config(self):
        """加载配置文件"""
        config_path = "config.json"
        default_config = {
            "batch_scan": {
                "sort_order": "none",  # none, numeric, alphabetical
                "show_detailed": True,
                "separator": "\n" + "-" * 50 + "\n"
            },
            "analysis": {
                "auto_wrap": True,
                "steg_max_output": 1024,
                "selected_channels": ["R", "G", "B"],
                "selected_bit_positions": ["LSB"],
                "max_channel_combinations": 10,
                "output_format": "auto"
            },
            "binary_tools": {
                "width": 100,
                "height": 100,
                "mode": "L",
                "reverse_bytes": False,
                "stego_detection": {
                    "enable": True,
                    "file_tail_size": 4096,
                    "text_threshold": 0.7,
                    "entropy_threshold": 4.0
                }
            }
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    # 合并默认配置，确保所有设置项都存在
                    for section in default_config:
                        if section not in config:
                            config[section] = default_config[section]
                        else:
                            for key in default_config[section]:
                                if key not in config[section]:
                                    config[section][key] = default_config[section][key]
                    return config
        except Exception as e:
            print(f"加载配置失败: {str(e)}")
        
        return default_config
    
    def save_config(self):
        """保存配置文件"""
        config_path = "config.json"
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"保存配置失败: {str(e)}")
    
    def handle_drop(self, event):
        """处理文件拖放事件，根据当前选项卡决定放入哪个模块"""
        files = event.data.split()
        
        # 根据当前选项卡决定放入哪个模块
        current_tab = self.notebook.index(self.notebook.select())
        
        if current_tab == 0:  # 扫描选项卡
            valid_files = [f for f in files if f.lower().endswith(
                ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'))]
            if valid_files:
                self.scan_module.handle_drop(valid_files)
        
        elif current_tab == 1:  # 分析选项卡
            valid_files = [f for f in files if f.lower().endswith(
                ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif', '.dat', '.bin'))]
            if valid_files:
                self.analysis_module.handle_drop(valid_files)
        
        elif current_tab == 2:  # 二进制工具选项卡
            valid_files = [f for f in files if f.lower().endswith(('.dat', '.bin', '.hex', '.txt'))]
            if valid_files:
                self.binary_tools_module.handle_drop(valid_files)
    
    def update_status(self, message):
        """更新状态栏"""
        self.status_var.set(message)


class ScanModule:
    """二维码扫描模块，封装扫描相关功能"""
    def __init__(self, parent, config):
        self.parent = parent
        self.config = config
        self.scanning = False
        self.stop_requested = False
        self.current_preview_image = None
        self.current_image_path = None
        self.current_image_url = None
        self.enhance_level = 1.0
        self.attempted_enhancements = 0
    
    def init_ui(self, parent_frame):
        """初始化扫描选项卡UI"""
        # 主容器 - 使用grid布局
        scan_container = ttk.Frame(parent_frame)
        scan_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧控制面板
        control_frame = ttk.LabelFrame(scan_container, text="扫描选项")
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=10)
        
        # 模式选择
        mode_frame = ttk.Frame(control_frame)
        mode_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        ttk.Label(mode_frame, text="扫描模式:").pack(side=tk.LEFT)
        
        self.mode_var = tk.StringVar(value="local")
        modes = [("本地图片", "local"), ("网络图片", "web"), ("批量扫描", "batch"), ("文件夹扫描", "folder")]
        
        mode_buttons_frame = ttk.Frame(mode_frame)
        mode_buttons_frame.pack(side=tk.LEFT, padx=10)
        
        for i, (text, value) in enumerate(modes):
            ttk.Radiobutton(mode_buttons_frame, text=text, variable=self.mode_var, 
                            value=value, command=self.update_ui).grid(
                                row=i//2, column=i%2, sticky="w", padx=2, pady=2)
        
        # 文件选择区域
        file_frame = ttk.Frame(control_frame)
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(file_frame, text="文件路径:").pack(side=tk.TOP, anchor="w")
        
        file_entry_frame = ttk.Frame(file_frame)
        file_entry_frame.pack(fill=tk.X, pady=5)
        
        self.file_entry = ttk.Entry(file_entry_frame)
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        button_frame = ttk.Frame(file_entry_frame)
        button_frame.pack(side=tk.RIGHT)
        
        self.browse_button = ttk.Button(button_frame, text="浏览...", width=8, command=self.browse_files)
        self.browse_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.folder_button = ttk.Button(button_frame, text="选择文件夹", width=10, command=self.browse_folder)
        self.folder_button.pack(side=tk.LEFT)
        
        # URL输入区域
        url_frame = ttk.Frame(control_frame)
        url_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(url_frame, text="图片URL:").pack(side=tk.TOP, anchor="w")
        self.url_entry = ttk.Entry(url_frame)
        self.url_entry.pack(fill=tk.X, pady=5)
        
        # 批量扫描选项框架
        batch_options_frame = ttk.LabelFrame(control_frame, text="批量扫描选项")
        batch_options_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 排序方式
        sort_frame = ttk.Frame(batch_options_frame)
        sort_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(sort_frame, text="排序方式:").pack(side=tk.LEFT)
        
        self.sort_var = tk.StringVar(value=self.config["batch_scan"]["sort_order"])
        sort_options = [("不排序", "none"), ("数字顺序", "numeric"), ("字母顺序", "alphabetical")]
        
        sort_buttons_frame = ttk.Frame(sort_frame)
        sort_buttons_frame.pack(side=tk.LEFT, padx=10)
        
        for i, (text, value) in enumerate(sort_options):
            ttk.Radiobutton(sort_buttons_frame, text=text, variable=self.sort_var, 
                            value=value).grid(row=0, column=i, padx=5)
        
        # 详细输出复选框
        self.detailed_output_var = tk.BooleanVar(value=self.config["batch_scan"]["show_detailed"])
        detailed_check = ttk.Checkbutton(batch_options_frame, text="详细输出结果", 
                                        variable=self.detailed_output_var)
        detailed_check.pack(anchor="w", padx=5, pady=(0, 5))
        
        # 异形二维码增强设置
        complex_qr_frame = ttk.Frame(control_frame)
        complex_qr_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.enhance_label = ttk.Label(complex_qr_frame, text="异形二维码增强:")
        self.enhance_label.pack(side=tk.LEFT)
        
        self.enhance_var = tk.StringVar(value="auto")
        enhance_options = [("自动", "auto"), ("中等", "medium"), ("强力", "strong")]
        
        for i, (text, value) in enumerate(enhance_options):
            ttk.Radiobutton(complex_qr_frame, text=text, variable=self.enhance_var, 
                           value=value).pack(side=tk.LEFT, padx=5)
        
        # 扫描按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.scan_button = ttk.Button(button_frame, text="扫描二维码", command=self.scan_qr, 
                   style="Accent.TButton")
        self.scan_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="停止扫描", command=self.stop_scan, 
                   style="Stop.TButton", state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 图片工具区域
        tool_frame = ttk.LabelFrame(control_frame, text="图片工具")
        tool_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 创建工具按钮框架
        tool_buttons_frame = ttk.Frame(tool_frame)
        tool_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 第一行按钮
        row1_frame = ttk.Frame(tool_buttons_frame)
        row1_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.merge_button = ttk.Button(row1_frame, text="合并图片", command=self.merge_images)
        self.merge_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.save_button = ttk.Button(row1_frame, text="保存预览", command=self.save_preview_image)
        self.save_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 第二行按钮
        row2_frame = ttk.Frame(tool_buttons_frame)
        row2_frame.pack(fill=tk.X)
        
        self.invert_button = ttk.Button(row2_frame, text="反色处理", command=self.invert_image)
        self.invert_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.reset_button = ttk.Button(row2_frame, text="重置图片", command=self.reset_image)
        self.reset_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 第三行按钮 - 异形二维码处理
        row3_frame = ttk.Frame(tool_buttons_frame)
        row3_frame.pack(fill=tk.X)
        
        self.enhance_qr_button = ttk.Button(row3_frame, text="增强二维码", command=self.enhance_qr)
        self.enhance_qr_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.transform_button = ttk.Button(row3_frame, text="变换视角", command=self.transform_perspective)
        self.transform_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 右侧结果面板
        result_frame = ttk.LabelFrame(scan_container, text="扫描结果")
        result_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, pady=10)
        
        # 创建结果文本框和滚动条
        result_container = ttk.Frame(result_frame)
        result_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(result_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.result_text = tk.Text(result_container, wrap=tk.WORD, height=15, 
                                 yscrollcommand=scrollbar.set)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.result_text.yview)
        
        # 添加超链接支持
                # 添加超链接支持
        self.result_text.tag_config("hyperlink", foreground="blue", underline=1)
        self.result_text.tag_bind("hyperlink", "<Button-1>", self.open_hyperlink)
        self.result_text.tag_bind("hyperlink", "<Enter>", lambda e: self.result_text.config(cursor="hand2"))
        self.result_text.tag_bind("hyperlink", "<Leave>", lambda e: self.result_text.config(cursor=""))
        
        # 创建图片预览区域
        preview_frame = ttk.LabelFrame(result_frame, text="图片预览")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.preview_label = ttk.Label(preview_frame, background="#e0e0e0")
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 进度条
        progress_frame = ttk.Frame(result_frame)
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                           mode='determinate')
        self.progress_bar.pack(fill=tk.X)
        self.progress_bar.pack_forget()  # 默认隐藏
        
        # 初始化UI状态
        self.update_ui()
    
    def update_ui(self):
        """根据选择的模式更新UI"""
        mode = self.mode_var.get()
        
        if mode == "local":
            self.file_entry.config(state=tk.NORMAL)
            self.url_entry.config(state=tk.DISABLED)
            self.browse_button.pack(side=tk.LEFT, padx=(0, 5))
            self.folder_button.pack_forget()
        elif mode == "web":
            self.file_entry.config(state=tk.DISABLED)
            self.url_entry.config(state=tk.NORMAL)
            self.browse_button.pack_forget()
            self.folder_button.pack_forget()
        elif mode == "batch":
            self.file_entry.config(state=tk.NORMAL)
            self.url_entry.config(state=tk.DISABLED)
            self.browse_button.pack(side=tk.LEFT, padx=(0, 5))
            self.folder_button.pack_forget()
        else:  # folder
            self.file_entry.config(state=tk.NORMAL)
            self.url_entry.config(state=tk.DISABLED)
            self.browse_button.pack_forget()
            self.folder_button.pack(side=tk.LEFT)
    
    def browse_files(self):
        """打开文件对话框选择文件"""
        mode = self.mode_var.get()
        current_path = self.file_entry.get()
        
        if mode == "local" or mode == "batch":
            if mode == "batch":
                file_paths = filedialog.askopenfilenames(
                    initialdir=os.path.dirname(current_path) if current_path else None,
                    filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.gif")])
                if file_paths:  # 只有当用户选择了文件时才更新
                    self.file_entry.delete(0, tk.END)
                    self.file_entry.insert(0, ";".join(file_paths))
                    if mode == "local":
                        self.current_image_path = file_paths[0]
            else:
                file_path = filedialog.askopenfilename(
                    initialdir=os.path.dirname(current_path) if current_path else None,
                    filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.gif")])
                if file_path:  # 只有当用户选择了文件时才更新
                    self.file_entry.delete(0, tk.END)
                    self.file_entry.insert(0, file_path)
                    if mode == "local":
                        self.current_image_path = file_path
    
    def browse_folder(self):
        """打开文件夹对话框选择文件夹"""
        folder_path = filedialog.askdirectory()
        if folder_path:  # 用户选择了文件夹
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, folder_path)
    
    def handle_drop(self, files):
        """处理拖放文件"""
        if len(files) == 1:
            self.mode_var.set("local")
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, files[0])
            self.current_image_path = files[0]
        else:
            self.mode_var.set("batch")
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, ";".join(files))
        
        self.update_ui()
    
    def scan_qr(self):
        """执行二维码扫描"""
        if self.scanning:
            return
            
        self.scanning = True
        self.stop_requested = False
        self.attempted_enhancements = 0
        self.scan_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.clear_preview()
        
        # 在后台线程中执行扫描
        scan_thread = threading.Thread(target=self._scan_thread, daemon=True)
        scan_thread.start()
    
    def _scan_thread(self):
        """后台扫描线程"""
        try:
            mode = self.mode_var.get()
            
            if mode == "local":
                file_path = self.file_entry.get()
                if not file_path:
                    self.parent.after(0, lambda: messagebox.showwarning("警告", "请选择要扫描的图片文件"))
                    return
                
                self.process_image(file_path)
            
            elif mode == "web":
                url = self.url_entry.get()
                if not url:
                    self.parent.after(0, lambda: messagebox.showwarning("警告", "请输入图片URL"))
                    return
                
                self.process_web_image(url)
            
            elif mode == "batch":
                file_paths = self.file_entry.get().split(";")
                if not any(file_paths):
                    self.parent.after(0, lambda: messagebox.showwarning("警告", "请选择要扫描的图片文件"))
                    return
                
                # 应用排序
                file_paths = self.apply_sorting(file_paths)
                
                total = len(file_paths)
                self.parent.after(0, lambda: self.progress_bar.pack(fill=tk.X))
                self.progress_var.set(0)
                
                for i, file_path in enumerate(file_paths):
                    if self.stop_requested:
                        break
                        
                    if not file_path.strip():
                        continue
                    
                    # 是否显示详细输出
                    if self.detailed_output_var.get():
                        self.parent.after(0, lambda i=i, file_path=file_path: 
                                         self.result_text.insert(tk.END, 
                                         f"\n\n--- 文件 {i+1}/{total}: {os.path.basename(file_path)} ---\n"))
                    
                    self.process_image(file_path.strip())
                    
                    # 更新进度
                    progress = (i + 1) / total * 100
                    self.parent.after(0, lambda p=progress: self.progress_var.set(p))
                    self.parent.after(0, lambda p=progress, i=i, total=total: 
                                     self.parent.update_status(f"处理中: {i+1}/{total} ({p:.1f}%)"))
                
                self.parent.after(0, lambda: self.progress_bar.pack_forget())
            
            elif mode == "folder":
                folder_path = self.file_entry.get()
                if not folder_path or not os.path.isdir(folder_path):
                    self.parent.after(0, lambda: messagebox.showwarning("警告", "请选择要扫描的文件夹"))
                    return
                
                # 获取所有图片文件
                image_files = self.get_image_files(folder_path)
                if not image_files:
                    self.parent.after(0, lambda: messagebox.showinfo("提示", "该文件夹下未找到图片文件"))
                    return
                
                # 应用排序
                image_files = self.apply_sorting(image_files)
                
                total = len(image_files)
                self.parent.after(0, lambda: self.progress_bar.pack(fill=tk.X))
                self.progress_var.set(0)
                
                for i, file_path in enumerate(image_files):
                    if self.stop_requested:
                        break
                        
                    # 是否显示详细输出
                    if self.detailed_output_var.get():
                        self.parent.after(0, lambda i=i, file_path=file_path: 
                                         self.result_text.insert(tk.END, 
                                         f"\n\n--- 文件 {i+1}/{total}: {os.path.relpath(file_path, folder_path)} ---\n"))
                    
                    self.process_image(file_path)
                    
                    # 更新进度
                    progress = (i + 1) / total * 100
                    self.parent.after(0, lambda p=progress: self.progress_var.set(p))
                    self.parent.after(0, lambda p=progress, i=i, total=total: 
                                     self.parent.update_status(f"处理中: {i+1}/{total} ({p:.1f}%)"))
                
                self.parent.after(0, lambda: self.progress_bar.pack_forget())
        
        except Exception as e:
            self.parent.after(0, lambda: self.parent.update_status(f"错误: {str(e)}"))
            self.parent.after(0, lambda: messagebox.showerror("错误", f"扫描过程中发生错误:\n{str(e)}"))
        finally:
            self.scanning = False
            self.stop_requested = False
            self.parent.after(0, lambda: self.scan_button.config(state=tk.NORMAL))
            self.parent.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
            self.parent.after(0, lambda: self.parent.update_status("扫描完成"))
    
    def apply_sorting(self, file_list):
        """应用排序到文件列表"""
        sort_order = self.sort_var.get()
        
        if sort_order == "none":
            return file_list
        
        try:
            if sort_order == "numeric":
                # 自然排序（数字顺序）
                return natsort.natsorted(file_list, key=lambda x: os.path.basename(x))
            elif sort_order == "alphabetical":
                # 字母顺序
                return sorted(file_list, key=lambda x: os.path.basename(x))
        except Exception:
            # 如果排序失败，返回原始列表
            return file_list
        
        return file_list
    
    def stop_scan(self):
        """停止扫描"""
        self.stop_requested = True
        self.parent.update_status("正在停止...")
    
    def get_image_files(self, folder_path):
        """递归获取文件夹中的所有图片文件"""
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif']
        image_files = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_files.append(os.path.join(root, file))
        
        return image_files
    
    def process_image(self, file_path):
        """处理本地图片文件"""
        try:
            # 保存当前图片路径
            self.current_image_path = file_path
            self.current_image_url = None
            
            # 打开并显示图片
            img = Image.open(file_path)
            self.show_preview(img)
            
            # 处理并扫描二维码
            processed_img = self.preprocess_image(img)
            results = self.scan_image(processed_img)
            
            # 如果没找到二维码且增强模式不是关闭，尝试更高级的识别方法
            enhance_level = self.enhance_var.get()
            if not results and enhance_level != "off" and self.attempted_enhancements < 3:
                self.attempted_enhancements += 1
                processed_img = self.enhance_qr_image(processed_img, level=enhance_level)
                results = self.scan_image(processed_img)
                self.parent.update_status(f"增强处理级别 {self.attempted_enhancements} 应用于: {os.path.basename(file_path)}")
            
            # 显示结果
            self.display_results(results, os.path.basename(file_path))
            self.parent.update_status(f"扫描完成: {os.path.basename(file_path)}")
        
        except Exception as e:
            self.parent.after(0, lambda: self.result_text.insert(tk.END, f"错误: {str(e)}\n"))
            self.parent.update_status(f"扫描失败: {os.path.basename(file_path)}")
    
    def process_web_image(self, url):
        """处理网络图片"""
        try:
            # 保存当前图片URL
            self.current_image_url = url
            self.current_image_path = None
            
            # 下载图片
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # 打开并显示图片
            img = Image.open(BytesIO(response.content))
            self.show_preview(img)
            
            # 处理并扫描二维码
            processed_img = self.preprocess_image(img)
            results = self.scan_image(processed_img)
            
            # 显示结果
            self.display_results(results, url)
            self.parent.update_status(f"扫描完成: {url}")
        
        except Exception as e:
            self.parent.after(0, lambda: self.result_text.insert(tk.END, f"错误: {str(e)}\n"))
            self.parent.update_status(f"扫描失败: {url}")
    
    def preprocess_image(self, img):
        """图像预处理以提高识别率"""
        # 转换为灰度图
        img = img.convert("L") if img else None
        
        # 增强对比度
        if img:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)
            
            # 增强锐度
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(2.0)
            
            # 调整大小（如果太小）
            if img.width < 300 or img.height < 300:
                img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
        
        return img
    
    def enhance_qr_image(self, img, level="auto"):
        """增强二维码图像以提高识别率"""
        if not img:
            return None
            
        # 设置增强级别
        if level == "auto":
            contrast_level = 2.5
            sharpness_level = 2.5
        elif level == "medium":
            contrast_level = 3.0
            sharpness_level = 3.0
        else:  # strong
            contrast_level = 4.0
            sharpness_level = 4.0
        
        # 应用自适应阈值
        img = ImageOps.autocontrast(img)
        
        # 增强对比度
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast_level)
        
        # 增强锐度
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(sharpness_level)
        
        # 尝试不同阈值方法
        img = img.point(lambda p: p > 128 and 255)
        
        return img
    
    def scan_image(self, img):
        """扫描图像中的二维码"""
        if not img:
            return []
            
        # 将PIL图像转换为numpy数组供pyzbar使用
        img_array = np.array(img)
        
        # 尝试扫描二维码
        decoded_objs = pyzbar.decode(img_array, symbols=[pyzbar.ZBarSymbol.QRCODE])
        
        # 如果未找到二维码，尝试使用更激进的阈值
        if not decoded_objs:
            # 应用Otsu's 二值化
            img = img.convert('L')
            img_array = np.array(img)
            thresh = np.percentile(img_array, 35)  # 使用较低的阈值
            img_array = np.where(img_array > thresh, 255, 0).astype(np.uint8)
            decoded_objs = pyzbar.decode(img_array, symbols=[pyzbar.ZBarSymbol.QRCODE])
        
        # 如果还没找到，尝试反转图像
        if not decoded_objs:
            img = ImageOps.invert(img.convert('RGB'))
            img_array = np.array(img)
            decoded_objs = pyzbar.decode(img_array, symbols=[pyzbar.ZBarSymbol.QRCODE])
        
        return decoded_objs
    
    def display_results(self, results, source):
        """显示扫描结果"""
        if not results:
            self.parent.after(0, lambda: self.result_text.insert(tk.END, f"未在 {source} 中找到二维码\n"))
            return
        
        # 只有在详细输出模式下才显示标题
        if self.detailed_output_var.get():
            self.parent.after(0, lambda: self.result_text.insert(tk.END, f"在 {source} 中找到 {len(results)} 个二维码:\n"))
        
        for i, obj in enumerate(results):
            try:
                data = obj.data.decode('utf-8')
            except:
                try:
                    data = obj.data.decode('latin-1')
                except:
                    data = str(obj.data)
            
            # 只有在详细输出模式下才显示二维码索引
            if self.detailed_output_var.get():
                self.parent.after(0, lambda i=i, obj=obj, data=data: 
                                 self.result_text.insert(tk.END, f"\n二维码 {i+1}:\n"))
                self.parent.after(0, lambda obj=obj: 
                                 self.result_text.insert(tk.END, f"类型: {obj.type}\n"))
                self.parent.after(0, lambda: self.result_text.insert(tk.END, "内容:\n"))
            
            # 检查内容是否为URL
            if data.startswith(('http://', 'https://')):
                self.parent.after(0, lambda data=data: 
                                 self.result_text.insert(tk.END, data, "hyperlink"))
            else:
                self.parent.after(0, lambda data=data: self.result_text.insert(tk.END, data))
            
            # 添加分隔符
            if self.detailed_output_var.get():
                self.parent.after(0, lambda: self.result_text.insert(tk.END, "\n" + "-" * 50 + "\n"))
            else:
                # 在简洁模式下，使用配置的分隔符
                separator = self.config["batch_scan"]["separator"]
                self.parent.after(0, lambda: self.result_text.insert(tk.END, separator))
    
    def show_preview(self, img):
        """显示图片预览，仅扫描模块使用此方法，分析模块应使用原始图片预览"""
        if not img:
            return
            
        # 保存原始图片对象
        self.current_preview_image = img.copy()
        
        # 调整图片大小以适应预览区域，不进行预处理
        max_size = (400, 300)
        preview_img = img.copy()
        preview_img.thumbnail(max_size, Image.LANCZOS)
        
        # 转换为PhotoImage
        self.preview_img_tk = ImageTk.PhotoImage(preview_img)
        self.parent.after(0, lambda: self.preview_label.config(image=self.preview_img_tk))

    def clear_preview(self):
        """清除图片预览"""
        self.preview_label.config(image='')
        self.preview_img_tk = None
        self.current_preview_image = None
        self.current_image_path = None
        self.current_image_url = None

    # ================== 图片工具功能 ==================
    
    def save_preview_image(self):
        """保存当前预览的图片"""
        if not self.current_preview_image:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可保存的预览图片"))
            return
        
        # 弹出文件保存对话框
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG 文件", "*.png"), 
                       ("JPEG 文件", "*.jpg;*.jpeg"),
                       ("BMP 文件", "*.bmp"),
                       ("所有文件", "*.*")])
        
        if not file_path:  # 用户取消了保存
            return
        
        try:
            # 根据文件扩展名确定保存格式
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ('.jpg', '.jpeg'):
                format = 'JPEG'
            elif ext == '.bmp':
                format = 'BMP'
            else:
                format = 'PNG'  # 默认保存为PNG
            
            # 保存图片
            self.current_preview_image.save(file_path, format=format)
            self.parent.update_status(f"图片已保存到: {file_path}")
            self.parent.after(0, lambda: messagebox.showinfo("成功", f"图片已成功保存到:\n{file_path}"))
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"保存图片时出错:\n{str(e)}"))
    
    def merge_images(self):
        """合并多张图片为一张大图"""
        # 让用户选择要合并的图片
        file_paths = filedialog.askopenfilenames(
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.gif")])
        
        if not file_paths:
            return
        
        # 询问用户每行图片数量
        cols = simpledialog.askinteger(
            "图片合并", 
            "请输入每行显示的图片数量:", 
            parent=self.parent,
            minvalue=1,
            maxvalue=10
        )
        
        if cols is None:  # 用户取消了输入
            return
        
        # 询问用户图片间距
        spacing = simpledialog.askinteger(
            "图片合并", 
            "请输入图片之间的间距(像素):", 
            parent=self.parent,
            minvalue=0,
            maxvalue=50,
            initialvalue=10
        )
        
        if spacing is None:  # 用户取消了输入
            return
        
        # 询问用户背景颜色
        bg_color = simpledialog.askstring(
            "图片合并", 
            "请输入背景颜色(名称或十六进制值):", 
            parent=self.parent,
            initialvalue="white"
        )
        
        if bg_color is None:  # 用户取消了输入
            return
        
        try:
            # 处理背景颜色
            if bg_color.startswith('#'):
                # 转换为RGB元组
                hex_color = bg_color.lstrip('#')
                if len(hex_color) == 3:
                    bg_color = tuple(int(hex_color[i]*2, 16) for i in (0, 1, 2))
                else:
                    bg_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            else:
                # 尝试使用颜色名称
                try:
                    from PIL import ImageColor
                    bg_color = ImageColor.getrgb(bg_color)
                except:
                    bg_color = (255, 255, 255)  # 默认白色
        except:
            bg_color = (255, 255, 255)  # 默认白色
        
        # 询问用户是否启用智能模式
        use_smart_mode = messagebox.askyesno(
            "智能模式", 
            "是否启用智能模式？\n(所有图片将统一调整为相同尺寸)"
        )
        
        try:
            # 加载所有图片
            images = []
            max_width, max_height = 0, 0
            for path in file_paths:
                img = Image.open(path)
                images.append(img)
                max_width = max(max_width, img.width)
                max_height = max(max_height, img.height)
            
            # 计算网格尺寸
            rows = math.ceil(len(images) / cols)
            
            # 在智能模式下，计算目标尺寸
            if use_smart_mode:
                # 计算平均尺寸作为目标尺寸
                total_width = sum(img.width for img in images)
                total_height = sum(img.height for img in images)
                avg_width = total_width // len(images)
                avg_height = total_height // len(images)
                
                # 使用最大尺寸或平均尺寸中较小的一个，防止图片过大
                target_width = min(max_width, avg_width)
                target_height = min(max_height, avg_height)
                
                # 创建缩放后的图片列表
                scaled_images = []
                for img in images:
                    # 保持宽高比缩放
                    ratio = min(target_width / img.width, target_height / img.height)
                    new_width = int(img.width * ratio)
                    new_height = int(img.height * ratio)
                    
                    # 高质量缩放
                    scaled_img = img.resize((new_width, new_height), Image.LANCZOS)
                    scaled_images.append(scaled_img)
                
                # 更新图片列表为缩放后的图片
                images = scaled_images
                
                # 更新最大尺寸为缩放后的尺寸
                max_width = max(img.width for img in images)
                max_height = max(img.height for img in images)
            
            # 计算大图尺寸
            total_width = cols * max_width + (cols - 1) * spacing
            total_height = rows * max_height + (rows - 1) * spacing
            
            # 创建新图片
            merged_img = Image.new('RGB', (total_width, total_height), bg_color)
            
            # 粘贴图片
            for i, img in enumerate(images):
                row = i // cols
                col = i % cols
                
                # 计算位置（左上角对齐）
                x = col * (max_width + spacing)
                y = row * (max_height + spacing)
                
                # 直接粘贴图片
                merged_img.paste(img, (x, y))
            
            # 显示合并后的图片
            self.show_preview(merged_img)
            self.parent.update_status(f"成功合并 {len(images)} 张图片")
            
            # 询问用户是否保存
            if messagebox.askyesno("保存图片", "是否保存合并后的图片？"):
                # 弹出文件保存对话框
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG 文件", "*.png"), 
                               ("JPEG 文件", "*.jpg;*.jpeg"),
                               ("所有文件", "*.*")])
                
                if file_path:
                    merged_img.save(file_path)
                    self.parent.update_status(f"合并图片已保存到: {file_path}")
                    self.parent.after(0, lambda: messagebox.showinfo("成功", f"图片已成功保存到:\n{file_path}"))
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"合并图片时出错:\n{str(e)}"))
    
    def invert_image(self):
        """对当前预览图像进行反色处理"""
        if not self.current_preview_image:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可处理的预览图片"))
            return
        
        try:
            # 对图像进行反色处理
            inverted_img = ImageOps.invert(self.current_preview_image.convert('RGB'))
            
            # 更新预览
            self.show_preview(inverted_img)
            self.parent.update_status("图片已反色处理")
            
            # 重新扫描
            if messagebox.askyesno("重新扫描", "是否使用反色后的图片重新扫描二维码？"):
                # 处理并扫描二维码
                processed_img = self.preprocess_image(inverted_img)
                results = self.scan_image(processed_img)
                
                # 显示结果
                source = "反色图片"
                if self.current_image_path:
                    source = os.path.basename(self.current_image_path)
                elif self.current_image_url:
                    source = self.current_image_url
                    
                self.result_text.delete(1.0, tk.END)
                self.display_results(results, source)
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"反色处理时出错:\n{str(e)}"))
    
    def reset_image(self):
        """重置图片到原始状态"""
        if self.current_image_path is None and self.current_image_url is None:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有原始图片可重置"))
            return
        
        try:
            if self.current_image_path:
                # 打开并显示原始图片
                img = Image.open(self.current_image_path)
                self.show_preview(img)
                self.parent.update_status("已重置到原始图片")
            elif self.current_image_url:
                # 重新下载图片
                response = requests.get(self.current_image_url, timeout=10)
                response.raise_for_status()
                
                # 打开并显示图片
                img = Image.open(BytesIO(response.content))
                self.show_preview(img)
                self.parent.update_status("已重置到原始图片")
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"重置图片时出错:\n{str(e)}"))
    
    def enhance_qr(self):
        """增强二维码识别"""
        if not self.current_preview_image:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可处理的预览图片"))
            return
        
        try:
            # 获取当前增强级别
            level = self.enhance_var.get()
            
            # 增强处理
            enhanced_img = self.enhance_qr_image(self.current_preview_image, level)
            
            # 显示处理后的图像
            self.show_preview(enhanced_img)
            self.parent.update_status("二维码增强处理完成")
            
            # 重新扫描
            if messagebox.askyesno("重新扫描", "是否使用增强后的图片重新扫描二维码？"):
                # 处理并扫描二维码
                processed_img = self.preprocess_image(enhanced_img)
                results = self.scan_image(processed_img)
                
                # 显示结果
                source = "增强图片"
                if self.current_image_path:
                    source = os.path.basename(self.current_image_path)
                elif self.current_image_url:
                    source = self.current_image_url
                    
                self.result_text.delete(1.0, tk.END)
                self.display_results(results, source)
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"二维码增强时出错:\n{str(e)}"))
    
    def transform_perspective(self):
        """变换图像视角"""
        if not self.current_preview_image:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可处理的预览图片"))
            return
        
        try:
            # 创建一个简单的视角变换
            width, height = self.current_preview_image.size
            
            # 定义变换矩阵 - 简单的倾斜变换
            transform_amount = 0.2
            transform_matrix = [
                1, transform_amount, 0,
                transform_amount, 1, 0,
                0, 0
            ]
            
            # 应用透视变换
            transformed_img = self.current_preview_image.transform(
                (width, height),
                Image.PERSPECTIVE,
                transform_matrix,
                Image.BICUBIC
            )
            
            # 显示处理后的图像
            self.show_preview(transformed_img)
            self.parent.update_status("视角变换完成")
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"变换视角时出错:\n{str(e)}"))
    
    def open_hyperlink(self, event):
        """打开超链接"""
        index = self.result_text.index(f"@{event.x},{event.y}")
        tags = self.result_text.tag_names(index)
        
        if "hyperlink" in tags:
            # 获取超链接文本
            start = self.result_text.index(f"{index} linestart")
            end = self.result_text.index(f"{index} lineend")
            line = self.result_text.get(start, end)
            
            # 提取URL（简单匹配）
            url_match = re.search(r'https?://[^\s]+', line)
            if url_match:
                url = url_match.group(0)
                webbrowser.open(url)


class AnalysisModule:
    """图片分析模块，封装图片分析相关功能"""
    def __init__(self, parent):
        self.parent = parent
        self.analysis_image = None
        self.analysis_image_path = None
        self.analysis_image_url = None
        self.preview_img_tk = None  # 用于存储分析模块的预览图片
        self.analysis_progress = 0  # 新增：分析进度
        self.max_progress = 100  # 新增：最大进度值
        self.analysis_cancelled = False  # 新增：取消分析标志
        self.original_analysis_image = None  # 保存原始分析图片
        self.analysis_config = self.parent.config["analysis"]
    
    def init_ui(self, parent_frame):
        """初始化分析选项卡UI"""
        # 主容器
        analysis_container = ttk.Frame(parent_frame)
        analysis_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧控制面板
        analysis_control_frame = ttk.LabelFrame(analysis_container, text="分析选项")
        analysis_control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=10)
        
        # 文件选择区域
        file_frame = ttk.Frame(analysis_control_frame)
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(file_frame, text="图片路径:").pack(anchor="w")
        self.analysis_file_entry = ttk.Entry(file_frame)
        self.analysis_file_entry.pack(fill=tk.X, pady=5)
        
        file_button_frame = ttk.Frame(file_frame)
        file_button_frame.pack(fill=tk.X)
        
        self.analysis_browse_button = ttk.Button(file_button_frame, text="浏览...", 
                                               command=self.browse_files)
        self.analysis_browse_button.pack(side=tk.LEFT)
        
        self.load_button = ttk.Button(file_button_frame, text="加载图片", 
                                    command=self.load_image_for_analysis)
        self.load_button.pack(side=tk.RIGHT)
        
        # URL输入区域
        url_frame = ttk.Frame(analysis_control_frame)
        url_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(url_frame, text="图片URL:").pack(anchor="w")
        self.analysis_url_entry = ttk.Entry(url_frame)
        self.analysis_url_entry.pack(fill=tk.X, pady=5)
        
        # 图片工具区域
        tool_frame = ttk.LabelFrame(analysis_control_frame, text="图片工具")
        tool_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 创建工具按钮框架
        tool_buttons_frame = ttk.Frame(tool_frame)
        tool_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 第一行按钮
        row1_frame = ttk.Frame(tool_buttons_frame)
        row1_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.info_button = ttk.Button(row1_frame, text="显示图片信息", 
                                    command=self.show_image_info)
        self.info_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 第二行按钮
        row2_frame = ttk.Frame(tool_buttons_frame)
        row2_frame.pack(fill=tk.X)
        
        self.invert_button = ttk.Button(row2_frame, text="反色处理", command=self.invert_image)
        self.invert_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.reset_button = ttk.Button(row2_frame, text="重置图片", command=self.reset_image)
        self.reset_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 第三行按钮
        row3_frame = ttk.Frame(tool_buttons_frame)
        row3_frame.pack(fill=tk.X)
        
        self.lsb_button = ttk.Button(row3_frame, text="显示LSB", command=self.show_lsb)
        self.lsb_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.bit_plane_button = ttk.Button(row3_frame, text="位平面", command=self.show_bit_plane)
        self.bit_plane_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 隐写分析区域
        steg_frame = ttk.LabelFrame(analysis_control_frame, text="隐写分析")
        steg_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 通道选择
        channel_frame = ttk.Frame(steg_frame)
        channel_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(channel_frame, text="分析通道:").pack(side=tk.LEFT)
        
        # 使用配置中的通道选择
        self.channel_vars = {
            'R': tk.BooleanVar(value='R' in self.analysis_config["selected_channels"]),
            'G': tk.BooleanVar(value='G' in self.analysis_config["selected_channels"]),
            'B': tk.BooleanVar(value='B' in self.analysis_config["selected_channels"])
        }
        
        for i, color in enumerate(['R', 'G', 'B']):
            ttk.Checkbutton(channel_frame, text=color, variable=self.channel_vars[color]
                           ).pack(side=tk.LEFT, padx=5)
        
        # 位位置选择
        bit_frame = ttk.Frame(steg_frame)
        bit_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(bit_frame, text="位位置:").pack(side=tk.LEFT)
        
        self.bit_vars = {
            'LSB': tk.BooleanVar(value='LSB' in self.analysis_config["selected_bit_positions"]),
            'MSB': tk.BooleanVar(value='MSB' in self.analysis_config["selected_bit_positions"])
        }
        
        for i, bit_pos in enumerate(['LSB', 'MSB']):
            ttk.Checkbutton(bit_frame, text=bit_pos, variable=self.bit_vars[bit_pos]
                           ).pack(side=tk.LEFT, padx=5)
        
        # 输出格式
        output_frame = ttk.Frame(steg_frame)
        output_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(output_frame, text="输出格式:").pack(side=tk.LEFT)
        
        self.output_var = tk.StringVar(value=self.analysis_config["output_format"])
        formats = [("自动检测", "auto"), ("Hex", "hex"), ("二进制", "bin"), ("ASCII", "ascii")]
        
        format_buttons_frame = ttk.Frame(output_frame)
        format_buttons_frame.pack(side=tk.LEFT, padx=10)
        
        for i, (text, value) in enumerate(formats):
            ttk.Radiobutton(format_buttons_frame, text=text, variable=self.output_var, 
                            value=value).grid(row=0, column=i, padx=5)
        
        # 最大输出字符数设置
        max_output_frame = ttk.Frame(steg_frame)
        max_output_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(max_output_frame, text="最大输出字符:").pack(side=tk.LEFT)
        
        self.max_output_var = tk.StringVar(value=str(self.analysis_config["steg_max_output"]))
        max_output_entry = ttk.Entry(max_output_frame, textvariable=self.max_output_var, width=10)
        max_output_entry.pack(side=tk.LEFT, padx=5)
        
        # 分析按钮
        button_frame = ttk.Frame(steg_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.steg_button = ttk.Button(button_frame, text="分析隐写", command=self.start_analysis)
        self.steg_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.stop_analysis_button = ttk.Button(button_frame, text="停止分析", command=self.cancel_analysis, state=tk.DISABLED)
        self.stop_analysis_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 结果处理区域
        result_frame = ttk.Frame(steg_frame)
        result_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        self.dump_var = tk.BooleanVar(value=False)
        dump_check = ttk.Checkbutton(result_frame, text="导出完整结果到文件", 
                                    variable=self.dump_var)
        dump_check.pack(side=tk.LEFT, padx=5)
        
        # 右侧结果面板
        analysis_result_frame = ttk.LabelFrame(analysis_container, text="分析结果")
        analysis_result_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, pady=10)
        
        # 创建结果文本框和滚动条
        result_container = ttk.Frame(analysis_result_frame)
        result_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(result_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.analysis_text = tk.Text(result_container, wrap=tk.WORD, height=25, 
                                   yscrollcommand=scrollbar.set)
        self.analysis_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.analysis_text.yview)
        
        # 添加文本标签样式
        self.analysis_text.tag_config("header", font=("TkDefaultFont", 10, "bold"))
        self.analysis_text.tag_config("subheader", font=("TkDefaultFont", 9, "bold"))
        self.analysis_text.tag_config("warning", foreground="red")
        
        # 创建图片预览区域
        preview_frame = ttk.LabelFrame(analysis_result_frame, text="图片预览")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.preview_label = ttk.Label(preview_frame, background="#e0e0e0")
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 进度条
        progress_frame = ttk.Frame(analysis_result_frame)
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                          mode='determinate')
        self.progress_bar.pack(fill=tk.X)
        self.progress_bar.pack_forget()  # 默认隐藏
        
        # 添加右键菜单
        self.create_context_menu()
    
    def create_context_menu(self):
        """创建右键菜单"""
        self.context_menu = tk.Menu(self.parent, tearoff=0)
        self.context_menu.add_command(label="复制", command=self.copy_text)
        self.context_menu.add_command(label="清空结果", command=self.clear_results)
        self.context_menu.add_command(label="保存结果", command=self.save_results)
        
        # 为结果文本框绑定右键菜单
        self.analysis_text.bind("<Button-3>", self.show_context_menu)
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        self.context_menu.post(event.x_root, event.y_root)
    
    def copy_text(self):
        """复制选中文本"""
        try:
            selected = self.analysis_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if selected:
                self.parent.clipboard_clear()
                self.parent.clipboard_append(selected)
        except:
            pass
    
    def clear_results(self):
        """清空结果区域"""
        self.analysis_text.delete(1.0, tk.END)
    
    def save_results(self):
        """保存结果到文件"""
        content = self.analysis_text.get(1.0, tk.END)
        
        if not content.strip():
            self.parent.after(0, lambda: messagebox.showinfo("提示", "结果区域为空"))
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        
        if not file_path:
            return
            
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.parent.after(0, lambda: messagebox.showinfo("成功", f"结果已保存到:\n{file_path}"))
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"保存结果时出错:\n{str(e)}"))
    
    def browse_files(self):
        """打开文件对话框选择文件"""
        current_path = self.analysis_file_entry.get()
        
        file_path = filedialog.askopenfilename(
            initialdir=os.path.dirname(current_path) if current_path else None,
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.gif;*.dat;*.bin")])
        
        if file_path:  # 只有当用户选择了文件时才更新
            self.analysis_file_entry.delete(0, tk.END)
            self.analysis_file_entry.insert(0, file_path)
    
    def handle_drop(self, files):
        """处理拖放文件"""
        if files:
            self.analysis_file_entry.delete(0, tk.END)
            self.analysis_file_entry.insert(0, files[0])
    
    def load_image_for_analysis(self):
        """加载图片用于分析，使用独立的预览功能，不使用扫描模块的预处理"""
        file_path = self.analysis_file_entry.get()
        url = self.analysis_url_entry.get()
        
        if not file_path and not url:
            self.parent.after(0, lambda: messagebox.showwarning("警告", "请选择图片文件或输入图片URL"))
            return
        
        try:
            if file_path:
                # 打开并显示图片
                img = Image.open(file_path)
                self.analysis_image_path = file_path
                self.analysis_image_url = None
            else:
                # 下载图片
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                # 打开并显示图片
                img = Image.open(BytesIO(response.content))
                self.analysis_image_url = url
                self.analysis_image_path = None
            
            # 保存原始图片对象用于分析
            self.analysis_image = img.copy()
            self.original_analysis_image = img.copy()  # 保存原始图片
            
            # 显示图片预览，使用分析模块自己的预览功能，不进行预处理
            self.show_preview(img)
            self.parent.update_status("图片加载成功")
            
        except Exception as e:
            self.parent.update_status(f"加载图片失败: {str(e)}")
            self.parent.after(0, lambda: messagebox.showerror("错误", f"加载图片时出错:\n{str(e)}"))
            self.analysis_image = None
            self.original_analysis_image = None
            self.clear_preview()
    
    def show_preview(self, img):
        """分析模块独立的图片预览功能，不进行预处理"""
        if not img:
            return
            
        # 调整图片大小以适应预览区域
        max_size = (400, 300)
        preview_img = img.copy()
        preview_img.thumbnail(max_size, Image.LANCZOS)
        
        # 转换为PhotoImage
        self.preview_img_tk = ImageTk.PhotoImage(preview_img)
        self.parent.after(0, lambda: self.preview_label.config(image=self.preview_img_tk))
    
    def clear_preview(self):
        """清除分析模块的图片预览"""
        self.preview_label.config(image='')
        self.preview_img_tk = None
    
    def invert_image(self):
        """对当前预览图像进行反色处理"""
        if not self.analysis_image:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可处理的预览图片"))
            return
        
        try:
            # 对图像进行反色处理
            inverted_img = ImageOps.invert(self.analysis_image.convert('RGB'))
            
            # 更新预览
            self.show_preview(inverted_img)
            self.analysis_image = inverted_img
            self.parent.update_status("图片已反色处理")
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"反色处理时出错:\n{str(e)}"))
    
    def reset_image(self):
        """重置图片到原始状态"""
        if not self.original_analysis_image:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有原始图片可重置"))
            return
        
        try:
            # 重置到原始图片
            self.analysis_image = self.original_analysis_image.copy()
            
            # 显示原始图片预览
            self.show_preview(self.original_analysis_image)
            self.parent.update_status("已重置到原始图片")
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"重置图片时出错:\n{str(e)}"))
    
    def show_image_info(self):
        """显示当前图片的详细信息"""
        try:
            self.analysis_text.delete(1.0, tk.END)
            
            if not self.analysis_image:
                self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可分析的图片"))
                return
                
            # 1. 基本图片信息
            self.analysis_text.insert(tk.END, "=== 图片基本信息 ===\n", "header")
            self.analysis_text.insert(tk.END, f"文件名: {os.path.basename(self.analysis_image_path) if self.analysis_image_path else '未知'}\n")
            self.analysis_text.insert(tk.END, f"尺寸: {self.analysis_image.width}x{self.analysis_image.height} 像素\n")
            self.analysis_text.insert(tk.END, f"模式: {self.analysis_image.mode}\n")
            self.analysis_text.insert(tk.END, f"格式: {self.analysis_image.format or '未知'}\n")
            self.analysis_text.insert(tk.END, f"文件大小: {os.path.getsize(self.analysis_image_path) if self.analysis_image_path else '未知'} 字节\n\n")
            
            # 2. 检查LSB平面（最低有效位），使用原始图片进行分析
            self.analysis_text.insert(tk.END, "=== LSB平面分析 ===\n", "header")
            try:
                # 转换为RGB模式
                if self.analysis_image.mode != 'RGB':
                    rgb_img = self.analysis_image.convert('RGB')
                else:
                    rgb_img = self.analysis_image
                
                r, g, b = rgb_img.split()
                
                # 提取LSB平面
                r_lsb = Image.eval(r, lambda x: (x & 1) * 255)
                g_lsb = Image.eval(g, lambda x: (x & 1) * 255)
                b_lsb = Image.eval(b, lambda x: (x & 1) * 255)
                
                # 合并LSB平面并计算熵
                lsb_img = Image.merge('RGB', (r_lsb, g_lsb, b_lsb))
                lsb_data = lsb_img.tobytes()
                
                # 计算熵
                entropy = self.calculate_entropy(lsb_data)
                self.analysis_text.insert(tk.END, f"LSB平面熵: {entropy:.4f} 比特/字节\n")
                
                # 分析熵值
                if entropy > 6.0:
                    self.analysis_text.insert(tk.END, "警告: LSB平面熵值异常高，可能包含隐藏数据\n", "warning")
                elif entropy < 2.0:
                    self.analysis_text.insert(tk.END, "LSB平面熵值低，可能已被处理\n")
                else:
                    self.analysis_text.insert(tk.END, "LSB平面熵值正常\n")
                
            except Exception as e:
                self.analysis_text.insert(tk.END, f"分析LSB平面时出错: {str(e)}\n")
            
            # 3. 检查通道直方图
            self.analysis_text.insert(tk.END, "\n=== 通道直方图分析 ===\n", "header")
            try:
                # 将图像转换为RGB模式以便分析通道
                if self.analysis_image.mode != 'RGB':
                    rgb_img = self.analysis_image.convert('RGB')
                else:
                    rgb_img = self.analysis_image
                
                r, g, b = rgb_img.split()
                
                # 获取各通道的直方图
                r_hist = r.histogram()
                g_hist = g.histogram()
                b_hist = b.histogram()
                
                # 找出每个通道最频繁的颜色值
                r_max = max(r_hist)
                g_max = max(g_hist)
                b_max = max(b_hist)
                
                # 检查是否存在异常峰值
                suspicious = False
                if r_max > (r.width * r.height) * 0.3:  # 超过30%的像素具有相同值
                    self.analysis_text.insert(tk.END, "红色通道有异常峰值\n", "warning")
                    suspicious = True
                if g_max > (g.width * g.height) * 0.3:
                    self.analysis_text.insert(tk.END, "绿色通道有异常峰值\n", "warning")
                    suspicious = True
                if b_max > (b.width * b.height) * 0.3:
                    self.analysis_text.insert(tk.END, "蓝色通道有异常峰值\n", "warning")
                    suspicious = True
                
                if not suspicious:
                    self.analysis_text.insert(tk.END, "通道直方图正常\n")
                
            except Exception as e:
                self.analysis_text.insert(tk.END, f"分析通道直方图时出错: {str(e)}\n")
            
            # 4. 检查异常文件结构
            self.analysis_text.insert(tk.END, "\n=== 文件结构分析 ===\n", "header")
            if self.analysis_image_path:
                try:
                    with open(self.analysis_image_path, 'rb') as f:
                        header = f.read(8)
                        f.seek(-8, 2)  # 跳转到文件末尾
                        footer = f.read(8)
                    
                    self.analysis_text.insert(tk.END, f"文件头: {binascii.hexlify(header).decode('utf-8')}\n")
                    self.analysis_text.insert(tk.END, f"文件尾: {binascii.hexlify(footer).decode('utf-8')}\n")
                    
                    # 检查常见的文件签名
                    common_signatures = {
                        b'\xFF\xD8\xFF': ('JPEG', True),
                        b'\x89PNG\r\n\x1a\n': ('PNG', True),
                        b'GIF87a': ('GIF87a', True),
                        b'GIF89a': ('GIF89a', True),
                        b'BM': ('BMP', True),
                        b'II*\x00': ('TIFF', True),
                        b'MM\x00*': ('TIFF', True),
                    }
                    
                    found_match = False
                    for sig, (format, valid) in common_signatures.items():
                        if header.startswith(sig):
                            found_match = True
                            if valid:
                                self.analysis_text.insert(tk.END, f"匹配签名: {format} (有效)\n")
                            else:
                                self.analysis_text.insert(tk.END, f"匹配签名: {format} (无效)\n", "warning")
                    
                    if not found_match:
                        self.analysis_text.insert(tk.END, "无法匹配常见文件签名\n", "warning")
                    
                except Exception as e:
                    self.analysis_text.insert(tk.END, f"分析文件结构时出错: {str(e)}\n")
            
            self.parent.update_status("图片信息分析完成")
        
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"获取图片信息时出错:\n{str(e)}"))
    
    def calculate_entropy(self, data):
        """计算数据的熵"""
        if not data:
            return 0.0
            
        entropy = 0
        total = len(data)
        if total == 0:
            return 0.0
            
        # 计算每个字节的频率
        freq = {}
        for byte in data:
            if byte in freq:
                freq[byte] += 1
            else:
                freq[byte] = 1
        
        # 计算熵
        for count in freq.values():
            p = count / total
            entropy -= p * math.log2(p)
            
        return entropy
    
    def show_lsb(self):
        """显示LSB平面"""
        if not self.analysis_image:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可分析的预览图片"))
            return
        
        try:
            # 转换为RGB模式
            if self.analysis_image.mode != 'RGB':
                rgb_img = self.analysis_image.convert('RGB')
            else:
                rgb_img = self.analysis_image
            
            r, g, b = rgb_img.split()
            
            # 提取LSB平面
            r_lsb = Image.eval(r, lambda x: (x & 1) * 255)
            g_lsb = Image.eval(g, lambda x: (x & 1) * 255)
            b_lsb = Image.eval(b, lambda x: (x & 1) * 255)
            
            # 合并为RGB图像显示
            lsb_img = Image.merge('RGB', (r_lsb, g_lsb, b_lsb))
            
            # 显示LSB平面
            self.show_preview(lsb_img)
            self.parent.update_status("LSB平面显示")
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"显示LSB平面时出错:\n{str(e)}"))
    
    def show_bit_plane(self):
        """显示位平面"""
        if not self.analysis_image:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可分析的预览图片"))
            return
        
        try:
            # 选择位平面
            bit_pos = simpledialog.askinteger(
                "位平面", 
                "请输入要查看的位平面(0-7, 0=LSB, 7=MSB):", 
                parent=self.parent,
                minvalue=0,
                maxvalue=7,
                initialvalue=0
            )
            
            if bit_pos is None:
                return
            
            # 转换为RGB模式
            if self.analysis_image.mode != 'RGB':
                rgb_img = self.analysis_image.convert('RGB')
            else:
                rgb_img = self.analysis_image
            
            r, g, b = rgb_img.split()
            
            # 提取指定的位平面
            r_bit = Image.eval(r, lambda x: ((x >> bit_pos) & 1) * 255)
            g_bit = Image.eval(g, lambda x: ((x >> bit_pos) & 1) * 255)
            b_bit = Image.eval(b, lambda x: ((x >> bit_pos) & 1) * 255)
            
            # 合并为RGB图像显示
            bit_img = Image.merge('RGB', (r_bit, g_bit, b_bit))
            
            # 显示位平面
            self.show_preview(bit_img)
            self.parent.update_status(f"显示位平面 {bit_pos} (0=LSB, 7=MSB)")
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"显示位平面时出错:\n{str(e)}"))
    
    def start_analysis(self):
        """开始隐写分析"""
        # 保存设置
        self.analysis_config["selected_channels"] = [c for c in ['R', 'G', 'B'] if self.channel_vars[c].get()]
        self.analysis_config["selected_bit_positions"] = [b for b in ['LSB', 'MSB'] if self.bit_vars[b].get()]
        self.analysis_config["output_format"] = self.output_var.get()
        
        try:
            self.analysis_config["steg_max_output"] = int(self.max_output_var.get())
        except:
            self.analysis_config["steg_max_output"] = 1024
        
        # 重置分析状态
        self.analysis_cancelled = False
        self.analysis_progress = 0
        
        # 更新界面状态
        self.steg_button.config(state=tk.DISABLED)
        self.stop_analysis_button.config(state=tk.NORMAL)
        self.clear_results()
        self.progress_bar.pack(fill=tk.X)
        self.progress_var.set(0)
        
        # 在后台线程中执行分析
        analysis_thread = threading.Thread(target=self.perform_analysis, daemon=True)
        analysis_thread.start()
    
    def cancel_analysis(self):
        """取消正在进行的分析"""
        self.analysis_cancelled = True
        self.parent.update_status("正在取消分析...")
    
    def perform_analysis(self):
        """执行隐写分析"""
        try:
            # 获取用户选择的选项
            output_format = self.output_var.get()
            max_output = self.analysis_config["steg_max_output"]
            
            # 获取图片
            img = self.analysis_image
            
            # 确保图片是RGB模式
            if img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
            else:
                self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "错误: 没有加载图片\n", "warning"))
                return
            
            # 分离通道
            r, g, b = img.split()
            channels = {
                'R': r,
                'G': g,
                'B': b
            }
            
            # 获取要分析的通道和位位置
            channels_to_analyze = self.analysis_config["selected_channels"]
            bit_positions = self.analysis_config["selected_bit_positions"]
            
            if not channels_to_analyze:
                self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "错误: 没有选择分析通道\n", "warning"))
                return
                
            if not bit_positions:
                self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "错误: 没有选择位位置\n", "warning"))
                return
            
            # 开始分析
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "=== 开始隐写分析 ===\n\n", "header"))
            
            total_combinations = len(channels_to_analyze) * len(bit_positions)
            completed = 0
            
            for channel in channels_to_analyze:
                for bit_pos in bit_positions:
                    if self.analysis_cancelled:
                        break
                        
                    # 更新进度
                    completed += 1
                    progress = int((completed / total_combinations) * 100)
                    self.parent.after(0, lambda p=progress: self.progress_var.set(p))
                    self.parent.after(0, lambda: self.parent.update_status(f"分析中: {progress}%"))
                    
                    # 分析指定的通道和位
                    self.analyze_channel(channels[channel], channel, bit_pos, output_format, max_output)
            
            self.parent.after(0, lambda: self.progress_bar.pack_forget())
            self.parent.update_status("隐写分析完成")
            
            # 如果选择了导出结果到文件
            if self.dump_var.get():
                self.parent.after(0, self.dump_full_results)
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"分析隐写数据时出错:\n{str(e)}"))
        finally:
            self.parent.after(0, lambda: self.steg_button.config(state=tk.NORMAL))
            self.parent.after(0, lambda: self.stop_analysis_button.config(state=tk.DISABLED))
    
    def analyze_channel(self, channel, channel_name, bit_position, output_format, max_output):
        """分析单个通道的隐写数据"""
        try:
            # 显示标题
            bit_name = "LSB" if bit_position == "LSB" else "MSB"
            header = f"=== 通道 {channel_name} - {bit_name} ==="
            self.parent.after(0, lambda h=header: self.analysis_text.insert(tk.END, h + "\n", "subheader"))
            
            # 提取位数据
            extracted_bits = []
            for pixel in channel.getdata():
                if bit_position == "LSB":
                    # 提取最低有效位 (LSB)
                    extracted_bits.append(pixel & 1)
                else:  # MSB
                    # 提取最高有效位 (MSB)
                    extracted_bits.append((pixel >> 7) & 1)
            
            # 转换为字节
            extracted_bytes = []
            byte = 0
            bit_count = 0
            for bit in extracted_bits:
                byte = (byte << 1) | bit
                bit_count += 1
                if bit_count == 8:
                    extracted_bytes.append(byte)
                    byte = 0
                    bit_count = 0
            
            # 如果还有剩余的位，添加最后一个字节
            if bit_count > 0:
                byte <<= (8 - bit_count)
                extracted_bytes.append(byte)
            
            extracted_data = bytes(extracted_bytes)
            
            # 输出结果
            self.parent.after(0, lambda s=f"提取数据大小: {len(extracted_data)} 字节": 
                             self.analysis_text.insert(tk.END, s + "\n"))
            
            # 根据选择的格式输出，自动检测格式
            if output_format == "auto":
                self.auto_detect_format_and_output(extracted_data, max_output)
            else:
                self.output_data(extracted_data, output_format, max_output)
            
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "\n"))
            
        except Exception as e:
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, f"分析通道 {channel_name} 时出错: {str(e)}\n"))
    
    def auto_detect_format_and_output(self, data, max_output):
        """自动检测数据格式并输出"""
        try:
            # 尝试解码为UTF-8
            try:
                ascii_data = data.decode('utf-8')
                
                # 检查是否看起来像文本
                text_ratio = sum(32 <= ord(c) <= 126 for c in ascii_data) / len(ascii_data) if len(ascii_data) > 0 else 0
                
                if text_ratio > 0.7:
                    # 看起来像文本，以ASCII格式输出
                    self.output_data(data, "ascii", max_output)
                    return
            except:
                pass
            
            # 尝试其他常见编码
            for encoding in ['gbk', 'latin-1', 'iso-8859-1']:
                try:
                    ascii_data = data.decode(encoding)
                    # 检查是否包含可打印字符
                    printable_count = sum(32 <= ord(c) <= 126 or 0xA0 <= ord(c) <= 0xFF for c in ascii_data)
                    text_ratio = printable_count / len(ascii_data) if len(ascii_data) > 0 else 0
                    
                    if text_ratio > 0.6:
                        self.parent.after(0, lambda e=encoding: 
                             self.analysis_text.insert(tk.END, f"检测到编码: {e}\n"))
                        self.output_data(data, "ascii", max_output)
                        return
                except:
                    continue
            
            # 尝试检测PNG文件
            if data.startswith(b'\x89PNG\r\n\x1a\n'):
                self.parent.after(0, lambda: 
                     self.analysis_text.insert(tk.END, "检测到PNG文件签名\n"))
                self.output_png_info(data, max_output)
                return
            
            # 尝试检测JPEG文件
            if data.startswith(b'\xFF\xD8'):
                self.parent.after(0, lambda: 
                     self.analysis_text.insert(tk.END, "检测到JPEG文件签名\n"))
                self.output_general_binary(data, max_output)
                return
                
            # 尝试检测ZIP文件 (PK header)
            if data.startswith(b'PK\x03\x04'):
                self.parent.after(0, lambda: 
                     self.analysis_text.insert(tk.END, "检测到ZIP文件签名\n"))
                self.output_general_binary(data, max_output)
                return
                
            # 默认十六进制输出
                        # 默认十六进制输出
            self.parent.after(0, lambda: 
                 self.analysis_text.insert(tk.END, "无法识别文件类型, 显示十六进制数据\n"))
            self.output_data(data, "hex", max_output)
            
        except Exception as e:
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, f"自动检测时出错: {str(e)}\n"))
    
    def output_data(self, data, format_type, max_output):
        """以指定格式输出数据"""
        if format_type == "hex":
            # 十六进制输出
            hex_data = binascii.hexlify(data).decode('utf-8')
            
            # 显示十六进制数据，限制输出大小
            display_data = hex_data
            if len(hex_data) > max_output * 2:
                display_data = hex_data[:max_output * 2] + f" ... (截断，只显示前{max_output}字节)"
                self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "十六进制数据 (截断):\n"))
            else:
                self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "十六进制数据:\n"))
            
            # 格式化输出，每行32个字节
            hex_lines = [display_data[i:i+64] for i in range(0, len(display_data), 64)]
            for line in hex_lines:
                self.parent.after(0, lambda l=line: self.analysis_text.insert(tk.END, l + '\n'))
        
        elif format_type == "bin":
            # 二进制输出
            bin_data = ''.join(f'{byte:08b}' for byte in data)
            
            # 显示二进制数据，限制输出大小
            display_data = bin_data
            if len(bin_data) > max_output * 8:
                display_data = bin_data[:max_output * 8] + f" ... (截断，只显示前{max_output}字节)"
                self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "二进制数据 (截断):\n"))
            else:
                self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "二进制数据:\n"))
            
            # 格式化输出，每行32位
            bin_lines = [display_data[i:i+32] for i in range(0, len(display_data), 32)]
            for i, line in enumerate(bin_lines):
                self.parent.after(0, lambda i=i, l=line: 
                                 self.analysis_text.insert(tk.END, f"{i*4:08X}: {l}\n"))
        
        else:  # ascii
            # ASCII输出
            try:
                ascii_data = data.decode('utf-8', errors='replace')
                
                # 显示ASCII数据，限制输出大小
                display_data = ascii_data
                if len(ascii_data) > max_output:
                    display_data = ascii_data[:max_output] + f"\n... (截断，显示前{max_output}字符)"
                    self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "ASCII数据 (截断):\n"))
                else:
                    self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "ASCII数据:\n"))
                
                self.parent.after(0, lambda d=display_data: self.analysis_text.insert(tk.END, d + '\n'))
            except Exception as e:
                self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "无法解码为ASCII文本，显示十六进制数据:\n"))
                # 尝试以十六进制格式输出
                hex_data = binascii.hexlify(data).decode('utf-8')
                hex_data = hex_data[:max_output * 2] + " ... (截断)" if len(hex_data) > max_output * 2 else hex_data
                hex_lines = [hex_data[i:i+64] for i in range(0, len(hex_data), 64)]
                for line in hex_lines:
                    self.parent.after(0, lambda l=line: self.analysis_text.insert(tk.END, l + '\n'))
    
    def output_png_info(self, data, max_output):
        """输出PNG文件信息"""
        try:
            # 解析PNG块
            if not data.startswith(b'\x89PNG\r\n\x1a\n'):
                self.output_general_binary(data, max_output)
                return
                
            # 跳过文件头
            pos = 8
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "PNG块结构:\n"))
            
            while pos < len(data) and pos < max_output + 8:
                # 读取块长度
                if pos + 4 > len(data):
                    break
                chunk_length = struct.unpack('>I', data[pos:pos+4])[0]
                pos += 4
                
                # 读取块类型
                if pos + 4 > len(data):
                    break
                chunk_type = data[pos:pos+4].decode('ascii')
                pos += 4
                
                # 读取块数据
                if pos + chunk_length > len(data):
                    break
                chunk_data = data[pos:pos+chunk_length]
                pos += chunk_length
                
                # 读取CRC
                if pos + 4 > len(data):
                    break
                crc = struct.unpack('>I', data[pos:pos+4])[0]
                pos += 4
                
                # 输出信息
                self.parent.after(0, lambda t=chunk_type, l=chunk_length: 
                                 self.analysis_text.insert(tk.END, f"\n块: {t}, 长度: {l}\n"))
                
                # 特殊处理IHDR块
                if chunk_type == 'IHDR':
                    width = struct.unpack('>I', chunk_data[0:4])[0]
                    height = struct.unpack('>I', chunk_data[4:8])[0]
                    bit_depth = chunk_data[8]
                    color_type = chunk_data[9]
                    compression = chunk_data[10]
                    filter_method = chunk_data[11]
                    interlace = chunk_data[12]
                    
                    self.parent.after(0, lambda w=width, h=height, b=bit_depth, c=color_type: 
                                     self.analysis_text.insert(tk.END, 
                                     f"尺寸: {w}x{h}, 位深度: {b}, 颜色类型: {c}\n"))
                
                # 特殊处理tEXt块
                if chunk_type == 'tEXt':
                    try:
                        null_pos = chunk_data.find(b'\x00')
                        if null_pos != -1:
                            keyword = chunk_data[:null_pos].decode('ascii')
                            text_data = chunk_data[null_pos+1:]
                            try:
                                text_str = text_data.decode('latin-1')
                                self.parent.after(0, lambda k=keyword, t=text_str: 
                                     self.analysis_text.insert(tk.END, f"关键字: {k}\n内容: {t}\n"))
                            except:
                                self.parent.after(0, lambda k=keyword: 
                                     self.analysis_text.insert(tk.END, f"关键字: {k}\n内容: <二进制数据>\n"))
                    except:
                        pass
                
                # 如果是IEND块，结束
                if chunk_type == 'IEND':
                    break
            
        except Exception as e:
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, f"解析PNG结构时出错: {str(e)}\n"))
            self.output_general_binary(data, max_output)
    
    def output_general_binary(self, data, max_output):
        """输出通用二进制信息"""
        if len(data) > max_output:
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, f"二进制数据 (只显示前{max_output}字节):\n"))
            data = data[:max_output]
        else:
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "二进制数据:\n"))
        
        # 以十六进制格式输出
        hex_data = binascii.hexlify(data).decode('utf-8')
        hex_lines = [hex_data[i:i+64] for i in range(0, len(hex_data), 64)]
        for line in hex_lines:
            self.parent.after(0, lambda l=line: self.analysis_text.insert(tk.END, l + '\n'))
    
    def dump_full_results(self):
        """导出完整的结果到文件"""
        try:
            # 如果没有分析图片，则返回
            if not self.analysis_image:
                return
                
            # 获取图片名称
            img_name = ""
            if self.analysis_image_path:
                img_name = os.path.basename(self.analysis_image_path)
            elif self.analysis_image_url:
                img_name = os.path.basename(self.analysis_image_url)
            else:
                img_name = "未知图片"
            
            # 创建输出目录
            output_dir = os.path.join(os.getcwd(), "隐写分析结果")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 创建文件路径
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"隐写分析_{img_name}_{timestamp}.txt")
            
            # 获取所有通道和位位置
            channels_to_analyze = self.analysis_config["selected_channels"]
            bit_positions = self.analysis_config["selected_bit_positions"]
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"=== 隐写分析结果 ===\n")
                f.write(f"图片来源: {img_name}\n")
                f.write(f"分析时间: {timestamp}\n")
                f.write(f"分析的通道: {', '.join(channels_to_analyze)}\n")
                f.write(f"分析的位位置: {', '.join(bit_positions)}\n\n")
                
                # 确保图片是RGB模式
                img = self.analysis_image
                if img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                else:
                    f.write("错误: 没有加载图片\n")
                    return
                
                # 分离通道
                r, g, b = img.split()
                channels = {
                    'R': r,
                    'G': g,
                    'B': b
                }
                
                # 遍历所有组合
                for channel in channels_to_analyze:
                    for bit_pos in bit_positions:
                        # 提取位数据
                        extracted_bits = []
                        for pixel in channels[channel].getdata():
                            if bit_pos == "LSB":
                                extracted_bits.append(pixel & 1)
                            else:  # MSB
                                extracted_bits.append((pixel >> 7) & 1)
                        
                        # 转换为字节
                        extracted_bytes = []
                        byte = 0
                        bit_count = 0
                        for bit in extracted_bits:
                            byte = (byte << 1) | bit
                            bit_count += 1
                            if bit_count == 8:
                                extracted_bytes.append(byte)
                                byte = 0
                                bit_count = 0
                        
                        if bit_count > 0:
                            byte <<= (8 - bit_count)
                            extracted_bytes.append(byte)
                        
                        extracted_data = bytes(extracted_bytes)
                        
                        # 写入结果
                        f.write(f"\n=== 通道 {channel} - {'LSB' if bit_pos == 'LSB' else 'MSB'} ===\n")
                        f.write(f"数据长度: {len(extracted_data)} 字节\n")
                        
                        hex_data = binascii.hexlify(extracted_data).decode('utf-8')
                        hex_lines = [hex_data[i:i+64] for i in range(0, len(hex_data), 64)]
                        for line in hex_lines:
                            f.write(line + '\n')
                        
                        f.write("\n")
            
            self.parent.after(0, lambda: messagebox.showinfo("成功", f"完整结果已导出到:\n{output_path}"))
        
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"导出完整结果时出错:\n{str(e)}"))


class BinaryToolsModule:
    """二进制工具模块，提供二进制数据处理功能"""
    def __init__(self, parent):
        self.parent = parent
        self.config = parent.config["binary_tools"]
        self.current_file = None
        self.current_data = None
        self.stego_results = None  # 存储隐写分析结果
    
    def init_ui(self, parent_frame):
        """初始化二进制工具选项卡UI"""
        # 主容器
        tools_container = ttk.Frame(parent_frame)
        tools_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 文件选择区域
        file_frame = ttk.Frame(tools_container)
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(file_frame, text="文件路径:").pack(side=tk.LEFT)
        self.file_entry = ttk.Entry(file_frame)
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.browse_button = ttk.Button(file_frame, text="浏览...", command=self.browse_file)
        self.browse_button.pack(side=tk.RIGHT)
        
        # 新增：隐写分析选项
        stego_frame = ttk.LabelFrame(tools_container, text="隐写分析选项")
        stego_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 文件尾分析
        tail_frame = ttk.Frame(stego_frame)
        tail_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(tail_frame, text="文件尾分析大小(字节):").pack(side=tk.LEFT)
        self.tail_size_var = tk.StringVar(value=str(self.config["stego_detection"]["file_tail_size"]))
        tail_size_entry = ttk.Entry(tail_frame, textvariable=self.tail_size_var, width=10)
        tail_size_entry.pack(side=tk.RIGHT, padx=5)
        
        # 文本阈值
        text_frame = ttk.Frame(stego_frame)
        text_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(text_frame, text="文本阈值(0-1):").pack(side=tk.LEFT)
        self.text_threshold_var = tk.StringVar(value=str(self.config["stego_detection"]["text_threshold"]))
        text_threshold_entry = ttk.Entry(text_frame, textvariable=self.text_threshold_var, width=10)
        text_threshold_entry.pack(side=tk.RIGHT, padx=5)
        
        # 熵阈值
        entropy_frame = ttk.Frame(stego_frame)
        entropy_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(entropy_frame, text="熵阈值(0-8):").pack(side=tk.LEFT)
        self.entropy_threshold_var = tk.StringVar(value=str(self.config["stego_detection"]["entropy_threshold"]))
        entropy_threshold_entry = ttk.Entry(entropy_frame, textvariable=self.entropy_threshold_var, width=10)
        entropy_threshold_entry.pack(side=tk.RIGHT, padx=5)
        
        # 分析模式
        mode_frame = ttk.Frame(stego_frame)
        mode_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(mode_frame, text="分析模式:").pack(side=tk.LEFT)
        self.analysis_mode_var = tk.StringVar(value="auto")
        mode_menu = ttk.Combobox(mode_frame, textvariable=self.analysis_mode_var, state="readonly")
        mode_menu['values'] = ['自动检测', '提取文本', '提取二进制', '文件尾分析']
        mode_menu.pack(side=tk.RIGHT, padx=5)
        
        # 分析按钮
        analyze_button_frame = ttk.Frame(tools_container)
        analyze_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.analyze_button = ttk.Button(analyze_button_frame, text="分析隐写", command=self.analyze_stego)
        self.analyze_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.clear_button = ttk.Button(analyze_button_frame, text="清除结果", command=self.clear_results)
        self.clear_button.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)
        
        # 选项区域
        options_frame = ttk.LabelFrame(tools_container, text="转换选项")
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 宽度设置
        width_frame = ttk.Frame(options_frame)
        width_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(width_frame, text="宽度:").pack(side=tk.LEFT)
        self.width_var = tk.StringVar(value=str(self.config["width"]))
        width_spin = ttk.Spinbox(width_frame, from_=10, to=5000, textvariable=self.width_var)
        width_spin.pack(side=tk.RIGHT, padx=5)
        
        # 高度设置
        height_frame = ttk.Frame(options_frame)
        height_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(height_frame, text="高度:").pack(side=tk.LEFT)
        self.height_var = tk.StringVar(value=str(self.config["height"]))
        height_spin = ttk.Spinbox(height_frame, from_=10, to=5000, textvariable=self.height_var)
        height_spin.pack(side=tk.RIGHT, padx=5)
        
        # 颜色模式
        mode_frame = ttk.Frame(options_frame)
        mode_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(mode_frame, text="颜色模式:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value=self.config["mode"])
        mode_menu = ttk.Combobox(mode_frame, textvariable=self.mode_var, state="readonly")
        mode_menu['values'] = ['L (灰度)', 'RGB', 'RGBA']
        mode_menu.pack(side=tk.RIGHT, padx=5)
        
        # 字节顺序
        byte_frame = ttk.Frame(options_frame)
        byte_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.reverse_var = tk.BooleanVar(value=self.config["reverse_bytes"])
        reverse_check = ttk.Checkbutton(byte_frame, text="反转字节顺序", variable=self.reverse_var)
        reverse_check.pack(side=tk.RIGHT, padx=5)
        
        # 按钮区域
        button_frame = ttk.Frame(tools_container)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.convert_button = ttk.Button(button_frame, text="转换为图片", command=self.convert_to_image)
        self.convert_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.save_button = ttk.Button(button_frame, text="保存图片", command=self.save_image, state=tk.DISABLED)
        self.save_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 结果区域
        result_frame = ttk.LabelFrame(tools_container, text="分析结果")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建结果文本框和滚动条
        result_container = ttk.Frame(result_frame)
        result_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(result_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.result_text = tk.Text(result_container, wrap=tk.WORD, height=15, 
                                 yscrollcommand=scrollbar.set)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.result_text.yview)
        
        # 预览区域
        preview_frame = ttk.LabelFrame(tools_container, text="图片预览")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.preview_label = ttk.Label(preview_frame, background="#e0e0e0")
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 进度条
        progress_frame = ttk.Frame(tools_container)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                          mode='determinate')
        self.progress_bar.pack(fill=tk.X)
        self.progress_bar.pack_forget()  # 默认隐藏
    
    def browse_file(self):
        """浏览二进制文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("所有文件", "*.*"), ("二进制文件", "*.bin;*.dat;*.hex")])
        
        if file_path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_path)
            self.current_file = file_path
    
    def handle_drop(self, files):
        """处理拖放文件"""
        if files:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, files[0])
            self.current_file = files[0]
    
    def analyze_stego(self):
        """分析二进制文件中的隐写数据"""
        file_path = self.file_entry.get()
        if not file_path or not os.path.exists(file_path):
            self.parent.after(0, lambda: messagebox.showwarning("警告", "请选择有效的文件"))
            return
        
        try:
            # 读取文件
            with open(file_path, 'rb') as f:
                self.current_data = f.read()
            
            # 获取分析选项
            try:
                tail_size = int(self.tail_size_var.get())
                text_threshold = float(self.text_threshold_var.get())
                entropy_threshold = float(self.entropy_threshold_var.get())
                analysis_mode = self.analysis_mode_var.get()
                
                # 更新配置
                self.parent.config["binary_tools"]["stego_detection"]["file_tail_size"] = tail_size
                self.parent.config["binary_tools"]["stego_detection"]["text_threshold"] = text_threshold
                self.parent.config["binary_tools"]["stego_detection"]["entropy_threshold"] = entropy_threshold
            except:
                tail_size = self.config["stego_detection"]["file_tail_size"]
                text_threshold = self.config["stego_detection"]["text_threshold"]
                entropy_threshold = self.config["stego_detection"]["entropy_threshold"]
                analysis_mode = self.analysis_mode_var.get()
            
            # 清空结果
            self.clear_results()
            self.progress_bar.pack(fill=tk.X)
            self.progress_var.set(0)
            self.parent.update_status("正在分析文件...")
            
            # 在后台线程中执行分析
            analyze_thread = threading.Thread(target=self.perform_stego_analysis, 
                                             args=(analysis_mode, tail_size, text_threshold, entropy_threshold),
                                             daemon=True)
            analyze_thread.start()
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"分析文件时出错: {str(e)}"))
    
    def perform_stego_analysis(self, analysis_mode, tail_size, text_threshold, entropy_threshold):
        """执行隐写分析"""
        try:
            if not self.current_data:
                self.parent.after(0, lambda: self.result_text.insert(tk.END, "错误: 没有加载文件数据\n", "warning"))
                return
            
            self.stego_results = {
                "auto": [],
                "text": None,
                "binary": None,
                "tail": None
            }
            
            total_steps = 4 if analysis_mode == "自动检测" else 1
            step = 0
            
            if analysis_mode == "自动检测" or analysis_mode == "提取文本":
                step += 1
                progress = int((step / total_steps) * 100)
                self.parent.after(0, lambda p=progress: self.progress_var.set(p))
                
                # 提取文本
                text_data = self.extract_text(self.current_data, text_threshold)
                self.stego_results["text"] = text_data
                
                if text_data:
                    self.parent.after(0, lambda d=text_data: self.result_text.insert(tk.END, "=== 文本提取结果 ===\n" + d + "\n"))
            
            if analysis_mode == "自动检测" or analysis_mode == "提取二进制":
                step += 1
                progress = int((step / total_steps) * 100)
                self.parent.after(0, lambda p=progress: self.progress_var.set(p))
                
                # 提取二进制数据
                binary_data = self.extract_binary(self.current_data, entropy_threshold)
                self.stego_results["binary"] = binary_data
                
                if binary_data:
                    self.parent.after(0, lambda: self.result_text.insert(tk.END, "=== 二进制提取结果 ===\n" + binary_data + "\n"))
            
            if analysis_mode == "自动检测" or analysis_mode == "文件尾分析":
                step += 1
                progress = int((step / total_steps) * 100)
                self.parent.after(0, lambda p=progress: self.progress_var.set(p))
                
                # 分析文件尾
                tail_data = self.analyze_file_tail(self.current_data, tail_size, text_threshold, entropy_threshold)
                self.stego_results["tail"] = tail_data
                
                if tail_data:
                    self.parent.after(0, lambda d=tail_data: self.result_text.insert(tk.END, "=== 文件尾分析结果 ===\n" + d + "\n"))
            
            if analysis_mode == "自动检测":
                step += 1
                progress = int((step / total_steps) * 100)
                self.parent.after(0, lambda p=progress: self.progress_var.set(p))
                
                # 自动检测最佳结果
                best_result = self.auto_detect_best_stego()
                if best_result:
                    self.parent.after(0, lambda d=best_result: self.result_text.insert(tk.END, "=== 自动检测最佳结果 ===\n" + d + "\n"))
            
            self.parent.after(0, lambda: self.progress_bar.pack_forget())
            self.parent.update_status("隐写分析完成")
            
        except Exception as e:
            self.parent.after(0, lambda: self.result_text.insert(tk.END, f"分析过程中出错: {str(e)}\n", "warning"))
        finally:
            self.parent.after(0, lambda: self.parent.update_status("隐写分析完成"))
    
    def extract_text(self, data, threshold):
        """从二进制数据中提取文本"""
        if not data:
            return ""
            
        # 尝试不同编码提取文本
        possible_texts = []
        
        # 尝试UTF-8编码
        try:
            text = data.decode('utf-8', errors='replace')
            # 计算可打印字符比例
            printable_ratio = sum(32 <= ord(c) <= 126 for c in text) / len(text) if len(text) > 0 else 0
            if printable_ratio > threshold:
                possible_texts.append(("UTF-8", text, printable_ratio))
        except:
            pass
        
        # 尝试GBK编码
        try:
            text = data.decode('gbk', errors='replace')
            # 计算可打印字符比例
            printable_ratio = sum(32 <= ord(c) <= 126 or 0xA0 <= ord(c) <= 0xFF for c in text) / len(text) if len(text) > 0 else 0
            if printable_ratio > threshold:
                possible_texts.append(("GBK", text, printable_ratio))
        except:
            pass
        
        # 尝试Latin-1编码
        try:
            text = data.decode('latin-1', errors='replace')
            # 计算可打印字符比例
            printable_ratio = sum(32 <= ord(c) <= 126 for c in text) / len(text) if len(text) > 0 else 0
            if printable_ratio > threshold:
                possible_texts.append(("Latin-1", text, printable_ratio))
        except:
            pass
        
        # 如果找到可能的文本，返回最佳结果
        if possible_texts:
            # 按可打印字符比例排序
            possible_texts.sort(key=lambda x: x[2], reverse=True)
            best_encoding, best_text, best_ratio = possible_texts[0]
            
            result = f"编码: {best_encoding}, 可打印比例: {best_ratio:.2f}\n{best_text}"
            return result
        
        return "未找到符合阈值的文本数据"
    
    def extract_binary(self, data, entropy_threshold):
        """从二进制数据中提取可疑二进制数据"""
        if not data:
            return ""
            
        # 计算数据熵
        entropy = self.calculate_entropy(data)
        result = f"数据熵: {entropy:.4f} 比特/字节\n"
        
        if entropy > entropy_threshold:
            result += "警告: 数据熵高于阈值，可能包含隐藏信息\n"
            result += self.format_binary(data)
        else:
            result += "数据熵正常，未发现可疑二进制数据"
        
        return result
    
    def analyze_file_tail(self, data, tail_size, text_threshold, entropy_threshold):
        """分析文件尾部数据"""
        if not data:
            return "文件为空，无法分析"
            
        # 确保tail_size不超过文件大小
        tail_size = min(tail_size, len(data))
        tail_data = data[-tail_size:]
        
        result = f"分析文件尾部 {tail_size} 字节数据:\n"
        
        # 计算熵
        entropy = self.calculate_entropy(tail_data)
        result += f"尾部数据熵: {entropy:.4f} 比特/字节\n"
        
        # 提取文本
        text_result = self.extract_text(tail_data, text_threshold)
        result += f"文本提取结果:\n{text_result}\n"
        
        # 检查是否有异常数据
        if entropy > entropy_threshold:
            result += "警告: 尾部数据熵高于阈值，可能包含隐藏信息\n"
        else:
            result += "尾部数据熵正常\n"
        
        return result
    
    def auto_detect_best_stego(self):
        """自动检测最佳隐写结果"""
        results = []
        
        # 检查文本提取结果
        if self.stego_results["text"] and "未找到" not in self.stego_results["text"]:
            results.append(("文本", self.stego_results["text"]))
        
        # 检查二进制提取结果
        if self.stego_results["binary"] and "未发现" not in self.stego_results["binary"]:
            results.append(("二进制", self.stego_results["binary"]))
        
        # 检查文件尾分析结果
        if self.stego_results["tail"] and ("警告" in self.stego_results["tail"] or "未找到" not in self.stego_results["tail"]):
            results.append(("文件尾", self.stego_results["tail"]))
        
        if results:
            return f"自动检测到可能的隐写数据 (最佳匹配: {results[0][0]}):\n{results[0][1]}"
        
        return "未检测到可疑的隐写数据"
    
    def calculate_entropy(self, data):
        """计算数据的熵"""
        if not data:
            return 0.0
            
        entropy = 0
        total = len(data)
        if total == 0:
            return 0.0
            
        # 计算每个字节的频率
        freq = {}
        for byte in data:
            if byte in freq:
                freq[byte] += 1
            else:
                freq[byte] = 1
        
        # 计算熵
        for count in freq.values():
            p = count / total
            entropy -= p * math.log2(p)
            
        return entropy
    
    def format_binary(self, data):
        """格式化二进制数据为十六进制"""
        hex_data = binascii.hexlify(data).decode('utf-8')
        formatted = ""
        for i in range(0, len(hex_data), 64):
            formatted += hex_data[i:i+64] + "\n"
        return formatted
    
    def convert_to_image(self):
        """将二进制数据转换为图片"""
        file_path = self.file_entry.get()
        if not file_path or not os.path.exists(file_path):
            self.parent.after(0, lambda: messagebox.showwarning("警告", "请选择有效的文件"))
            return
        
        try:
            # 读取文件
            with open(file_path, 'rb') as f:
                self.current_data = f.read()
            
            # 获取参数
            width = int(self.width_var.get())
            height = int(self.height_var.get())
            mode = self.mode_var.get().split(' ')[0]  # 从 "L (灰度)" 中提取 "L"
            reverse = self.reverse_var.get()
            
            # 验证参数
            if width <= 0 or height <= 0:
                raise ValueError("宽度和高度必须是正整数")
            
            # 计算所需数据量
            channels = 1 if mode == 'L' else 3 if mode == 'RGB' else 4
            required_size = width * height * channels
            
            if len(self.current_data) < required_size:
                raise ValueError(f"文件大小不足，需要至少 {required_size} 字节")
            
            # 如果数据太多，截断
            if len(self.current_data) > required_size:
                self.parent.update_status(f"警告: 文件大小({len(self.current_data)}字节)超过所需大小，已截断")
                self.current_data = self.current_data[:required_size]
            
            # 如果指定了反转字节顺序
            if reverse:
                self.current_data = bytes(reversed(self.current_data))
            
            # 创建图像
            img = Image.frombytes(mode, (width, height), self.current_data)
            
            # 显示预览
            max_size = (400, 300)
            preview_img = img.copy()
            preview_img.thumbnail(max_size, Image.LANCZOS)
            preview_img_tk = ImageTk.PhotoImage(preview_img)
            
            self.preview_label.config(image=preview_img_tk)
            self.preview_label.image = preview_img_tk  # 保持引用
            
            self.parent.update_status(f"成功创建 {width}x{height} {mode} 图像")
            self.save_button.config(state=tk.NORMAL)
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"转换失败: {str(e)}"))
    
    def save_image(self):
        """保存生成的图片"""
        if not self.current_data:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可保存的图像"))
            return
        
        try:
            # 获取保存路径
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG 文件", "*.png"), ("JPEG 文件", "*.jpg;*.jpeg"), ("所有文件", "*.*")])
            
            if not file_path:
                return
            
            # 获取参数
            width = int(self.width_var.get())
            height = int(self.height_var.get())
            mode = self.mode_var.get().split(' ')[0]
            
            # 创建图像
            img = Image.frombytes(mode, (width, height), self.current_data)
            
            # 保存图片
            img.save(file_path)
            
            # 更新配置
            self.parent.config["binary_tools"]["width"] = width
            self.parent.config["binary_tools"]["height"] = height
            self.parent.config["binary_tools"]["mode"] = mode
            self.parent.config["binary_tools"]["reverse_bytes"] = self.reverse_var.get()
            
            self.parent.after(0, lambda: messagebox.showinfo("成功", f"图片已保存到:\n{file_path}"))
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"保存图片时出错: {str(e)}"))
    
    def clear_results(self):
        """清除结果区域"""
        self.result_text.delete(1.0, tk.END)


class SettingsModule:
    """设置模块，用于管理应用程序设置"""
    def __init__(self, parent, config):
        self.parent = parent
        self.config = config
    
    def init_ui(self, parent_frame):
        """初始化设置选项卡UI"""
        # 主容器
        settings_container = ttk.Frame(parent_frame)
        settings_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 创建滚动区域
        canvas = tk.Canvas(settings_container)
        scrollbar = ttk.Scrollbar(settings_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 批量扫描设置
        batch_frame = ttk.LabelFrame(scrollable_frame, text="批量扫描设置")
        batch_frame.pack(fill=tk.X, padx=10, pady=10, ipadx=10, ipady=10)
        
        # 排序方式
        sort_frame = ttk.Frame(batch_frame)
        sort_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(sort_frame, text="排序方式:").pack(side=tk.LEFT)
        
        self.sort_var = tk.StringVar(value=self.config["batch_scan"]["sort_order"])
        sort_options = [("不排序", "none"), ("数字顺序", "numeric"), ("字母顺序", "alphabetical")]
        
        sort_buttons_frame = ttk.Frame(sort_frame)
        sort_buttons_frame.pack(side=tk.LEFT, padx=10)
        
        for i, (text, value) in enumerate(sort_options):
            ttk.Radiobutton(sort_buttons_frame, text=text, variable=self.sort_var, 
                            value=value).grid(row=0, column=i, padx=5)
        
        # 详细输出
        self.detailed_var = tk.BooleanVar(value=self.config["batch_scan"]["show_detailed"])
        detailed_check = ttk.Checkbutton(batch_frame, text="详细输出结果", 
                                        variable=self.detailed_var,
                                        command=self.update_settings)
        detailed_check.pack(anchor="w", padx=5, pady=(0, 5))
        
        # 分隔符设置
        separator_frame = ttk.Frame(batch_frame)
        separator_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(separator_frame, text="结果分隔符:").pack(side=tk.LEFT)
        
        self.separator_var = tk.StringVar(value=self.config["batch_scan"]["separator"])
        separator_entry = ttk.Entry(separator_frame, textvariable=self.separator_var, width=20)
        separator_entry.pack(side=tk.LEFT, padx=5)
        separator_entry.bind("<KeyRelease>", self.update_settings)
        
        # 分隔符示例
        example_frame = ttk.Frame(batch_frame)
        example_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(example_frame, text="示例:").pack(side=tk.LEFT)
        self.example_label = ttk.Label(example_frame, text=self.separator_var.get())
        self.example_label.pack(side=tk.LEFT, padx=5)
        
        # 分析设置
        analysis_frame = ttk.LabelFrame(scrollable_frame, text="分析设置")
        analysis_frame.pack(fill=tk.X, padx=10, pady=10, ipadx=10, ipady=10)
        
        # 自动换行
        self.auto_wrap_var = tk.BooleanVar(value=self.config["analysis"]["auto_wrap"])
        wrap_check = ttk.Checkbutton(analysis_frame, text="结果自动换行", 
                                    variable=self.auto_wrap_var,
                                    command=self.update_settings)
        wrap_check.pack(anchor="w", padx=5, pady=5)
        
        # 最大输出字符数
        max_output_frame = ttk.Frame(analysis_frame)
        max_output_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(max_output_frame, text="最大输出字符数:").pack(side=tk.LEFT)
        
        self.max_output_var = tk.StringVar(value=str(self.config["analysis"]["steg_max_output"]))
        max_output_entry = ttk.Entry(max_output_frame, textvariable=self.max_output_var, width=10)
        max_output_entry.pack(side=tk.LEFT, padx=5)
        
        # 隐写分析通道设置
        channel_frame = ttk.Frame(analysis_frame)
        channel_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(channel_frame, text="隐写分析通道:").pack(side=tk.LEFT)
        
        self.channel_vars = {
            'R': tk.BooleanVar(value='R' in self.config["analysis"]["selected_channels"]),
            'G': tk.BooleanVar(value='G' in self.config["analysis"]["selected_channels"]),
            'B': tk.BooleanVar(value='B' in self.config["analysis"]["selected_channels"])
        }
        
        for i, color in enumerate(['R', 'G', 'B']):
            ttk.Checkbutton(channel_frame, text=color, variable=self.channel_vars[color],
                           command=self.update_settings).pack(side=tk.LEFT, padx=5)
        
        # 隐写分析位位置设置
        bit_frame = ttk.Frame(analysis_frame)
        bit_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(bit_frame, text="位位置:").pack(side=tk.LEFT)
        
        self.bit_vars = {
            'LSB': tk.BooleanVar(value='LSB' in self.config["analysis"]["selected_bit_positions"]),
            'MSB': tk.BooleanVar(value='MSB' in self.config["analysis"]["selected_bit_positions"])
        }
        
        for i, bit_pos in enumerate(['LSB', 'MSB']):
            ttk.Checkbutton(bit_frame, text=bit_pos, variable=self.bit_vars[bit_pos],
                           command=self.update_settings).pack(side=tk.LEFT, padx=5)
        
        # 二进制工具设置
        binary_frame = ttk.LabelFrame(scrollable_frame, text="二进制工具设置")
        binary_frame.pack(fill=tk.X, padx=10, pady=10, ipadx=10, ipady=10)
        
        # 默认宽度
        width_frame = ttk.Frame(binary_frame)
        width_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(width_frame, text="默认宽度:").pack(side=tk.LEFT)
        
        self.width_var = tk.StringVar(value=str(self.config["binary_tools"]["width"]))
        width_entry = ttk.Entry(width_frame, textvariable=self.width_var, width=10)
        width_entry.pack(side=tk.LEFT, padx=5)
        
        # 默认高度
        height_frame = ttk.Frame(binary_frame)
        height_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(height_frame, text="默认高度:").pack(side=tk.LEFT)
        
        self.height_var = tk.StringVar(value=str(self.config["binary_tools"]["height"]))
        height_entry = ttk.Entry(height_frame, textvariable=self.height_var, width=10)
        height_entry.pack(side=tk.LEFT, padx=5)
        
        # 默认颜色模式
        mode_frame = ttk.Frame(binary_frame)
        mode_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(mode_frame, text="默认颜色模式:").pack(side=tk.LEFT)
        
        self.mode_var = tk.StringVar(value=self.config["binary_tools"]["mode"])
        mode_menu = ttk.Combobox(mode_frame, textvariable=self.mode_var, state="readonly", width=8)
        mode_menu['values'] = ['L', 'RGB', 'RGBA']
        mode_menu.pack(side=tk.LEFT, padx=5)
        
        # 默认字节顺序
        byte_frame = ttk.Frame(binary_frame)
        byte_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.reverse_var = tk.BooleanVar(value=self.config["binary_tools"]["reverse_bytes"])
        reverse_check = ttk.Checkbutton(byte_frame, text="默认反转字节顺序", 
                                       variable=self.reverse_var,
                                       command=self.update_settings)
        reverse_check.pack(side=tk.LEFT, padx=5)
        
        # 隐写分析设置
        stego_frame = ttk.LabelFrame(scrollable_frame, text="隐写分析设置")
        stego_frame.pack(fill=tk.X, padx=10, pady=10, ipadx=10, ipady=10)
        
        # 文件尾分析大小
        tail_size_frame = ttk.Frame(stego_frame)
        tail_size_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(tail_size_frame, text="文件尾分析大小(字节):").pack(side=tk.LEFT)
        
        self.tail_size_var = tk.StringVar(value=str(self.config["binary_tools"]["stego_detection"]["file_tail_size"]))
        tail_size_entry = ttk.Entry(tail_size_frame, textvariable=self.tail_size_var, width=10)
        tail_size_entry.pack(side=tk.LEFT, padx=5)
        
        # 文本阈值
        text_threshold_frame = ttk.Frame(stego_frame)
        text_threshold_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(text_threshold_frame, text="文本阈值(0-1):").pack(side=tk.LEFT)
        
        self.text_threshold_var = tk.StringVar(value=str(self.config["binary_tools"]["stego_detection"]["text_threshold"]))
        text_threshold_entry = ttk.Entry(text_threshold_frame, textvariable=self.text_threshold_var, width=10)
        text_threshold_entry.pack(side=tk.LEFT, padx=5)
        
        # 熵阈值
        entropy_threshold_frame = ttk.Frame(stego_frame)
        entropy_threshold_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(entropy_threshold_frame, text="熵阈值(0-8):").pack(side=tk.LEFT)
        
        self.entropy_threshold_var = tk.StringVar(value=str(self.config["binary_tools"]["stego_detection"]["entropy_threshold"]))
        entropy_threshold_entry = ttk.Entry(entropy_threshold_frame, textvariable=self.entropy_threshold_var, width=10)
        entropy_threshold_entry.pack(side=tk.LEFT, padx=5)
        
        # 保存按钮
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        save_button = ttk.Button(button_frame, text="保存设置", 
                                command=self.save_settings,
                                style="Accent.TButton")
        save_button.pack(pady=10, ipadx=10, ipady=5)
    
    def update_settings(self, event=None):
        """更新设置预览并保存到内存"""
        # 更新批量扫描设置
        self.config["batch_scan"]["sort_order"] = self.sort_var.get()
        self.config["batch_scan"]["show_detailed"] = self.detailed_var.get()
        self.config["batch_scan"]["separator"] = self.separator_var.get()
        self.example_label.config(text=self.separator_var.get())
        
        # 更新分析设置
        self.config["analysis"]["auto_wrap"] = self.auto_wrap_var.get()
        
        try:
            self.config["analysis"]["steg_max_output"] = int(self.max_output_var.get())
        except:
            self.config["analysis"]["steg_max_output"] = 1024
        
        self.config["analysis"]["selected_channels"] = [c for c in ['R', 'G', 'B'] if self.channel_vars[c].get()]
        self.config["analysis"]["selected_bit_positions"] = [b for b in ['LSB', 'MSB'] if self.bit_vars[b].get()]
        
        # 更新二进制工具设置
        try:
            self.config["binary_tools"]["width"] = int(self.width_var.get())
            self.config["binary_tools"]["height"] = int(self.height_var.get())
        except:
            pass
        
        self.config["binary_tools"]["mode"] = self.mode_var.get()
        self.config["binary_tools"]["reverse_bytes"] = self.reverse_var.get()
        
        # 更新隐写分析设置
        try:
            self.config["binary_tools"]["stego_detection"]["file_tail_size"] = int(self.tail_size_var.get())
            self.config["binary_tools"]["stego_detection"]["text_threshold"] = float(self.text_threshold_var.get())
            self.config["binary_tools"]["stego_detection"]["entropy_threshold"] = float(self.entropy_threshold_var.get())
        except:
            pass
    
    def save_settings(self):
        """保存设置到配置文件"""
        self.parent.save_config()
        messagebox.showinfo("成功", "设置已保存")

if __name__ == "__main__":
    # 创建应用实例
    app = QRScannerApp()
    
    # 应用主题样式
    try:
        # 尝试使用Windows 10/11的现代主题
        app.tk.call("source", "sun-valley.tcl")
        app.tk.call("set_theme", "light")
    except:
        pass
    
    # 运行主循环
    app.mainloop()