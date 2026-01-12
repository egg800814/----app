"""
config.py
---------
描述：全域設定與工具函式庫。
功能：
      1. 定義應用程式共用的常數 (如 COLORS 配色表)。
      2. 提供資源路徑解析函式 (resource_path)，解決開發環境與打包環境 (PyInstaller) 的路徑差異問題。
"""
import sys
import os
from PyQt5.QtGui import QColor

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller 
        Prioritizes external assets folder next to the executable when frozen """
    if getattr(sys, 'frozen', False):
        # PyInstaller mode: Check external folder first (next to .exe)
        base_path = os.path.dirname(sys.executable)
        external_path = os.path.join(base_path, relative_path)
        if os.path.exists(external_path):
            return external_path
            
        # Fallback to bundled resource
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
            
        return external_path
    else:
        # Dev mode
        return os.path.abspath(relative_path)

# --- 配色設定 ---
COLORS = [
    QColor(220, 20, 60),   # 猩紅
    QColor(255, 215, 0),   # 金色
    QColor(178, 34, 34),   # 耐火磚紅
    QColor(218, 165, 32),  # 麒麟金
    QColor(139, 0, 0),     # 深紅
    QColor(238, 232, 170)  # 蒼麒麟色
]
