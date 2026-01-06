import sys
import os
from PyQt5.QtGui import QColor

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- 配色設定 ---
COLORS = [
    QColor(220, 20, 60),   # 猩紅
    QColor(255, 215, 0),   # 金色
    QColor(178, 34, 34),   # 耐火磚紅
    QColor(218, 165, 32),  # 麒麟金
    QColor(139, 0, 0),     # 深紅
    QColor(238, 232, 170)  # 蒼麒麟色
]
