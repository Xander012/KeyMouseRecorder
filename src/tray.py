# -*- coding: utf-8 -*-
"""系统托盘（纯 ctypes 实现 Shell_NotifyIcon，无第三方依赖）。"""
import ctypes
import queue
import threading
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)
shell32 = ctypes.WinDLL('shell32', use_last_error=True)

# 函数原型（x64 下必须显式声明 restype，避免句柄被截断为 32 位）
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.LoadIconW.restype = wintypes.HICON
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadCursorW.restype = wintypes.HANDLE
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                                   wintypes.HINSTANCE, wintypes.LPVOID]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_size_t]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.restype = ctypes.c_ssize_t
user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
user32.PostMessageW.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_size_t]
user32.DestroyWindow.restype = wintypes.BOOL
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.c_void_p]
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.restype = wintypes.BOOL
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
user32.DestroyMenu.restype = wintypes.BOOL
user32.DestroyMenu.argtypes = [wintypes.HMENU]

shell32.Shell_NotifyIconW.restype = wintypes.BOOL
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.c_void_p]


def _res(res_id):
    """MAKEINTRESOURCE：把整型资源 ID 转成 LPCWSTR 指针（用于标准图标/光标）。"""
    return ctypes.cast(ctypes.c_void_p(res_id), wintypes.LPCWSTR)

# 窗口/消息常量
WM_QUIT = 0x0012
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_APP = 0x8000
WM_TRAY = WM_APP + 1
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
IDI_APPLICATION = 32512

# Shell_NotifyIcon 常量
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 0x0001
NIF_ICON = 0x0002
NIF_TIP = 0x0004
NIF_INFO = 0x0010
NIIF_INFO = 0x0001
NIIF_NONE = 0x0000

# 图标加载
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040

# 菜单
MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
TPM_RIGHTBUTTON = 0x0002

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             ctypes.c_size_t, ctypes.c_size_t)


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('hWnd', wintypes.HWND),
        ('uID', wintypes.UINT),
        ('uFlags', wintypes.UINT),
        ('uCallbackMessage', wintypes.UINT),
        ('hIcon', wintypes.HICON),
        ('szTip', wintypes.WCHAR * 128),
        ('dwState', wintypes.DWORD),
        ('dwStateMask', wintypes.DWORD),
        ('szInfo', wintypes.WCHAR * 256),
        ('uTimeout', wintypes.UINT),
        ('szInfoTitle', wintypes.WCHAR * 64),
        ('dwInfoFlags', wintypes.DWORD),
    ]


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ('style', wintypes.UINT),
        ('lpfnWndProc', WNDPROC),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON),
        ('hCursor', wintypes.HANDLE),
        ('hbrBackground', wintypes.HANDLE),
        ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR),
    ]


class TrayIcon:
    """独立线程运行消息循环的系统托盘图标。

    事件通过内部队列传出，由 GUI 用 drain() 轮询：
      ('left_click',)   鼠标左键单击/双击
      ('command', id)   菜单项被点击（id 为 set_menu 传入的整数）
    """

    def __init__(self, title, icon_path=None):
        self.title = title
        self.icon_path = icon_path
        self._menu_items = []          # [(label, id)] 或 (None, None) 表示分隔线
        self._thread = None
        self._running = False
        self._hwnd = None
        self._nid = None
        self._hicon = None
        self._q = queue.Queue()
        self._wndproc_ref = None

    # ------------------------------------------------------------------ 对外 API
    def set_menu(self, items):
        """items: 由 (label, id) 组成的列表，分隔线用 (None, None)。"""
        self._menu_items = list(items)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name='tray')
        self._thread.start()

    def stop(self):
        self._running = False
        if self._hwnd is not None:
            try:
                user32.PostMessageW(self._hwnd, WM_QUIT, 0, 0)
            except Exception:
                pass

    def drain(self):
        """取出当前累积的所有托盘事件。"""
        out = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                break
        return out

    def notify(self, title, msg):
        """气泡提示（需在图标已添加后调用）。"""
        try:
            nid = self._make_nid(NIF_INFO)
            nid.szInfo = str(msg)[:255]
            nid.szInfoTitle = str(title)[:63]
            nid.uTimeout = 3000
            nid.dwInfoFlags = NIIF_INFO
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        except Exception:
            pass

    # ------------------------------------------------------------------ 内部
    def _load_icon(self):
        hicon = None
        if self.icon_path:
            try:
                hicon = user32.LoadImageW(
                    None, self.icon_path, IMAGE_ICON, 0, 0,
                    LR_LOADFROMFILE | LR_DEFAULTSIZE)
            except Exception:
                hicon = None
        if not hicon:
            hicon = user32.LoadIconW(None, _res(IDI_APPLICATION))
        return hicon

    def _make_nid(self, flags):
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = flags
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._hicon
        nid.szTip = self.title[:127]
        return nid

    def _run(self):
        hinst = kernel32.GetModuleHandleW(None)
        self._hicon = self._load_icon()

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAY:
                if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self._q.put(('left_click',))
                elif lparam == WM_RBUTTONUP:
                    self._show_menu(hwnd)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc_ref = WNDPROC(wndproc)

        wc = WNDCLASS()
        wc.style = CS_HREDRAW | CS_VREDRAW
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hinst
        wc.hCursor = user32.LoadCursorW(None, _res(IDI_APPLICATION))
        wc.lpszClassName = 'KBMacroTrayWindow'
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            return

        self._hwnd = user32.CreateWindowExW(
            0, 'KBMacroTrayWindow', 'KBMacroTray', 0,
            0, 0, 0, 0, None, None, hinst, None)
        if not self._hwnd:
            return

        nid = self._make_nid(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        self._nid = nid

        msg = wintypes.MSG()
        while self._running:
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # 退出前删除图标与窗口
        try:
            if self._nid is not None:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        except Exception:
            pass
        if self._hwnd is not None:
            try:
                user32.DestroyWindow(self._hwnd)
            except Exception:
                pass
        self._hwnd = None

    def _show_menu(self, hwnd):
        try:
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            pos = 0
            id_map = {}
            cmd_id = 1000
            for label, ident in self._menu_items:
                if label is None:
                    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                else:
                    cmd_id += 1
                    id_map[cmd_id] = ident
                    user32.AppendMenuW(menu, MF_STRING, cmd_id, str(label))
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            chosen = user32.TrackPopupMenu(
                menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON,
                pt.x, pt.y, 0, hwnd, None)
            if chosen in id_map:
                self._q.put(('command', id_map[chosen]))
        finally:
            user32.DestroyMenu(menu)
