# -*- coding: utf-8 -*-
"""配置管理：控制热键、回放参数、录制参数，持久化到 JSON。"""
import copy
import json
import os
import sys
import threading

APP_NAME = 'KeyMouseRecorder'

# 控制热键默认值（keyboard 库语法：键名小写，'+' 连接组合键）
DEFAULT_HOTKEYS = {
    'record_toggle': 'f6',
    'play_toggle': 'f7',
    'emergency_stop': 'f8',
    'show_hide': 'ctrl+f12',
}

HOTKEY_LABELS = {
    'record_toggle': '开始/停止录制',
    'play_toggle': '开始/停止回放',
    'emergency_stop': '紧急停止',
    'show_hide': '显示/隐藏主界面',
}

DEFAULTS = {
    'hotkeys': dict(DEFAULT_HOTKEYS),
    'record_mouse_moves': True,      # 是否录制鼠标移动轨迹
    'sample_interval_ms': 15,        # 移动采样最小间隔(毫秒)
    'min_move_distance': 3,          # 移动最小距离(像素)，用于降采样
    'default_loop_count': 1,         # 回放次数：0=无限循环，>=1=指定次数
    'default_speed': 1.0,            # 回放速度倍率
    'always_on_top': True,           # 启动时窗口是否置顶（固定最上层）
    'mini_bar_enabled': False,       # 是否显示迷你悬浮状态条
    'sound_feedback': True,          # 声音提示开关
    'start_minimized': False,        # 启动时是否最小化到托盘
}


def app_data_dir():
    """返回程序自身所在目录（便携模式）：脚本/配置/日志与 exe 同目录，不写入 C 盘。"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 冻结后：exe 所在目录
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        # 源码运行：项目根目录（src 的上一级）
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return base


class Config:
    def __init__(self, path=None):
        self.path = path or os.path.join(app_data_dir(), 'config.json')
        self.data = copy.deepcopy(DEFAULTS)
        self._lock = threading.RLock()
        self.load()

    def load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
                # 热键单独合并，保证新版本新增热键不会缺失
                if isinstance(loaded.get('hotkeys'), dict):
                    for k, v in loaded['hotkeys'].items():
                        if k in self.data['hotkeys']:
                            self.data['hotkeys'][k] = v
        except FileNotFoundError:
            pass
        except Exception:
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with self._lock:
                with open(self.path, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, save=True):
        self.data[key] = value
        if save:
            self.save()

    def hotkey(self, name):
        return self.data.get('hotkeys', {}).get(name, DEFAULT_HOTKEYS.get(name))
