import os
import sys
from PyQt5.QtWidgets import (QWidget, QApplication, QVBoxLayout, QGridLayout, QLabel, 
                             QScrollArea, QPushButton, QFrame, QGraphicsOpacityEffect, QGraphicsDropShadowEffect)
from PyQt5.QtGui import QPixmap, QCursor, QPainter, QPainterPath, QColor
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QEvent

class ClickableLabel(QLabel):
    clicked = pyqtSignal(str) # emit path

    def __init__(self, image_path, size=180, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        # Keep photo fully opaque, use a solid white border so it pops on the dim background
        self.setStyleSheet("border: 4px solid rgba(255, 255, 255, 1); border-radius: 15px; background: transparent;")
        
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
        # Hover Effect: Bright Yellow Border (no translucent overlay so photo stays bright)
        self.setStyleSheet("border: 5px solid #f1c40f; border-radius: 15px; background: transparent;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet("border: 4px solid rgba(255, 255, 255, 1); border-radius: 15px; background: transparent;")
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

        # Dim background (lightbox) — keep as child widget overlay, slightly stronger dim
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.8);")

        # Main Layout (overlay)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(50, 50, 50, 50)

        # Create a centered panel that visually separates the photo grid from the dim background
        panel = QFrame()
        panel.setObjectName('photoPanel')
        panel.setStyleSheet('background-color: rgba(0, 0, 0, 0.85); border-radius: 20px;')
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(40, 40, 40, 40)
        panel_layout.setSpacing(20)

        # Soft drop shadow for the panel
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 200))
        panel.setGraphicsEffect(shadow)

        # Title (bright)
        title = QLabel("選人")
        title.setStyleSheet("color: #f1c40f; font-size: 80px; font-weight: bold; background: transparent; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        panel_layout.addWidget(title, 0, Qt.AlignCenter)

        # Scroll Area (contains grid)
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
        panel_layout.addWidget(scroll, 1)

        # Close Button
        close_btn = QPushButton("關閉 / 取消")
        close_btn.setFixedSize(250, 70)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0392b; color: white; font-size: 28px; 
                border-radius: 35px; border: 3px solid #e74c3c; font-weight: bold;
            }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:pressed { background-color: #a93226; }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        panel_layout.addWidget(close_btn, 0, Qt.AlignCenter)

        layout.addWidget(panel)

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
        # Ensure the overlay covers the full parent (top-level) window and stays on top
        parent_window = None
        if self.parent() is not None:
            parent_window = self.parent().window()

        # As a child overlay: match parent size and show on top of siblings
        parent = self.parent()
        if parent is not None:
            self.resize(parent.size())
            # ensure the overlay is visually above other children
            self.raise_()
            self.show()
        else:
            # Fallback behavior: just show normally
            self.raise_()
            self.show()
