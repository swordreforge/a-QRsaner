import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image, ImageTk, ImageOps, ImageEnhance
import requests
from io import BytesIO
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol  # 导入正确的符号类型
import numpy as np
import os
import re
import webbrowser
import threading
import cv2
import qrcode
from pyzxing import BarCodeReader
import time
import queue
import traceback

class QRScannerApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("高级二维码扫描工具")
        self.geometry("1000x750")
        self.configure(bg="#f0f0f0")
        
        # 创建主框架
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 创建左侧控制面板
        control_frame = ttk.LabelFrame(main_frame, text="扫描选项")
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=10)
        
        # 模式选择
        ttk.Label(control_frame, text="扫描模式:").grid(row=0, column=0, sticky="w", pady=(10, 5))
        self.mode_var = tk.StringVar(value="local")
        modes = [("本地图片", "local"), ("网络图片", "web"), ("批量扫描", "batch"), ("文件夹扫描", "folder")]
        for i, (text, value) in enumerate(modes):
            ttk.Radiobutton(control_frame, text=text, variable=self.mode_var, 
                            value=value, command=self.update_ui).grid(
                                row=i+1, column=0, sticky="w", padx=10)
        
        # 二维码类型选择
        ttk.Label(control_frame, text="二维码类型:").grid(row=5, column=0, sticky="w", pady=(20, 5))
        self.code_type_var = tk.StringVar(value="auto")
        code_types = [("自动检测", "auto"), 
                     ("标准QR码", "qrcode"), 
                     ("汉信码", "hanxin"),
                     ("Data Matrix", "datamatrix"),
                     ("PDF417", "pdf417"),
                     ("Aztec", "aztec")]
        
        for i, (text, value) in enumerate(code_types):
            ttk.Radiobutton(control_frame, text=text, variable=self.code_type_var, 
                            value=value).grid(row=i+6, column=0, sticky="w", padx=10, pady=2)
        
        # 文件选择区域
        ttk.Label(control_frame, text="文件路径:").grid(row=12, column=0, sticky="w", pady=(20, 5))
        self.file_entry = ttk.Entry(control_frame, width=30)
        self.file_entry.grid(row=13, column=0, padx=10, sticky="ew")
        self.browse_button = ttk.Button(control_frame, text="浏览...", command=self.browse_files)
        self.browse_button.grid(row=13, column=1, padx=(5, 10))
        
        # 文件夹浏览按钮
        self.folder_button = ttk.Button(control_frame, text="选择文件夹", command=self.browse_folder)
        self.folder_button.grid(row=13, column=2, padx=(0, 10))
        
        # URL输入区域
        ttk.Label(control_frame, text="图片URL:").grid(row=14, column=0, sticky="w", pady=(20, 5))
        self.url_entry = ttk.Entry(control_frame, width=30)
        self.url_entry.grid(row=15, column=0, columnspan=2, padx=10, sticky="ew")
        
        # 网络超时设置
        ttk.Label(control_frame, text="网络超时(秒):").grid(row=16, column=0, sticky="w", pady=(10, 5))
        self.timeout_var = tk.StringVar(value="15")
        timeout_entry = ttk.Entry(control_frame, textvariable=self.timeout_var, width=8)
        timeout_entry.grid(row=16, column=1, padx=(5, 10), sticky="w")
        
        # 扫描按钮
        self.scan_button = ttk.Button(control_frame, text="扫描二维码", command=self.scan_qr, 
                   style="Accent.TButton")
        self.scan_button.grid(row=17, column=0, columnspan=2, pady=20)
        
        # 停止扫描按钮
        self.stop_button = ttk.Button(control_frame, text="停止扫描", command=self.stop_scan, 
                   style="Stop.TButton", state=tk.DISABLED)
        self.stop_button.grid(row=17, column=2, pady=20, padx=(0, 10))
        
        # 创建右侧结果面板
        result_frame = ttk.LabelFrame(main_frame, text="扫描结果")
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
        
        self.preview_label = ttk.Label(preview_frame)
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(result_frame, variable=self.progress_var, 
                                           mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.progress_bar.pack_forget()  # 默认隐藏
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 配置样式
        self.style = ttk.Style()
        self.style.configure("Accent.TButton", foreground="white", background="#4CAF50")
        self.style.configure("Stop.TButton", foreground="white", background="#F44336")
        self.style.configure("TButton", padding=6)
        
        # 初始化UI状态
        self.update_ui()
        
        # 设置拖放功能
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.handle_drop)
        
        # 添加右键菜单
        self.create_context_menu()
        
        # 扫描控制变量
        self.scanning = False
        self.stop_requested = False
        self.thread_queue = queue.Queue()
        
        # 初始化汉信码识别器
        self.hanxin_reader = BarCodeReader()
        
        # 定期检查线程状态
        self.after(100, self.process_thread_queue)
    
    def process_thread_queue(self):
        """定期检查线程队列中的任务状态"""
        try:
            while True:
                # 从队列中获取任务，不阻塞
                task = self.thread_queue.get_nowait()
                task()  # 执行任务
        except queue.Empty:
            pass
        self.after(100, self.process_thread_queue)
    
    def create_context_menu(self):
        """创建右键菜单"""
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="复制", command=self.copy_text)
        self.context_menu.add_command(label="清空结果", command=self.clear_results)
        self.context_menu.add_command(label="保存结果", command=self.save_results)
        self.result_text.bind("<Button-3>", self.show_context_menu)
    
    def save_results(self):
        """保存扫描结果到文件"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.result_text.get("1.0", tk.END))
            self.status_var.set(f"结果已保存到: {file_path}")
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        self.context_menu.post(event.x_root, event.y_root)
    
    def copy_text(self):
        """复制选中文本"""
        selected = self.result_text.get(tk.SEL_FIRST, tk.SEL_LAST)
        if selected:
            self.clipboard_clear()
            self.clipboard_append(selected)
    
    def clear_results(self):
        """清空结果区域"""
        self.result_text.delete(1.0, tk.END)
        self.clear_preview()
    
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
    
    def update_ui(self):
        """根据选择的模式更新UI"""
        mode = self.mode_var.get()
        
        if mode == "local":
            self.file_entry.config(state=tk.NORMAL)
            self.url_entry.config(state=tk.DISABLED)
            self.browse_button.grid()
            self.folder_button.grid_remove()
        elif mode == "web":
            self.file_entry.config(state=tk.DISABLED)
            self.url_entry.config(state=tk.NORMAL)
            self.browse_button.grid_remove()
            self.folder_button.grid_remove()
        elif mode == "batch":
            self.file_entry.config(state=tk.NORMAL)
            self.url_entry.config(state=tk.DISABLED)
            self.browse_button.grid()
            self.folder_button.grid_remove()
        else:  # folder
            self.file_entry.config(state=tk.NORMAL)
            self.url_entry.config(state=tk.DISABLED)
            self.browse_button.grid_remove()
            self.folder_button.grid()
    
    def browse_files(self):
        """打开文件对话框选择文件"""
        mode = self.mode_var.get()
        current_path = self.file_entry.get()
        
        if mode == "local":
            file_path = filedialog.askopenfilename(
                initialdir=os.path.dirname(current_path) if current_path else None,
                filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.gif")])
            if file_path:  # 只有当用户选择了文件时才更新
                self.file_entry.delete(0, tk.END)
                self.file_entry.insert(0, file_path)
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
    
    def handle_drop(self, event):
        """处理文件拖放事件"""
        files = event.data.split()
        valid_files = [f for f in files if f.lower().endswith(
            ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'))]
        
        if not valid_files:
            return
        
        if len(valid_files) == 1:
            self.mode_var.set("local")
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, valid_files[0])
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
                    self.thread_queue.put(lambda: messagebox.showwarning("警告", "请选择要扫描的图片文件"))
                    return
                
                self.process_image(file_path)
            
            elif mode == "web":
                url = self.url_entry.get()
                if not url:
                    self.thread_queue.put(lambda: messagebox.showwarning("警告", "请输入图片URL"))
                    return
                
                # 在单独的线程中处理网络图片下载
                web_thread = threading.Thread(target=self.process_web_image, args=(url,), daemon=True)
                web_thread.start()
            
            elif mode == "batch":
                file_paths = self.file_entry.get().split(";")
                if not any(file_paths):
                    self.thread_queue.put(lambda: messagebox.showwarning("警告", "请选择要扫描的图片文件"))
                    return
                
                total = len(file_paths)
                self.thread_queue.put(lambda: self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 5)))
                self.thread_queue.put(lambda: self.progress_var.set(0))
                
                for i, file_path in enumerate(file_paths):
                    if self.stop_requested:
                        break
                        
                    if not file_path.strip():
                        continue
                    
                    text = f"\n\n--- 文件 {i+1}/{total}: {os.path.basename(file_path)} ---\n"
                    self.thread_queue.put(lambda t=text: self.result_text.insert(tk.END, t))
                    self.process_image(file_path.strip())
                    
                    # 更新进度
                    progress = (i + 1) / total * 100
                    self.thread_queue.put(lambda p=progress: self.progress_var.set(p))
                    status = f"处理中: {i+1}/{total} ({progress:.1f}%)"
                    self.thread_queue.put(lambda s=status: self.status_var.set(s))
                
                self.thread_queue.put(lambda: self.progress_bar.pack_forget())
            
            elif mode == "folder":
                folder_path = self.file_entry.get()
                if not folder_path or not os.path.isdir(folder_path):
                    self.thread_queue.put(lambda: messagebox.showwarning("警告", "请选择要扫描的文件夹"))
                    return
                
                # 获取所有图片文件
                image_files = self.get_image_files(folder_path)
                if not image_files:
                    self.thread_queue.put(lambda: messagebox.showinfo("提示", "该文件夹下未找到图片文件"))
                    return
                
                total = len(image_files)
                self.thread_queue.put(lambda: self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 5)))
                self.thread_queue.put(lambda: self.progress_var.set(0))
                
                for i, file_path in enumerate(image_files):
                    if self.stop_requested:
                        break
                        
                    text = f"\n\n--- 文件 {i+1}/{total}: {os.path.relpath(file_path, folder_path)} ---\n"
                    self.thread_queue.put(lambda t=text: self.result_text.insert(tk.END, t))
                    self.process_image(file_path)
                    
                    # 更新进度
                    progress = (i + 1) / total * 100
                    self.thread_queue.put(lambda p=progress: self.progress_var.set(p))
                    status = f"处理中: {i+1}/{total} ({progress:.1f}%)"
                    self.thread_queue.put(lambda s=status: self.status_var.set(s))
                
                self.thread_queue.put(lambda: self.progress_bar.pack_forget())
        
        except Exception as e:
            error_msg = f"扫描过程中发生错误:\n{str(e)}\n{traceback.format_exc()}"
            self.thread_queue.put(lambda: self.status_var.set(f"错误: {str(e)}"))
            self.thread_queue.put(lambda: messagebox.showerror("错误", error_msg))
        finally:
            self.scanning = False
            self.stop_requested = False
            self.thread_queue.put(lambda: self.scan_button.config(state=tk.NORMAL))
            self.thread_queue.put(lambda: self.stop_button.config(state=tk.DISABLED))
            self.thread_queue.put(lambda: self.status_var.set("扫描完成"))
    
    def stop_scan(self):
        """停止扫描"""
        self.stop_requested = True
        self.status_var.set("正在停止...")
    
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
            # 打开并显示图片
            img = Image.open(file_path)
            self.thread_queue.put(lambda i=img: self.show_preview(i))
            
            # 处理并扫描二维码
            processed_img = self.preprocess_image(img)
            results = self.scan_image(processed_img, file_path)
            
            # 显示结果
            self.thread_queue.put(lambda r=results, s=os.path.basename(file_path): self.display_results(r, s))
            self.thread_queue.put(lambda: self.status_var.set(f"扫描完成: {os.path.basename(file_path)}"))
        
        except Exception as e:
            error_msg = f"错误: {str(e)}\n"
            self.thread_queue.put(lambda msg=error_msg: self.result_text.insert(tk.END, msg))
            self.thread_queue.put(lambda: self.status_var.set(f"扫描失败: {os.path.basename(file_path)}"))
    
    def process_web_image(self, url):
        """处理网络图片 - 在单独的线程中执行"""
        try:
            self.thread_queue.put(lambda: self.status_var.set(f"正在下载图片: {url}"))
            
            # 获取超时设置
            try:
                timeout = int(self.timeout_var.get())
            except ValueError:
                timeout = 15
                
            # 下载图片（带超时）
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            
            # 打开并显示图片
            img = Image.open(BytesIO(response.content))
            self.thread_queue.put(lambda i=img: self.show_preview(i))
            
            # 处理并扫描二维码
            processed_img = self.preprocess_image(img)
            results = self.scan_image(processed_img, url)
            
            # 显示结果
            self.thread_queue.put(lambda r=results: self.display_results(r, url))
            self.thread_queue.put(lambda: self.status_var.set(f"扫描完成: {url}"))
        
        except requests.exceptions.Timeout:
            error_msg = f"下载超时: {url}\n"
            self.thread_queue.put(lambda msg=error_msg: self.result_text.insert(tk.END, msg))
            self.thread_queue.put(lambda: self.status_var.set(f"下载超时: {url}"))
        except requests.exceptions.RequestException as e:
            error_msg = f"网络错误: {str(e)}\n"
            self.thread_queue.put(lambda msg=error_msg: self.result_text.insert(tk.END, msg))
            self.thread_queue.put(lambda: self.status_var.set(f"网络错误: {url}"))
        except Exception as e:
            error_msg = f"错误: {str(e)}\n"
            self.thread_queue.put(lambda msg=error_msg: self.result_text.insert(tk.END, msg))
            self.thread_queue.put(lambda: self.status_var.set(f"扫描失败: {url}"))
        finally:
            # 确保最终恢复按钮状态
            self.scanning = False
            self.stop_requested = False
            self.thread_queue.put(lambda: self.scan_button.config(state=tk.NORMAL))
            self.thread_queue.put(lambda: self.stop_button.config(state=tk.DISABLED))
    
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
    
    def scan_image(self, img, source):
        """扫描图像中的二维码，支持多种格式"""
        code_type = self.code_type_var.get()
        results = []
        
        # 将PIL图像转换为OpenCV格式
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        # 自动检测模式
        if code_type == "auto":
            # 尝试使用pyzbar检测所有支持的格式
            img_array = np.array(img)
            decoded_objs = pyzbar.decode(img_array)
            results.extend(decoded_objs)
            
            # 如果没有检测到结果，尝试汉信码
            if not results:
                self.thread_queue.put(lambda: self.status_var.set(f"尝试汉信码检测: {source}"))
                hanxin_results = self.detect_hanxin(img_cv)
                results.extend(hanxin_results)
            
            # 如果还是没有结果，尝试其他方法
            if not results:
                self.thread_queue.put(lambda: self.status_var.set(f"尝试增强检测: {source}"))
                # 应用自适应阈值
                img_enhanced = img.point(lambda p: p > 128 and 255)
                img_array = np.array(img_enhanced)
                decoded_objs = pyzbar.decode(img_array)
                results.extend(decoded_objs)
        
        # 特定类型检测
        else:
            if code_type == "hanxin":
                self.thread_queue.put(lambda: self.status_var.set(f"检测汉信码: {source}"))
                results.extend(self.detect_hanxin(img_cv))
            else:
                # 设置pyzbar只检测特定类型
                img_array = np.array(img)
                try:
                    # 映射类型名称到pyzbar常量
                    type_mapping = {
                        "qrcode": ZBarSymbol.QRCODE,
                        "datamatrix": ZBarSymbol.DATAMATRIX,
                        "pdf417": ZBarSymbol.PDF417,
                        "aztec": ZBarSymbol.AZTEC
                    }
                    symbol = type_mapping.get(code_type, ZBarSymbol.QRCODE)
                    
                    decoded_objs = pyzbar.decode(img_array, symbols=[symbol])
                    results.extend(decoded_objs)
                    
                    # 如果没有结果，尝试增强图像
                    if not results:
                        self.thread_queue.put(lambda: self.status_var.set(f"尝试增强检测: {source}"))
                        img_enhanced = img.point(lambda p: p > 128 and 255)
                        img_array = np.array(img_enhanced)
                        decoded_objs = pyzbar.decode(img_array, symbols=[symbol])
                        results.extend(decoded_objs)
                except Exception as e:
                    error_msg = f"检测错误: {str(e)}\n"
                    self.thread_queue.put(lambda msg=error_msg: self.result_text.insert(tk.END, msg))
        
        return results
    
    def detect_hanxin(self, img_cv):
        """使用专用库检测汉信码"""
        results = []
        try:
            # 保存临时图像文件
            temp_file = "temp_hanxin.jpg"
            cv2.imwrite(temp_file, img_cv)
            
            # 使用pyzxing检测汉信码
            decoded = self.hanxin_reader.decode(temp_file)
            
            # 处理结果
            if decoded and 'raw' in decoded:
                # 创建类似pyzbar的结果对象
                from collections import namedtuple
                QRCode = namedtuple('QRCode', ['type', 'data', 'rect', 'polygon'])
                
                # 尝试提取位置信息
                points = decoded.get('points', [])
                if points:
                    rect = (min(p[0] for p in points), 
                            min(p[1] for p in points),
                            max(p[0] for p in points) - min(p[0] for p in points),
                            max(p[1] for p in points) - min(p[1] for p in points))
                    polygon = [(p[0], p[1]) for p in points]
                else:
                    rect = (0, 0, img_cv.shape[1], img_cv.shape[0])
                    polygon = []
                
                result = QRCode(
                    type="HANXIN",
                    data=decoded['raw'].encode('utf-8'),
                    rect=rect,
                    polygon=polygon
                )
                results.append(result)
            
            # 清理临时文件
            os.remove(temp_file)
            
        except Exception as e:
            error_msg = f"汉信码检测错误: {str(e)}\n"
            self.thread_queue.put(lambda msg=error_msg: self.result_text.insert(tk.END, msg))
        
        return results
    
    def display_results(self, results, source):
        """显示扫描结果"""
        if not results:
            self.result_text.insert(tk.END, f"未在 {source} 中找到二维码\n")
            return
        
        self.result_text.insert(tk.END, f"在 {source} 中找到 {len(results)} 个二维码:\n")
        
        for i, obj in enumerate(results):
            try:
                data = obj.data.decode('utf-8')
            except:
                try:
                    data = obj.data.decode('latin-1')
                except:
                    data = str(obj.data)
            
            self.result_text.insert(tk.END, f"\n二维码 {i+1}:\n")
            self.result_text.insert(tk.END, f"类型: {obj.type}\n")
            self.result_text.insert(tk.END, "内容:\n")
            
            # 检查内容是否为URL
            if data.startswith(('http://', 'https://')):
                self.result_text.insert(tk.END, data, "hyperlink")
            else:
                self.result_text.insert(tk.END, data)
            
            self.result_text.insert(tk.END, "\n" + "-" * 50 + "\n")
    
    def show_preview(self, img):
        """显示图片预览"""
        # 调整图片大小以适应预览区域
        max_size = (400, 300)
        img.thumbnail(max_size, Image.LANCZOS)
        
        # 转换为PhotoImage
        self.preview_img = ImageTk.PhotoImage(img)
        self.preview_label.config(image=self.preview_img)
    
    def clear_preview(self):
        """清除图片预览"""
        self.preview_label.config(image='')
        self.preview_img = None

if __name__ == "__main__":
    app = QRScannerApp()
    app.mainloop()
