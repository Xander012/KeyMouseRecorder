# -*- coding: utf-8 -*-
"""脚本文件管理：保存/加载/重命名/删除 .macro 文件（内容为 JSON）。"""
import json
import os
import re

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class MacroStore:
    def __init__(self, dir_path):
        self.dir = dir_path
        try:
            os.makedirs(dir_path, exist_ok=True)
        except Exception:
            pass

    @staticmethod
    def sanitize(name):
        name = _ILLEGAL.sub('_', str(name)).strip().strip('.')
        if not name:
            name = '未命名脚本'
        return name

    def path_for(self, name):
        name = self.sanitize(name)
        if not name.lower().endswith('.macro'):
            name += '.macro'
        return os.path.join(self.dir, name)

    def list(self):
        files = []
        try:
            for fn in os.listdir(self.dir):
                if fn.lower().endswith('.macro'):
                    files.append(fn)
        except OSError:
            pass
        return sorted(files, key=str.lower)

    def exists(self, name):
        return os.path.exists(self.path_for(name))

    def save(self, name, data, overwrite=False):
        path = self.path_for(name)
        if not overwrite and os.path.exists(path):
            raise FileExistsError('已存在同名脚本: %s' % os.path.basename(path))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return os.path.basename(path)

    def unique_name(self, name):
        """重名时追加序号（-2、-3…），返回不与现有文件冲突的名称。"""
        name = self.sanitize(name)
        base = name[:-6] if name.lower().endswith('.macro') else name
        candidate = base + '.macro'
        i = 2
        while os.path.exists(os.path.join(self.dir, candidate)):
            candidate = '%s-%d.macro' % (base, i)
            i += 1
        return candidate

    def load(self, name):
        path = self.path_for(name)
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def rename(self, old, new):
        old_path = self.path_for(old)
        new_path = self.path_for(new)
        if not os.path.exists(old_path):
            raise FileNotFoundError('源脚本不存在: %s' % old)
        if os.path.exists(new_path):
            raise FileExistsError('目标脚本已存在: %s' % new)
        os.rename(old_path, new_path)
        return os.path.basename(new_path)

    def delete(self, name):
        path = self.path_for(name)
        if os.path.exists(path):
            os.remove(path)
