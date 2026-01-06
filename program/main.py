import sys
import os
import random
import math
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                             QFileDialog, QMessageBox, QLineEdit, QComboBox, 
                             QGroupBox, QFormLayout, QFrame, QInputDialog, QDesktopWidget, QSizePolicy, QListWidget, QGraphicsOpacityEffect)
from PyQt5.QtCore import Qt, QTimer, QUrl, QSize, QPropertyAnimation, QEasingCurve, QRectF, pyqtSignal, pyqtProperty, QPoint, QVariantAnimation
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
    
    def get_angle(self):
        return self.current_angle

    def set_angle(self, val):
        self.current_angle = val
        self.update()
        self._process_tick_logic_only() # 在動畫模式下，只處理由角度變動觸發的單音

    angle = pyqtProperty(float, fget=get_angle, fset=set_angle)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = ["員工A", "員工B", "員工C", "員工D", "員工E"] 
        self.current_angle = 0
        self.rotation_speed = 0
        self.is_spinning = False
        self.base_friction = 0.99 # 一般滑行摩擦力 (阻力小)
        self.peg_friction = 0.85  # 撞針摩擦力 (阻力大，模擬碰到擋板減速)
        self.friction = self.base_friction # 當前摩擦力
        
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

        # LED 裝飾邏輯
        self.led_count = 36
        self.led_phase = 0.0
        self.led_timer = QTimer(self)
        self.led_timer.timeout.connect(self.update_leds)
        self.led_timer.start(50) # 20 FPS for LEDs (順暢度足夠)

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

    def update_leds(self):
        # LED 動畫更新
        if self.is_spinning:
            # 跑馬燈模式：速度隨轉速變化
            # rotation_speed 是 "度/10ms"，這裡 led_timer 是 50ms 一次
            # 讓 LED 跑動速度跟轉盤看起來有連動感
            speed_factor = self.rotation_speed * 0.5 
            if speed_factor < 0.5: speed_factor = 0.5 # 最低速度
            self.led_phase = (self.led_phase + speed_factor) % self.led_count
        else:
            # 呼吸燈模式
            self.led_phase += 0.4 # 加快速度製造緊張感
        
        # 如果沒有在轉動 (update_spin 沒在跑)，這裡要觸發 update 讓 LED 動起來
        if not self.is_spinning:
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

        # [新增] 真實物理場模擬 (Potential Energy Field)
        # 將擋板視為高能量區，指針在中間是低能量區
        # 當指針靠近擋板(扇區邊緣)時，會受到一個「排斥力/推力」使其離開擋板
        n = len(self.items)
        if n > 0:
            slice_angle = 360 / n
            offset = (270 - self.current_angle) % slice_angle
            
            # 參數設定
            peg_influence = 0.5  # [修正] 縮小影響範圍 (只在交界處 1 度內)
            force_strength = 0.24 # 原本的力道
            
            total_force = 0
            
            # [修正] 物理邏輯：前進時給予強大阻力 (撞擊)，後退時給予極小推力 (滑落)
            # 避免像彈簧一樣劇烈反彈
            # [修正] 全對稱擋板物理邏輯
            # 無論正轉或反轉，撞到擋板都會受到相同的物理阻力
            
            # 1. 檢測與"下一個擋板" (扇區終點) 的碰撞 -> 產生負向推力 (阻擋正轉)
            dist_from_end = slice_angle - offset
            if dist_from_end < peg_influence:
                factor = (peg_influence - dist_from_end) / peg_influence
                total_force -= force_strength * factor 

            # 2. 檢測與"上一個擋板" (扇區起點) 的碰撞 -> 產生正向推力 (阻擋反轉)
            if offset < peg_influence:
                factor = (peg_influence - offset) / peg_influence
                total_force += force_strength * factor 
            
            # 儲存舊速度以偵測碰撞反彈
            old_speed = self.rotation_speed
            
            # [修正] 避免反彈後持續被力場加速
            # 如果力場方向與速度方向相同 (代表正在被推著跑/反彈加速中)
            # 大幅削減這個推力，讓它變成 "滑落" 而非 "加速"
            if (total_force * self.rotation_speed) > 0:
                total_force *= 0.05 # [強制修正] 用戶之前改回0.6導致搖擺，這裡強制改回0.05以消除搖擺
            
            self.rotation_speed += total_force

            # [新增] 磁力歸中機制 (Center Magnet)
            # 當速度慢下來時，施加一個微小的力，將指針拉向扇區的正中央
            # 這能保證轉盤永遠不會停在交界處 (解決"無法判定中獎"的問題)
            if abs(self.rotation_speed) < 5.0:
                center_offset = slice_angle / 2
                dist_to_center = center_offset - offset
                # 磁力係數，越靠近中心吸力越小
                magnet_force = dist_to_center * 0.03 
                self.rotation_speed += magnet_force
            
            # [新增] 只有在 "離開擋板" (回彈滑落) 的時候，施加超重摩擦力
            is_rebounding_next = (dist_from_end < peg_influence and self.rotation_speed < 0)
            is_rebounding_prev = (offset < peg_influence and self.rotation_speed > 0)
            
            if is_rebounding_next or is_rebounding_prev:
                self.rotation_speed *= 0.85 # 強力阻尼
                
            # [核心修正] 動能耗損邏輯
            
            # [核心修正] 動能耗損邏輯
            # 當速度方向改變 (例如正轉變反轉，代表撞到擋板彈回來了)
            # 強制將動力降為剩餘的 30% (模擬非彈性碰撞)
            if (old_speed > 0 and self.rotation_speed < 0) or (old_speed < 0 and self.rotation_speed > 0):
                self.rotation_speed *= 0.3
            
            # # [新增] 限制最大反彈速度 (避免倒退嚕太快)
            # if self.rotation_speed < -2.0:
            #     self.rotation_speed = -2.0

        # 摩擦力衰減 (全程使用 base_friction，因為阻力來源已經由力場模擬了)
        self.rotation_speed *= self.base_friction
        
        # --- 音效觸發邏輯 ---
        # 決定聲音模式
        abs_speed = abs(self.rotation_speed)
        target_mode = 'tick'
        if abs_speed > 20: target_mode = 'fast'
        elif abs_speed > 8: target_mode = 'medium'
        elif abs_speed > 4: target_mode = 'slow'
        else: target_mode = 'tick'
            
        # 模式切換邏輯
        if target_mode != self.current_sound_mode:
            self._update_sound_volumes(target_mode)
            self.current_sound_mode = target_mode

        if n > 0:
            # 更新索引與播放滴答聲 (tick)
            # 使用目前的指針角度判定
            relative_angle = (270 - self.current_angle) % 360
            current_index = int(relative_angle / slice_angle)
            
            if target_mode == 'tick':
                 if current_index != self.last_sector_index:
                    # 只要跨越格子邊界 (index 改變)，就播放音效
                    if abs_speed > 0.1: # 避免靜止時微動一直響
                        self._play_tick()
                    self.last_sector_index = current_index
            else:
                self.last_sector_index = current_index

        # [修正] 停止條件
        # 必須同時滿足：
        # 1. 速度極低
        # 2. 不受顯著外力 (代表已經滑進扇區中間，不在擋板上)
        is_stable = False
        if n > 0:
             # 檢查是否在穩定的中間區域 (沒受擋板力)
             # 即 offset > peg_influence AND dist_from_end > peg_influence
             offset = (270 - self.current_angle) % slice_angle
             dist_from_end = 360/n - offset
             if offset > peg_influence and dist_from_end > peg_influence:
                 is_stable = True
        
        if abs(self.rotation_speed) <= 0.05 and self.is_spinning and is_stable:
             self.rotation_speed = 0
             self.timer.stop()
             self.is_spinning = False
             self._stop_all_loops()
             
             winner = self.items[current_index]
             # [調整] 轉盤停下後，停頓 1 秒再彈出中獎畫面 (原本是 3秒 太久了)
             QTimer.singleShot(1000, lambda: self._emit_finished(winner))
        
        self.update()

    def _play_tick(self):
         if self.tick_sounds:
             effect = self.tick_sounds[self.tick_index]
             if effect.isPlaying():
                 effect.stop() 
             effect.play()
             self.tick_index = (self.tick_index + 1) % len(self.tick_sounds)

    def _process_tick_logic_only(self):
        # 專門給 QPropertyAnimation 使用的輕量化邏輯 (只判斷過扇區)
        n = len(self.items)
        if n > 0:
            slice_angle = 360 / n
            relative_angle = (270 - self.current_angle) % 360
            current_index = int(relative_angle / slice_angle)
            
            if current_index != self.last_sector_index:
                self._play_tick()
                self.last_sector_index = current_index

    def stop_spin(self):
        # 將物理旋轉模式切換為「動畫著陸模式」
        self.timer.stop()
        self.is_spinning = False # 標記物理引擎停止
        self._stop_all_loops()   # 停止循環音效
        
        # 決定中獎者 (隨機)
        target_index = random.randint(0, len(self.items) - 1)
        
        # 計算目標角度 (要讓指針停在該扇區中央)
        # 指針在 270 度 (上方)
        # 270 - angle = (index * slice) + (slice/2)
        # angle = 270 - (index * slice + slice/2)
        slice_angle = 360 / len(self.items)
        target_angle_base = 270 - (target_index * slice_angle + slice_angle / 2)
        
        # 為了避免看起來像 "停了又跑" (偷跑)，我們不再固定加圈數，只補足到目標角度
        # 並使用 OutQuart 曲線，讓最後的減速更線性、沒有回彈，確保視覺上的絕對靜止
        
        current_mod = self.current_angle % 360
        # 如果 target_angle_base 比 current_mod 小，要加 360 確保是未來 (順時針找最近的目標)
        diff = target_angle_base - current_mod
        while diff < 0: diff += 360
        
        # [核心修正] 動態補償邏輯
        # 如果目標距離太近 (<150度)，會導致煞車太急；太遠則不需要補圈
        # 加上一圈可以讓短距離變長，長距離保持原樣 (避免總距離過長導致加速)
        if diff < 150:
            diff += 360
            
        # 只轉「不足一圈」的距離，讓它最快停下
        final_angle = self.current_angle + diff
        
        # 啟動動畫
        self.anim = QPropertyAnimation(self, b"angle")
        self.anim.setDuration(2500) # [調整] 延長煞車時間至 2.5 秒
        self.anim.setStartValue(self.current_angle)
        self.anim.setEndValue(final_angle)
        self.anim.setEasingCurve(QEasingCurve.OutQuart) # 平滑減速至停止，無回彈，避免誤會
        self.anim.finished.connect(lambda: self.on_anim_finished(target_index))
        self.anim.start()

    def on_anim_finished(self, winner_index):
        # 確保最後角度精確
        winner = self.items[winner_index]
        # [新增] 停止後等待 3 秒再發送訊號 (顯示結果)
        QTimer.singleShot(3000, lambda: self._emit_finished(winner))

    def _emit_finished(self, winner):
        self.spinFinished.emit(winner)
        # Animation finished, clean up?
        # self.current_angle %= 360 # Optional reset, but might jump visually if redraw happens

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
        
        # [新增] 繪製 LED 燈圈 (畫在扇形上方，避免被蓋住)
        self.draw_leds(painter, center, radius)

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
            painter.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            painter.drawText(QRectF(lx, ly, label_w, label_h), Qt.AlignCenter, "抽獎人")

    def draw_leds(self, painter, center, radius):
        # LED 參數
        led_radius = radius * 1.12 # 稍微在光暈外
        bulb_size = radius * 0.04  # 燈泡大小
        
        painter.save()
        painter.translate(center)
        
        for i in range(self.led_count):
            angle_deg = i * (360 / self.led_count)
            angle_rad = math.radians(angle_deg)
            
            # 計算位置
            lx = led_radius * math.cos(angle_rad)
            ly = led_radius * math.sin(angle_rad)
            
            # 計算亮度/顏色
            if self.is_spinning:
                # 跑馬燈 (Chasing)
                # 計算當前 LED 距離 "跑馬頭" (led_phase) 的距離
                # 這裡 led_phase 是 0 ~ led_count 的浮點數
                dist = (self.led_phase - i) % self.led_count
                
                # 拖尾效果: 距離越近越亮
                # 假設尾巴長度 8 顆
                tail_len = 8.0
                if dist < tail_len:
                    intensity = 1.0 - (dist / tail_len)
                else:
                    intensity = 0.1 # 底色微亮
                
                # 顏色: 旋轉時用彩色或亮黃色
                # 這裡用 金黃色 高亮
                alpha = int(255 * intensity)
                # color = QColor(255, 215, 0, alpha)
                # 讓頭部稍微白一點
                if intensity > 0.8:
                     color = QColor(255, 255, 200, alpha)
                else:
                     color = QColor(255, 165, 0, alpha)
                     
            else:
                # 呼吸燈 (Breathing)
                # 全部一起閃爍
                # sin 範圍 -1 ~ 1 -> 0 ~ 1
                intensity = (math.sin(self.led_phase) + 1) / 2
                # 限制最小值，不要全暗
                intensity = 0.3 + 0.7 * intensity
                
                alpha = int(255 * intensity)
                # 呼吸時用 喜氣洋洋的紅色 或 金色? 用多色交替?
                # 偶數紅，奇數黃
                if i % 2 == 0:
                    color = QColor(255, 69, 0, alpha) # 紅橙
                else:
                    color = QColor(255, 215, 0, alpha) # 金
            
            # 畫燈泡
            
            # 1. 燈泡光暈
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), int(alpha * 0.5)))
            painter.drawEllipse(QRectF(lx - bulb_size*0.8, ly - bulb_size*0.8, bulb_size*1.6, bulb_size*1.6))
            
            # 2. 燈泡本體
            painter.setBrush(color)
            painter.drawEllipse(QRectF(lx - bulb_size/2, ly - bulb_size/2, bulb_size, bulb_size))
            
        painter.restore()

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


class ConfettiWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.particles = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_particles)
        self.is_active = False

    def start(self):
        self.is_active = True
        self.particles = []
        for _ in range(100):
            self.particles.append(self._create_particle())
        self.timer.start(20)
        self.show()
        self.raise_()

    def stop(self):
        self.is_active = False
        self.timer.stop()
        self.hide()

    def _create_particle(self):
        return {
            'x': random.randint(0, self.width()),
            'y': random.randint(-self.height(), 0),
            'speed': random.randint(5, 15),
            'size': random.randint(5, 10),
            'color': random.choice(COLORS),
            'drift': random.uniform(-2, 2)
        }

    def update_particles(self):
        if not self.is_active: return
        for p in self.particles:
            p['y'] += p['speed']
            p['x'] += p['drift']
            if p['y'] > self.height():
                # Reset to top
                p['y'] = random.randint(-50, 0)
                p['x'] = random.randint(0, self.width())
        self.update()

    def paintEvent(self, event):
        if not self.is_active: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for p in self.particles:
            painter.setBrush(p['color'])
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(p['x']), int(p['y']), p['size'], p['size'])



class FlyingLabel(QLabel):
    """飛行動畫用的臨時標籤"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("color: gold; font-weight: bold; font-size: 40px; background: transparent;")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.adjustSize()
        self.show()

    def set_scale(self, scale):
        # 簡單模擬縮放 (調整字體大小)
        font = self.font()
        font.setPointSizeF(40 * scale)
        self.setFont(font)
        self.adjustSize()

class WinnerOverlay(QWidget):
    """大螢幕的中獎顯示遮罩"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.85);")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.title_label = QLabel("🎉 恭喜中獎 🎉")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #e74c3c; font-size: 80px; font-weight: bold; margin-bottom: 20px;")
        
        self.prize_label = QLabel("")
        self.prize_label.setAlignment(Qt.AlignCenter)
        self.prize_label.setStyleSheet("color: #ffffff; font-size: 50px; font-weight: bold; margin-bottom: 10px;")

        self.name_label = QLabel("")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("color: #f1c40f; font-size: 120px; font-weight: bold;")
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.prize_label)
        layout.addWidget(self.name_label)

    def show_winner(self, name, prize):
        self.prize_label.setText(f"🎁 {prize} 🎁")
        self.name_label.setText(name)
        self.show()
        self.raise_()
        
        # [新增] 第一階段：彈出慶祝動畫 (Pop-up Celebration)
        # 使用不透明度 + 幾何彈跳模擬 Scale Up 效果
        if not self.name_label.graphicsEffect():
             eff = QGraphicsOpacityEffect(self.name_label)
             self.name_label.setGraphicsEffect(eff)
        
        # 透明度淡入
        self.op_anim = QPropertyAnimation(self.name_label.graphicsEffect(), b"opacity")
        self.op_anim.setDuration(800)
        self.op_anim.setStartValue(0.0)
        self.op_anim.setEndValue(1.0)
        self.op_anim.setEasingCurve(QEasingCurve.OutBack)
        self.op_anim.start()
        
        # 背景淡入
        self.bg_anim = QPropertyAnimation(self, b"windowOpacity")
        self.bg_anim.setDuration(500)
        self.bg_anim.setStartValue(0)
        self.bg_anim.setEndValue(1)
        self.bg_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200))


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