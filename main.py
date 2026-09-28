# -*- coding: utf-8 -*-
"""程序入口。运行方式：python main.py"""
import multiprocessing

from src import singleinstance
from src.app import run


if __name__ == '__main__':
    # PyInstaller 冻结环境下需要 freeze_support
    multiprocessing.freeze_support()

    # 单实例：若已在运行，唤起已有实例并提示，然后退出，防止二次启动
    _single_handle, already = singleinstance.acquire_single_instance()
    if already:
        singleinstance.signal_existing_instance()
        singleinstance.show_message('程序已在后台运行，已为您唤起主窗口。')
        raise SystemExit(0)

    run()
