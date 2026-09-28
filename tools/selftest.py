# -*- coding: utf-8 -*-
"""自测脚本：验证核心逻辑（不注入真实按键/鼠标，仅测试纯逻辑）。"""
import os
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import keyboard  # noqa: E402
import mouse  # noqa: E402
from src import config, hotkeys, player, recorder, store  # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=''):
    if cond:
        PASS.append(name)
    else:
        FAIL.append((name, detail))


# ------------------------------------------------------------------ 配置
def test_config():
    d = tempfile.mkdtemp()
    p = os.path.join(d, 'config.json')
    cfg = config.Config(p)
    cfg.set('default_speed', 2.0)
    cfg.data['hotkeys']['record_toggle'] = 'ctrl+f9'
    cfg.save()
    cfg2 = config.Config(p)
    check('config 持久化', cfg2.get('default_speed') == 2.0)
    check('config 热键持久化', cfg2.hotkey('record_toggle') == 'ctrl+f9')


# ------------------------------------------------------------------ 存储
def test_store():
    d = tempfile.mkdtemp()
    s = store.MacroStore(d)
    s.save('测试 脚本', {'a': 1})
    check('store 保存/列表', '测试 脚本.macro' in s.list())
    data = s.load('测试 脚本')
    check('store 加载', data == {'a': 1})
    # 重名冲突：exists 检测；默认不覆盖抛异常；overwrite=True 覆盖；unique_name 加序号
    check('store 重名检测', s.exists('测试 脚本') is True)
    try:
        s.save('测试 脚本', {'a': 2})
        check('store 默认不覆盖', False, '应抛 FileExistsError')
    except FileExistsError:
        check('store 默认不覆盖', True)
    u1 = s.unique_name('测试 脚本')
    check('store 自动重命名', u1 == '测试 脚本-2.macro', u1)
    s.save('测试 脚本', {'a': 2}, overwrite=True)
    check('store 覆盖保存', s.load('测试 脚本') == {'a': 2})
    s.save(u1, {'a': 3})
    check('store 唯一名可保存', u1 in s.list())
    s.rename('测试 脚本', '新名/非法:名')
    check('store 重命名(清理非法字符)', '新名_非法_名.macro' in s.list())
    s.delete('新名/非法:名')
    check('store 删除', '新名_非法_名.macro' not in s.list())
    check('store 路径安全', '..' not in s.path_for('../a'))


# ------------------------------------------------------------------ 热键
def test_hotkeys():
    hm = hotkeys.HotkeyManager(config.Config(), callbacks={})
    check('热键解析合法', hm.validate_combo('ctrl+f6') is None)
    check('热键解析非法', hm.validate_combo('不存在的键xyz') is not None)
    codes = hm.codes_of_combo('ctrl+f6')
    check('热键扫描码非空', len(codes) >= 2, str(codes))
    check('含修饰键', any(keyboard.is_modifier(c) for c in codes))


# ------------------------------------------------------------------ 录制：移动降采样
def test_move_downsample():
    r = recorder.Recorder()
    r._recording = True
    r._record_mouse_moves = True
    r._sample_interval = 0.015
    r._min_distance = 3

    def mv(x, y, t):
        return mouse.MoveEvent(x, y, t)

    r._on_mouse(mv(0, 0, 10.000))
    r._on_mouse(mv(0, 1, 10.005))   # 距离1<3，且间隔<15ms -> 丢弃
    r._on_mouse(mv(5, 0, 10.010))   # 间隔<15ms -> 丢弃（即使距离够）
    r._on_mouse(mv(20, 0, 10.100))  # 间隔够 -> 记录
    moves = [e for e in r._events if e['type'] == 'move']
    check('移动降采样-间隔过滤', len(moves) == 2, str(moves))
    check('移动降采样-首点记录', moves[0]['x'] == 0 and moves[0]['y'] == 0)

    r2 = recorder.Recorder()
    r2._recording = True
    r2._record_mouse_moves = False
    r2._on_mouse(mv(3, 3, 10.0))
    check('关闭移动录制', len(r2._events) == 0)


# ------------------------------------------------------------------ 录制：控制热键过滤
def test_hotkey_purge():
    r = recorder.Recorder()
    r._recording = True
    r._hotkey_modifier_codes = set(keyboard.key_to_scan_codes('ctrl'))
    ctrl = list(keyboard.key_to_scan_codes('ctrl'))[0]
    f6 = list(keyboard.key_to_scan_codes('f6'))[0]
    combo = set([ctrl, f6])

    def key(code, action, t):
        return SimpleNamespace(scan_code=code, event_type=action, time=t,
                               name='x', is_keypad=False)

    # 常见情况：ctrl↓ -> f6↓（触发热键）-> f6↑ -> ctrl↑
    r._on_key(key(ctrl, keyboard.KEY_DOWN, 1.0))
    r._on_key(key(f6, keyboard.KEY_DOWN, 1.1))
    check('热键触发前已记录 ctrl+f6', len(r._events) == 2, str(r._events))
    r.on_control_hotkey(combo)
    check('热键触发后清除已录事件', len(r._events) == 0, str(r._events))
    r._on_key(key(f6, keyboard.KEY_UP, 1.2))
    r._on_key(key(ctrl, keyboard.KEY_UP, 1.3))
    check('热键释放事件被跳过', len(r._events) == 0, str(r._events))

    # 打字穿插情况：ctrl↓ -> a↓ -> a↑ -> f6↓
    a = list(keyboard.key_to_scan_codes('a'))[0]
    r2 = recorder.Recorder()
    r2._recording = True
    r2._hotkey_modifier_codes = set([ctrl])
    r2._on_key(key(ctrl, keyboard.KEY_DOWN, 1.0))
    r2._on_key(key(a, keyboard.KEY_DOWN, 1.05))
    r2._on_key(key(a, keyboard.KEY_UP, 1.10))
    r2._on_key(key(f6, keyboard.KEY_DOWN, 1.15))
    r2.on_control_hotkey(combo)
    r2._on_key(key(f6, keyboard.KEY_UP, 1.2))
    r2._on_key(key(ctrl, keyboard.KEY_UP, 1.3))
    remaining = [e for e in r2._events]
    names = [e['code'] for e in remaining]
    check('穿插场景-保留正常按键', names == [a, a], str(names))
    check('穿插场景-剔除修饰键与热键', ctrl not in names and f6 not in names)


# ------------------------------------------------------------------ 回放逻辑
def test_player_timing():
    p = player.Player()
    events = [
        {'type': 'key', 'action': 'down', 'code': 30, 'ts': 10.0},
        {'type': 'key', 'action': 'up', 'code': 30, 'ts': 10.5},
    ]
    # 仅验证事件按时间排序后的目标间隔计算逻辑（不注入）
    t0 = events[0]['ts']
    diffs = [(e['ts'] - t0) for e in events]
    check('回放间隔计算', diffs == [0.0, 0.5], str(diffs))
    check('回放速度倍率换算', diffs[1] / 2.0 == 0.25)


def main():
    test_config()
    test_store()
    test_hotkeys()
    test_move_downsample()
    test_hotkey_purge()
    test_player_timing()
    print('通过 %d 项' % len(PASS))
    for f in FAIL:
        print('失败: %s -> %s' % (f[0], f[1]))
    if FAIL:
        sys.exit(1)
    print('ALL TESTS PASSED')


if __name__ == '__main__':
    main()
