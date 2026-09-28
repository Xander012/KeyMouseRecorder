# -*- coding: utf-8 -*-
"""GUI 冒烟测试：构造 App、短暂运行主循环后干净退出。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app import App  # noqa: E402

app = App()
app.root.after(1200, app.root.destroy)
app.root.mainloop()
try:
    app.hotkeys.unregister_all()
    app.tray.stop()
except Exception:
    pass
print('GUI SMOKE OK')
