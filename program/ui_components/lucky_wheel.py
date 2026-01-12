"""
lucky_wheel.py
--------------
描述：幸運轉盤客製化元件 (Custom Widget)。
功能：負責轉盤的核心繪圖與邏輯，包含：
      1. 繪製扇形、獎項文字、指針、光暈與特效 (速度線、聚光燈)。
      2. 模擬物理旋轉 (慣性、摩擦力、力場阻尼、磁力歸中)。
      3. 管理轉動動畫與減速停車邏輯。
      4. 處理 LED 跑馬燈特效。
"""
import os
import random
import math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QUrl, QPropertyAnimation, QEasingCurve, QRectF, pyqtSignal, pyqtProperty, QPoint
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QRadialGradient, QPainterPath, QPixmap, QBrush, QLinearGradient
from PyQt5.QtMultimedia import QSoundEffect
from utils.config import COLORS, resource_path

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
        if os.path.exists(resource_path("assets/sounds/tick.wav")):
            for _ in range(50): # 建立 50 個音效實例，避免快速轉動時不夠用
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(resource_path("assets/sounds/tick.wav")))
                effect.setVolume(1.0) # 音量全開
                self.tick_sounds.append(effect)
        
        # 載入循環音效 (快/中/慢)
        self.snd_fast = self._load_loop_sound(resource_path("assets/sounds/fast.wav"))
        self.snd_medium = self._load_loop_sound(resource_path("assets/sounds/medium.wav"))
        self.snd_slow = self._load_loop_sound(resource_path("assets/sounds/slow.wav"))
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

        # 震動特效偏移量
        self.shake_offset = QPoint(0, 0)
        
        # [新增] 長按互動旗標
        self.is_holding = False
        self.max_speed = 50.0

    def _load_loop_sound(self, filename):
        if os.path.exists(filename):
            snd = QSoundEffect(self)
            snd.setSource(QUrl.fromLocalFile(filename))
            snd.setLoopCount(QSoundEffect.Infinite)
            snd.setVolume(1.0)
            return snd
        return None

    def load_default_logo(self):
        if os.path.exists(resource_path("assets/images/logo.png")):
            self.logo_pixmap = QPixmap(resource_path("assets/images/logo.png"))

    def set_items(self, items_text):
        if isinstance(items_text, list):
             self.items = items_text
        elif not items_text.strip():
            self.items = []
        else:
            self.items = [line.strip() for line in items_text.split('\n') if line.strip()]
        self.update()

    def set_presenter_avatar(self, image_path, crop_mode='smart'):
        # crop_mode: 'smart' (自動縮放裁切上半身), 'fit' (填滿圓形)
        size = 900 # [設定] 轉盤中心頭像的清晰度 (尺寸越大越清晰)
        try:
            if image_path and os.path.exists(image_path):
                original = QPixmap(image_path)
                if original.isNull():
                    print(f"[LuckyWheel] Error: Failed to load image from {image_path}")
                    self.presenter_pixmap = None
                else:
                    if crop_mode == 'smart':
                        # [優化] 自動裁切邏輯：頂部居中裁切 (Top-Center Crop) + 自動縮放 (Zoom)
                        # 透過 zoom_factor 放大圖片，只取上半身特寫
                        zoom_factor = 1.8  # [設定] 縮放係數：1.0=原圖裁切, 1.35=半身特寫, 1.5=大頭特寫
                        
                        target_w = int(size * zoom_factor)
                        target_h = int(size * zoom_factor)
                        
                        # 1. 等比縮放至填滿 (size * zoom) 的區域
                        scaled = original.scaled(target_w, target_h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                        
                        # 2. 計算裁切位置 (保留水平中心，垂直靠上)
                        # 這樣可以確保裁切出的是 "放大的上半身"
                        crop_x = (scaled.width() - size) // 2
                        
                        # [微調] 垂直偏移：稍微往下挪一點點 (避免頭頂切太齊)，但主要還是靠上
                        crop_y = 0 
                        if crop_x < 0: crop_x = 0
                        
                        # 3. 取得裁切後的正方形 (size x size)
                        cropped = scaled.copy(crop_x, crop_y, size, size)
                        final_pix = cropped
                        
                    else:
                        # [還原] 一般填滿模式 (Fit) - 用於電腦端選取時
                        # 直接縮放至填滿圓形 (KeepAspectRatioByExpanding) 然後居中裁切
                        scaled = original.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                        
                        crop_x = (scaled.width() - size) // 2
                        crop_y = (scaled.height() - size) // 2
                        
                        cropped = scaled.copy(crop_x, crop_y, size, size)
                        final_pix = cropped

                    self.presenter_pixmap = QPixmap(size, size)
                    self.presenter_pixmap.fill(Qt.transparent)
                    
                    painter = QPainter(self.presenter_pixmap)
                    try:
                        painter.setRenderHint(QPainter.Antialiasing)
                        path = QPainterPath()
                        path.addEllipse(0, 0, size, size)
                        painter.setClipPath(path)
                        # 繪製裁切好的正方形
                        painter.drawPixmap(0, 0, final_pix)
                    finally:
                        painter.end()
            else:
                self.presenter_pixmap = None
        except Exception as e:
             print(f"[LuckyWheel] Exception in set_presenter_avatar: {e}")
             self.presenter_pixmap = None

        self.update()

    def update_leds(self):
        # LED 動畫更新
        # [新增] 頻閃模式判定 (快停下來前)
        if self.is_spinning and 0 < abs(self.rotation_speed) < 8.0:
             # Strobe Light: 快速切換開關
             # 頻率: update_leds 是 50ms 一次，每次切換 = 10Hz 閃爍 (非常快)
             if not hasattr(self, 'strobe_on'): self.strobe_on = False
             self.strobe_on = not self.strobe_on
        elif self.is_spinning:
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

    # [保留 for 相容性] 瞬間啟動 (系統端可能會用到，或者作為 Fallback)
    def start_spin(self, initial_speed=None):
        if not self.items or self.is_spinning:
            return
        
        if initial_speed is not None:
             self.rotation_speed = initial_speed
        else:
             self.rotation_speed = random.uniform(25, 40)
             
        self.is_spinning = True
        self.is_holding = False # 確保不是 Holding 模式
        
        # [預先啟動所有循環音效] 以音量控制切換，避免播放時 lag
        self._start_loop_sounds()
        
        # 初始狀態通常是 fast (如果速度夠快)
        initial_mode = 'fast' if self.rotation_speed > 20 else 'tick'
        self._update_sound_volumes(initial_mode)
        self.current_sound_mode = initial_mode
        
        self.timer.start(10)

    # [新增] 按下按鈕：開始加速旋轉
    def start_holding(self):
        if not self.items: return
        if self.is_spinning and not self.is_holding: return # 已經在跑且不是 holding 狀態，忽略
        
        self.is_spinning = True
        self.is_holding = True
        
        # 若是剛開始，速度歸零開始加速
        if not self.timer.isActive():
             self.rotation_speed = 0
             self._start_loop_sounds()
             self.timer.start(10)
             
    # [新增] 放開按鈕：進入減速模式
    def release_holding(self):
        if self.is_holding:
            self.is_holding = False
            
            # [修正] 避免按太快導致速度不夠就停了
            # 如果放開時速度還太慢（例如點一下就放開），強制給予一個基礎初速
            if self.rotation_speed < 30.0:
                self.rotation_speed = random.uniform(30.0, 40.0)
            
            # 此時 rotation_speed 應該已經很快，接下來交給 update_spin 的物理邏輯去減速

    def _start_loop_sounds(self):
        if self.snd_fast: 
            self.snd_fast.setVolume(0)
            self.snd_fast.play()
        if self.snd_medium:
            self.snd_medium.setVolume(0) 
            self.snd_medium.play()
        if self.snd_slow: 
            self.snd_slow.setVolume(0)
            self.snd_slow.play()

    def update_spin(self):
        # [修改] 1. 長按加速邏輯
        if self.is_holding:
            # 加速直到 Max Speed
            if self.rotation_speed < self.max_speed:
                self.rotation_speed += 0.8 # 加速度
            else:
                self.rotation_speed = self.max_speed
            
            # 旋轉更新 (此時不受物理擋板影響，全力衝刺)
            self.current_angle += self.rotation_speed
            self.current_angle %= 360
            
            # 聲音更新
            abs_speed = abs(self.rotation_speed)
            target_mode = 'fast' if abs_speed > 20 else ('medium' if abs_speed > 8 else 'tick')
            if target_mode != self.current_sound_mode:
                self._update_sound_volumes(target_mode)
                self.current_sound_mode = target_mode
                
            # 仍然要更新 last_sector_index 避免放開瞬間 index 亂跳
            n = len(self.items)
            if n > 0:
                slice_angle = 360 / n
                relative_angle = (270 - self.current_angle) % 360
                self.last_sector_index = int(relative_angle / slice_angle)
            
            return # [跳出] 長按時不執行減速/擋板物理
            
        # -------------------------------------------------------------------------
        # 以下為原本的物理減速邏輯 (放開按鈕後執行)
        # -------------------------------------------------------------------------

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
                self.rotation_speed *= self.peg_friction # 強力阻尼 (可調整)
                
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
         # [新增] 震動特效：每次跟著音效產生微小位移
         shift_x = random.randint(-3, 3) 
         shift_y = random.randint(-3, 3)
         self.shake_offset = QPoint(shift_x, shift_y)

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
        
        # [新增] 應用震動位移
        if not self.shake_offset.isNull():
            painter.translate(self.shake_offset)
            # 畫完這一幀後重置，確保只持續一幀 (Impulse)
            # 注意：不能在這裡直接修改 self.shake_offset，因為 paintEvent 可能會被重繪多次
            # 但在這個邏輯下，我們希望它顯現一次就消失，所以這是一種簡單的 auto-reset
            self.shake_offset = QPoint(0, 0)
            
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

                # Loop 1: 繪製扇形 (背景)
                for i in range(n):
                    painter.save()
                    painter.rotate(-i * slice_angle)
                    
                    base_c = COLORS[i % len(COLORS)]
                    
                    # 建立線性漸層 (從圓心往外)
                    grad = QLinearGradient(0, 0, radius, 0)
                    grad.setColorAt(0.0, base_c.darker(130))
                    grad.setColorAt(0.5, base_c.lighter(140))
                    grad.setColorAt(1.0, base_c.darker(130))
                    
                    painter.setBrush(QBrush(grad))
                    painter.setPen(QPen(Qt.white, 3))
                    
                    path = QPainterPath()
                    path.moveTo(0, 0)
                    path.arcTo(-radius, -radius, radius*2, radius*2, 0, -slice_angle)
                    path.closeSubpath()
                    painter.drawPath(path)
                    painter.restore()

                # Loop 2: 繪製文字 (確保文字永遠在扇形上方，且清晰可見)
                for i in range(n):
                    painter.save()
                    try:
                        # 計算文字角度 (每個扇區的中間線)
                        mid_angle = -i * slice_angle - slice_angle / 2
                        painter.rotate(-mid_angle) 
                        
                        font_size = max(10, int(radius * 0.08))
                        if n > 12: font_size = int(font_size * 0.8)
                        font = QFont("Microsoft JhengHei", font_size, QFont.Bold)
                        painter.setFont(font)
                        
                        text_rect = QRectF(radius*0.2, -30, radius*0.75, 60)
                        text_str = self.items[i]
                        
                        # [新增] 文字陰影 (Drop Shadow) - 解決金色背景吃字問題
                        painter.setPen(QColor(0, 0, 0, 120)) # 半透明黑
                        # 稍微偏移畫一次黑色的
                        painter.drawText(text_rect.translated(2, 2), Qt.AlignRight | Qt.AlignVCenter, text_str)
                        
                        # 畫白色正文
                        painter.setPen(Qt.white)
                        painter.drawText(text_rect, Qt.AlignRight | Qt.AlignVCenter, text_str)

                    finally:
                        painter.restore()
            finally:
                painter.restore()
        


        # [新增] 速度線特效 (當速度夠快時)
        if abs(self.rotation_speed) > 20:
             self.draw_speed_lines(painter, center, radius)

        # 3. 指針 (從中間往外指，指向12點鐘方向)
        self.draw_pointer(painter, rect, radius)

        # 4. 中心區域 (抽獎人頭像 或 LOGO)
        # 如果有抽獎人頭像，優先顯示；否則顯示 LOGO
        logo_radius = radius * 0.25 # [設定] 轉盤中心頭像的顯示大小 (半徑比例 0.25)
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

        # [新增] 聚光燈特效 (轉動時背景變暗，聚焦於指針)
        if self.is_spinning:
            self.draw_spotlight(painter, rect, radius)
            
        # [修改] 將 LED 移至最上層繪製 (避免被 Spotlight 遮住)
        self.draw_leds(painter, center, radius)

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
            if self.is_spinning and 0 < abs(self.rotation_speed) < 8.0:
                # [新增] 頻閃模式 (全亮/全暗)
                is_on = getattr(self, 'strobe_on', True)
                if is_on:
                    color = QColor(255, 255, 255, 255) # 超亮白
                    alpha = 255
                else:
                    color = QColor(0, 0, 0, 0)
                    alpha = 0
            
            elif self.is_spinning:
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

    def draw_speed_lines(self, painter, center, radius):
        """繪製速度線特效 (白色半透明放射狀線條)"""
        # 使用隨機與時間因子產生動態感
        # 這裡不重度依賴 random 以免閃爍太嚴重，可以用 current_angle 當作種子
        
        painter.save()
        painter.translate(center)
        
        # 不需要跟隨轉盤旋轉 (這是一種視覺殘留特效)
        # 但給一點偏移讓它看起來不是死的
        import time
        t = time.time() * 10 
        
        count = 12 # 線條數量
        
        for i in range(count):
            painter.save()
            
            # 角度分佈均勻但帶有一些隨機偏移
            base_angle = i * (360 / count)
            # 隨機偏移 (-15 ~ +15 度)
            # 使用偽隨機，讓它在每幀變化
            offset = (math.sin(t + i) * 20) 
            angle = base_angle + offset
            
            painter.rotate(angle)
            
            # 繪製長條三角形
            # 從外圈向內指
            # Y軸負方向是上方
            
            # 隨機長度與寬度
            length_factor = 0.3 + (math.cos(t * 2 + i) * 0.1) # 20% ~ 40% 半徑長
            width_factor = 3 + (math.sin(t * 3 + i) * 2)      # 1 ~ 5 px 寬
            
            # 透明度
            alpha = int(100 + math.sin(t + i*2) * 80) # 20 ~ 180
            alpha = max(0, min(255, alpha))
            
            color = QColor(255, 255, 255, alpha)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            
            path = QPainterPath()
            # 三角形尖端朝圓心 (半徑 * (1-length)) 位置
            inner_r = radius * (1.0 - length_factor)
            outer_r = radius * 1.05 # 稍微超出轉盤
            
            # 這裡我們畫一個細長的梯形/三角形
            # y 軸向上 (painter 預設是 y 向下，但我們 rotate 了)
            # 其實不用太複雜，就畫一個三角形
            # p1: (0, -outer_r)
            # p2: (-w, -outer_r)
            # p3: (0, -inner_r)
            # p4: (w, -outer_r)
            
            path.moveTo(0, -inner_r)
            path.lineTo(-width_factor, -outer_r)
            path.lineTo(width_factor, -outer_r)
            path.closeSubpath()
            
            painter.drawPath(path)
            
            painter.restore()
            
        painter.restore()

    def draw_spotlight(self, painter, rect, radius):
        """繪製聚光燈效果 (黑色遮罩 + 挖洞)"""
        # 1. 建立遮罩路徑 (全螢幕矩形)
        overlay_path = QPainterPath()
        overlay_path.addRect(QRectF(rect))
        
        # 2. 建立挖洞路徑 (圓形亮區)
        # 洞的位置應該在指針尖端，並往上延伸以覆蓋文字
        center = rect.center()
        
        # 文字大約分佈在半徑的 0.2 ~ 0.95 處
        # 我們將聚光燈中心定在約 0.65 半徑處 (偏上方)，以覆蓋指針下方的文字區
        target_dist = radius * 0.65
        spot_center_y = center.y() - target_dist
        
        # 亮區大小 (加大以覆蓋整個扇區文字)
        spot_radius = radius * 0.45
        spot_center = QPoint(center.x(), int(spot_center_y))
        
        spot_path = QPainterPath()
        spot_path.addEllipse(spot_center, spot_radius, spot_radius)
        
        # 3. 相減得到「有洞的遮罩」 (OddEvenFill 規則)
        overlay_path.addPath(spot_path)
        
        painter.save()
        painter.setPen(Qt.NoPen)
        # 半透明黑色
        painter.setBrush(QColor(0, 0, 0, 160))
        # 設置填充規則為 OddEven (重疊部分挖空)
        painter.drawPath(overlay_path)
        painter.restore()


