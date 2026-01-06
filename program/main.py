import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from windows.control_window import ControlWindow

if __name__ == '__main__':
    from PyQt5.QtCore import QCoreApplication
    
    # 嘗試設定 PyQt5 Plugin 路徑 (解決打包後或特定環境下圖片/平台錯誤)
    venv_root = os.path.dirname(os.path.dirname(sys.executable))
    plugin_path = os.path.join(venv_root, "Lib", "site-packages", "PyQt5", "Qt5", "plugins")
    
    if os.path.exists(plugin_path):
        QCoreApplication.addLibraryPath(plugin_path)
    
    app = QApplication(sys.argv)
    
    # 建立主視窗 (控制台) - 它會自動建立並管理 DisplayWindow
    control_window = ControlWindow() 
    control_window.show() # 控制台可以一般顯示，不一定要全螢幕
    
    font = QFont("Microsoft JhengHei", 10)
    app.setFont(font)
    
    sys.exit(app.exec_())