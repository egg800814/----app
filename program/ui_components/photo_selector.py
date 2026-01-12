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
PREVIEW_SCALE = 2.0  # [設定] 懸停時的放大倍率 (例如 1.6 代表放大 1.6 倍)

# [設定] 照片參數
IMAGE_QUALITY_SCALE = 4.0   # [設定] 清晰度設定：數字越大越清晰 (預設 4.0)
SUBJECT_FILL_RATIO = 1.0   # [設定] 人物主體在格狀內的佔比 (0.1~1.0，預設 0.95)

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
        # 移除 CSS 邊框，改用透明背景
        self.setStyleSheet("background: transparent;")

        # store current pixmap for fast scaled display
        self._pix_normal = None
        self._pix_hover = None
        if os.path.exists(image_path):
            # pre-render a larger pixmap to allow high quality zooming/preview
            render_size = int(self.base_size * IMAGE_QUALITY_SCALE) 
            self.set_image(image_path, render_size)
            
            # Initial display
            if self._pix_normal:
                self.setScaledContents(True)
                self.setPixmap(self._pix_normal)

    def process_transparent_border(self, pixmap, border_color=(255, 255, 255), extra_dilation=0):
        """
        自動影像處理流程 (支援自訂邊框顏色與額外擴張)：
        1. 轉換 QPixmap -> OpenCV image
        2. 偵測非白色的主體 (Subject Detection) - 門檻值 220
        3. 建立遮罩 (Mask)
        4. 遮罩擴張 (Dilation) -> 製造邊框
        5. 將背景去背 (Set Alpha) 並上色邊框
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
            
            img_bgr = arr[:, :, :3].copy()

            # 2. 灰階化
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

            # 3. 二值化 (Thresholding)
            thresh_val = 220
            _, mask_fg = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)

            # 填補孔洞
            kernel_close = np.ones((5,5), np.uint8)
            mask_fg = cv2.morphologyEx(mask_fg, cv2.MORPH_CLOSE, kernel_close)

            # [新增] 輪廓篩選 (去雜訊)
            # 找出所有輪廓 (RETR_EXTERNAL 只找外輪廓)
            contours, _ = cv2.findContours(mask_fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 建立乾淨的遮罩 (全黑)
            mask_clean = np.zeros_like(mask_fg)
            
            # 設定面積門檻 (例如 500 px)，濾除太小的雜訊塊
            min_area = 500 
            
            # 找出最大的輪廓 (比較保險的做法：假設最大的是人)
            if contours:
                # 方法 A: 只保留最大的一個主體 (最乾淨)
                max_cnt = max(contours, key=cv2.contourArea)
                if cv2.contourArea(max_cnt) > min_area:
                    cv2.drawContours(mask_clean, [max_cnt], -1, 255, thickness=cv2.FILLED)
                
                # 方法 B (備用): 保留所有大於門檻的區塊 (如果有人跟手分開的情況)
                # for cnt in contours:
                #     if cv2.contourArea(cnt) > min_area:
                #         cv2.drawContours(mask_clean, [cnt], -1, 255, thickness=cv2.FILLED)
            
            # 更新 mask_fg 為過濾後的乾淨遮罩
            mask_fg = mask_clean

            # 4. 遮罩擴張 (Dilation) - 製造邊框
            # 基本擴張 (10px) + 額外擴張 (for Hover)
            base_dilation = 10
            total_dilation = base_dilation + extra_dilation
            kernel_size = 2 * total_dilation + 1 
            kernel_dilate = np.ones((kernel_size, kernel_size), np.uint8)
            mask_total = cv2.dilate(mask_fg, kernel_dilate, iterations=1)

            # 5. 組合影像 (BGRA)
            b, g, r = cv2.split(img_bgr)
            
            # 邏輯：
            # - mask_fg 覆蓋區域 -> 主體 (保留原色)
            # - mask_total - mask_fg -> 邊框 (填入 border_color)
            # - mask_total 以外 -> 透明
            
            fg_locs = (mask_fg == 255) # 主體
            border_locs = (mask_total == 255) & (mask_fg == 0) # 邊框
            
            final_b = b.copy()
            final_g = g.copy()
            final_r = r.copy()
            
            # 填入邊框顏色 (OpenCV is BGR)
            # border_color 輸入預期是 (R, G, B)
            bc_r, bc_g, bc_b = border_color
            
            final_b[border_locs] = bc_b
            final_g[border_locs] = bc_g
            final_r[border_locs] = bc_r
            
            # [Optional] 如果原本圖片的主體有雜點，也可以在這裡過濾，但通常保留原圖較自然
            
            img_bgra = cv2.merge([final_b, final_g, final_r, mask_total])

            # [新增] 自動裁切與標準化縮放 (Standardization)
            # 1. 找出邊界框 (Bounding Box)
            # 使用 alpha channel (mask_total) 來找
            x, y, w, h = cv2.boundingRect(mask_total)
            
            if w > 0 and h > 0:
                # 2. 裁切主體 (Crop)
                img_crop = img_bgra[y:y+h, x:x+w]
                
                # 3. 計算縮放與建立正方形畫布 (Center on Canvas)
                # 目標：讓主體的長邊佔畫布的 85% (保留 15% 留白，視覺舒適)
                max_dim = max(w, h)
                target_ratio = SUBJECT_FILL_RATIO
                canvas_size = int(max_dim / target_ratio)
                
                # 建立全透明畫布
                canvas = np.zeros((canvas_size, canvas_size, 4), dtype=np.uint8)
                
                # 4. 居中貼合
                start_x = (canvas_size - w) // 2
                start_y = (canvas_size - h) // 2
                
                canvas[start_y:start_y+h, start_x:start_x+w] = img_crop
                
                # 使用標準化後的 canvas 作為最終輸出
                img_final = canvas
            else:
                img_final = img_bgra

            # 6. BGRA -> QImage -> QPixmap
            h, w, ch = img_final.shape
            bytes_per_line = ch * w
            final_qimg = QImage(img_final.data, w, h, bytes_per_line, QImage.Format_ARGB32).copy()
            
            return QPixmap.fromImage(final_qimg)

        except Exception as e:
            print(f"[PhotoSelector] Auto-processing failed: {e}")
            return pixmap

    def _apply_scaling_and_clipping(self, pixmap, size):
        """Helper to scale and apply rounded rect clipping."""
        if not pixmap or pixmap.isNull():
            return QPixmap()

        scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
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
        return final

    def set_image(self, path, size):
        pix = QPixmap(path)
        if pix and not pix.isNull():
            # 1. 產生 [一般狀態] 圖片：白色邊框
            try:
                processed_normal_pix = self.process_transparent_border(pix, border_color=(255, 255, 255), extra_dilation=0)
                self._pix_normal = self._apply_scaling_and_clipping(processed_normal_pix, size)
            except Exception:
                self._pix_normal = self._apply_scaling_and_clipping(pix, size)
                
            # 2. 產生 [懸停狀態] 圖片：金色邊框 (241, 196, 15) (#f1c40f)，且更粗一點
            try:
                processed_hover_pix = self.process_transparent_border(pix, border_color=(241, 196, 15), extra_dilation=8)
                self._pix_hover = self._apply_scaling_and_clipping(processed_hover_pix, size)
            except Exception:
                self._pix_hover = self._apply_scaling_and_clipping(pix, size)


    def enterEvent(self, event):
        self.hovered.emit(self)
        # visual: change border color only (keep width constant to avoid layout shifts)
        # self.setStyleSheet(f"border: {BORDER_WIDTH}px solid {HOVER_BORDER_COLOR}; border-radius: 15px; background: transparent;")
        if self._pix_hover:
            self.setPixmap(self._pix_hover)
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
        # self.setStyleSheet("border: 4px solid rgba(255, 255, 255, 1); border-radius: 15px; background: transparent;")
        if self._pix_normal:
            self.setPixmap(self._pix_normal)
            
        # Remove any graphics effect (shadow) to restore original look
        try:
            self.setGraphicsEffect(None)
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
        self._cursor_img_hover_path = os.path.join(images_root, "wood_hammer1.png")
        self._cursor_img_click_path = os.path.join(images_root, "wood_hammer2.png")
        
        # 預先載入游標以避免延遲
        self._cursor_hover = None
        self._cursor_click = None
        self._load_cursors()

    def _load_cursors(self):
        try:
            # Load Hover Cursor (Hammer Up)
            if os.path.exists(self._cursor_img_hover_path):
                pix = QPixmap(self._cursor_img_hover_path)
                if not pix.isNull():
                    pix = pix.scaled(CURSOR_SIZE, CURSOR_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    # 設定熱點在中心
                    self._cursor_hover = QCursor(pix, pix.width()//2, pix.height()//2)

            # Load Click Cursor (Hammer Down)
            if os.path.exists(self._cursor_img_click_path):
                pix = QPixmap(self._cursor_img_click_path)
                if not pix.isNull():
                    pix = pix.scaled(CURSOR_SIZE, CURSOR_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    # 設定熱點在中心
                    self._cursor_click = QCursor(pix, pix.width()//2, pix.height()//2)
        except Exception as e:
            print(f"Error loading cursors: {e}")

    def showEvent(self, event):
        # 當 Overlay 顯示時，強制設定為木鎚游標
        try:
            if self._cursor_hover:
                # 為了確保覆蓋，先清除所有舊的 override
                while QApplication.overrideCursor() is not None:
                    QApplication.restoreOverrideCursor()
                QApplication.setOverrideCursor(self._cursor_hover)
        except Exception:
            pass
        super().showEvent(event)

    def mousePressEvent(self, event):
        # 按下時切換為敲擊游標
        if event.button() == Qt.LeftButton and self._cursor_click:
            try:
                QApplication.changeOverrideCursor(self._cursor_click)
            except Exception:
                pass
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # 放開時切換回舉起游標
        if event.button() == Qt.LeftButton and self._cursor_hover:
            try:
                QApplication.changeOverrideCursor(self._cursor_hover)
            except Exception:
                pass
        super().mouseReleaseEvent(event)

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
            photo = SelectablePhoto(full_path, size=300) # [設定] 網格中照片的大小 (寬高像素)
            photo.clicked.connect(self.on_photo_clicked)
            photo.hovered.connect(self.on_child_hover)
            photo.unhovered.connect(self.on_child_unhover)
            self.grid_layout.addWidget(photo, row, col)
            
            col += 1
            if col >= cols:
                col = 0
                row += 1

    def on_photo_clicked(self, path):
        # 增加打擊感延遲：
        # 1. 立即顯示槌子敲下 (wood_hammer2)
        # 2. 強制刷新介面
        # 3. 延遲 300ms 後才真正執行選取與關閉
        try:
            print(f"[PhotoSelector] Selected: {path}")
            if self._logpath:
                with open(self._logpath, 'a', encoding='utf-8') as f:
                    f.write(f"PhotoSelector: clicked -> {path}\n")
            
            # 立即視覺回饋：切換到敲擊游標
            if self._cursor_click:
                QApplication.changeOverrideCursor(self._cursor_click)
                QApplication.processEvents() # 強制刷新畫面確保游標改變
                
        except Exception:
            pass

        # 定義延遲執行的動作
        def delayed_action():
            # 發出選取訊號（由 DisplayWindow / ControlWindow 接手後續處理）
            try:
                self.photoSelected.emit(path)
            except Exception:
                pass
            # 隱藏 Overlay
            try:
                self.hide()
            except Exception:
                pass

        # 設定 300ms 延遲，讓使用者看清楚敲擊動作
        try:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(300, delayed_action)
        except Exception:
            delayed_action() # Fallback if timer fails
        
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
                # 移除方形邊框，因為圖片本身已有發光輪廓
                self._highlight_label.setStyleSheet("background: transparent;")
                
            # 使用 SelectablePhoto 預先渲染的 pixmap (使用 hover 版本) 作為來源
            try:
                # 優先使用 _pix_hover (有金邊效果)，若無則用 _pix_normal
                source_pix = widget._pix_hover if widget._pix_hover else widget._pix_normal
                
                if source_pix:
                    pix = source_pix.scaled(preview_size, preview_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
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
                # restore border and size if SelectablePhoto
                if isinstance(w, SelectablePhoto):
                    # 還原CSS: 移除邊框，改為透明
                    w.setStyleSheet("background: transparent;")
                    w.setFixedSize(w.base_size, w.base_size)
                    # 還原圖片為正常版 (白邊)
                    if hasattr(w, '_pix_normal') and w._pix_normal:
                        w.setPixmap(w._pix_normal)
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
