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

class QRScannerApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("高级二维码扫描与分析工具")
        self.geometry("900x750")
        self.configure(bg="#f0f0f0")
        
        # 初始化模块数据
        self.scan_module = ScanModule(self)
        self.analysis_module = AnalysisModule(self)
        
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
        
        # 初始化各模块UI
        self.scan_module.init_ui(scan_tab)
        self.analysis_module.init_ui(analysis_tab)
        
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
    
    def handle_drop(self, event):
        """处理文件拖放事件，根据当前选项卡决定放入哪个模块"""
        files = event.data.split()
        valid_files = [f for f in files if f.lower().endswith(
            ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'))]
        
        if not valid_files:
            return
        
        # 根据当前选项卡决定放入哪个模块
        current_tab = self.notebook.index(self.notebook.select())
        
        if current_tab == 0:  # 扫描选项卡
            self.scan_module.handle_drop(files)
        else:  # 分析选项卡
            self.analysis_module.handle_drop(files)
    
    def update_status(self, message):
        """更新状态栏"""
        self.status_var.set(message)


class ScanModule:
    """二维码扫描模块，封装扫描相关功能"""
    def __init__(self, parent):
        self.parent = parent
        self.scanning = False
        self.stop_requested = False
        self.current_preview_image = None
        self.current_image_path = None
        self.current_image_url = None
    
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
        
        # 第二行按钮（新增反色按钮）
        row2_frame = ttk.Frame(tool_buttons_frame)
        row2_frame.pack(fill=tk.X)
        
        self.invert_button = ttk.Button(row2_frame, text="反色处理", command=self.invert_image)
        self.invert_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.reset_button = ttk.Button(row2_frame, text="重置图片", command=self.reset_image)
        self.reset_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
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
            file_path = filedialog.askopenfilename(
                initialdir=os.path.dirname(current_path) if current_path else None,
                filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.gif")])
            if file_path:  # 只有当用户选择了文件时才更新
                self.file_entry.delete(0, tk.END)
                self.file_entry.insert(0, file_path)
                if mode == "local":
                    self.current_image_path = file_path
        elif mode == "batch":
            file_paths = filedialog.askopenfilenames(
                initialdir=os.path.dirname(current_path) if current_path else None,
                filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.gif")])
            if file_paths:  # 只有当用户选择了文件时才更新
                self.file_entry.delete(0, tk.END)
                self.file_entry.insert(0, ";".join(file_paths))
    
    def browse_folder(self):
        """打开文件夹对话框选择文件夹"""
        folder_path = filedialog.askdirectory()
        if folder_path:  # 用户选择了文件夹
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, folder_path)
    
    def handle_drop(self, files):
        """处理拖放文件"""
        valid_files = [f for f in files if f.lower().endswith(
            ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'))]
        
        if not valid_files:
            return
        
        if len(valid_files) == 1:
            self.mode_var.set("local")
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, valid_files[0])
            self.current_image_path = valid_files[0]
        else:
            self.mode_var.set("batch")
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, ";".join(valid_files))
        
        self.update_ui()
    
    def scan_qr(self):
        """执行二维码扫描"""
        if self.scanning:
            return
            
        self.scanning = True
        self.stop_requested = False
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
                
                total = len(file_paths)
                self.parent.after(0, lambda: self.progress_bar.pack(fill=tk.X))
                self.progress_var.set(0)
                
                for i, file_path in enumerate(file_paths):
                    if self.stop_requested:
                        break
                        
                    if not file_path.strip():
                        continue
                    
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
                
                total = len(image_files)
                self.parent.after(0, lambda: self.progress_bar.pack(fill=tk.X))
                self.progress_var.set(0)
                
                for i, file_path in enumerate(image_files):
                    if self.stop_requested:
                        break
                        
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
        img = img.convert("L")
        
        # 增强对比度
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        # 增强锐度
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)
        
        # 调整大小（如果太小）
        if img.width < 300 or img.height < 300:
            img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
        
        return img
    
    def scan_image(self, img):
        """扫描图像中的二维码"""
        # 将PIL图像转换为numpy数组供pyzbar使用
        img_array = np.array(img)
        
        # 尝试扫描二维码
        decoded_objs = pyzbar.decode(img_array)
        
        # 如果未找到二维码，尝试使用更激进的阈值
        if not decoded_objs:
            # 应用自适应阈值
            img = img.point(lambda p: p > 128 and 255)
            img_array = np.array(img)
            decoded_objs = pyzbar.decode(img_array)
        
        return decoded_objs
    
    def display_results(self, results, source):
        """显示扫描结果"""
        if not results:
            self.parent.after(0, lambda: self.result_text.insert(tk.END, f"未在 {source} 中找到二维码\n"))
            return
        
        self.parent.after(0, lambda: self.result_text.insert(tk.END, f"在 {source} 中找到 {len(results)} 个二维码:\n"))
        
        for i, obj in enumerate(results):
            try:
                data = obj.data.decode('utf-8')
            except:
                try:
                    data = obj.data.decode('latin-1')
                except:
                    data = str(obj.data)
            
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
            
            self.parent.after(0, lambda: self.result_text.insert(tk.END, "\n" + "-" * 50 + "\n"))
    
    def show_preview(self, img):
        """显示图片预览，仅扫描模块使用此方法，分析模块应使用原始图片预览"""
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
        if self.current_preview_image is None:
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
        if self.current_preview_image is None:
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
        
        # 第二行按钮（新增反色按钮）
        row2_frame = ttk.Frame(tool_buttons_frame)
        row2_frame.pack(fill=tk.X)
        
        self.invert_button = ttk.Button(row2_frame, text="反色处理", command=self.invert_image)
        self.invert_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.reset_button = ttk.Button(row2_frame, text="重置图片", command=self.reset_image)
        self.reset_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 隐写分析区域
        steg_frame = ttk.LabelFrame(analysis_control_frame, text="隐写分析")
        steg_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 通道选择
        channel_frame = ttk.Frame(steg_frame)
        channel_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(channel_frame, text="分析通道:").pack(side=tk.LEFT)
        
        self.channel_var = tk.StringVar(value="all_channels")
        channels = [
            ("LSB - 所有通道", "all_channels_lsb"),
            ("MSB - 所有通道", "all_channels_msb"),
            ("LSB - 单个通道", "single_channel_lsb"),
            ("MSB - 单个通道", "single_channel_msb"),
            ("通道爆破 - 所有组合", "channel_brute_force")
        ]
        
        channel_buttons_frame = ttk.Frame(channel_frame)
        channel_buttons_frame.pack(side=tk.LEFT, padx=10)
        
        for i, (text, value) in enumerate(channels):
            ttk.Radiobutton(channel_buttons_frame, text=text, variable=self.channel_var, 
                            value=value).grid(row=i, column=0, sticky="w", padx=2, pady=2)
        
        # 单个通道选择（仅在选择单个通道时显示）
        self.channel_choice_frame = ttk.Frame(steg_frame)
        self.channel_choice_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(self.channel_choice_frame, text="选择通道:").pack(side=tk.LEFT)
        self.channel_choice = tk.StringVar(value="R")
        channel_options = [("R", "R"), ("G", "G"), ("B", "B")]
        
        for i, (text, value) in enumerate(channel_options):
            ttk.Radiobutton(self.channel_choice_frame, text=text, variable=self.channel_choice, 
                           value=value).pack(side=tk.LEFT, padx=5)
        self.channel_choice_frame.pack_forget()  # 默认为隐藏
        
        # 输出格式
        output_frame = ttk.Frame(steg_frame)
        output_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(output_frame, text="输出格式:").pack(side=tk.LEFT)
        
        self.output_var = tk.StringVar(value="auto")
        formats = [("自动检测", "auto"), ("Hex", "hex"), ("二进制", "bin"), ("ASCII", "ascii")]
        
        format_buttons_frame = ttk.Frame(output_frame)
        format_buttons_frame.pack(side=tk.LEFT, padx=10)
        
        for i, (text, value) in enumerate(formats):
            ttk.Radiobutton(format_buttons_frame, text=text, variable=self.output_var, 
                            value=value).grid(row=0, column=i, padx=5)
        
        # 分析按钮
        button_frame = ttk.Frame(steg_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.steg_button = ttk.Button(button_frame, text="分析隐写", command=self.start_analysis)
        self.steg_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.stop_analysis_button = ttk.Button(button_frame, text="停止分析", command=self.cancel_analysis, state=tk.DISABLED)
        self.stop_analysis_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
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
        
        # 绑定通道选择变化事件
        self.channel_var.trace_add("write", self.update_channel_controls)
    
    def update_channel_controls(self, *args):
        """根据通道选择更新控件显示"""
        channel_mode = self.channel_var.get()
        if channel_mode.startswith("single_channel"):
            self.channel_choice_frame.pack(fill=tk.X, padx=5, pady=5)
        else:
            self.channel_choice_frame.pack_forget()
    
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
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.gif")])
        
        if file_path:  # 只有当用户选择了文件时才更新
            self.analysis_file_entry.delete(0, tk.END)
            self.analysis_file_entry.insert(0, file_path)
    
    def handle_drop(self, files):
        """处理拖放文件"""
        valid_files = [f for f in files if f.lower().endswith(
            ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'))]
        
        if not valid_files:
            return
        
        self.analysis_file_entry.delete(0, tk.END)
        self.analysis_file_entry.insert(0, valid_files[0])
    
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
    
    def show_preview(self, img):
        """分析模块独立的图片预览功能，不进行预处理"""
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
        if self.analysis_image is None:
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
        if self.original_analysis_image is None:
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
        if self.analysis_image is None:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可分析的预览图片"))
            return
        
        try:
            # 清空分析结果区域
            self.analysis_text.delete(1.0, tk.END)
            
            # 获取图片信息
            img = self.analysis_image
            
            # 基本信息
            self.analysis_text.insert(tk.END, "=== 图片基本信息 ===\n", "header")
            # 修复格式显示为None的问题，使用更安全的方式获取格式
            img_format = img.format if hasattr(img, 'format') and img.format else "未知"
            self.analysis_text.insert(tk.END, f"格式: {img_format}\n")
            self.analysis_text.insert(tk.END, f"尺寸: {img.width} x {img.height} 像素\n")
            self.analysis_text.insert(tk.END, f"模式: {img.mode}\n")
            
            # 文件信息
            if self.analysis_image_path:
                try:
                    file_size = os.path.getsize(self.analysis_image_path)
                    file_time = datetime.datetime.fromtimestamp(
                        os.path.getmtime(self.analysis_image_path)
                    ).strftime('%Y-%m-%d %H:%M:%S')
                    self.analysis_text.insert(tk.END, f"文件大小: {file_size} 字节\n")
                    self.analysis_text.insert(tk.END, f"修改时间: {file_time}\n")
                except Exception as e:
                    self.analysis_text.insert(tk.END, f"获取文件信息时出错: {str(e)}\n")
            
            # EXIF 信息
            exif_data = None
            try:
                # 尝试使用新方法
                if hasattr(img, 'getexif'):
                    exif_data = img.getexif()
                # 尝试使用旧方法
                elif hasattr(img, '_getexif'):
                    exif_data = img._getexif()
            except Exception as e:
                self.analysis_text.insert(tk.END, f"获取EXIF信息时出错: {str(e)}\n")
            
            if exif_data:
                self.analysis_text.insert(tk.END, "\n=== EXIF 信息 ===\n", "header")
                for tag_id, value in exif_data.items():
                    tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                    # 处理日期时间
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8')
                        except:
                            value = str(value)
                    elif tag_name in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
                        try:
                            value = datetime.datetime.strptime(value, '%Y:%m:%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            pass
                    self.analysis_text.insert(tk.END, f"{tag_name}: {value}\n")
            
            # PNG 块信息
            if hasattr(img, 'info') and img.info:
                self.analysis_text.insert(tk.END, "\n=== 元数据信息 ===\n", "header")
                for key, value in img.info.items():
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8')
                        except:
                            value = binascii.hexlify(value).decode('utf-8')
                    self.analysis_text.insert(tk.END, f"{key}: {value}\n")
            
            # 计算CRC（仅适用于PNG）
            if img_format == "PNG" and self.analysis_image_path:
                try:
                    with open(self.analysis_image_path, 'rb') as f:
                        data = f.read()
                    # PNG文件以IHDR块开始，计算其CRC
                    if data.startswith(b'\x89PNG\r\n\x1a\n'):
                        # 跳过文件头
                        pos = 8
                        self.analysis_text.insert(tk.END, "\n=== PNG 块信息 ===\n", "header")
                        while pos < len(data):
                            # 读取块长度
                            chunk_length = struct.unpack('>I', data[pos:pos+4])[0]
                            pos += 4
                            
                            # 读取块类型
                            chunk_type = data[pos:pos+4].decode('ascii')
                            pos += 4
                            
                            # 读取块数据
                            chunk_data = data[pos:pos+chunk_length]
                            pos += chunk_length
                            
                            # 读取CRC
                            crc = struct.unpack('>I', data[pos:pos+4])[0]
                            pos += 4
                            
                            # 计算CRC
                            calculated_crc = zlib.crc32(chunk_type.encode('ascii') + chunk_data) & 0xFFFFFFFF
                            
                            # 输出信息
                            self.analysis_text.insert(tk.END, f"\n块: {chunk_type}\n")
                            self.analysis_text.insert(tk.END, f"长度: {chunk_length}\n")
                            self.analysis_text.insert(tk.END, f"存储的CRC: {crc:08X}\n")
                            self.analysis_text.insert(tk.END, f"计算的CRC: {calculated_crc:08X}\n")
                            self.analysis_text.insert(tk.END, f"CRC验证: {'通过' if crc == calculated_crc else '失败'}\n")
                            
                            # 如果是IEND块，结束
                            if chunk_type == 'IEND':
                                break
                except Exception as e:
                    self.analysis_text.insert(tk.END, f"计算CRC时出错: {str(e)}\n")
            
            # 检查可能的隐写迹象
            self.analysis_text.insert(tk.END, "\n=== 隐写分析指示器 ===\n", "header")
            
            # 1. 检查文件大小与图像数据大小的差异
            if self.analysis_image_path:
                try:
                    bands = len(img.getbands())
                    img_data_size = img.width * img.height * bands
                    file_size = os.path.getsize(self.analysis_image_path)
                    size_diff = file_size - img_data_size
                    self.analysis_text.insert(tk.END, f"图像数据大小: {img_data_size} 字节\n")
                    self.analysis_text.insert(tk.END, f"文件大小: {file_size} 字节\n")
                    self.analysis_text.insert(tk.END, f"大小差异: {size_diff} 字节\n")
                    if size_diff > 1024:  # 大于1KB的差异可能表示有隐藏数据
                        self.analysis_text.insert(tk.END, "警告: 文件大小显著大于图像数据大小，可能存在隐藏数据\n", "warning")
                except Exception as e:
                    self.analysis_text.insert(tk.END, f"计算大小差异时出错: {str(e)}\n")
            
            # 2. 检查LSB平面（最低有效位），使用原始图片进行分析
            try:
                # 将图像转换为RGB模式以便分析通道
                if img.mode != 'RGB':
                    rgb_img = img.convert('RGB')
                else:
                    rgb_img = img
                
                r, g, b = rgb_img.split()
                
                # 提取LSB平面
                r_lsb = Image.eval(r, lambda x: (x & 1) * 255)
                g_lsb = Image.eval(g, lambda x: (x & 1) * 255)
                b_lsb = Image.eval(b, lambda x: (x & 1) * 255)
                
                # 计算LSB平面的熵
                r_entropy = self.calculate_entropy(r_lsb)
                g_entropy = self.calculate_entropy(g_lsb)
                b_entropy = self.calculate_entropy(b_lsb)
                
                self.analysis_text.insert(tk.END, f"LSB平面熵 (R): {r_entropy:.4f}\n")
                self.analysis_text.insert(tk.END, f"LSB平面熵 (G): {g_entropy:.4f}\n")
                self.analysis_text.insert(tk.END, f"LSB平面熵 (B): {b_entropy:.4f}\n")
                
                # 正常图像的LSB平面熵通常接近1，隐藏数据可能使熵降低
                if r_entropy < 0.9 or g_entropy < 0.9 or b_entropy < 0.9:
                    self.analysis_text.insert(tk.END, "警告: LSB平面熵较低，可能存在隐写数据\n", "warning")
            
            except Exception as e:
                self.analysis_text.insert(tk.END, f"分析LSB平面时出错: {str(e)}\n")
            
            self.parent.update_status("图片信息分析完成")
        
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"获取图片信息时出错:\n{str(e)}"))
    
    def calculate_entropy(self, img):
        """计算图像的熵"""
        try:
            # 转换为灰度
            if img.mode != 'L':
                img = img.convert('L')
            # 获取直方图
            hist = img.histogram()
            # 计算像素总数
            total_pixels = sum(hist)
            # 计算熵
            entropy = 0.0
            for count in hist:
                if count > 0:
                    probability = count / total_pixels
                    entropy -= probability * math.log2(probability)
            return entropy
        except Exception:
            return 0.0
    
    def start_analysis(self):
        """开始隐写分析，支持通道爆破"""
        if self.analysis_image is None:
            self.parent.after(0, lambda: messagebox.showinfo("提示", "没有可分析的预览图片"))
            return
        
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
        """执行隐写分析，支持通道爆破"""
        try:
            # 获取用户选择的选项
            channel_mode = self.channel_var.get()
            output_format = self.output_var.get()
            
            # 获取图片
            img = self.analysis_image
            
            # 确保图片是RGB模式
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 分离通道
            r, g, b = img.split()
            channels = {
                'R': r,
                'G': g,
                'B': b
            }
            
            # 通道组合列表，用于通道爆破
            channel_combinations = [
                ['R'], ['G'], ['B'],       # 单个通道
                ['R', 'G'], ['R', 'B'], ['G', 'B'],  # 两个通道
                ['R', 'G', 'B']  # 所有三个通道
            ]
            
            # 确定要分析的通道组合
            if channel_mode == "all_channels_lsb":
                channel_combinations = [['R', 'G', 'B']]  # 所有通道LSB
                channel_type = "LSB"
            elif channel_mode == "all_channels_msb":
                channel_combinations = [['R', 'G', 'B']]  # 所有通道MSB
                channel_type = "MSB"
            elif channel_mode == "single_channel_lsb":
                channel = self.channel_choice.get()
                channel_combinations = [[channel]]  # 单个通道LSB
                channel_type = "LSB"
            elif channel_mode == "single_channel_msb":
                channel = self.channel_choice.get()
                channel_combinations = [[channel]]  # 单个通道MSB
                channel_type = "MSB"
            else:  # channel_brute_force
                channel_type = "LSB"  # 通道爆破使用LSB
                self.max_progress = len(channel_combinations) * 2  # 每个组合分析LSB和MSB
            
            # 分析每个通道组合
            self.analysis_text.insert(tk.END, "=== 隐写分析结果 ===\n\n", "header")
            
            for i, channels_to_analyze in enumerate(channel_combinations):
                if self.analysis_cancelled:
                    break
                    
                # 更新进度
                self.analysis_progress = int((i / len(channel_combinations)) * 100)
                self.parent.after(0, lambda p=self.analysis_progress: self.progress_var.set(p))
                self.parent.after(0, lambda: self.parent.update_status(f"分析中: {self.analysis_progress}%"))
                
                # 分析LSB和MSB（仅在通道爆破模式下）
                if channel_mode == "channel_brute_force":
                    for bit_position in ["LSB", "MSB"]:
                        if self.analysis_cancelled:
                            break
                            
                        self.analyze_channel_combination(channels, channels_to_analyze, bit_position, output_format)
                        
                        # 更新进度
                        self.analysis_progress = int(((i * 2 + 1) / (len(channel_combinations) * 2)) * 100)
                        self.parent.after(0, lambda p=self.analysis_progress: self.progress_var.set(p))
                        self.parent.after(0, lambda: self.parent.update_status(f"分析中: {self.analysis_progress}%"))
                else:
                    self.analyze_channel_combination(channels, channels_to_analyze, channel_type, output_format)
            
            self.parent.after(0, lambda: self.progress_bar.pack_forget())
            self.parent.update_status("隐写分析完成")
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("错误", f"分析隐写数据时出错:\n{str(e)}"))
        finally:
            self.parent.after(0, lambda: self.steg_button.config(state=tk.NORMAL))
            self.parent.after(0, lambda: self.stop_analysis_button.config(state=tk.DISABLED))
    
    def analyze_channel_combination(self, channels, channels_to_analyze, bit_position, output_format):
        """分析指定的通道组合"""
        try:
            # 构建通道组合名称
            combo_name = '+'.join(channels_to_analyze)
            bit_name = "LSB" if bit_position == "LSB" else "MSB"
            combo_header = f"=== {combo_name} 通道 - {bit_name} ==="
            
            self.parent.after(0, lambda h=combo_header: self.analysis_text.insert(tk.END, h + "\n", "subheader"))
            
            # 提取每个通道的数据
            all_pixels = []
            for channel in channels_to_analyze:
                all_pixels.extend(list(channels[channel].getdata()))
            
            # 提取位数据
            extracted_bits = []
            for pixel in all_pixels:
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
            
            # 转换为字节数组
            extracted_data = bytes(extracted_bytes)
            
            # 输出结果
            self.parent.after(0, lambda s=f"提取数据大小: {len(extracted_data)} 字节": 
                             self.analysis_text.insert(tk.END, s + "\n"))
            
            # 根据选择的格式输出，自动检测格式
            if output_format == "auto":
                self.auto_detect_format_and_output(extracted_data)
            else:
                self.output_data(extracted_data, output_format)
            
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "\n"))
            
        except Exception as e:
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, f"分析通道组合 {channels_to_analyze} 时出错: {str(e)}\n"))
    
    def auto_detect_format_and_output(self, data):
        """自动检测数据格式并输出"""
        try:
            # 尝试解码为UTF-8
            ascii_data = data.decode('utf-8', errors='replace')
            
            # 检查是否看起来像文本
            text_ratio = sum(32 <= ord(c) <= 126 for c in ascii_data) / len(ascii_data) if len(ascii_data) > 0 else 0
            
            if text_ratio > 0.5:
                # 看起来像文本，以ASCII格式输出
                self.output_data(data, "ascii")
            else:
                # 看起来像二进制数据，以十六进制格式输出
                self.output_data(data, "hex")
        except:
            # 解码失败，以十六进制格式输出
            self.output_data(data, "hex")
    
    def output_data(self, data, format_type):
        """以指定格式输出数据"""
        if format_type == "hex":
            # 十六进制输出
            hex_data = binascii.hexlify(data).decode('utf-8')
            
            # 完整输出所有数据
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "十六进制数据:\n"))
            
            # 格式化输出，每行32个字节
            hex_lines = [hex_data[i:i+64] for i in range(0, len(hex_data), 64)]
            for line in hex_lines:
                self.parent.after(0, lambda l=line: self.analysis_text.insert(tk.END, l + '\n'))
        
        elif format_type == "bin":
            # 二进制输出
            bin_data = ''.join(f'{byte:08b}' for byte in data)
            
            # 完整输出所有数据
            self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "二进制数据:\n"))
            
            # 格式化输出，每行32位
            bin_lines = [bin_data[i:i+32] for i in range(0, len(bin_data), 32)]
            for i, line in enumerate(bin_lines):
                self.parent.after(0, lambda i=i, l=line: 
                                 self.analysis_text.insert(tk.END, f"{i*4:08X}: {l}\n"))
        
        else:  # ascii
            # ASCII输出
            try:
                ascii_data = data.decode('utf-8', errors='replace')
                self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "ASCII数据:\n"))
                
                # 完整输出所有数据
                if len(ascii_data) > 1024:
                    ascii_data = ascii_data[:1024] + "\n... (截断，显示前1024字符)"
                self.parent.after(0, lambda d=ascii_data: self.analysis_text.insert(tk.END, d + '\n'))
            except Exception as e:
                self.parent.after(0, lambda: self.analysis_text.insert(tk.END, "无法解码为ASCII文本，显示十六进制数据:\n"))
                # 尝试以十六进制格式输出
                hex_data = binascii.hexlify(data).decode('utf-8')
                hex_lines = [hex_data[i:i+64] for i in range(0, len(hex_data), 64)]
                for line in hex_lines:
                    self.parent.after(0, lambda l=line: self.analysis_text.insert(tk.END, l + '\n'))

if __name__ == "__main__":
    app = QRScannerApp()
    app.mainloop()
