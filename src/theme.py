# -*- coding: utf-8 -*-
"""Windows 11 Fluent 风格界面主题（基于 ttk 'clam' 主题定制）。

在 tkinter 能力范围内尽量贴近 Windows 11 浅色 Fluent Design：
Microsoft YaHei UI 字体、#0067C0 强调色、扁平按钮、白色输入框、
细滚动条、高分屏 DPI 感知。
"""
import ctypes
import tkinter as tk
from tkinter import ttk

# ---- 调色板（浅色模式）----
ACCENT = '#0067C0'          # Windows 11 强调色
ACCENT_HOVER = '#1975C5'
ACCENT_ACTIVE = '#00579F'

BG = '#F3F3F3'              # 窗口背景
SURFACE = '#FFFFFF'         # 输入框/卡片背景
SURFACE_ALT = '#F9F9F9'     # 次级表面
SURFACE_HOVER = '#EBEBEB'
SURFACE_PRESSED = '#E1E1E1'
SURFACE_DISABLED = '#F0F0F0'

TEXT = '#1B1B1B'
TEXT_SECONDARY = '#5D5D5D'
TEXT_DISABLED = '#A0A0A0'

BORDER = '#D1D1D1'
BORDER_HOVER = '#AEAEAE'

SUCCESS = '#0F7B0F'         # 就绪/成功状态点
DANGER = '#C42B1C'          # 录制/停止状态点

FONT_FAMILY = 'Microsoft YaHei UI'
FONT = (FONT_FAMILY, 9)
FONT_SMALL = (FONT_FAMILY, 8)
FONT_BOLD = (FONT_FAMILY, 9, 'bold')
FONT_TITLE = (FONT_FAMILY, 12, 'bold')


def enable_dpi_awareness():
    """启用 Per-Monitor DPI 感知，保证高分屏字体清晰（Tk 9 已自带，此处兜底）。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def apply_theme(root):
    """给 root（及其所有 Toplevel）套用 Windows 11 Fluent 风格。"""
    root.option_add('*Font', FONT)
    root.configure(bg=BG)

    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=FONT, background=BG, foreground=TEXT)

    _style_frames(style)
    _style_labels(style)
    _style_buttons(style)
    _style_inputs(style)
    _style_misc(style)
    return style


def _style_frames(style):
    style.configure('TFrame', background=BG)
    style.configure('TLabelframe', background=BG, bordercolor=BORDER)
    style.configure('TLabelframe.Label', background=BG, foreground=TEXT, font=FONT_BOLD)


def _style_labels(style):
    style.configure('TLabel', background=BG, foreground=TEXT)
    style.configure('Secondary.TLabel', background=BG, foreground=TEXT_SECONDARY)
    style.configure('Title.TLabel', background=BG, foreground=TEXT, font=FONT_TITLE)
    style.configure('Section.TLabel', background=BG, foreground=TEXT, font=FONT_BOLD)
    style.configure('Status.TLabel', background=SURFACE_ALT, foreground=TEXT_SECONDARY,
                    padding=(12, 7))


def _style_buttons(style):
    # 次级按钮（默认）
    style.configure('TButton', font=FONT, background=SURFACE_ALT, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=SURFACE_ALT, darkcolor=SURFACE_ALT,
                    borderwidth=1, relief='flat', padding=(12, 6))
    style.map('TButton',
              background=[('pressed', SURFACE_PRESSED), ('active', SURFACE_HOVER),
                          ('disabled', SURFACE_DISABLED)],
              foreground=[('disabled', TEXT_DISABLED)],
              bordercolor=[('active', BORDER_HOVER), ('disabled', BORDER)],
              lightcolor=[('pressed', SURFACE_PRESSED), ('active', SURFACE_HOVER),
                          ('disabled', SURFACE_DISABLED)],
              darkcolor=[('pressed', SURFACE_PRESSED), ('active', SURFACE_HOVER),
                          ('disabled', SURFACE_DISABLED)])

    # 主按钮（强调色填充）
    style.configure('Accent.TButton', font=FONT_BOLD, background=ACCENT, foreground='#FFFFFF',
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                    borderwidth=1, relief='flat', padding=(16, 6))
    style.map('Accent.TButton',
              background=[('pressed', ACCENT_ACTIVE), ('active', ACCENT_HOVER),
                          ('disabled', SURFACE_DISABLED)],
              foreground=[('disabled', TEXT_DISABLED)],
              bordercolor=[('pressed', ACCENT_ACTIVE), ('active', ACCENT_HOVER),
                           ('disabled', SURFACE_DISABLED)],
              lightcolor=[('pressed', ACCENT_ACTIVE), ('active', ACCENT_HOVER),
                          ('disabled', SURFACE_DISABLED)],
              darkcolor=[('pressed', ACCENT_ACTIVE), ('active', ACCENT_HOVER),
                          ('disabled', SURFACE_DISABLED)])


def _style_inputs(style):
    style.configure('TEntry', fieldbackground=SURFACE, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    insertcolor=TEXT, borderwidth=1, padding=(5, 5))
    style.map('TEntry',
              bordercolor=[('focus', ACCENT)],
              lightcolor=[('focus', ACCENT)],
              darkcolor=[('focus', ACCENT)])

    style.configure('TSpinbox', fieldbackground=SURFACE, foreground=TEXT,
                    background=SURFACE_ALT, bordercolor=BORDER, arrowcolor=TEXT_SECONDARY,
                    lightcolor=BORDER, darkcolor=BORDER, borderwidth=1, padding=(5, 5))
    style.map('TSpinbox',
              bordercolor=[('focus', ACCENT)],
              lightcolor=[('focus', ACCENT)],
              darkcolor=[('focus', ACCENT)])

    style.configure('TCombobox', fieldbackground=SURFACE, foreground=TEXT,
                    background=SURFACE_ALT, bordercolor=BORDER, arrowcolor=TEXT_SECONDARY,
                    lightcolor=BORDER, darkcolor=BORDER, borderwidth=1, padding=(5, 5))
    style.map('TCombobox',
              fieldbackground=[('readonly', SURFACE)],
              bordercolor=[('focus', ACCENT)],
              lightcolor=[('focus', ACCENT)],
              darkcolor=[('focus', ACCENT)])

    style.configure('TCheckbutton', background=BG, foreground=TEXT)
    style.map('TCheckbutton', background=[('active', BG)])


def _style_misc(style):
    style.configure('TScrollbar', background='#C4C4C4', troughcolor=BG,
                    bordercolor=BG, arrowcolor='#8A8A8A', relief='flat',
                    borderwidth=0, gripcount=0)
    style.map('TScrollbar', background=[('active', '#9A9A9A')])
    style.configure('TSeparator', background=BORDER)
