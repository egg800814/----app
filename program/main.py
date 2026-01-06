import sys
import os
import random
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                             QFileDialog, QMessageBox, QLineEdit, QComboBox, 
                             QGroupBox, QFormLayout, QFrame, QInputDialog, QDesktopWidget, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, QUrl, QSize, QPropertyAnimation, QEasingCurve, QRectF, pyqtSignal
from PyQt5.QtGui import (QPainter, QColor, QPen, QFont, QRadialGradient, 
                         QPainterPath, QPixmap, QIcon, QImage)
from PyQt5.QtMultimedia import QSoundEffect

# --- 配色設定 ---
COLORS = [
    QColor(220, 20, 60),   # 猩紅
    QColor(255, 215, 0),   # 金色
    QColor(178, 34, 34),   # 耐火磚紅
    QColor(218, 165, 32),  # 麒麟金
    QColor(139, 0, 0),     # 深紅
    QColor(238, 232, 170)  # 蒼麒麟色
]

class LuckyWheelWidget(QWidget):
    spinFinished = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = ["員工A", "員工B", "員工C", "員工D", "員工E"] 
        self.current_angle = 0
        self.rotation_speed = 0
        self.is_spinning = False
        self.friction = 0.985
        
        # 音效設定
        # 音效設定 (建立音效池以支援多重發聲)
        self.tick_sounds = []
        self.tick_index = 0
        if os.path.exists("assets/sounds/tick.wav"):
            for _ in range(50): # 建立 50 個音效實例，避免快速轉動時不夠用
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile("assets/sounds/tick.wav"))
                effect.setVolume(1.0) # 音量全開
                self.tick_sounds.append(effect)
        
        # 載入循環音效 (快/中/慢)
        self.snd_fast = self._load_loop_sound("assets/sounds/fast.wav")
        self.snd_medium = self._load_loop_sound("assets/sounds/medium.wav")
        self.snd_slow = self._load_loop_sound("assets/sounds/slow.wav")
        self.current_sound_mode = None # None, 'fast', 'medium', 'slow'

        # 轉盤邏輯
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_spin)
        self.last_sector_index = -1
        
        # 圖片資源
        self.presenter_pixmap = None 
        self.logo_pixmap = None
        self.load_default_logo()

    def _load_loop_sound(self, filename):
        if os.path.exists(filename):
            snd = QSoundEffect(self)
            snd.setSource(QUrl.fromLocalFile(filename))
            snd.setLoopCount(QSoundEffect.Infinite)
            snd.setVolume(1.0)
            return snd
        return None

    def load_default_logo(self):
        if os.path.exists("assets/images/logo.png"):
            self.logo_pixmap = QPixmap("assets/images/logo.png")

    def set_items(self, items_text):
        if isinstance(items_text, list):
             self.items = items_text
        elif not items_text.strip():
            self.items = []
        else:
            self.items = [line.strip() for line in items_text.split('\n') if line.strip()]
        self.update()

    def set_presenter_avatar(self, image_path):
        size = 100
        if image_path:
            original = QPixmap(image_path)
            self.presenter_pixmap = QPixmap(size, size)
            self.presenter_pixmap.fill(Qt.transparent)
            painter = QPainter(self.presenter_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addEllipse(0, 0, size, size)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, size, size, original)
            painter.end()
        else:
            self.presenter_pixmap = None
        self.update()

    def _update_sound_volumes(self, mode):
        # 根據模式調整音量 (只開啟對應模式的聲音)
        if self.snd_fast: self.snd_fast.setVolume(1.0 if mode == 'fast' else 0.0)
        if self.snd_medium: self.snd_medium.setVolume(1.0 if mode == 'medium' else 0.0)
        if self.snd_slow: self.snd_slow.setVolume(1.0 if mode == 'slow' else 0.0)

    def start_spin(self, initial_speed=None):
        if not self.items or self.is_spinning:
            return
        
        if initial_speed is not None:
             self.rotation_speed = initial_speed
        else:
             self.rotation_speed = random.uniform(25, 40)
             
        self.is_spinning = True
        
        # [預先啟動所有循環音效] 以音量控制切換，避免播放時 lag
        if self.snd_fast: 
            self.snd_fast.setVolume(0)
            self.snd_fast.play()
        if self.snd_medium:
            self.snd_medium.setVolume(0) 
            self.snd_medium.play()
        if self.snd_slow: 
            self.snd_slow.setVolume(0)
            self.snd_slow.play()
        
        # 初始狀態通常是 fast (如果速度夠快)
        initial_mode = 'fast' if self.rotation_speed > 20 else 'tick'
        self._update_sound_volumes(initial_mode)
        self.current_sound_mode = initial_mode
        
        self.timer.start(10) # [修正] 提高更新頻率，讓動畫更流暢 (原本16ms=60fps, 10ms=100fps) 

    def update_spin(self):
        self.current_angle += self.rotation_speed
        self.current_angle %= 360
        self.rotation_speed *= self.friction
        
        # --- 音效觸發邏輯 ---
        # 決定聲音模式
        target_mode = 'tick'
        if self.rotation_speed > 20:
            target_mode = 'fast'
        elif self.rotation_speed > 8:
            target_mode = 'medium'
        elif self.rotation_speed > 4: # [調整] 提高門檻，讓最後單音的階段更長一點 (4以下的都算單音)
            target_mode = 'slow'
        else:
            target_mode = 'tick'
            
        # 模式切換邏輯
        # 模式切換邏輯 (改用音量控制，不在此處 stop/play 避免 lag)
        if target_mode != self.current_sound_mode:
            self._update_sound_volumes(target_mode)
            self.current_sound_mode = target_mode

        n = len(self.items)
        if n > 0:
            slice_angle = 360 / n
            relative_angle = (270 - self.current_angle) % 360
            current_index = int(relative_angle / slice_angle)
            
            # [修正] 絕對索引變更偵測
            # 只有在 'tick' 模式下才使用原本的單音觸發
            if target_mode == 'tick':
                 # 只要跨越格子，或者剛進入 tick 模式的第一個 frame (防止切換瞬間漏掉)
                 if current_index != self.last_sector_index:
                    if self.is_spinning and self.rotation_speed > 0:
                         if self.tick_sounds:
                             effect = self.tick_sounds[self.tick_index]
                             if effect.isPlaying():
                                 effect.stop() 
                             effect.play()
                             self.tick_index = (self.tick_index + 1) % len(self.tick_sounds)
                    self.last_sector_index = current_index
            else:
                # 在 Loop 模式下只更新索引但不播單音
                self.last_sector_index = current_index

        if self.rotation_speed < 0.1:
            self.stop_spin()
        
        self.update()

    def stop_spin(self):
        self.timer.stop()
        self.is_spinning = False
        self.rotation_speed = 0
        # 延遲 300 毫秒後才公布中獎結果，增加張力
        # 延遲 300 毫秒後才公布中獎結果，增加張力
        self._stop_all_loops()
        QTimer.singleShot(1000, self.determine_winner)

    def _stop_all_loops(self):
        if self.snd_fast: self.snd_fast.stop()
        if self.snd_medium: self.snd_medium.stop()
        if self.snd_slow: self.snd_slow.stop()
        self.current_sound_mode = None

    def determine_winner(self):
        if not self.items: return
        n = len(self.items)
        slice_angle = 360 / n
        
        # [修正] 計算中獎索引 (修正為270度 - 角度)
        normalized_angle = (270 - self.current_angle) % 360
        index = int(normalized_angle / slice_angle)
        
        # 防止索引越界
        index = index % n
        
        winner = self.items[index]
        self.spinFinished.emit(winner)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2 * 0.8 

        # 1. 轉盤背景光暈
        painter.setPen(Qt.NoPen)
        radial = QRadialGradient(center, radius * 1.1)
        radial.setColorAt(0, QColor(255, 215, 0, 80))
        radial.setColorAt(1, Qt.transparent)
        painter.setBrush(radial)
        painter.drawEllipse(center, radius * 1.1, radius * 1.1)

        # 2. 扇形
        n = len(self.items)
        if n > 0:
            slice_angle = 360 / n
            painter.save()
            try:
                painter.translate(center)
                painter.rotate(self.current_angle)

                for i in range(n):
                    painter.setBrush(COLORS[i % len(COLORS)])
                    painter.setPen(QPen(Qt.white, 3))
                    path = QPainterPath()
                    path.moveTo(0, 0)
                    path.arcTo(-radius, -radius, radius*2, radius*2, -i*slice_angle, -slice_angle)
                    path.closeSubpath()
                    painter.drawPath(path)
                    
                    # 文字
                    painter.save()
                    try:
                        mid_angle = -i * slice_angle - slice_angle / 2
                        painter.rotate(-mid_angle) 
                        # [修正] 文字大小隨轉盤半徑縮放
                        font_size = max(10, int(radius * 0.08))
                        if n > 12: font_size = int(font_size * 0.8) # 項目多時縮小字體
                        font = QFont("Microsoft JhengHei", font_size, QFont.Bold)
                        painter.setFont(font)
                        painter.setPen(Qt.white)
                        
                        painter.drawText(QRectF(radius*0.2, -30, radius*0.75, 60), Qt.AlignRight | Qt.AlignVCenter, self.items[i])
                    finally:
                        painter.restore()
            finally:
                painter.restore()

        # 3. 指針 (從中間往外指，指向12點鐘方向)
        self.draw_pointer(painter, rect, radius)

        # 4. 中心區域 (抽獎人頭像 或 LOGO)
        # 如果有抽獎人頭像，優先顯示；否則顯示 LOGO
        logo_radius = radius * 0.25
        painter.setBrush(Qt.white)
        painter.setPen(QPen(QColor(218, 165, 32), 5))
        painter.drawEllipse(center, logo_radius, logo_radius)
        
        display_pixmap = self.presenter_pixmap if self.presenter_pixmap else self.logo_pixmap

        if display_pixmap:
            painter.save()
            try:
                path = QPainterPath()
                path.addEllipse(center, logo_radius-5, logo_radius-5)
                painter.setClipPath(path)
                target_rect = QRectF(center.x() - logo_radius, center.y() - logo_radius, logo_radius*2, logo_radius*2)
                painter.drawPixmap(target_rect.toRect(), display_pixmap)
            finally:
                painter.restore()
        
        if self.presenter_pixmap:
             # 如果是抽獎人，加個文字標籤
            painter.setBrush(QColor(0, 0, 0, 150))
            painter.setPen(Qt.NoPen)
            # 調整標籤位置到圓圈下方
            label_w = 80
            label_h = 24
            lx = center.x() - label_w/2
            ly = center.y() + logo_radius - 20 
            painter.drawRoundedRect(int(lx), int(ly), int(label_w), int(label_h), 10, 10)
            painter.setPen(Qt.white)
            painter.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            painter.drawText(QRectF(lx, ly, label_w, label_h), Qt.AlignCenter, "抽獎人")

    def draw_pointer(self, painter, rect, radius):
        center_x = rect.center().x()
        center_y = rect.center().y()
        
        logo_diameter = radius * 0.5
        pointer_len = logo_diameter * 0.85
        
        # [修正] 指針寬度改為動態比例，避免小視窗時指針太肥 (約為半徑的 1/4)
        pointer_w = radius * 0.25
        
        path = QPainterPath()
        path.moveTo(center_x, center_y - pointer_len)
        path.lineTo(center_x + pointer_w/2, center_y)
        path.lineTo(center_x - pointer_w/2, center_y)
        path.closeSubpath()
        
        painter.save()
        try:
            painter.translate(2, 2)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 100))
            painter.drawPath(path)
        finally:
            painter.restore()

        painter.save() # New save for the second part distinct from first
        try:
            painter.setPen(QPen(Qt.white, 2))
            painter.setBrush(QColor(138, 43, 226)) 
            painter.drawPath(path)
        finally:
             painter.restore()


