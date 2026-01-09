import os
import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, 
                             QScrollArea, QPushButton, QFrame, QGraphicsOpacityEffect)
from PyQt5.QtGui import QPixmap, QCursor, QPainter, QPainterPath
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QEvent

class ClickableLabel(QLabel):
    clicked = pyqtSignal(str) # emit path

    def __init__(self, image_path, size=180, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("border: 3px solid rgba(255, 255, 255, 0.5); border-radius: 15px; background-color: rgba(0,0,0,0.3);")
        
        # Load and verify image
        if os.path.exists(image_path):
            self.set_image(image_path, size)
    
    def set_image(self, path, size):
        pix = QPixmap(path)
        if not pix.isNull():
            # Scale Aspect Fill
            scaled = pix.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            
            # Crop center
            final = QPixmap(size, size)
            final.fill(Qt.transparent)
            p = QPainter(final)
            p.setRenderHint(QPainter.Antialiasing)
            
            # Rounded rect visual clip
            path_draw = QPainterPath()
            path_draw.addRoundedRect(0, 0, size, size, 15, 15)
            p.setClipPath(path_draw)
            
            # Draw center
            x = (size - scaled.width()) // 2
            y = (size - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
            p.end()
            
            self.setPixmap(final)

    def enterEvent(self, event):
        # Hover Effect: Bright Yellow Border + Slightly Lighter Background
        self.setStyleSheet("border: 5px solid #f1c40f; border-radius: 15px; background-color: rgba(255,255,255,0.1);")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet("border: 3px solid rgba(255, 255, 255, 0.5); border-radius: 15px; background-color: rgba(0,0,0,0.3);")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.image_path)


class PhotoSelectorOverlay(QWidget):
    photoSelected = pyqtSignal(str) # Emit path when selected

    def __init__(self, parent=None, images_dir="assets/presenters"):
        super().__init__(parent)
        self.images_dir = images_dir
        
        # Resolve path relative to project root if needed
        if not os.path.isabs(self.images_dir):
            # Assuming this file is in program/ui_components/
            # base = program/ui_components
            base = os.path.dirname(os.path.abspath(__file__)) 
            # root = app folder (parent of program) -> app/program/ui_components/../../ = app/
            root = os.path.dirname(os.path.dirname(base)) 
            self.real_dir = os.path.join(root, self.images_dir)
        else:
            self.real_dir = self.images_dir
            
        self.hide()
        
        # Background
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.90);") # Darker overlay
        
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(50, 50, 50, 50)
        
        # Title
        title = QLabel("選人")
        title.setStyleSheet("color: #f1c40f; font-size: 80px; font-weight: bold; background: transparent; margin-bottom: 30px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QWidget { background: transparent; }
            QScrollBar:vertical { 
                width: 20px; 
                background: #2c3e50; 
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical { 
                background: #95a5a6; 
                min-height: 50px; 
                border-radius: 10px; 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(30)
        self.grid_layout.setAlignment(Qt.AlignCenter)
        
        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, 1) # Expand
        
        # Close Button
        close_btn = QPushButton("關閉 / 取消")
        close_btn.setFixedSize(250, 70)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0392b; color: white; font-size: 28px; 
                border-radius: 35px; border: 3px solid #e74c3c; font-weight: bold;
            }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:pressed { background-color: #a93226; transform: scale(0.98); }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        
        layout.addWidget(close_btn, 0, Qt.AlignCenter)

    def refresh_images(self):
        # Clear existing items
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Check directory
        if not os.path.exists(self.real_dir):
            lbl = QLabel(f"資料夾不存在: {self.real_dir}")
            lbl.setStyleSheet("color: red; font-size: 24px;")
            self.grid_layout.addWidget(lbl, 0, 0)
            return

        files = [f for f in os.listdir(self.real_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
        
        if not files:
            lbl = QLabel("沒有找到照片 (請放入 assets/presenters)")
            lbl.setStyleSheet("color: #ecf0f1; font-size: 24px;")
            self.grid_layout.addWidget(lbl, 0, 0)
            return
            
        # Add items
        row, col = 0, 0
        cols = 5 # 每行 5 張
        
        for f in files:
            full_path = os.path.join(self.real_dir, f)
            lbl = ClickableLabel(full_path, size=200)
            lbl.clicked.connect(self.on_photo_clicked)
            self.grid_layout.addWidget(lbl, row, col)
            
            col += 1
            if col >= cols:
                col = 0
                row += 1

    def on_photo_clicked(self, path):
        # 點擊照片後發送路徑訊號，並關閉視窗
        print(f"[PhotoSelector] Selected: {path}")
        self.photoSelected.emit(path)
        self.hide()
        
    def show_selector(self):
        self.refresh_images() # 每次開啟重新掃描，確保有新照片能讀到
        self.resize(self.parent().size()) # Match parent size
        self.raise_()
        self.show()
