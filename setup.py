# setup.py
from cx_Freeze import setup, Executable
import sys

base = None
if sys.platform == "win32":
    base = "Win32GUI"  # 不显示命令行窗口

executables = [
    Executable(
        script="qrcode-v2.py",
        base=base,
        target_name="QRCodeTool.exe",  # 可执行文件名称
        icon="scaner.png"  # 可选：应用图标
    )
]

packages = ["tkinter", "tkinterdnd2", "PIL", "pyzbar", "numpy", "requests"]
options = {
    'build_exe': {
        'packages': packages,
        'include_files': [
            ('scaner.png', 'images'),  # 资源文件
            ('scaner.png', 'icons')
        ],
    },
}

setup(
    name="QRScannerApp",
    options=options,
    version="1.0",
    description="高级二维码扫描与分析工具",
    executables=executables
)