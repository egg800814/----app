import random
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QColor
from utils.config import COLORS

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
