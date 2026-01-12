"""
display_window.py
-----------------
描述：大螢幕顯示視窗 (Audience Display)。
功能：這是投放到投影機或第二螢幕的視窗，主要負責：
      1. 顯示幸運轉盤 (LuckyWheel) 與目前的獎項標題。
      2. 顯示右側的「榮譽榜」(已中獎名單)。
      3. 執行各種視覺動畫 (轉動、煙火、彈出視窗、飛入名單動畫)。
      4. 播放背景音樂與中獎音效。
"""
import os
import sys

# 若直接執行此檔案，將上層目錄加入 sys.path 以讀取模組
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QGraphicsOpacityEffect, QApplication
from PyQt5.QtGui import QPixmap, QCursor, QImage
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QVariantAnimation, QEasingCurve, QTimer, QEvent, QThread
from ui_components.lucky_wheel import LuckyWheelWidget
from ui_components.effects import ConfettiWidget, WinnerOverlay, FlyingLabel
from ui_components.photo_selector import PhotoSelectorOverlay # [新增]

class DisplayWindow(QWidget):
    """
    大螢幕視窗 (觀眾視角)
    - 轉盤(左) + 得獎名單(右)
    - 兩段式揭曉與動態特效
    """
    requestSpin = pyqtSignal() # 保留給其他用途，或相容性
    spinStarted = pyqtSignal() # [新增] 通知主控端轉動開始 (鎖定UI)
    avatarUpdated = pyqtSignal(str) # [新增] 通知主控端已選擇新照片
    wheelReady = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("大螢幕抽獎")
        
        # Overlay and Confetti (Initialize early)
        self.overlay = WinnerOverlay(self)
        self.confetti = ConfettiWidget(self)
        self.photo_selector = PhotoSelectorOverlay(self) # [新增] 照片選擇器
        self.photo_selector.photoSelected.connect(self.on_photo_selected)
        
        self.overlay.hide()
        self.confetti.hide()
        self.photo_selector.hide()
        
        # [新增] 初始化飛行動畫屬性
        self.fly_anim = None

        # [新增] 滑鼠跟隨 Logo
        self.cursor_fol_label = QLabel(self)
        self.cursor_state = "normal" # normal, active
        self.pixmap_normal = None
        self.pixmap_active = None
        
        try:
            # 取得 assets 資料夾絕對路徑
            # base_dir = .../program
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # project_root = .../抽獎轉盤app
            project_root = os.path.dirname(base_dir)
            
            # logo.jpg 與 90_logo.jpg 都在 專案根目錄/assets/images 下
            logo_path = os.path.join(project_root, "assets", "images", "logo.jpg")
            logo_active_path = os.path.join(project_root, "assets", "images", "90_logo.jpg")
            
            # 如果找不到，嘗試在 program/assets/images 找 (容錯)
            if not os.path.exists(logo_active_path):
                 logo_active_path = os.path.join(base_dir, "assets", "images", "90_logo.jpg")
            
            # 載入一般狀態圖片 (Logo)
            if os.path.exists(logo_path):
                pix = QPixmap(logo_path)
                # 90 週年圖片與 Logo 去背處理 (將白色背景轉為透明)
                # 注意：這會將所有純白色像素變更為透明
                pix.setMask(pix.createMaskFromColor(Qt.white))
                self.pixmap_normal = pix.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                print(f"Warning: Logo not found at {logo_path}")

            # 載入活躍狀態圖片 (90_logo)
            if os.path.exists(logo_active_path):
                pix = QPixmap(logo_active_path)
                
                # [修正] 使用 QImage.Format_ARGB32 (5) 以支援透明度
                # 之前使用 4 (RGB32) 會導致 Alpha 被忽略，變成黑色
                temp_pix = pix.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                img = temp_pix.toImage().convertToFormat(QImage.Format_ARGB32)
                
                width = img.width()
                height = img.height()
                
                from PyQt5.QtGui import qRed, qGreen, qBlue
                
                # BFS Flood Fill (從四個角落開始找白色背景)
                visited = set()
                # 檢查四個角落，如果是白色就加入起始點
                start_points = [(0, 0), (width-1, 0), (0, height-1), (width-1, height-1)]
                stack = []
                
                for x, y in start_points:
                    p = img.pixel(x, y)
                    # [調整] 門檻值設為 230，更能容忍 JPG 的白色雜訊，確保背景能被選取
                    if qRed(p) > 230 and qGreen(p) > 230 and qBlue(p) > 230:
                        stack.append((x, y))

                while stack:
                    x, y = stack.pop()
                    if (x, y) in visited: continue
                    visited.add((x, y))
                    
                    # 檢查四鄰居
                    for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
                        if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                            p = img.pixel(nx, ny)
                            # 同樣使用 230
                            if qRed(p) > 230 and qGreen(p) > 230 and qBlue(p) > 230:
                                stack.append((nx, ny))
                
                # [新增] 邊緣保留邏輯 (Erosion)
                # 使用者希望能保留 "一點點" 白色邊緣
                # 加大 padding_size 讓白邊更明顯
                padding_size = 5 # 保留 5 像素寬的白邊
                
                bg_pixels = visited
                
                for _ in range(padding_size):
                    border_pixels = set()
                    for x, y in bg_pixels:
                        # 檢查 8 鄰居 (讓邊緣更圓滑)
                        is_border = False
                        for nx in range(x-1, x+2):
                            for ny in range(y-1, y+2):
                                if (nx == x and ny == y): continue
                                # 如果鄰居在圖片範圍內，且不在 current bg_pixels 裡，代表它是 "內容" (或是已保留的邊緣)
                                # 那目前的 (x,y) 就是新的邊緣，應該被保留
                                if 0 <= nx < width and 0 <= ny < height:
                                    if (nx, ny) not in bg_pixels:
                                        is_border = True
                                        break
                            if is_border: break
                        
                        if is_border:
                            border_pixels.add((x, y))
                    
                    # 將邊緣從背景集合中移除 (也就是保留下來不透明)
                    bg_pixels = bg_pixels - border_pixels
                
                # 最後執行去背
                for x, y in bg_pixels:
                     img.setPixel(x, y, 0)
                
                self.pixmap_active = QPixmap.fromImage(img)
            else:
                print(f"Warning: Active Logo not found at {logo_active_path}")

            # 初始設定
            if self.pixmap_normal:
                self.cursor_fol_label.setPixmap(self.pixmap_normal)
                self.cursor_fol_label.setFixedSize(self.pixmap_normal.size())
                self.cursor_fol_label.setAttribute(Qt.WA_TransparentForMouseEvents) # 讓滑鼠點擊可穿透
                self.cursor_fol_label.show()
                self.cursor_fol_label.raise_()
                
        except Exception as e:
            print(f"Error loading cursor logo: {e}")

        self.setMouseTracking(True) # 啟用滑鼠追蹤
        
        # [修改] 使用 Timer 進行滑鼠追蹤更新
        # 這能確保 (1) 游標永遠在最上層 (透過不斷 raise_) (2) 跟隨速度穩定流暢
        self.cursor_timer = QTimer(self)
        self.cursor_timer.timeout.connect(self.update_cursor_position)
        self.cursor_timer.start(16) # 約 60 FPS



        # Main Layout (Horizontal)
        if os.path.exists("background_display.jpg"):
            self.setStyleSheet(f"DisplayWindow {{ border-image: url(background_display.jpg) 0 0 0 0 stretch stretch; }}")
        else:
            self.setStyleSheet("background-color: #2c3e50;")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- LEFT SIDE: Wheel & Title ---
        self.left_container = QWidget()
        self.left_layout = QVBoxLayout(self.left_container)

        # 頂部：目前抽獎項目標題
        self.prize_label = QLabel("🎉 MDIT 尾牙抽獎活動準備中 🎉")
        self.prize_label.setAlignment(Qt.AlignCenter)
        self.prize_label.setStyleSheet("""
            QLabel {
                color: #f1c40f;
                font-size: 50px;
                font-weight: bold;
                font-family: "Microsoft JhengHei";
                margin-bottom: 20px;
            }
        """)

        # 轉盤 (attempt immediate creation; if it fails we'll create later)
        try:
            self.wheel = LuckyWheelWidget()
        except Exception:
            self.wheel = None
        # 開始按鈕 (設為浮動，不放入 Layout 以免影響轉盤大小)
        self.spin_btn = QPushButton("開始抽獎", self)
        self.spin_btn.setFixedSize(200, 80)
        self.spin_btn.setCursor(Qt.PointingHandCursor)
        self.spin_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e74c3c, stop:1 #c0392b);
                color: white; font-size: 30px; border-radius: 40px; border: 3px solid #fff; font-weight: bold;
            }
            QPushButton:hover { background-color: #ff6b6b; }
            QPushButton:pressed { background-color: #a93226; }
            QPushButton:disabled { background-color: #95a5a6; border-color: #bdc3c7; }
        """)
        # [修改] 改為長按互動邏輯
        self.spin_btn.pressed.connect(self.on_btn_pressed)
        # self.spin_btn.released.connect(self.on_btn_released) # [修改] 移除標準信號，改由 eventFilter 全權處理

        # [新增] 安裝事件過濾器以處理「按住後移出按鈕外放開」的情況
        self.spin_btn.installEventFilter(self)

        # ---------------------------------------------------------
        # [按鈕位置設定]
        # 若要修改按鈕位置，請調整以下兩個數值：
        # 1. current_offset_x (水平偏移): 正數往右，負數往左
        # 2. current_margin_bottom (底部距離): 數值越大離底部越遠
        # ---------------------------------------------------------
        self.current_offset_x = 600
        self.current_margin_bottom = 150
        # ---------------------------------------------------------

        # 初始定位
        QTimer.singleShot(0, self.update_btn_pos)

        self.left_layout.addWidget(self.prize_label)
        if hasattr(self, 'wheel') and self.wheel is not None:
            self.left_layout.addWidget(self.wheel, 1)

        # --- RIGHT SIDE: Winner List ---
        self.right_container = QWidget()
        self.right_container.setFixedWidth(350)
        self.right_container.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.4); 
                border-left: 3px solid rgba(255, 215, 0, 0.5);
                border-radius: 15px;
            }
        """)
        right_layout = QVBoxLayout(self.right_container)

        lbl_list_title = QLabel("🏆 榮譽榜")
        lbl_list_title.setAlignment(Qt.AlignCenter)
        lbl_list_title.setStyleSheet("color: #f1c40f; font-size: 32px; font-weight: bold; padding: 10px; background: transparent; border: none;")

        self.winner_list = QListWidget()
        self.winner_list.setFocusPolicy(Qt.NoFocus)
        self.winner_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                color: white;
                font-size: 24px;
                font-weight: bold;
                font-family: "Microsoft JhengHei";
                outline: none;
            }
            QListWidget::item {
                padding: 15px;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                color: #ecf0f1;
            }
            QListWidget::item:selected {
                background: transparent;
                color: #f1c40f;
            }
        """)
        right_layout.addWidget(lbl_list_title)
        right_layout.addWidget(self.winner_list)

        # Add to main layout
        main_layout.addWidget(self.left_container, 7)
        main_layout.addWidget(self.right_container, 3)

        # 全螢幕設定
        self.showFullScreen()

        # Ensure the wheel exists (deferred init will create and add if missing)
        QTimer.singleShot(50, self.ensure_wheel_initialized)

    def eventFilter(self, obj, event):
        """處理按鈕的特殊事件 (例如移出邊界後放開)"""
        if obj == self.spin_btn:
            if event.type() == QEvent.MouseButtonRelease:
                # 無論滑鼠是否在按鈕內，只要放開左鍵，都視為結束長按
                # 判斷是否為左鍵
                if event.button() == Qt.LeftButton:
                    self.on_btn_released()
                    return True # 事件已處理
        return super().eventFilter(obj, event)

    def ensure_wheel_initialized(self):
        """Ensure `self.wheel` exists and is added to the left layout. Emits `wheelReady` when ready."""
        try:
            if hasattr(self, 'wheel') and self.wheel is not None:
                # already initialized
                return True

            # create wheel and insert into left layout
            self.wheel = LuckyWheelWidget()
            # add to left layout (ensure attribute exists)
            if hasattr(self, 'left_layout'):
                self.left_layout.addWidget(self.wheel, 1)

            # position adjustments
            try:
                QTimer.singleShot(0, self.update_btn_pos)
            except Exception:
                pass

            # notify listeners
            try:
                self.wheelReady.emit()
            except Exception:
                pass

            return True
        except Exception:
            return False

    def on_btn_pressed(self):
        """按下按鈕：開始轉動 (加速)"""
        # 進入專注模式 (變暗背景等)
        self.set_focus_mode(True)
        # 開始轉動
        self.wheel.start_holding()
        # 通知控制端鎖定按鈕
        self.spinStarted.emit()

    def on_btn_released(self):
        """放開按鈕：停止加速 (進入物理減速)"""
        self.wheel.release_holding()
        # 防止再次按下 (一次性互動)
        self.spin_btn.setEnabled(False)
        
    def update_btn_pos(self):
        """[絕對定位] 根據目前的 x, y 與 左側容器位置，計算按鈕座標"""
        # 確保 spin_btn 在最上層且顯示，但如果照片選擇 overlay 正在顯示，避免把按鈕蓋在 overlay 之上
        if hasattr(self, 'spin_btn'):
            # only show/raise if photo selector not visible
            if not (hasattr(self, 'photo_selector') and self.photo_selector.isVisible()):
                self.spin_btn.show()
                self.spin_btn.raise_()
            else:
                # still ensure button is shown but do not raise above overlay
                self.spin_btn.show()
        
        # 如果沒有 spin_btn（尚未建立），直接離開
        if not hasattr(self, 'spin_btn'):
            return

        # 取得左側容器的中心點 X
        # 注意：在程式剛啟動時 geometry 可能尚未完全確定，使用 resizeEvent 修正
        if hasattr(self, 'left_container'):
            container_geo = self.left_container.geometry()
            center_x = container_geo.center().x()
        else:
            center_x = self.width() * 0.35 # 粗略估計

        btn_w = self.spin_btn.width()
        btn_h = self.spin_btn.height()
        
        # 計算 X: 容器中心 + 偏移量 - 按鈕一半寬
        target_x = center_x + self.current_offset_x - (btn_w / 2)
        
        # 計算 Y: 視窗底部 - 底部距離 - 按鈕高
        # 注意: 這裡都用 self.height() (視窗總高)，確保是相對於螢幕底部
        target_y = self.height() - self.current_margin_bottom - btn_h
        
        self.spin_btn.move(int(target_x), int(target_y))

    def set_focus_mode(self, active):
        """專注模式：轉動時將右側名單變暗"""
        op = QGraphicsOpacityEffect(self.right_container)
        op.setOpacity(0.2 if active else 1.0) # 轉動時變很暗 (0.2)
        self.right_container.setGraphicsEffect(op)

    def animate_winner_to_list(self, name):
        """第二階段動畫：名字飛入名單 (Fly-in Collection)"""
        # 1. 計算起點 (螢幕中心) 與 終點 (名單末尾)
        start_pos = self.rect().center()
        
        # 取得右側名單 widget
        list_widget = self.winner_list
        # 計算名單中下一個項目的預計位置
        count = list_widget.count()
        if count > 0:
            last_rect = list_widget.visualItemRect(list_widget.item(count-1))
            target_y = last_rect.bottom() + 10
        else:
            target_y = 10
            
        # 轉換座標 (WinnerList -> DisplayWindow)
        # 注意：winner_list 在 right_container 內，需兩層轉換
        global_list_pos = list_widget.mapToGlobal(QPoint(0, 0))
        local_list_pos = self.mapFromGlobal(global_list_pos)
        
        # 終點 X 設為名單中心，Y 設為列表尾端
        end_x = local_list_pos.x() + list_widget.width() / 2
        end_y = local_list_pos.y() + target_y
        end_pos = QPoint(int(end_x), int(end_y))
        
        # 2. 創建飛行標籤
        fly_label = FlyingLabel(name, self)
        fly_label.move(start_pos)
        
        # 3. 貝茲曲線與屬性動畫
        self.fly_anim = QVariantAnimation(self)
        self.fly_anim.setDuration(1200) # 1.2秒飛入，增加優雅感
        self.fly_anim.setStartValue(0.0)
        self.fly_anim.setEndValue(1.0)
        self.fly_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 控制點 (決定弧度)
        # 設在起點與終點的中間，但往上拉高 (Y軸減小)，形成拋物線
        mid_x = (start_pos.x() + end_pos.x()) / 2
        ctrl_p1 = QPoint(int(mid_x), start_pos.y() - 300) 
        
        def update_step(t):
            # 貝茲曲線公式: (1-t)^2 * P0 + 2(1-t)t * P1 + t^2 * P2
            x = (1-t)**2 * start_pos.x() + 2*(1-t)*t * ctrl_p1.x() + t**2 * end_pos.x()
            y = (1-t)**2 * start_pos.y() + 2*(1-t)*t * ctrl_p1.y() + t**2 * end_pos.y()
            fly_label.move(int(x), int(y))
            
            # 同步縮放 (從 2.5倍 縮到 1.0倍)
            scale = 2.5 - (1.5 * t)
            fly_label.set_scale(scale)

        def on_finished():
            fly_label.close()
            # [重要] 真正將名字加入名單
            self.add_winner(name) 
            # 播放入榜音效 (如果有的話)
            # QApplication.beep() 
            
        self.fly_anim.valueChanged.connect(update_step)
        self.fly_anim.finished.connect(on_finished)
        self.fly_anim.start()

    def add_winner(self, name):
        prize = self.prize_label.text().replace("🎉", "").strip()
        if "準備中" in prize: prize = "特別獎"
        
        # Format: [Prize] Name
        item_text = f"【{prize}】\n   {name}"
        self.winner_list.addItem(item_text)
        self.winner_list.scrollToBottom()

    def resizeEvent(self, event):
        if hasattr(self, 'overlay'):
            self.overlay.resize(self.size())
        if hasattr(self, 'confetti'):
            self.confetti.resize(self.size())
        if hasattr(self, 'cursor_fol_label'):
             self.cursor_fol_label.raise_()
        
        if hasattr(self, 'spin_btn'):
            self.update_btn_pos()
            
        if hasattr(self, 'photo_selector'):
            self.photo_selector.resize(self.size())
            
        super().resizeEvent(event)

    def show_photo_selector(self):
        """顯示照片選擇器 (由控制端觸發)"""
        # 舊的呼叫介面（不提供獎項名稱）維持相容
        self.photo_selector.show_selector()

    def show_photo_selector_for_prize(self, prize_name):
        """顯示照片選擇器並顯示指定的獎項名稱（由 ControlWindow 呼叫）"""
        try:
            self.photo_selector.show_selector(prize_name)
        except Exception:
            # 回退到不帶參數的呼叫
            self.photo_selector.show_selector()

    def on_photo_selected(self, path):
        """當在大螢幕選完照片後"""
        print(f"[Display] Photo selected: {path}")
        try:
            logpath = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'selection.log'))
            with open(logpath, 'a', encoding='utf-8') as f:
                f.write(f"DisplayWindow: on_photo_selected -> {path}\n")
        except Exception:
            pass
        # 更新轉盤：改為延遲執行以避免在選取流程中直接觸發 native 層的 race/crash
        try:
            def _safe_set():
                try:
                    if hasattr(self, 'wheel') and self.wheel is not None:
                        self.wheel.set_presenter_avatar(path)
                except Exception as e:
                    try:
                        logpath = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'selection.log'))
                        with open(logpath, 'a', encoding='utf-8') as f:
                            f.write(f"DisplayWindow: safe_set_presenter_avatar ERROR -> {e}\n")
                    except Exception:
                        pass

            QTimer.singleShot(100, _safe_set)
        except Exception as e:
            print(f"[Display] Unexpected error scheduling set_presenter_avatar: {e}")

        # 通知控制端 (以便存檔與同步)
        try:
            self.avatarUpdated.emit(path)
        except Exception:
            pass

    def update_prize_name(self, prize_name):
        self.prize_label.setText(prize_name)
        
    def show_winner_message(self, winner_name, prize_name):
        self.spin_btn.hide() # 中獎時隱藏按鈕
        self.overlay.show_winner(winner_name, prize_name)
        
    def hide_winner_message(self):
        self.overlay.hide()
        self.spin_btn.show()

    def update_cursor_position(self):
        """定時更新 Logo 位置與層級"""
        # [修正] 確保按鈕在最上層，但當照片選擇 overlay 顯示時，不要把按鈕抬到 overlay 之上
        if hasattr(self, 'spin_btn') and self.spin_btn.isVisible():
            if not (hasattr(self, 'photo_selector') and self.photo_selector.isVisible()):
                self.spin_btn.raise_()
            
        if hasattr(self, 'cursor_fol_label') and self.cursor_fol_label.isVisible():
            # 1. 強制置頂
            self.cursor_fol_label.raise_()
            
            # 2. 偵測滑鼠下方的元件狀態 (檢查是否為手指游標)
            global_pos = QCursor.pos()
            widget_under_mouse = QApplication.widgetAt(global_pos)
            
            is_hovering_btn = False
            if widget_under_mouse:
                # 向上遍歷檢查是否有 PointingHandCursor
                curr = widget_under_mouse
                while curr:
                    if curr.cursor().shape() == Qt.PointingHandCursor:
                        is_hovering_btn = True
                        break
                    if curr.isWindow(): break # 到了視窗層就停止
                    curr = curr.parent()
            
            # 狀態切換邏輯
            target_pixmap = self.pixmap_normal
            current_state_str = "normal"
            
            if is_hovering_btn and self.pixmap_active:
                target_pixmap = self.pixmap_active
                current_state_str = "active"
            
            # 只有在狀態改變時才更新 Pixmap (節省資源)
            if self.cursor_state != current_state_str:
                self.cursor_state = current_state_str
                if target_pixmap:
                    self.cursor_fol_label.setPixmap(target_pixmap)
                    self.cursor_fol_label.setFixedSize(target_pixmap.size())

            # 3. 計算位置
            local_pos = self.mapFromGlobal(global_pos)
            
            
            if self.cursor_state == "active":
                # 手指狀態：放在手指下方且置中
                # [修正] 圖片寬度改為 250，所以向左移 125 以置中
                # 假設手指游標高約 30，所以向下移 30
                target_pos = local_pos + QPoint(-125, 30)
            else:
                # 一般狀態：緊貼箭頭右下
                target_pos = local_pos + QPoint(8, 8)
            
            self.cursor_fol_label.move(target_pos)

    # 移除 eventFilter，改用 Timer 處理全域滑鼠
    # def eventFilter(self, source, event): ...



if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    
    # 嘗試設定 PyQt5 Plugin 路徑
    # 假設 sys.executable 在 .venv/Scripts/python.exe
    venv_root = os.path.dirname(os.path.dirname(sys.executable))
    plugin_path = os.path.join(venv_root, "Lib", "site-packages", "PyQt5", "Qt5", "plugins")
    
    if os.path.exists(plugin_path):
        QCoreApplication.addLibraryPath(plugin_path)
    
    app = QApplication(sys.argv)
    window = DisplayWindow()
    window.show()
    sys.exit(app.exec_())

