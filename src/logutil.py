# -*- coding: utf-8 -*-
"""简单日志：输出到 stderr 与日志文件，便于排查问题。"""
import logging
import os

_logger = None


def get_logger(log_dir=None):
    """返回全局单例 logger。log_dir 提供时同时写入 <log_dir>/app.log。"""
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger('kbmacro')
    _logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S')
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(logging.INFO)
    _logger.addHandler(console)

    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
            file_h = logging.FileHandler(os.path.join(log_dir, 'app.log'), encoding='utf-8')
            file_h.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            file_h.setLevel(logging.DEBUG)
            _logger.addHandler(file_h)
        except Exception:
            pass
    return _logger
