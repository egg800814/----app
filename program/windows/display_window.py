import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QVariantAnimation, QEasingCurve, QTimer
from ui_components.lucky_wheel import LuckyWheelWidget
from ui_components.effects import ConfettiWidget, WinnerOverlay, FlyingLabel

class DisplayWindow(QWidget):
    """
    大螢幕視窗 (觀眾視角)
    - 轉盤(左) + 得獎名單(右)
    - 兩段式揭曉與動態特效
    """
    requestSpin = pyqtSignal()
    
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
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        
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
        
        # 轉盤
        self.wheel = LuckyWheelWidget()
        
        # 開始按鈕 (保留，但現在主要由後台控制)
        self.spin_btn = QPushButton("開始抽獎")
        self.spin_btn.setFixedSize(200, 80)
        self.spin_btn.setCursor(Qt.PointingHandCursor)
        self.spin_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e74c3c, stop:1 #c0392b);
                color: white; font-size: 30px; border-radius: 40px; border: 3px solid #fff; font-weight: bold;
            }
            QPushButton:hover { background-color: #ff6b6b; }
            QPushButton:pressed { background-color: #a93226; }
        """)
        self.spin_btn.clicked.connect(self.requestSpin.emit)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.spin_btn)
        btn_layout.addStretch()

        left_layout.addWidget(self.prize_label)
        left_layout.addWidget(self.wheel, 1)
        left_layout.addLayout(btn_layout)
        
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
        main_layout.addWidget(left_container, 7)
        main_layout.addWidget(self.right_container, 3)

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
        super().resizeEvent(event)

    def update_prize_name(self, prize_name):
        self.prize_label.setText(prize_name)
        
    def show_winner_message(self, winner_name, prize_name):
        self.spin_btn.hide() # 中獎時隱藏按鈕
        self.overlay.show_winner(winner_name, prize_name)
        
    def hide_winner_message(self):
        self.overlay.hide()
        self.spin_btn.show()
