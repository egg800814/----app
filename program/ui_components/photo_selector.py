"""
photo_selector.py
-----------------
描述：選人模式的照片選擇器 (Overlay)。
功能：
      1. 提供一個全螢幕的覆蓋層，顯示 assets/presenters 中的所有候選人照片。
      2. 支援圖片網格排列、懸停放大預覽、以及點擊選取功能。
      3. 選取照片後，會將圖片路徑回傳給控制端或大螢幕更新轉盤中心頭像。
"""
import os
import sys
from PyQt5.QtWidgets import (QWidget, QApplication, QVBoxLayout, QGridLayout, QLabel, 
                             QScrollArea, QPushButton, QFrame, QGraphicsOpacityEffect, QGraphicsDropShadowEffect)
from PyQt5.QtGui import QPixmap, QCursor, QPainter, QPainterPath, QColor, QImage
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QEvent
from PyQt5.QtCore import QPoint, QTimer
from PyQt5.QtCore import QPropertyAnimation
import cv2
import numpy as np

# -----------------------------
# 可調整的互動參數（中文註解）
# - BORDER_WIDTH: 邊框寬度（固定寬度以避免懸停時版面跳動）
# - HOVER_BORDER_COLOR: 懸停時的邊框顏色
# - DIM_OPACITY: 未被選中的照片暗度（0.0 - 1.0）
# - ANIM_DURATION_MS: 透明度動畫時間（毫秒），值越小反應越快
# 請在此區修改值以調整互動強度與速度。
# -----------------------------
BORDER_WIDTH = 4
HOVER_BORDER_COLOR = "#f1c40f"
DIM_OPACITY = 0.4
ANIM_DURATION_MS = 60
# 游標尺寸（像素）。如需縮放游標圖示，調整此值。
CURSOR_SIZE = 120
PREVIEW_SCALE = 1.6

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

        # store current pixmap for fast scaled display
        self._raw_pix = None
        self._display_pix = None
        if os.path.exists(image_path):
            # pre-render a larger pixmap (3.0x) to allow high quality zooming/preview
            render_size = int(self.base_size * 10.0)
            self.set_image(image_path, render_size)
            if self._raw_pix:
                # set scaled contents so QLabel will scale pixmap with widget size
                self.setScaledContents(True)
                self.setPixmap(self._display_pix.scaled(self.base_size, self.base_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def process_transparent_border(self, pixmap):
        """
        自動影像處理流程：
        1. 轉換 QPixmap -> OpenCV image
        2. 偵測非白色的主體 (Subject Detection) - 門檻值 240
        3. 建立遮罩 (Mask)
        4. 遮罩擴張 (Dilation) 10px -> 透過白色邊框
        5. 將背景去背 (Set Alpha)
           - 遮罩內: 若原圖是 "背景白(>=240)", 強制轉為純白(255)
           - 遮罩外: 透明
        6. 轉換回 QPixmap
        """
        try:
            # 1. QPixmap -> QImage -> Numpy
            qimg = pixmap.toImage().convertToFormat(4) # QImage.Format_RGB32
            width = qimg.width()
            height = qimg.height()
            ptr = qimg.bits()
            ptr.setsize(height * width * 4)
            arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
            
            # 複製 RGB (忽略原本 Alpha)
            img_bgr = arr[:, :, :3].copy()

            # 2. 灰階化
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

            # 3. 二值化 (Thresholding)
            # 亮度 < 240 -> 前景 (255)
            # 亮度 >= 240 -> 背景 (0)
            thresh_val = 220
            _, mask_fg = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)

            # [Optional] 填補主體內部的洞
            kernel_close = np.ones((5,5), np.uint8)
            mask_fg = cv2.morphologyEx(mask_fg, cv2.MORPH_CLOSE, kernel_close)

            # 4. 遮罩擴張 (Dilation) - 製造白邊
            # 擴張 10px -> Kernel size = 2 * 10 + 1 = 21
            kernel_size = 10
            kernel_dilate = np.ones((kernel_size, kernel_size), np.uint8)
            mask_dilated = cv2.dilate(mask_fg, kernel_dilate, iterations=1)

            # 5. 組合影像 (BGRA)
            b, g, r = cv2.split(img_bgr)
            
            # 處裡 "雜訊白" -> "純白"
            # 我們的目標: 
            #   - mask_fg 覆蓋的區域 (主體) -> 保留原色
            #   - mask_dilated 覆蓋但 mask_fg 沒覆蓋的區域 (邊框) -> 設為純白
            #   - mask_dilated 以外 -> 透明 (Alpha=0)
            
            fg_locs = (mask_fg == 255) # 主體位置
            
            # 先將原圖所有非主體的位置都填成純白 (255, 255, 255)
            # 這會包含 "邊框區" 以及 "背景區"
            # 之後再透過 Alpha Channel 決定顯示範圍，這樣邊框就是純白的
            final_b = b.copy()
            final_g = g.copy()
            final_r = r.copy()
            
            final_b[~fg_locs] = 255
            final_g[~fg_locs] = 255
            final_r[~fg_locs] = 255
            
            # Merge: B, G, R, Alpha(mask_dilated)
            img_bgra = cv2.merge([final_b, final_g, final_r, mask_dilated])

            # 6. BGRA -> QImage -> QPixmap
            h, w, ch = img_bgra.shape
            bytes_per_line = ch * w
            final_qimg = QImage(img_bgra.data, w, h, bytes_per_line, QImage.Format_ARGB32).copy()
            
            return QPixmap.fromImage(final_qimg)

        except Exception as e:
            print(f"[PhotoSelector] Auto-processing failed: {e}")
            return pixmap

    def set_image(self, path, size):
        pix = QPixmap(path)
        if pix and not pix.isNull():
            # [新增] 自動影像處理 (去背+白邊)
            try:
                processed_pix = self.process_transparent_border(pix)
            except Exception:
                processed_pix = pix

            self._raw_pix = processed_pix
            
            # 使用處理後的圖片進行縮放
            # Qt.KeepAspectRatio -> 確保整張顯示，不裁切
            scaled = processed_pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            final = QPixmap(size, size)
            final.fill(Qt.transparent)
            p = QPainter(final)
            p.setRenderHint(QPainter.Antialiasing)
            
            # 雖然圖片已經去背，但我們還是保留圓角外框裁切，讓整體風格一致 (圓角矩形)
            path_draw = QPainterPath()
            path_draw.addRoundedRect(0, 0, size, size, 15, 15)
            p.setClipPath(path_draw)
            
            x = (size - scaled.width()) // 2
            y = (size - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
            p.end()
            
            # store display pixmap for fast reuse
            self._display_pix = final

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
        
        # Resolve path - support both Dev and PyInstaller (Frozen) modes
        if getattr(sys, 'frozen', False):
            # Running as compiled exe: look in the folder containing the exe
            root = os.path.dirname(sys.executable)
        else:
            # Running as script: relative to this file
            # This file is in program/ui_components/
            base = os.path.dirname(os.path.abspath(__file__)) 
            # root = app folder (parent of program) -> app/program/ui_components/../../ = app/
            root = os.path.dirname(os.path.dirname(base)) 

        if not os.path.isabs(self.images_dir):
            self.real_dir = os.path.join(root, self.images_dir)
        else:
            self.real_dir = self.images_dir
            
        self.hide()

        # Dim background (lightbox) — keep as child widget overlay, slightly stronger dim
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.8);")
        # small event log to help trace selection flow
        try:
            self._logpath = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'selection.log'))
        except Exception:
            self._logpath = None

        # 主佈局（Overlay）
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(50, 50, 50, 50)

        # 中央面板：將照片網格與暗背景視覺區隔
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

        # 標題區（包含主標題與副標題） - 主標題會動態顯示目前要選的人員所屬獎項
        self.title_container = QWidget()
        title_layout = QVBoxLayout(self.title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)

        # 主標題（會由後台傳入獎項名稱）
        self.dynamic_prize_label = QLabel("🎉 準備選人 🎉")
        self.dynamic_prize_label.setAlignment(Qt.AlignCenter)
        self.dynamic_prize_label.setStyleSheet("color: #f1c40f; font-size: 60px; font-weight: bold; background: transparent;")
        # 加陰影以在深色背景上清晰可見
        prize_shadow = QGraphicsDropShadowEffect(self.dynamic_prize_label)
        prize_shadow.setBlurRadius(20)
        prize_shadow.setOffset(0, 4)
        prize_shadow.setColor(QColor(0,0,0,200))
        self.dynamic_prize_label.setGraphicsEffect(prize_shadow)

        # 副標題：固定引導文字
        self.subtitle_label = QLabel("榮耀時刻，請指定開啟幸運的推手")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("color: white; font-size: 32px; background: transparent;")

        title_layout.addWidget(self.dynamic_prize_label)
        title_layout.addWidget(self.subtitle_label)
        panel_layout.addWidget(self.title_container, 0, Qt.AlignCenter)

        # 在主標題與照片網格之間保留空間
        panel_layout.addSpacing(10)

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
        self.grid_layout.setSpacing(48) # [設定] 這裡控制照片之間的間距 (像素)
        self.grid_layout.setAlignment(Qt.AlignCenter)

        scroll.setWidget(self.grid_container)
        # keep reference to scroll area so we can preserve scroll position during hover effects
        self.scroll = scroll
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
        close_btn.clicked.connect(self._on_close_clicked)
        panel_layout.addWidget(close_btn, 0, Qt.AlignCenter)

        layout.addWidget(panel)

        # 用於懸停時顯示的浮動放大預覽（避免改變原本格子大小導致布局跳動）
        self._highlight_label = None
        # 儲存預設游標，以便還原
        self._default_cursor = QApplication.overrideCursor()
        # 儲存先前 override cursor（如果有）以便正確還原
        self._prev_override = None
        # 準備游標圖片路徑（預設在專案根目錄的 assets/images）
        # Resolve cursor image path - support both Dev and PyInstaller (Frozen) modes
        if getattr(sys, 'frozen', False):
             root = os.path.dirname(sys.executable)
        else:
             base = os.path.dirname(os.path.abspath(__file__))
             project_root = os.path.dirname(os.path.dirname(base))
             root = project_root

        images_root = os.path.join(root, "assets", "images")
        self._cursor_img_hover = os.path.join(images_root, "wood_hammer1.png")
        self._cursor_img_click = os.path.join(images_root, "wood_hammer2.png")

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
            photo = SelectablePhoto(full_path, size=300)
            photo.clicked.connect(self.on_photo_clicked)
            photo.hovered.connect(self.on_child_hover)
            photo.unhovered.connect(self.on_child_unhover)
            self.grid_layout.addWidget(photo, row, col)
            
            col += 1
            if col >= cols:
                col = 0
                row += 1

    def on_photo_clicked(self, path):
        # 更安全的選取處理流程：先發出訊號，短延遲後再由 hideEvent 統一處理關閉與游標還原
        try:
            print(f"[PhotoSelector] Selected: {path}")
            if self._logpath:
                with open(self._logpath, 'a', encoding='utf-8') as f:
                    f.write(f"PhotoSelector: clicked -> {path}\n")
        except Exception:
            pass

        # 發出選取訊號（由 DisplayWindow / ControlWindow 接手後續處理）
        try:
            self.photoSelected.emit(path)
        except Exception:
            pass

        # 切換到點擊游標（視覺回饋） -> [FIX] 移除以避免 Windows 崩潰 (Invalid cursor shape)
        # try:
        #     if os.path.exists(self._cursor_img_click):
        #         pix = QPixmap(self._cursor_img_click)
        #         if not pix.isNull():
        #             sp = pix.scaled(CURSOR_SIZE, CURSOR_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        #             if self._prev_override is None:
        #                 try:
        #                     self._prev_override = QApplication.overrideCursor()
        #                 except Exception:
        #                     self._prev_override = None
        #             QApplication.setOverrideCursor(QCursor(sp, sp.width()//2, sp.height()//2))
        # except Exception:
        #     pass

        # 延遲隱藏 overlay，避免在 signal/slot 連鎖中立刻造成資源競爭
        try:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(120, lambda: self.hide())
        except Exception:
            try:
                self.hide()
            except Exception:
                pass
        
    def show_selector(self, prize_name=None):
        # 開啟選人視窗；可傳入 prize_name 以更新主標題
        if prize_name:
            try:
                self.dynamic_prize_label.setText(prize_name)
            except Exception:
                pass
        self.refresh_images() # 每次開啟重新掃描，確保有新照片能讀到
        # Ensure the overlay covers the full parent (top-level) window and stays on top
        parent_window = None
        if self.parent() is not None:
            parent_window = self.parent().window()

        # As a child overlay: match parent size and show on top of siblings
        parent = self.parent()
        if parent is not None:
            # 當 overlay 顯示時，暫時隱藏父層的游標跟隨標誌（例如 DisplayWindow.cursor_fol_label）
            try:
                if hasattr(parent, 'cursor_fol_label') and parent.cursor_fol_label is not None:
                    parent.cursor_fol_label.hide()
            except Exception:
                pass

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
        # 顯示浮動放大預覽並讓其他圖片變暗
        # 1) 建立或更新浮動預覽
        try:
            # 計算浮動預覽大小（比原圖大一些以提供明顯放大反饋）
            preview_size = int(widget.base_size * PREVIEW_SCALE)
            # 建立浮動 QLabel
            if not self._highlight_label:
                self._highlight_label = QLabel(self)
                self._highlight_label.setAttribute(Qt.WA_TransparentForMouseEvents)
                self._highlight_label.setStyleSheet('border: 5px solid %s; border-radius: 18px;' % HOVER_BORDER_COLOR)
            # 使用 SelectablePhoto 預先渲染的 pixmap 作為來源，保持品質
            try:
                if widget._display_pix:
                    pix = widget._display_pix.scaled(preview_size, preview_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    self._highlight_label.setPixmap(pix)
                    self._highlight_label.setFixedSize(preview_size, preview_size)
                    # 計算浮動位置：以被懸停照片中心為中心點
                    # use widget coordinates mapped to overlay to avoid global <-> local jitter
                    local_center = widget.mapTo(self, widget.rect().center())
                    top_left = QPoint(local_center.x() - preview_size//2, local_center.y() - preview_size//2)
                    self._highlight_label.move(top_left)
                    self._highlight_label.show()
                    self._highlight_label.raise_()
            except Exception:
                pass
        except Exception:
            pass

        # 2) 讓其他照片變暗
        # Preserve scroll offsets to avoid the scroll area re-centering briefly
        try:
            vval = self.scroll.verticalScrollBar().value()
            hval = self.scroll.horizontalScrollBar().value()
        except Exception:
            vval = hval = None

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
                        # Apply a simple, immediate opacity effect (avoids animation-induced layout jitter)
                        eff = QGraphicsOpacityEffect(w)
                        eff.setOpacity(DIM_OPACITY)
                        w.setGraphicsEffect(eff)
                    except Exception:
                        pass
            except Exception:
                pass
        # restore scroll offsets (if we saved them) to prevent visible jumps
        try:
            if vval is not None:
                self.scroll.verticalScrollBar().setValue(vval)
            if hval is not None:
                self.scroll.horizontalScrollBar().setValue(hval)
        except Exception:
            pass
        # 3) 變更游標為木鎚（懸停圖） -> [FIX] 移除以避免 Windows 崩潰
        # try:
        #     if os.path.exists(self._cursor_img_hover):
        #         pix = QPixmap(self._cursor_img_hover)
        #         if not pix.isNull():
        #             sp = pix.scaled(CURSOR_SIZE, CURSOR_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        #             # 儲存先前的 override（只儲存一次）
        #             if self._prev_override is None:
        #                 try:
        #                     self._prev_override = QApplication.overrideCursor()
        #                 except Exception:
        #                     self._prev_override = None
        #             QApplication.setOverrideCursor(QCursor(sp, sp.width()//2, sp.height()//2))
        # except Exception:
        #     pass

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
        # otherwise reset所有視覺狀態
        self.reset_focus()
        # 還原游標（使用儲存的先前 override，或直接 restore）
        try:
            if self._prev_override is not None:
                # 移除目前 override，並恢復先前儲存的 override（若存在）
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    pass
                try:
                    if self._prev_override is not None:
                        QApplication.setOverrideCursor(self._prev_override)
                except Exception:
                    pass
                self._prev_override = None
            else:
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    pass
        except Exception:
            pass

    def reset_focus(self):
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            w = item.widget()
            if not w:
                continue
            try:
                # remove any transient graphics effect (opacity/shadow)
                try:
                    # remove any transient graphics effect immediately
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
        # 隱藏並清理浮動放大預覽
        try:
            if self._highlight_label:
                try:
                    self._highlight_label.hide()
                except Exception:
                    pass
        except Exception:
            pass

    def _on_close_clicked(self):
        # 使用者按下關閉按鈕：還原游標並關閉 overlay
        # 清除所有 override cursor，恢復系統預設游標
        try:
            while QApplication.overrideCursor() is not None:
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    break
        except Exception:
            pass
        try:
            self.reset_focus()
        except Exception:
            pass
        try:
            self.hide()
        except Exception:
            pass

    def hideEvent(self, event):
        # 當 overlay 隱藏時，確保還原游標與清理浮動預覽
        # 清除所有 override cursor，恢復系統預設游標
        try:
            if getattr(self, '_logpath', None):
                with open(self._logpath, 'a', encoding='utf-8') as f:
                    f.write("PhotoSelector: hideEvent called\n")
        except Exception:
            pass
        try:
            while QApplication.overrideCursor() is not None:
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    break
        except Exception:
            pass
        try:
            if self._highlight_label:
                self._highlight_label.hide()
        except Exception:
            pass
        # 還原父層的 cursor_fol_label（若存在）
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, 'cursor_fol_label'):
                try:
                    parent.cursor_fol_label.show()
                except Exception:
                    pass
        except Exception:
            pass
        super().hideEvent(event)
