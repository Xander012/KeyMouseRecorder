# -*- coding: utf-8 -*-
"""声音提示：用 winsound 播放不同频率的提示音（后台线程，非阻塞）。

用于在独占全屏等看不到窗口的场景下，通过声音感知录制/回放状态。
"""
import threading
import time
import winsound

_ENABLED = True


def set_enabled(on):
    global _ENABLED
    _ENABLED = bool(on)


def is_enabled():
    return _ENABLED


def _play(beeps):
    """beeps: [(频率Hz, 时长ms), ...]，按顺序播放，中间留短暂间隔。"""
    if not _ENABLED:
        return

    def run():
        for i, (freq, ms) in enumerate(beeps):
            try:
                winsound.Beep(freq, ms)
            except Exception:
                return
            if i < len(beeps) - 1:
                time.sleep(0.09)
    threading.Thread(target=run, daemon=True).start()


def record_start():
    """开始录制：一声。"""
    _play([(880, 130)])


def record_stop():
    """停止录制：两声短音。"""
    _play([(880, 100), (880, 100)])


def play_start():
    """开始回放：一声高音。"""
    _play([(1319, 120)])


def play_finished():
    """回放正常结束：上行两音。"""
    _play([(659, 120), (880, 120)])


def play_aborted():
    """回放被中止：一声低音。"""
    _play([(440, 150)])
