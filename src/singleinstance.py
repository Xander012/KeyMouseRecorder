# -*- coding: utf-8 -*-
"""单实例保障：命名互斥体 + 命名事件。

- 命名互斥体：防止二次启动（第二个进程检测到已存在即提示并退出）。
- 命名事件：二次启动时通知已有实例，唤起其主窗口。
"""
import ctypes

_MUTEX_NAME = 'Local\\KeyMouseRecorder_SingleInstance'
_EVENT_NAME = 'Local\\KeyMouseRecorder_ShowEvent'

ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0
WAIT_INFINITE = 0xFFFFFFFF

_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
_kernel32.CreateMutexW.restype = ctypes.c_void_p
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
_kernel32.CreateEventW.restype = ctypes.c_void_p
_kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
_kernel32.OpenEventW.restype = ctypes.c_void_p
_kernel32.OpenEventW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
_kernel32.SetEvent.restype = ctypes.c_int
_kernel32.SetEvent.argtypes = [ctypes.c_void_p]
_kernel32.ResetEvent.restype = ctypes.c_int
_kernel32.ResetEvent.argtypes = [ctypes.c_void_p]
_kernel32.WaitForSingleObject.restype = ctypes.c_uint32
_kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
_kernel32.CloseHandle.restype = ctypes.c_int
_kernel32.CloseHandle.argtypes = [ctypes.c_void_p]


def acquire_single_instance():
    """创建单实例互斥体。返回 (句柄, 是否已存在其他实例)。"""
    handle = _kernel32.CreateMutexW(None, 0, _MUTEX_NAME)
    err = ctypes.get_last_error()
    return handle, (err == ERROR_ALREADY_EXISTS)


def signal_existing_instance():
    """通知已有实例：用户想打开主窗口。"""
    try:
        event = _kernel32.OpenEventW(EVENT_MODIFY_STATE | SYNCHRONIZE, 0, _EVENT_NAME)
        if event:
            _kernel32.SetEvent(event)
            _kernel32.CloseHandle(event)
            return True
    except Exception:
        pass
    return False


def create_show_event():
    """创建（或打开）唤起事件并返回句柄；已有实例用它监听唤起请求。"""
    # 手动复位(bManualReset=1)，初始未触发(bInitialState=0)
    return _kernel32.CreateEventW(None, 1, 0, _EVENT_NAME)


def wait_and_reset(event):
    """阻塞等待唤起事件被触发；触发后复位并返回 True，异常返回 False。"""
    if _kernel32.WaitForSingleObject(event, WAIT_INFINITE) == WAIT_OBJECT_0:
        _kernel32.ResetEvent(event)
        return True
    return False


def show_message(text):
    """弹出信息提示框（不依赖 tk，可在创建主窗口前调用）。"""
    try:
        ctypes.windll.user32.MessageBoxW(None, text, '键鼠录制回放工具', 0x40)
    except Exception:
        pass
