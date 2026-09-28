# -*- coding: utf-8 -*-
"""录制引擎：全局钩子录制键盘/鼠标事件，带时间戳，支持移动降采样与控制热键过滤。"""
import threading
import time

import keyboard
import mouse


class Recorder:
    def __init__(self, on_status=None):
        self._lock = threading.RLock()
        self._recording = False
        self._events = []
        self._start_time = 0.0

        # 控制热键过滤相关
        self._skip_codes = set()            # 控制热键手势进行中，需跳过的扫描码
        self._mod_down_idx = {}             # 修饰键扫描码 -> 事件列表下标
        self._hotkey_modifier_codes = set()  # 所有控制热键中出现的修饰键扫描码

        # 移动降采样
        self._record_mouse_moves = True
        self._sample_interval = 0.015
        self._min_distance = 3
        self._last_move_ts = 0.0
        self._last_move_pos = (None, None)

        self._kb_hook = None
        self._ms_hook = None
        self.on_status = on_status

    # ------------------------------------------------------------------ 控制热键协作
    def set_hotkey_codes(self, all_codes, modifier_codes):
        """录制前注入所有控制热键的扫描码，用于录制时过滤。"""
        with self._lock:
            self._hotkey_modifier_codes = set(modifier_codes)

    def on_control_hotkey(self, combo_codes):
        """控制热键被触发时调用：清除已录制的该热键事件，并跳过其后续释放事件。"""
        with self._lock:
            if not self._recording:
                return
            combo = set(combo_codes)
            # 1) 清除末尾属于该热键的事件（常见情况：修饰键按下紧邻触发键）
            while self._events and self._events[-1].get('code') in combo:
                self._events.pop()
            # 2) 清除仍处于按下状态的该热键修饰键（处理打字穿插的边界情况）
            for code in list(self._mod_down_idx):
                if code in combo:
                    idx = self._mod_down_idx.pop(code)
                    if 0 <= idx < len(self._events) and self._events[idx].get('code') == code:
                        del self._events[idx]
                        for k, v in self._mod_down_idx.items():
                            if v > idx:
                                self._mod_down_idx[k] = v - 1
            # 3) 后续的触发键/修饰键释放事件直接跳过
            self._skip_codes.update(combo)

    # ------------------------------------------------------------------ 生命周期
    def start(self, record_mouse_moves=True, sample_interval_ms=15, min_distance=3):
        with self._lock:
            if self._recording:
                return False
            self._events = []
            self._skip_codes = set()
            self._mod_down_idx = {}
            self._last_move_ts = 0.0
            self._last_move_pos = (None, None)
            self._record_mouse_moves = bool(record_mouse_moves)
            self._sample_interval = max(0, int(sample_interval_ms)) / 1000.0
            self._min_distance = max(0, int(min_distance))
            self._recording = True
            self._start_time = time.time()
        try:
            self._kb_hook = keyboard.hook(self._on_key, suppress=False)
            self._ms_hook = mouse.hook(self._on_mouse)
        except Exception:
            with self._lock:
                self._recording = False
            self._status('录制启动失败（钩子安装异常）')
            return False
        self._status('已开始录制')
        return True

    def stop(self):
        with self._lock:
            if not self._recording:
                return None
            self._recording = False
            events = list(self._events)
            self._events = []
        self._unhook()
        self._status('已停止录制')
        return events

    def is_recording(self):
        return self._recording

    def _unhook(self):
        if self._kb_hook is not None:
            try:
                keyboard.unhook(self._kb_hook)
            except Exception:
                pass
            self._kb_hook = None
        if self._ms_hook is not None:
            try:
                mouse.unhook(self._ms_hook)
            except Exception:
                pass
            self._ms_hook = None

    def _status(self, msg):
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass

    # ------------------------------------------------------------------ 事件回调
    def _on_key(self, event):
        with self._lock:
            if not self._recording:
                return
            code = event.scan_code
            if code in self._skip_codes:
                if event.event_type == keyboard.KEY_UP:
                    self._skip_codes.discard(code)
                return
            ev = {
                'type': 'key',
                'action': event.event_type,
                'code': code,
                'name': getattr(event, 'name', ''),
                'kp': bool(getattr(event, 'is_keypad', False)),
                'ts': event.time,
            }
            self._events.append(ev)
            if event.event_type == keyboard.KEY_DOWN and code in self._hotkey_modifier_codes:
                self._mod_down_idx[code] = len(self._events) - 1
            elif event.event_type == keyboard.KEY_UP:
                self._mod_down_idx.pop(code, None)

    def _on_mouse(self, event):
        with self._lock:
            if not self._recording:
                return
            if isinstance(event, mouse.MoveEvent):
                self._on_move(event)
            elif isinstance(event, mouse.WheelEvent):
                self._events.append({'type': 'wheel', 'delta': event.delta, 'ts': event.time})
            else:  # ButtonEvent
                action = event.event_type
                if action == 'double':  # 双击归一化为一次按下，配合随后的 up 自然构成双击
                    action = 'down'
                self._events.append(
                    {'type': 'mouse', 'action': action, 'btn': event.button, 'ts': event.time})

    def _on_move(self, event):
        if not self._record_mouse_moves:
            return
        now = event.time
        if (now - self._last_move_ts) < self._sample_interval:
            return
        px, py = self._last_move_pos
        if px is not None and self._min_distance > 0:
            dx = event.x - px
            dy = event.y - py
            if dx * dx + dy * dy < self._min_distance * self._min_distance:
                return
        self._last_move_ts = now
        self._last_move_pos = (event.x, event.y)
        self._events.append({'type': 'move', 'x': int(event.x), 'y': int(event.y), 'ts': event.time})
