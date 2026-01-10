import os
import sys
from PyQt5.QtWidgets import (QWidget, QApplication, QVBoxLayout, QGridLayout, QLabel, 
                             QScrollArea, QPushButton, QFrame, QGraphicsOpacityEffect, QGraphicsDropShadowEffect)
from PyQt5.QtGui import QPixmap, QCursor, QPainter, QPainterPath, QColor
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QEvent
from PyQt5.QtCore import QPropertyAnimation

# -----------------------------
# Tunable interaction parameters
# - BORDER_WIDTH: keep constant to avoid layout shifts when hovering
# - HOVER_BORDER_COLOR: color of highlighted border
# - DIM_OPACITY: opacity applied to non-hovered photos
# - ANIM_DURATION_MS: animation duration for opacity transitions (reduce for snappier response)
# Modify these values below to tweak responsiveness and visual strength.
# -----------------------------
BORDER_WIDTH = 4
HOVER_BORDER_COLOR = "#f1c40f"
DIM_OPACITY = 0.4
ANIM_DURATION_MS = 60

class SelectablePhoto(QLabel):
    hovered = pyqtSignal(object)  # emit self
    unhovered = pyqtSignal(object)
    clicked = pyqtSignal(str)

    def __init__(self, image_path, size=180, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.base_size = size
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("border: 4px solid rgba(255, 255, 255, 1); border-radius: 15px; background: transparent;")

        # Do not attach a persistent QGraphicsOpacityEffect here because
        # Qt may take ownership and delete it when another effect is set.
        # We'll create effects on-demand when dimming/restoring.

        # Note: do NOT create a persistent QGraphicsDropShadowEffect here.
        # We'll create a fresh shadow effect when hovered to avoid Qt ownership/deletion issues.

        # store current pixmap for fast scaled display
        self._raw_pix = None
        self._display_pix = None
        if os.path.exists(image_path):
            # pre-render a slightly larger pixmap to allow smooth scaling down/up
            render_size = int(self.base_size * 1.2)
            self.set_image(image_path, render_size)
            if self._raw_pix:
                # set scaled contents so QLabel will scale pixmap with widget size
                self.setScaledContents(True)
                self.setPixmap(self._display_pix.scaled(self.base_size, self.base_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def set_image(self, path, size):
        pix = QPixmap(path)
        if pix and not pix.isNull():
            self._raw_pix = pix
            scaled = pix.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            final = QPixmap(size, size)
            final.fill(Qt.transparent)
            p = QPainter(final)
            p.setRenderHint(QPainter.Antialiasing)
            path_draw = QPainterPath()
            path_draw.addRoundedRect(0, 0, size, size, 15, 15)
            p.setClipPath(path_draw)
            x = (size - scaled.width()) // 2
            y = (size - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
            p.end()
            # store display pixmap for fast reuse
            self._display_pix = final
            # do not call setPixmap here when pre-rendering larger size

    def enterEvent(self, event):
        self.hovered.emit(self)
        # visual: change border color only (keep width constant to avoid layout shifts)
        self.setStyleSheet(f"border: {BORDER_WIDTH}px solid {HOVER_BORDER_COLOR}; border-radius: 15px; background: transparent;")
        # Create a transient shadow effect for glow
        try:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(24)
            shadow.setOffset(0, 0)
            shadow.setColor(QColor(241, 196, 15, 200))
            self.setGraphicsEffect(shadow)
        except Exception:
            pass
        # slight visual emphasis: keep same widget size but rely on shadow and border
        # because resizing within layouts causes relayout jitter. If a higher-quality
        # scale is desired, the pre-rendered pixmap will allow crisp visuals.
        try:
            # refresh pixmap to ensure scaledContents fills nicely
            if self._display_pix:
                self.setPixmap(self._display_pix.scaled(self.width(), self.height(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        except Exception:
            pass
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.unhovered.emit(self)
        # revert visuals
        self.setStyleSheet("border: 4px solid rgba(255, 255, 255, 1); border-radius: 15px; background: transparent;")
        # Remove any graphics effect (shadow) to restore original look
        try:
            self.setGraphicsEffect(None)
        except Exception:
            pass
        try:
            if self._display_pix:
                self.setPixmap(self._display_pix.scaled(self.width(), self.height(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        except Exception:
            pass
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
            photo = SelectablePhoto(full_path, size=200)
            photo.clicked.connect(self.on_photo_clicked)
            photo.hovered.connect(self.on_child_hover)
            photo.unhovered.connect(self.on_child_unhover)
            self.grid_layout.addWidget(photo, row, col)
            
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

    # -------------------------
    # 聚光燈互動邏輯
    # -------------------------
    def on_child_hover(self, widget):
        # Called when a SelectablePhoto is hovered
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            w = item.widget()
            if not w:
                continue
            try:
                if w is widget:
                    # ensure this widget is fully visible; remove any dimming effect
                    try:
                        w.setGraphicsEffect(None)
                    except Exception:
                        pass
                    # hover visuals are handled by SelectablePhoto.enterEvent
                else:
                    # dim others by installing a transient opacity effect with a short animation
                    try:
                        eff = QGraphicsOpacityEffect(w)
                        w.setGraphicsEffect(eff)
                        anim = QPropertyAnimation(eff, b"opacity", self)
                        anim.setDuration(ANIM_DURATION_MS)
                        anim.setStartValue(1.0)
                        anim.setEndValue(DIM_OPACITY)
                        anim.start()
                        # keep reference to avoid GC
                        w._opacity_anim = anim
                    except Exception:
                        pass
            except Exception:
                pass

    def on_child_unhover(self, widget):
        # Called when a SelectablePhoto is unhovered.
        # If mouse is still over another photo, do nothing (that photo will emit its hover).
        pos = QCursor.pos()
        under = QApplication.widgetAt(pos)
        while under:
            if isinstance(under, SelectablePhoto):
                return
            if under.isWindow():
                break
            under = under.parent()
        # otherwise reset all
        self.reset_focus()

    def reset_focus(self):
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            w = item.widget()
            if not w:
                continue
            try:
                # remove any transient graphics effect (opacity/shadow)
                try:
                    # animate opacity back to 1.0 if there is an effect
                    eff = w.graphicsEffect()
                    if isinstance(eff, QGraphicsOpacityEffect):
                        try:
                            anim = QPropertyAnimation(eff, b"opacity", self)
                            anim.setDuration(ANIM_DURATION_MS)
                            anim.setStartValue(eff.opacity())
                            anim.setEndValue(1.0)
                            anim.start()
                            w._opacity_anim = anim
                            # ensure it is removed after animation
                            def _cleanup():
                                try:
                                    w.setGraphicsEffect(None)
                                except Exception:
                                    pass
                            anim.finished.connect(_cleanup)
                        except Exception:
                            try:
                                w.setGraphicsEffect(None)
                            except Exception:
                                pass
                    else:
                        try:
                            w.setGraphicsEffect(None)
                        except Exception:
                            pass
                except Exception:
                    pass
                # restore border and size if SelectablePhoto
                if isinstance(w, SelectablePhoto):
                    w.setStyleSheet("border: 4px solid rgba(255, 255, 255, 1); border-radius: 15px; background: transparent;")
                    w.setFixedSize(w.base_size, w.base_size)
                    if w._raw_pix:
                        w.set_image(w.image_path, w.base_size)
            except Exception:
                pass
