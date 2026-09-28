# -*- coding: utf-8 -*-
"""迷你悬浮状态条：无边框、置顶、可拖动，显示状态点与「录制/停止」按钮。

用于在游戏（无边框窗口模式）中常驻浮于最上层，快速观察状态并控制录制。
"""
import tkinter as tk

from . import theme


class MiniBar:
    """常驻最上层的迷你条。默认隐藏，用 show()/hide() 控制显隐。"""

    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.withdraw()                      # 默认隐藏，由 show() 显式显示
        self.win.configure(bg=theme.BORDER)

        body = tk.Frame(self.win, bg=theme.SURFACE, bd=0)
        body.pack(fill='both', expand=True, padx=1, pady=1)

        self._off = (0, 0)

        self.dot = tk.Label(body, text='●', bg=theme.SURFACE, fg=theme.TEXT_SECONDARY,
                            font=(theme.FONT_FAMILY, 11))
        self.dot.pack(side='left', padx=(12, 5), pady=7)

        self.state_lbl = tk.Label(body, text='就绪', bg=theme.SURFACE, fg=theme.TEXT,
                                  font=theme.FONT)
        self.state_lbl.pack(side='left', padx=(0, 10))

        self.btn = tk.Button(body, text='● 录制', command=self._on_record_click,
                             bg=theme.ACCENT, fg='#FFFFFF', activebackground=theme.ACCENT_HOVER,
                             activeforeground='#FFFFFF', relief='flat', bd=0,
                             font=theme.FONT_BOLD, padx=14, pady=5, cursor='hand2')
        self.btn.pack(side='left', padx=(0, 4))

        close = tk.Label(body, text='✕', bg=theme.SURFACE, fg=theme.TEXT_SECONDARY,
                         font=theme.FONT, cursor='hand2')
        close.pack(side='left', padx=(0, 10))
        close.bind('<Button-1>', lambda e: self.hide())

        # 空白处可拖动
        for w in (body, self.dot, self.state_lbl):
            w.bind('<Button-1>', self._on_press)
            w.bind('<B1-Motion>', self._on_drag)

        # 默认放到屏幕右上角
        self.win.update_idletasks()
        w = self.win.winfo_reqwidth()
        sw = self.win.winfo_screenwidth()
        self.win.geometry('+%d+%d' % (max(0, sw - w - 24), 24))

    # ------------------------------------------------------------------ 交互
    def _on_record_click(self):
        self.app._toggle_record()

    def _on_press(self, e):
        self._off = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _on_drag(self, e):
        self.win.geometry('+%d+%d' % (e.x_root - self._off[0], e.y_root - self._off[1]))

    # ------------------------------------------------------------------ 对外 API
    def show(self):
        self.win.deiconify()

    def hide(self):
        self.win.withdraw()

    def is_visible(self):
        try:
            return self.win.state() != 'withdrawn'
        except Exception:
            return False

    def update_state(self, rec, play):
        if rec:
            self.dot.config(fg=theme.DANGER)
            self.state_lbl.config(text='正在录制')
            self.btn.config(text='■ 停止', bg=theme.DANGER, activebackground='#A02318')
        elif play:
            self.dot.config(fg=theme.ACCENT)
            self.state_lbl.config(text='正在回放')
            self.btn.config(text='● 录制', bg=theme.ACCENT, activebackground=theme.ACCENT_HOVER)
        else:
            self.dot.config(fg=theme.TEXT_SECONDARY)
            self.state_lbl.config(text='就绪')
            self.btn.config(text='● 录制', bg=theme.ACCENT, activebackground=theme.ACCENT_HOVER)

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass
