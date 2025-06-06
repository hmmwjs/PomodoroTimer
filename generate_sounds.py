#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成番茄钟提醒声音
创建柔和、低频的水滴风格通知声音
"""

import os
import numpy as np
from scipy.io import wavfile
from scipy import signal

# 确保sounds目录存在
if not os.path.exists('sounds'):
    os.makedirs('sounds')

# 采样率
SAMPLE_RATE = 44100  # 44.1kHz, CD质量

def apply_envelope(audio, attack=0.01, decay=0.1, sustain=0.7, release=0.2, sustain_level=0.8):
    """应用ADSR包络"""
    total_length = len(audio)
    attack_length = int(attack * total_length)
    decay_length = int(decay * total_length)
    release_length = int(release * total_length)
    sustain_length = total_length - attack_length - decay_length - release_length
    
    envelope = np.ones(total_length)
    
    # Attack: 0 到 1
    if attack_length > 0:
        envelope[:attack_length] = np.linspace(0, 1, attack_length)
    
    # Decay: 1 到 sustain_level
    if decay_length > 0:
        envelope[attack_length:attack_length+decay_length] = np.linspace(1, sustain_level, decay_length)
    
    # Sustain: 保持在sustain_level
    envelope[attack_length+decay_length:attack_length+decay_length+sustain_length] = sustain_level
    
    # Release: sustain_level 到 0
    if release_length > 0:
        envelope[-release_length:] = np.linspace(sustain_level, 0, release_length)
    
    return audio * envelope

def generate_tone(freq, duration, volume=0.5, wave_type='sine'):
    """生成音调"""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    
    if wave_type == 'sine':
        tone = np.sin(freq * 2 * np.pi * t)
    elif wave_type == 'square':
        tone = signal.square(freq * 2 * np.pi * t)
    elif wave_type == 'triangle':
        tone = signal.sawtooth(freq * 2 * np.pi * t, 0.5)
    elif wave_type == 'sawtooth':
        tone = signal.sawtooth(freq * 2 * np.pi * t)
    else:
        tone = np.sin(freq * 2 * np.pi * t)  # 默认使用正弦波
    
    return tone * volume

def add_harmonics(tone, freq, harmonics_profile):
    """添加谐波"""
    result = np.copy(tone)
    t = np.linspace(0, len(tone)/SAMPLE_RATE, len(tone), False)
    
    for harmonic, amplitude in harmonics_profile.items():
        result += amplitude * np.sin(freq * harmonic * 2 * np.pi * t)
    
    return result

def apply_reverb(audio, delay=0.05, decay=0.5):
    """应用简单的混响效果"""
    delay_samples = int(delay * SAMPLE_RATE)
    reverb = np.zeros_like(audio)
    reverb[delay_samples:] = audio[:-delay_samples] * decay
    return audio + reverb

def create_water_drop_sound(freq, duration, filename, volume=0.4):
    """创建水滴风格的声音"""
    # 水滴声特征：快速的起音，然后是较长的衰减
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    
    # 基础音调 - 使用正弦波
    tone = np.sin(freq * 2 * np.pi * t) * volume
    
    # 频率调制 - 水滴声通常从高到低
    freq_mod = np.exp(-3 * t)  # 指数衰减
    freq_mod_tone = np.sin(freq * 2 * np.pi * t * (1 + 0.5 * freq_mod)) * volume * 0.3
    
    # 组合基础音调和调制音调
    audio = tone + freq_mod_tone
    
    # 应用水滴特有的包络 - 快速起音，长衰减
    envelope = np.exp(-5 * t)  # 指数衰减包络
    envelope[:int(0.01 * SAMPLE_RATE)] = np.linspace(0, 1, int(0.01 * SAMPLE_RATE))  # 快速起音
    
    audio = audio * envelope
    
    # 添加轻微混响
    audio = apply_reverb(audio, delay=0.03, decay=0.2)
    
    # 添加低频成分增强厚度
    lowpass = signal.butter(2, 800/(SAMPLE_RATE/2), 'lowpass')
    low_freq = signal.lfilter(lowpass[0], lowpass[1], audio)
    audio = audio + 0.3 * low_freq
    
    # 归一化
    audio = audio / np.max(np.abs(audio))
    
    # 转换为16位整数
    audio_int16 = (audio * 32767).astype(np.int16)
    
    # 保存为WAV文件
    wavfile.write(f'sounds/{filename}.wav', SAMPLE_RATE, audio_int16)
    print(f"✅ 已创建声音: sounds/{filename}.wav")
    
    return audio_int16

def create_soft_tone(frequencies, duration, filename, attack=0.05, decay=0.2, release=0.5):
    """创建柔和的音调"""
    # 基础音调
    audio = np.zeros(int(SAMPLE_RATE * duration))
    
    # 添加多个频率成分
    for i, freq in enumerate(frequencies):
        # 音量随频率降低
        volume = 0.4 * (1 - i * 0.15)
        tone = generate_tone(freq, duration, volume=volume, wave_type='sine')
        
        # 添加柔和的谐波
        harmonics = {2: 0.15, 3: 0.05}
        tone = add_harmonics(tone, freq, harmonics)
        
        # 应用柔和的包络
        tone = apply_envelope(tone, attack=attack, decay=decay, sustain=0.3, release=release, sustain_level=0.6)
        
        audio += tone
    
    # 添加轻微混响效果
    audio = apply_reverb(audio, delay=0.05, decay=0.3)
    
    # 添加低频成分增强温暖感
    lowpass = signal.butter(2, 1000/(SAMPLE_RATE/2), 'lowpass')
    low_freq = signal.lfilter(lowpass[0], lowpass[1], audio)
    audio = audio + 0.25 * low_freq
    
    # 归一化
    audio = audio / np.max(np.abs(audio))
    
    # 转换为16位整数
    audio_int16 = (audio * 32767).astype(np.int16)
    
    # 保存为WAV文件
    wavfile.write(f'sounds/{filename}.wav', SAMPLE_RATE, audio_int16)
    print(f"✅ 已创建声音: sounds/{filename}.wav")
    
    return audio_int16

def create_start_sound():
    """创建开始工作的声音 - 柔和的水滴声"""
    # 使用较低的频率
    return create_water_drop_sound(330, 0.8, "start", volume=0.4)  # E4

def create_complete_sound():
    """创建完成工作的声音 - 柔和的双音调"""
    # 使用较低的频率组合
    frequencies = [392, 523.25]  # G4, C5
    return create_soft_tone(frequencies, 1.0, "complete", attack=0.05, decay=0.2, release=0.6)

def create_break_end_sound():
    """创建休息结束的声音 - 三连水滴声"""
    # 创建三个不同频率的水滴声并连接
    drop1 = create_water_drop_sound(294, 0.4, "drop1_temp", volume=0.35)  # D4
    drop2 = create_water_drop_sound(349, 0.4, "drop2_temp", volume=0.35)  # F4
    drop3 = create_water_drop_sound(392, 0.4, "drop3_temp", volume=0.35)  # G4
    
    # 连接三个水滴声
    combined = np.concatenate([drop1, np.zeros(int(SAMPLE_RATE * 0.1)), drop2, np.zeros(int(SAMPLE_RATE * 0.1)), drop3])
    
    # 归一化
    combined = combined / np.max(np.abs(combined))
    
    # 转换为16位整数
    combined_int16 = (combined * 32767).astype(np.int16)
    
    # 保存为WAV文件
    wavfile.write('sounds/break_end.wav', SAMPLE_RATE, combined_int16)
    print("✅ 已创建声音: sounds/break_end.wav")
    
    # 删除临时文件
    for temp_file in ['sounds/drop1_temp.wav', 'sounds/drop2_temp.wav', 'sounds/drop3_temp.wav']:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    return combined_int16

def main():
    """生成所有声音文件"""
    print("🔊 开始生成番茄钟提醒声音...")
    create_start_sound()
    create_complete_sound()
    create_break_end_sound()
    print("✅ 所有声音文件生成完成！")

if __name__ == "__main__":
    main() 