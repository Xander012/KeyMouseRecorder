# -*- coding: utf-8 -*-
"""控制热键管理：全局注册（带拦截 suppress=True）、冲突检测、解析扫描码。"""
import keyboard


def normalize_combo(combo):
    """规范化热键字符串：去空白、转小写、'+' 两侧统一。"""
    parts = [p.strip().lower() for p in str(combo).replace('+', ' ').split()]
    return '+'.join(parts)


class HotkeyManager:
    def __init__(self, config, callbacks, on_hotkey_trigger=None):
        self.config = config
        self.callbacks = callbacks            # name -> callable(name)
        self.on_hotkey_trigger = on_hotkey_trigger  # callable(name, codes)
        self._handlers = {}                   # name -> remove 函数
        self._combo_codes = {}                # name -> set(scan_codes)

    # ------------------------------------------------------------------ 注册
    def register_all(self):
        for name in self.config.data.get('hotkeys', {}):
            self.register(name)

    def register(self, name):
        self.unregister(name)
        combo = self.config.hotkey(name)
        if not combo:
            return
        codes = self._codes_of(combo)
        self._combo_codes[name] = codes
        try:
            self._handlers[name] = keyboard.add_hotkey(
                combo,
                lambda n=name: self._fire(n),
                suppress=True,
                trigger_on_release=False,
            )
        except Exception as exc:
            self._handlers[name] = None
            if self.on_status:
                self.on_status('热键「%s」注册失败: %s' % (combo, exc))

    def unregister(self, name):
        h = self._handlers.pop(name, None)
        if h:
            try:
                keyboard.remove_hotkey(h)
            except Exception:
                pass

    def unregister_all(self):
        for name in list(self._handlers):
            self.unregister(name)

    def _fire(self, name):
        codes = self._combo_codes.get(name, set())
        if self.on_hotkey_trigger:
            try:
                self.on_hotkey_trigger(name, codes)
            except Exception:
                pass
        cb = self.callbacks.get(name)
        if cb:
            try:
                cb(name)
            except Exception:
                pass

    # ------------------------------------------------------------------ 扫描码
    @staticmethod
    def _codes_of(combo):
        codes = set()
        try:
            parsed = keyboard.parse_hotkey(combo)
            for step in parsed:
                for key_codes in step:
                    for c in key_codes:
                        codes.add(c)
        except Exception:
            pass
        return codes

    def all_codes(self):
        all_codes = set()
        for codes in self._combo_codes.values():
            all_codes |= codes
        return all_codes

    def modifier_codes(self):
        mods = set()
        for codes in self._combo_codes.values():
            for c in codes:
                if keyboard.is_modifier(c):
                    mods.add(c)
        return mods

    def codes_of_combo(self, combo):
        return self._codes_of(combo)

    # ------------------------------------------------------------------ 冲突检测
    @staticmethod
    def validate_combo(combo):
        """返回 None 表示合法，否则返回错误描述。"""
        combo = str(combo).strip()
        if not combo:
            return '热键不能为空'
        try:
            parsed = keyboard.parse_hotkey(combo)
            if not parsed:
                return '无法解析热键'
        except Exception as exc:
            return '无法解析热键「%s」：%s' % (combo, exc)
        return None

    def conflict_with_other_hotkey(self, name, combo):
        """检查与其他控制热键的冲突。返回 (冲突热键名, 说明) 或 None。"""
        norm = normalize_combo(combo)
        my_codes = self._codes_of(combo)
        for other, other_combo in self.config.data.get('hotkeys', {}).items():
            if other == name:
                continue
            if not other_combo:
                continue
            if normalize_combo(other_combo) == norm:
                return other, '与控制热键「%s」(%s) 完全相同' % (
                    self._label(other), other_combo)
            other_codes = self._codes_of(other_combo)
            if my_codes and other_codes:
                if my_codes <= other_codes or other_codes <= my_codes:
                    return other, '与控制热键「%s」(%s) 按键范围重叠' % (
                        self._label(other), other_combo)
        return None

    @staticmethod
    def conflict_with_macro_keys(combo, macro):
        """检查热键按键是否出现在已加载脚本录制的按键中。返回说明或 None。"""
        if not macro or not isinstance(macro, dict):
            return None
        events = macro.get('events') or []
        if not events:
            return None
        codes = HotkeyManager._codes_of(combo)
        if not codes:
            return None
        recorded = set()
        for ev in events:
            if ev.get('type') == 'key':
                recorded.add(ev.get('code'))
        overlap = codes & recorded
        if overlap:
            return '该热键的部分按键已出现在当前脚本录制内容中，回放时可能被过滤或误触发'
        return None

    @staticmethod
    def _label(name):
        from .config import HOTKEY_LABELS
        return HOTKEY_LABELS.get(name, name)
