import wave
import random
import struct
import math

def generate_tick(filename, duration_ms=50, volume_scale=1.0):
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000.0)
    
    with wave.open(filename, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        
        data = []
        for i in range(num_samples):
            t = float(i) / sample_rate
            
            # 成分1: 短正弦波 (高音)
            vol_sine = 25000.0 * volume_scale * math.exp(-t * 150)
            wave_val = math.sin(2 * math.pi * 2000 * t) 
            
            # 成分2: 雜訊 (Impact)
            vol_noise = 20000.0 * volume_scale * math.exp(-t * 400)
            noise_val = random.uniform(-1, 1)
            
            value = (vol_sine * wave_val) + (vol_noise * noise_val)
            
            if value > 32767: value = 32767
            if value < -32768: value = -32768
            data.append(int(value))
            
        packed_data = struct.pack('<' + ('h' * len(data)), *data)
        f.writeframes(packed_data)
    print(f"Generated {filename}")

def generate_loop(filename, ticks_per_sec, total_duration_sec=2.0):
    sample_rate = 44100
    total_samples = int(sample_rate * total_duration_sec)
    samples_per_tick = int(sample_rate / ticks_per_sec)
    
    with wave.open(filename, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        
        data = []
        current_tick_sample = 0
        
        for i in range(total_samples):
            # 判斷是否該觸發 tick
            pos_in_tick = i % samples_per_tick
            
            value = 0
            if pos_in_tick < 2000: # 只有前 ~45ms 有聲音
                t = float(pos_in_tick) / sample_rate
                
                # 稍微降低音量避免太吵
                vol_scale = 0.8
                
                vol_sine = 25000.0 * vol_scale * math.exp(-t * 150)
                wave_val = math.sin(2 * math.pi * 2000 * t) 
                
                vol_noise = 20000.0 * vol_scale * math.exp(-t * 400)
                noise_val = random.uniform(-1, 1)
                
                value = (vol_sine * wave_val) + (vol_noise * noise_val)
            
            if value > 32767: value = 32767
            if value < -32768: value = -32768
            data.append(int(value))
            
        packed_data = struct.pack('<' + ('h' * len(data)), *data)
        f.writeframes(packed_data)
    print(f"Generated Loop {filename}")

def generate_fanfare(filename):
    sample_rate = 44100
    
    def get_wave(freq, t):
        # 銅管合成：鋸齒波 + 些許正弦波修飾
        # 基頻 + 泛音序列
        val = 0
        for h in range(1, 8):
            # 泛音強度隨頻率遞減
            amp = 1.0 / h
            val += amp * math.sin(2 * math.pi * freq * h * t)
        return val * 0.4

    def generate_note(freq, duration, vol=1.0):
        ns = int(sample_rate * duration)
        res = []
        for i in range(ns):
            t = float(i) / sample_rate
            # ADSR Envelope
            env = 1.0
            attack = 0.08
            release = 0.3
            
            if t < attack:
                env = t / attack
            elif t > duration - release:
                env = max(0, (duration - t) / release)
            
            val = get_wave(freq, t) * env * vol * 8000.0
            res.append(val)
        return res

    # 旋律 (頻率, 時長) - 模仿經典勝利開場 (約 5 秒含餘音)
    # 節奏: Ta-Ta-Ta-Daaa... (Pause) ... Daaa-Daaa
    
    # 旋律聲部
    melody_notes = [
        (523.25, 0.2), # C4
        (0,      0.05),
        (523.25, 0.2), # C4
        (0,      0.05),
        (523.25, 0.2), # C4
        (0,      0.05),
        (523.25, 0.6), # C4 (Long)
        (0,      0.1),
        (466.16, 0.4), # Bb3
        (587.33, 0.4), # D4
        (523.25, 2.5), # C4 (Very Long)
    ]
    
    # 和聲聲部 (低三度/五度)
    harmony_notes = [
        (329.63, 0.2), # E3
        (0,      0.05),
        (329.63, 0.2), # E3
        (0,      0.05),
        (329.63, 0.2), # E3
        (0,      0.05),
        (329.63, 0.6), # E3
        (0,      0.1),
        (261.63, 0.4), # C3 (Bb -> C ?) 讓和聲走 C3
        (293.66, 0.4), # D3
        (329.63, 2.5), # E3
    ]
    
    # 合成聲部
    def synthesize_track(notes):
        track_data = []
        for freq, dur in notes:
            if freq == 0:
                track_data.extend([0] * int(sample_rate * dur))
            else:
                track_data.extend(generate_note(freq, dur))
        return track_data

    track1 = synthesize_track(melody_notes)
    track2 = synthesize_track(harmony_notes)
    
    # 混音
    max_len = max(len(track1), len(track2))
    mixed_data = []
    
    # 補齊長度
    track1 += [0] * (max_len - len(track1))
    track2 += [0] * (max_len - len(track2))
    
    for i in range(max_len):
        # 簡單混音：相加並限制範圍
        val = track1[i] * 0.7 + track2[i] * 0.6
        val = max(min(int(val), 32767), -32768)
        mixed_data.append(val)

    with wave.open(filename, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(struct.pack('<' + ('h' * len(mixed_data)), *mixed_data))
        
    print(f"Generated Epic Fanfare {filename}")

if __name__ == "__main__":
    import os
    
    # 計算專案根目錄
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    assets_dir = os.path.join(project_root, "assets", "sounds")

    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
        
    generate_tick(os.path.join(assets_dir, "tick.wav"), 50, 1.0) # 單發
    generate_loop(os.path.join(assets_dir, "fast.wav"), 15)      # 一秒 15 下
    generate_loop(os.path.join(assets_dir, "medium.wav"), 8)     # 一秒 8 下
    generate_loop(os.path.join(assets_dir, "slow.wav"), 4)       # 一秒 4 下
    generate_fanfare(os.path.join(assets_dir, "win.wav"))       # 勝利號角
