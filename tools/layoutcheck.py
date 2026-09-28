# -*- coding: utf-8 -*-
"""布局自检：确认默认窗口尺寸下「控制热键」状态栏与下方日志区（运行窗口）完整可见。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app import App  # noqa: E402


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


app = App()
root = app.root
root.update_idletasks()
root.update()

win_h = root.winfo_height()
win_w = root.winfo_width()
origin_y = root.winfo_rooty()

print('geometry   = %s' % root.geometry())
print('window     = %dx%d' % (win_w, win_h))
print('requested  = %dx%d' % (root.winfo_reqwidth(), root.winfo_reqheight()))
print('screen     = %dx%d' % (root.winfo_screenwidth(), root.winfo_screenheight()))

worst = (0, '')
mapped = 0
for w in walk(root):
    if not w.winfo_ismapped():
        continue
    mapped += 1
    bottom = w.winfo_rooty() - origin_y + w.winfo_height()
    if bottom > worst[0]:
        worst = (bottom, w.__class__.__name__)

log = app.log_text
log_top = log.winfo_rooty() - origin_y
log_h = log.winfo_height()
print('log_area   = y=%d h=%d bottom=%d' % (log_top, log_h, log_top + log_h))
print('mapped     = %d widgets' % mapped)
print('lowest     = %s bottom=%d' % (worst[1], worst[0]))

ok = (worst[0] <= win_h) and (log_h >= 80) and (log_top + log_h <= win_h)
print('all_widgets_inside_window = %s' % (worst[0] <= win_h))
print('log_area_usable           = %s' % (log_h >= 80))

app.hotkeys.unregister_all()
app.tray.stop()
root.destroy()
print('LAYOUT OK' if ok else 'LAYOUT PROBLEM')
sys.exit(0 if ok else 1)
