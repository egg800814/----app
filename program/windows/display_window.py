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

class DisplayWindow(QWidget):
    """
    大螢幕視窗 (觀眾視角)
    - 轉盤(左) + 得獎名單(右)
    - 兩段式揭曉與動態特效
    """
    requestSpin = pyqtSignal() # 保留給其他用途，或相容性
    spinStarted = pyqtSignal() # [新增] 通知主控端轉動開始 (鎖定UI)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("大螢幕抽獎")
        
        # Overlay and Confetti (Initialize early)
        self.overlay = WinnerOverlay(self)
        self.confetti = ConfettiWidget(self)
        self.overlay.hide()
        self.confetti.hide()
        
        # [新增] 初始化飛行動畫屬性
        self.fly_anim = None
        
        # [修改] 載入兩種狀態的槌子游標
        self.cursor_normal = None
        self.cursor_pressed = None

        try:
             base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
             project_root = os.path.dirname(base_dir)
             
             # load wood_hammer1.png (Normal)
             hammer1_path = os.path.join(project_root, "assets", "images", "wood_hammer1.png")
             if not os.path.exists(hammer1_path):
                 hammer1_path = os.path.join(base_dir, "assets", "images", "wood_hammer1.png") # Fallback
            
             if os.path.exists(hammer1_path):
                 pix1 = QPixmap(hammer1_path).scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                 self.cursor_normal = QCursor(pix1, 20, 20)
             else:
                 print(f"Hammer1 not found at {hammer1_path}")

             # load wood_hammer2.png (Pressed)
             hammer2_path = os.path.join(project_root, "assets", "images", "wood_hammer2.png")
             if not os.path.exists(hammer2_path):
                 hammer2_path = os.path.join(base_dir, "assets", "images", "wood_hammer2.png") # Fallback

             if os.path.exists(hammer2_path):
                 pix2 = QPixmap(hammer2_path).scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                 # 調整 Pressed 狀態的熱點，模擬槌下去的位移感 (如果需要)
                 # 這裡暫時設為一樣，確保對齊
                 self.cursor_pressed = QCursor(pix2, 20, 20)
             else:
                 print(f"Hammer2 not found at {hammer2_path}")

             # 設定初始游標
             if self.cursor_normal:
                 self.setCursor(self.cursor_normal)

        except Exception as e:
            print(f"Error setting custom cursors: {e}")

        self.setMouseTracking(True) # 啟用滑鼠追蹤



        # 全螢幕設定
        self.showFullScreen()
        
        if os.path.exists("background_display.jpg"):
             self.setStyleSheet(f"DisplayWindow {{ border-image: url(background_display.jpg) 0 0 0 0 stretch stretch; }}")
        else:
             self.setStyleSheet("background-color: #2c3e50;")

        # Main Layout (Horizontal)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # --- LEFT SIDE: Wheel & Title ---
        self.left_container = QWidget()
        left_layout = QVBoxLayout(self.left_container)
        
        # 頂部：目前抽獎項目標題
        self.prize_label = QLabel("🎉 MDIT 尾牙抽獎活動 🎉")
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
        
        # 轉盤
        self.wheel = LuckyWheelWidget()
        # [修改] 轉盤連接 - 監聽開始轉動訊號
        self.wheel.spinStarted.connect(self.on_wheel_spin_started)
        
        left_layout.addWidget(self.prize_label)
        left_layout.addWidget(self.wheel, 1)
        
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

    def on_wheel_spin_started(self):
        """當轉盤開始轉動時觸發"""
        # 進入專注模式 (變暗背景等)
        self.set_focus_mode(True)
        # 通知控制端鎖定按鈕
        self.spinStarted.emit()

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
        # [移除] cursor_fol_label 相關
        
        super().resizeEvent(event)

    def update_prize_name(self, prize_name):
        self.prize_label.setText(prize_name)
        
    def show_winner_message(self, winner_name, prize_name):
        # self.spin_btn.hide() # 中獎時隱藏按鈕
        self.overlay.show_winner(winner_name, prize_name)
        
    def hide_winner_message(self):
        self.overlay.hide()
        # self.spin_btn.show()


    # 移除 eventFilter，改用 Timer 處理全域滑鼠
    # def eventFilter(self, source, event): ...




    def mousePressEvent(self, event):
        """按下時切換成 Hammer 2 (敲擊狀態)"""
        if event.button() == Qt.LeftButton and self.cursor_pressed:
            self.setCursor(self.cursor_pressed)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """放開時切換回 Hammer 1 (一般狀態)"""
        if event.button() == Qt.LeftButton and self.cursor_normal:
            self.setCursor(self.cursor_normal)
        super().mouseReleaseEvent(event)

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