class WinnerOverlay(QWidget):
    """大螢幕的中獎顯示遮罩"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True) # 讓點擊穿透 (如果需要)
        self.hide()
        
        # 半透明背景
        self.setStyleSheet("background-color: rgba(0, 0, 0, 200);")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.msg_label = QLabel()
        self.msg_label.setAlignment(Qt.AlignCenter)
        self.msg_label.setStyleSheet("""
            QLabel {
                color: #f1c40f;
                font-size: 80px;
                font-weight: bold;
                font-family: "Microsoft JhengHei";
            }
        """)
        layout.addWidget(self.msg_label)
        
    def show_winner(self, winner_name, prize_name):
        text = f"恭喜\n\n【{winner_name}】\n\n獲得\n\n🎁 {prize_name} 🎁"
        self.msg_label.setText(text)
        self.show()
        self.raise_()
        
        # 動畫淡入效果
        self.opacity = QPropertyAnimation(self, b"windowOpacity")
        self.opacity.setDuration(500)
        self.opacity.setStartValue(0)
        self.opacity.setEndValue(1)
        self.opacity.start()

    def paintEvent(self, event):
        # 繪製半透明背景，因 setStyleSheet 在某些情況下對全螢幕視窗可能無效
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200))


class DisplayWindow(QWidget):
    """
    大螢幕視窗 (觀眾視角)
    - 只有轉盤 + 開始標籤
    - 顯示中獎動畫
    """
    requestSpin = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("大螢幕抽獎")
        
        # Initialize overlay FIRST so it exists for any subsequent resize events
        self.overlay = WinnerOverlay(self)
        
        # 全螢幕設定
        self.showFullScreen()
        
        if os.path.exists("background_display.jpg"):
             self.setStyleSheet(f"DisplayWindow {{ border-image: url(background_display.jpg) 0 0 0 0 stretch stretch; }}")
        else:
             self.setStyleSheet("background-color: #111;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)

        # 頂部：目前抽獎項目標題
        self.prize_label = QLabel("🎉 MDIT 尾牙抽獎活動準備中 🎉")
        self.prize_label.setAlignment(Qt.AlignCenter)
        self.prize_label.setStyleSheet("""
            QLabel {
                color: #f1c40f;
                font-size: 60px;
                font-weight: bold;
                font-family: "Microsoft JhengHei";
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(self.prize_label)
        
        # 轉盤部分
        self.wheel = LuckyWheelWidget()
        layout.addWidget(self.wheel, 1) # 佔據大部分空間
        
        # 開始按鈕
        self.spin_btn = QPushButton("開始抽獎")
        self.spin_btn.setFixedSize(300, 100)
        self.spin_btn.setCursor(Qt.PointingHandCursor)
        self.spin_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e74c3c, stop:1 #c0392b);
                color: white;
                font-size: 40px;
                border-radius: 50px;
                border: 4px solid #fff;
                font-weight: bold;
                font-family: "Microsoft JhengHei";
            }
            QPushButton:hover {
                background-color: #ff6b6b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
        
        # 讓按鈕置中
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.spin_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.spin_btn.clicked.connect(self.requestSpin.emit)
        
    
    def resizeEvent(self, event):
        if hasattr(self, 'overlay'):
            self.overlay.resize(self.size())
        super().resizeEvent(event)

    def update_prize_name(self, prize_name):
        self.prize_label.setText(prize_name)
        
    def show_winner_message(self, winner_name, prize_name):
        self.spin_btn.hide() # 中獎時隱藏按鈕
        self.overlay.show_winner(winner_name, prize_name)
        
    def hide_winner_message(self):
        self.overlay.hide()
        self.spin_btn.show()

class MainWindow(QMainWindow):
    """
    系統控制視窗 (操作者視角)
    - 包含控制面板
    - 預覽畫面
    - 決定是否保留中獎結果
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("後台控制系統 - 90週年尾牙")
        self.resize(1200, 800) # 可縮放，預設大小
        
        # 音效
        self.win_sound = QSoundEffect()
        # 音效
        self.win_sound = QSoundEffect()
        if os.path.exists("assets/sounds/win.wav"):
            self.win_sound.setSource(QUrl.fromLocalFile("assets/sounds/win.wav"))
            self.win_sound.setVolume(0.8)

        self.prizes = [
            "副總經理獎 - 6,000元", 
            "副總經理獎 - 6,000元", 
            "總經理獎 - 8,000元", 
            "總經理獎 - 8,000元", 
            "社長獎 - 10,000元"
        ]
        self.prize_avatars = {}
        
        # 初始化大螢幕視窗
        self.display_window = DisplayWindow()
        self.display_window.show() # 開啟第二視窗 (通常會出現在第二螢幕，若無則重疊)
        
        # 嘗試將第二視窗移至第二螢幕
        desktop = QApplication.desktop()
        if desktop.screenCount() > 1:
            second_screen_rect = desktop.screenGeometry(1)
            self.display_window.move(second_screen_rect.topLeft())
            self.display_window.showFullScreen()
        
        # 連接大螢幕的開始信號
        self.display_window.requestSpin.connect(self.master_start_spin)
        
        # 若是關閉系統視窗，連同大螢幕一起關閉
        # 透過 closeEvent 處理
        
        self.init_ui()
        self.setup_style()
        
        # [新增] 即時監控 Timer
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_live_monitor)
        self.monitor_timer.start(200) # 每 200ms 更新一次
        
    def closeEvent(self, event):
        # 可以在此加入確認對話框
        reply = QMessageBox.question(self, '關閉系統',
                                     "確定要結束抽獎程式嗎？\n這將會關閉大螢幕畫面。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.display_window.close()
            event.accept()
        else:
            event.ignore()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_widget.setStyleSheet("background-color: #2c3e50;")

        layout = QHBoxLayout(main_widget)
        
        # --- 左側：控制面板 ---
        control_panel = QFrame()
        control_panel.setFixedWidth(400)
        control_panel.setStyleSheet("""
            QFrame { background-color: #34495e; color: white; }
            QLabel { color: bdfeff; font-weight: bold; font-size: 16px; font-family: "Microsoft JhengHei"; }
            QPushButton { background-color: #2980b9; color: white; padding: 10px; border-radius: 5px; font-weight: bold; font-family: "Microsoft JhengHei";}
            QPushButton:hover { background-color: #3498db; }
            QLineEdit, QComboBox, QTextEdit { padding: 8px; color: #333; background: #ecf0f1; border-radius: 4px; font-size: 14px; }
            QGroupBox { border: 2px solid #7f8c8d; border-radius: 5px; margin-top: 20px; font-weight: bold; color: #ecf0f1; padding: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        
        ctrl_layout = QVBoxLayout(control_panel)
        
        # 標題
        title = QLabel("🎛️ 系統控制台")
        title.setStyleSheet("font-size: 24px; color: gold; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignCenter)
        ctrl_layout.addWidget(title)

        # 1. 獎項管理區
        prize_group = QGroupBox("🏆 獎項設定")
        pg_layout = QVBoxLayout(prize_group)
        
        self.prize_combo = QComboBox()
        self.prize_combo.addItems(self.prizes)
        self.prize_combo.setCurrentIndex(-1) # [修改] 預設不選擇任何獎項
        self.prize_combo.currentIndexChanged.connect(self.update_preview_content)
        
        edit_prize_btn = QPushButton("✏️ 修改名稱")
        edit_prize_btn.clicked.connect(self.edit_prize)
        
        combo_layout = QHBoxLayout()
        combo_layout.setContentsMargins(0, 0, 0, 0)
        combo_layout.addWidget(self.prize_combo, 2)
        combo_layout.addWidget(edit_prize_btn, 1)
        
        self.new_prize_input = QLineEdit()
        self.new_prize_input.setPlaceholderText("輸入新獎項...")
        add_prize_btn = QPushButton("➕ 追加獎項")
        add_prize_btn.clicked.connect(self.add_prize)
        
        pg_layout.addLayout(combo_layout)
        pg_layout.addWidget(self.new_prize_input)
        pg_layout.addWidget(add_prize_btn)
        
        # 2. 名單管理區
        list_group = QGroupBox("👥 名單管理")
        lg_layout = QVBoxLayout(list_group)
        
        self.list_edit = QTextEdit()
        self.list_edit.setPlainText(
            "許惠英副總\n"
            "陳逸人\n林宛萩\n黃聖文\n陳淑萍\n陳瑞雯\n洪立恩\n蔡沛容\n林聖家\n"
            "張書友\n譚文男\n邱振威\n莊達富\n顏宏光\n黃智傑\n簡鴻彬\n楊浩智\n李承哲\n李哲旭\n許漢德\n徐明億\n吳敬霆\n"
            "黃珮珊\n楊麗玉\n江辰平\n范孝慈\n陳妍淇\n張芮溱"
        )
        
        shuffle_btn = QPushButton("🔀 打散名單排序")
        shuffle_btn.setStyleSheet("background-color: #2980b9; margin-top: 5px;")
        shuffle_btn.clicked.connect(self.shuffle_list)

        update_list_btn = QPushButton("🔄 更新暫存名單 (僅預覽)")
        update_list_btn.setStyleSheet("background-color: #27ae60; margin-top: 5px;")
        update_list_btn.clicked.connect(self.update_preview_list)
        
        btns_layout = QHBoxLayout()
        btns_layout.addWidget(shuffle_btn)
        btns_layout.addWidget(update_list_btn)
        
        lg_layout.addWidget(self.list_edit)
        lg_layout.addLayout(btns_layout)
        
        # 3. 抽獎人設定
        presenter_btn = QPushButton("📷 設定此獎項抽獎人頭像")
        presenter_btn.setStyleSheet("background-color: #e67e22;")
        presenter_btn.clicked.connect(self.load_avatar)
        
        # 4. 發布與控制
        
        # [新增] 發布按鈕
        publish_btn = QPushButton("🚀 發布設定到大螢幕 🚀")
        publish_btn.setStyleSheet("""
            QPushButton { 
                background-color: #8e44ad; color: white; margin-top: 20px; font-size: 18px; padding: 15px; 
            }
            QPushButton:hover { background-color: #9b59b6; }
        """)
        publish_btn.clicked.connect(self.publish_to_display)

        # 系統操作
        close_sys_btn = QPushButton("❌ 關閉系統")
        close_sys_btn.setStyleSheet("background-color: #c0392b; margin-top: 10px;")
        close_sys_btn.clicked.connect(self.close) # 觸發 closeEvent

        ctrl_layout.addWidget(prize_group)
        ctrl_layout.addWidget(list_group)
        ctrl_layout.addWidget(presenter_btn)
        ctrl_layout.addWidget(publish_btn)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(close_sys_btn)
        
        # --- 右側：預覽與主操作 ---
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        
        self.preview_label = QLabel("📺 準備狀態 (PREVIEW)")
        self.preview_label.setStyleSheet("font-size: 20px; color: white; font-weight: bold;")
        self.preview_label.setAlignment(Qt.AlignCenter)
        
        # 預覽用的轉盤
        self.preview_wheel = LuckyWheelWidget()
        # [修正] 移除固定大小，改成自適應縮放
        self.preview_wheel.setMinimumSize(500, 500) 
        self.preview_wheel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 為了保持預覽轉盤居中
        wheel_container = QWidget()
        wc_layout = QHBoxLayout(wheel_container)
        wc_layout.addStretch()
        wc_layout.addWidget(self.preview_wheel)
        wc_layout.addStretch()
        
        # 在系統端的開始按鈕
        self.sys_spin_btn = QPushButton("🎰 START (系統端啟動)")
        self.sys_spin_btn.setMinimumHeight(60)
        self.sys_spin_btn.setStyleSheet("""
            QPushButton { 
                background-color: gold;
                color: black; font-size: 24px; border-radius: 10px; border: 2px solid white;
            }
            QPushButton:hover { background-color: #f1c40f; }
        """)
        self.sys_spin_btn.clicked.connect(self.master_start_spin)
        
        # [新增] 右下角即時監控
        kp_layout = QHBoxLayout()
        kp_layout.addStretch()
        
        monitor_container = QFrame()
        monitor_container.setStyleSheet("background-color: black; border: 2px solid #e74c3c;")
        monitor_layout = QVBoxLayout(monitor_container)
        monitor_layout.setContentsMargins(2, 2, 2, 2)
        
        lbl_monitor_title = QLabel("🔴 LIVE OUTPUT")
        lbl_monitor_title.setStyleSheet("color: red; font-weight: bold; background: none; border: none;")
        lbl_monitor_title.setAlignment(Qt.AlignCenter)
        
        self.live_monitor_label = QLabel()
        self.live_monitor_label.setFixedSize(320, 180) # 16:9 小視窗
        self.live_monitor_label.setStyleSheet("background-color: #000; border: 1px solid #333;")
        self.live_monitor_label.setScaledContents(True) # 讓截圖自動縮放填滿
        
        monitor_layout.addWidget(lbl_monitor_title)
        monitor_layout.addWidget(self.live_monitor_label)
        
        kp_layout.addWidget(monitor_container)
        
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(wheel_container, 1)
        preview_layout.addWidget(self.sys_spin_btn)
        preview_layout.addLayout(kp_layout) # 放到最下方
        
        layout.addWidget(control_panel, 1)
        layout.addWidget(preview_panel, 2)

        # 連接【大螢幕】轉盤的結束信號 (即使系統端不轉，邏輯由大螢幕觸發)
        self.display_window.wheel.spinFinished.connect(self.on_spin_finished)
        
        # 初始化預覽數據
        self.update_preview_list()
        
        # [新增] 即時監控 Timer
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_live_monitor)
        self.monitor_timer.start(1000) # 每 1000ms 更新一次 (降低資源消耗)

    def update_live_monitor(self):
        """定期截圖大螢幕並顯示在監控區"""
        if self.display_window.isVisible():
            pixmap = self.display_window.grab()
            self.live_monitor_label.setPixmap(pixmap)

    def setup_style(self):
        # 設定全域 MessageBox 樣式
        self.setStyleSheet(self.styleSheet() + """
            QMessageBox { background-color: #333; color: white; }
            QMessageBox QLabel { color: white; font-size: 16px; }
            QMessageBox QPushButton { background-color: gold; color: black; padding: 5px 15px; }
        """)

    def update_preview_content(self):
        """僅更新預覽畫面，不影響大螢幕"""
        current_prize = self.prize_combo.currentText()
        avatar_path = self.prize_avatars.get(current_prize)
        self.preview_wheel.set_presenter_avatar(avatar_path)
        
        # 更新此處的標題以顯示目前選擇的獎項
        self.preview_label.setText(f"📺 預覽中：{current_prize}")
        
        # 大螢幕不更新，等待發布
        
    def publish_to_display(self):
        """將目前設定發布到大螢幕"""
        current_prize = self.prize_combo.currentText()
        avatar_path = self.prize_avatars.get(current_prize)
        items_text = self.list_edit.toPlainText()
        
        # 更新大螢幕
        self.display_window.update_prize_name(current_prize)
        self.display_window.wheel.set_items(items_text)
        self.display_window.wheel.set_presenter_avatar(avatar_path)
        
        # [修改] 發布時，如果大螢幕還在中獎畫面，這也是一種 "重置" 訊號
        self.display_window.hide_winner_message()
        self.display_window.spin_btn.setEnabled(True)
        
        msg = QMessageBox(self)
        msg.setWindowTitle("發布成功")
        msg.setText("設定已同步至主螢幕！")
        msg.setIcon(QMessageBox.NoIcon)
        msg.exec_()

    def edit_prize(self):
        current_index = self.prize_combo.currentIndex()
        if current_index < 0: return
        
        old_name = self.prizes[current_index]
        new_name, ok = QInputDialog.getText(self, "修改獎項", "請輸入新的獎項名稱:", text=old_name)
        
        if ok and new_name.strip():
            new_name = new_name.strip()
            self.prizes[current_index] = new_name
            self.prize_combo.setItemText(current_index, new_name)
            
            if old_name in self.prize_avatars:
                self.prize_avatars[new_name] = self.prize_avatars.pop(old_name)
                
            self.update_preview_content()
            QMessageBox.information(self, "成功", "獎項名稱已修改！")

    def add_prize(self):
        text = self.new_prize_input.text().strip()
        if text:
            self.prizes.append(text)
            self.prize_combo.addItem(text)
            self.prize_combo.setCurrentText(text)
            self.new_prize_input.clear()
            msg = QMessageBox(self)
            msg.setWindowTitle("成功")
            msg.setText("獎項已追加！")
            msg.setIcon(QMessageBox.NoIcon)
            msg.exec_()

    def shuffle_list(self):
        text = self.list_edit.toPlainText()
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            random.shuffle(lines)
            self.list_edit.setPlainText("\n".join(lines))
            self.update_preview_list() # 自動更新預覽，讓使用者直接看到打散後的轉盤

    def update_preview_list(self):
        items_text = self.list_edit.toPlainText()
        # 僅更新預覽轉盤
        self.preview_wheel.set_items(items_text)

    def load_avatar(self):
        fname, _ = QFileDialog.getOpenFileName(self, '選擇照片', '', "Images (*.jpg *.jpeg *.png *.bmp *.JPG *.JPEG *.PNG);;All Files (*)")
        if fname:
            image = QImage(fname)
            if image.isNull():
                QMessageBox.warning(self, "讀取錯誤", "圖片讀取失敗，請確認格式。")
                return

            current_prize = self.prize_combo.currentText()
            self.prize_avatars[current_prize] = fname
            
            self.update_preview_content()
            msg = QMessageBox(self)
            msg.setWindowTitle("設定成功")
            msg.setText(f"【{current_prize}】的抽獎人已更新 (請記得發布到大螢幕)")
            msg.setIcon(QMessageBox.NoIcon)
            msg.exec_()

    def master_start_spin(self):
        """主控端與顯示端同步啟動"""
        # 檢查是否轉動中 (檢查大螢幕狀態)
        if self.display_window.wheel.is_spinning:
            return

        # 產生同步的速度參數
        speed = random.uniform(25, 40)
        
        # self.preview_wheel.start_spin(speed) # [修改] 系統端轉盤不跟著轉
        self.display_window.wheel.start_spin(speed)
        self.display_window.spin_btn.setEnabled(False) # 暫時禁用
        self.sys_spin_btn.setEnabled(False)

    def on_spin_finished(self, winner_name):
        """當轉盤停止時，由 ControlWindow 處理邏輯"""
        # if self.win_sound.status() != QSoundEffect.Error:
        #    self.win_sound.play()
        
        current_prize = self.prize_combo.currentText()
        
        # 1. 大螢幕顯示結果 (純展示)
        self.display_window.show_winner_message(winner_name, current_prize)
        
        # 2. 系統端跳出決策視窗
        msg = QMessageBox(self)
        msg.setWindowTitle("🎉 抽獎結果確認")
        msg.setText(f"結果：{winner_name}\n獎項：{current_prize}\n\n請問是否確認此結果？")
        msg.setIcon(QMessageBox.NoIcon)
        
        confirm_btn = msg.addButton("確認 (移除名單)", QMessageBox.YesRole)
        keep_btn = msg.addButton("保留名單 (測試/重抽)", QMessageBox.NoRole)
        
        msg.exec_()
        
        if msg.clickedButton() == confirm_btn:
            # 確認中獎：移除名單
            items = self.list_edit.toPlainText().split('\n')
            items = [x.strip() for x in items if x.strip() != winner_name]
            self.list_edit.setPlainText("\n".join(items))
            self.update_preview_list()
            
            msg_ok = QMessageBox(self)
            msg_ok.setWindowTitle("完成")
            msg_ok.setText(f"已將 {winner_name} 從轉盤移除。")
            msg_ok.setIcon(QMessageBox.NoIcon)
            msg_ok.exec_()
        else:
            # 保留名單：什麼都不做，或者視為重抽
            pass
            
        # 3. 恢復系統端操作，但大螢幕保持中獎畫面直到「發布」
        self.sys_spin_btn.setEnabled(True)

if __name__ == '__main__':
    from PyQt5.QtCore import QCoreApplication
    
    venv_root = os.path.dirname(os.path.dirname(sys.executable))
    plugin_path = os.path.join(venv_root, "Lib", "site-packages", "PyQt5", "Qt5", "plugins")
    
    if os.path.exists(plugin_path):
        QCoreApplication.addLibraryPath(plugin_path)
    
    app = QApplication(sys.argv)
    
    # 建立主視窗 (控制台) - 它會自動建立並管理 DisplayWindow
    control_window = MainWindow() 
    control_window.show() # 控制台可以一般顯示，不一定要全螢幕
    
    font = QFont("Microsoft JhengHei", 10)
    app.setFont(font)
    
    sys.exit(app.exec_())