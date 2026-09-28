# -*- coding: utf-8 -*-
"""回放引擎：按原始时间间隔精确回放，支持速度倍率、循环次数、紧急停止与按键释放。"""
import threading
import time

import keyboard
import mouse


class Player:
    def __init__(self, on_status=None, on_finished=None):
        self._stop = threading.Event()
        self._thread = None
        self._pressed_keys = set()
        self._pressed_buttons = set()
        self.on_status = on_status
        self.on_finished = on_finished

    def is_playing(self):
        return self._thread is not None and self._thread.is_alive()

    def play(self, events, loop_count=1, speed=1.0):
        if self.is_playing():
            return False
        if not events:
            self._status('脚本为空，无法回放')
            return False
        self._stop.clear()
        self._pressed_keys = set()
        self._pressed_buttons = set()
        self._thread = threading.Thread(
            target=self._run, args=(events, loop_count, speed), daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """立即中止回放并释放所有按下的键（线程安全）。"""
        self._stop.set()
        self._release_all()

    # ------------------------------------------------------------------ 内部
    def _run(self, events, loop_count, speed):
        self._status('开始回放')
        try:
            if loop_count is None or int(loop_count) <= 0:
                loops = None  # 无限循环
            else:
                loops = int(loop_count)
            i = 0
            while loops is None or i < loops:
                if self._stop.is_set():
                    break
                self._play_once(events, speed)
                i += 1
        except Exception as exc:
            self._status('回放异常: %s' % exc)
        finally:
            self._release_all()
            if self._stop.is_set():
                self._status('回放已中止')
            else:
                self._status('回放完成')
            if self.on_finished:
                try:
                    self.on_finished(self._stop.is_set())
                except Exception:
                    pass

    def _play_once(self, events, speed):
        if speed is None or speed <= 0:
            speed = 1.0
        t0 = events[0]['ts']
        start = time.monotonic()
        for ev in events:
            if self._stop.is_set():
                break
            target = (ev['ts'] - t0) / speed
            now = time.monotonic() - start
            wait = target - now
            if wait > 0:
                # 可中断的睡眠，保证紧急停止立即生效
                if self._stop.wait(wait):
                    break
            self._dispatch(ev)

    def _dispatch(self, ev):
        t = ev.get('type')
        if t == 'key':
            code = ev.get('code')
            if ev.get('action') == 'down':
                try:
                    keyboard.press(code)
                except Exception:
                    return
                self._pressed_keys.add(code)
            else:
                try:
                    keyboard.release(code)
                except Exception:
                    pass
                self._pressed_keys.discard(code)
        elif t == 'mouse':
            btn = ev.get('btn', 'left')
            if ev.get('action') == 'down':
                try:
                    mouse.press(btn)
                except Exception:
                    return
                self._pressed_buttons.add(btn)
            else:
                try:
                    mouse.release(btn)
                except Exception:
                    pass
                self._pressed_buttons.discard(btn)
        elif t == 'move':
            try:
                mouse.move(int(ev.get('x', 0)), int(ev.get('y', 0)), absolute=True)
            except Exception:
                pass
        elif t == 'wheel':
            try:
                mouse.wheel(int(ev.get('delta', 1)))
            except Exception:
                pass

    def _release_all(self):
        for code in list(self._pressed_keys):
            try:
                keyboard.release(code)
            except Exception:
                pass
        self._pressed_keys.clear()
        for btn in list(self._pressed_buttons):
            try:
                mouse.release(btn)
            except Exception:
                pass
        self._pressed_buttons.clear()
        # 兜底：释放常见修饰键，避免任何情况下卡键
        for name in ('ctrl', 'shift', 'alt', 'windows'):
            try:
                keyboard.release(name)
            except Exception:
                pass

    def _status(self, msg):
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass
