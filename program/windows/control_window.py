import os
import random
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                             QFileDialog, QMessageBox, QLineEdit, QComboBox, 
                             QGroupBox, QFrame, QInputDialog, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, QUrl, QSize
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtMultimedia import QSoundEffect
from .display_window import DisplayWindow
from ui_components.lucky_wheel import LuckyWheelWidget

class ControlWindow(QMainWindow):
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
        
        # [新增] 一開始就先同步名單到大螢幕 (不需按發布)
        self.display_window.wheel.set_items(self.list_edit.toPlainText())
        
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
        
        self.display_window.set_focus_mode(True)
        # 2. 開始轉動
        self.display_window.wheel.start_spin()
        
        # 3. UI 狀態
        self.display_window.spin_btn.setEnabled(False)
        self.sys_spin_btn.setEnabled(False)

    def on_spin_finished(self, winner_name):
        """當轉盤動畫完全停止時觸發"""
        current_prize = self.prize_combo.currentText()
        
        # 1. 大螢幕顯示彈窗 (Overlay) (使用 DisplayWindow 內的 overlay 物件)
        if hasattr(self.display_window, 'overlay'):
            self.display_window.overlay.show_winner(winner_name, current_prize)
        
        # [修改] 中獎音樂提前至此處播放
        if hasattr(self, 'win_sound') and self.win_sound.source().isValid():
            self.win_sound.play()

        # 2. 系統端跳出確認視窗 (Action)
        msg = QMessageBox(self)
        msg.setWindowTitle("中獎確認")
        msg.setText(f"獎項：{current_prize}\n中獎者：{winner_name}\n\n請確認是否歸檔？")
        btn_confirm = msg.addButton("確認 (Confirm)", QMessageBox.YesRole)
        btn_cancel = msg.addButton("保留 (Cancel)", QMessageBox.NoRole)
        msg.setIcon(QMessageBox.Question)
        msg.exec_()
        
        if msg.clickedButton() == btn_confirm:
            self.confirm_winner(winner_name)
        else:
            # Cancel: 隱藏 Overlay，重置狀態，但不移除名單
            self.display_window.overlay.hide()
            self.display_window.set_focus_mode(False)
            self.sys_spin_btn.setEnabled(True)
            self.display_window.spin_btn.setEnabled(True)

    def confirm_winner(self, winner_name):
        # 1. 啟動彩帶 (音效已提前播放)
        
        self.display_window.overlay.hide()
        self.display_window.confetti.start()
        
        # 3秒後停止彩帶
        QTimer.singleShot(3000, self.display_window.confetti.stop)
        
        # [修改] 2. 執行飛入動畫並加入名單
        self.display_window.animate_winner_to_list(winner_name)
        
        # 3. 從轉盤名單移除
        current_text = self.list_edit.toPlainText()
        lines = [line.strip() for line in current_text.split('\n') if line.strip()]
        
        if winner_name in lines:
            lines.remove(winner_name)
            self.list_edit.setPlainText("\n".join(lines))
            self.display_window.wheel.set_items(lines)
            self.update_preview_list() # 更新預覽
        
        # 4. 恢復一般模式
        self.display_window.set_focus_mode(False)
        self.sys_spin_btn.setEnabled(True)
        self.display_window.spin_btn.setEnabled(True)
