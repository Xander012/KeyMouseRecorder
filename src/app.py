# -*- coding: utf-8 -*-
"""主程序：tkinter 图形界面（中文），整合录制/回放/文件管理/热键/系统托盘。"""
import datetime
import os
import queue
import sys
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import keyboard

from . import config, hotkeys, logutil, minibar, player, recorder, singleinstance, sounds, store, theme, tray

APP_TITLE = '键鼠录制回放工具'


def resource_path(rel):
    """兼容 PyInstaller 冻结与源码运行两种形态的资源定位。"""
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _clear_pressed_state():
    """清理 keyboard 库残留的按下状态，避免连续检测热键时组合键叠加。

    keyboard.read_hotkey(suppress=True) 会拦截 KEY_UP，导致库内部全局的
    _pressed_events 残留上次按下的键；不清理的话，下次检测会把残留键
    一并拼进结果，出现「组合键越叠越长」。
    """
    try:
        lock = getattr(keyboard, '_pressed_events_lock', None)
        pressed = getattr(keyboard, '_pressed_events', None)
        if lock is not None and pressed is not None:
            with lock:
                pressed.clear()
    except Exception:
        pass


class App:
    CMD_RECORD = 'record'
    CMD_PLAY = 'play'
    CMD_STOP = 'stop'
    CMD_SHOW = 'show'
    CMD_QUIT = 'quit'

    def __init__(self):
        self.cfg = config.Config()
        self.log = logutil.get_logger(config.app_data_dir())
        self.store = store.MacroStore(os.path.join(config.app_data_dir(), 'macros'))

        self.q = queue.Queue()
        self.current_macro = None
        self.mini_bar = None
        self._capture_cancelled = {}

        self.recorder = recorder.Recorder(on_status=self._enqueue_status)
        self.player = player.Player(on_status=self._enqueue_status,
                                    on_finished=lambda aborted: self.q.put(('play_finished', aborted)))
        self.hotkeys = hotkeys.HotkeyManager(
            self.cfg,
            callbacks={
                'record_toggle': self._hotkey_record_toggle,
                'play_toggle': self._hotkey_play_toggle,
                'emergency_stop': self._hotkey_emergency,
                'show_hide': self._hotkey_show_hide,
            },
            on_hotkey_trigger=self.recorder.on_control_hotkey,
        )

        self._build_ui()
        self.mini_bar = minibar.MiniBar(self)
        sounds.set_enabled(self.cfg.get('sound_feedback', True))
        if self.cfg.get('mini_bar_enabled', False):
            self.mini_bar.show()
        self._setup_tray()
        self._start_show_event_listener()
        self.hotkeys.register_all()
        self.recorder.set_hotkey_codes(self.hotkeys.all_codes(),
                                       self.hotkeys.modifier_codes())

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self.root.after(100, self._poll)
        self._update_ui_state()
        self._refresh_scripts()
        self._log('就绪')
        if self.cfg.get('start_minimized'):
            self.root.after(300, self._hide_to_tray)

    # ================================================================== UI
    def _build_ui(self):
        theme.enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.configure(bg=theme.BG)
        try:
            self.root.iconbitmap(resource_path('assets/app.ico'))
        except Exception:
            pass
        theme.apply_theme(self.root)

        # 顶部标题区
        header = ttk.Frame(self.root)
        header.pack(fill='x', padx=18, pady=(16, 10))
        ttk.Label(header, text=APP_TITLE, style='Title.TLabel').pack(side='left')
        self.var_topmost = tk.BooleanVar(value=bool(self.cfg.get('always_on_top', True)))
        ttk.Checkbutton(header, text='窗口置顶', variable=self.var_topmost,
                        command=self._apply_topmost).pack(side='right', padx=(12, 0))
        self.var_minibar = tk.BooleanVar(value=bool(self.cfg.get('mini_bar_enabled', False)))
        ttk.Checkbutton(header, text='悬浮条', variable=self.var_minibar,
                        command=self._toggle_minibar).pack(side='right', padx=(12, 0))
        self.state_badge = ttk.Label(header, text='● 就绪', style='Secondary.TLabel')
        self.state_badge.pack(side='right')

        # 工具栏（两行：主要操作 + 文件/设置，避免高 DPI 下单行按钮被挤出窗口）
        bar = ttk.Frame(self.root)
        bar.pack(fill='x', padx=18, pady=(0, 10))

        bar_main = ttk.Frame(bar)
        bar_main.pack(fill='x')
        self.btn_record = ttk.Button(bar_main, text='开始录制', style='Accent.TButton',
                                     command=self._toggle_record)
        self.btn_record.pack(side='left', padx=(0, 8))
        self.btn_play = ttk.Button(bar_main, text='回放', style='Accent.TButton',
                                   command=self._toggle_play)
        self.btn_play.pack(side='left', padx=(0, 8))
        self.btn_stop = ttk.Button(bar_main, text='停止', command=self._stop_all)
        self.btn_stop.pack(side='left')

        bar_file = ttk.Frame(bar)
        bar_file.pack(fill='x', pady=(8, 0))
        ttk.Button(bar_file, text='保存', command=self._save_macro).pack(side='left', padx=(0, 8))
        ttk.Button(bar_file, text='加载', command=self._load_selected).pack(side='left', padx=(0, 8))
        ttk.Button(bar_file, text='设置', command=self._open_settings).pack(side='left')

        # 回放参数
        opts = ttk.Frame(self.root)
        opts.pack(fill='x', padx=18, pady=(0, 10))
        ttk.Label(opts, text='回放次数').pack(side='left')
        self.var_loop = tk.StringVar(value=str(self.cfg.get('default_loop_count', 1)))
        self.spin_loop = ttk.Spinbox(opts, from_=0, to=99999, width=6, textvariable=self.var_loop)
        self.spin_loop.pack(side='left', padx=(8, 4))
        ttk.Label(opts, text='(0=无限)', style='Secondary.TLabel').pack(side='left', padx=(0, 20))
        ttk.Label(opts, text='速度').pack(side='left')
        self.var_speed = tk.StringVar(value=self._fmt_speed(self.cfg.get('default_speed', 1.0)))
        ttk.Combobox(opts, textvariable=self.var_speed, width=6, state='readonly',
                     values=('0.5x', '1x', '2x', '4x')).pack(side='left', padx=(8, 0))

        # 底部区：状态栏（控制热键）+ 日志区（运行窗口）。
        # 必须先按 side='bottom' 打包：pack 按打包顺序分配空间，后打包的组件最先被裁掉；
        # 这样窗口变小时被裁的是上方脚本列表（自带滚动条），而不是这块运行窗口。
        bottom = ttk.Frame(self.root)
        bottom.pack(side='bottom', fill='both', expand=True, padx=18, pady=(0, 14))

        self.status_var = tk.StringVar(value='就绪')
        ttk.Label(bottom, textvariable=self.status_var, style='Status.TLabel',
                  anchor='w').pack(fill='x', pady=(0, 6))

        self.log_text = tk.Text(bottom, height=8, state='disabled', wrap='word',
                                bg=theme.SURFACE_ALT, fg=theme.TEXT_SECONDARY,
                                relief='flat', borderwidth=0,
                                highlightthickness=1, highlightbackground=theme.BORDER,
                                font=theme.FONT_SMALL, padx=8, pady=6)
        self.log_text.pack(fill='both', expand=True)

        # 脚本列表：高度收敛且不再争抢剩余空间，多出来的高度全部给日志区。
        mid = ttk.Frame(self.root)
        mid.pack(side='top', fill='x', padx=18, pady=(0, 10))
        ttk.Label(mid, text='脚本列表', style='Section.TLabel').pack(anchor='w', pady=(0, 6))
        body = ttk.Frame(mid)
        body.pack(fill='both', expand=True)
        list_frame = ttk.Frame(body)
        list_frame.pack(side='left', fill='both', expand=True)
        self.script_list = tk.Listbox(
            list_frame, height=6, exportselection=False,
            bg=theme.SURFACE, fg=theme.TEXT, relief='flat', borderwidth=0,
            highlightthickness=1, highlightbackground=theme.BORDER,
            highlightcolor=theme.ACCENT, selectbackground=theme.ACCENT,
            selectforeground='#FFFFFF', font=theme.FONT, activestyle='none')
        self.script_list.pack(side='left', fill='both', expand=True)
        sb = ttk.Scrollbar(list_frame, orient='vertical', command=self.script_list.yview)
        sb.pack(side='left', fill='y')
        self.script_list.config(yscrollcommand=sb.set)
        self.script_list.bind('<Double-1>', lambda e: self._load_selected())

        side = ttk.Frame(body)
        side.pack(side='right', fill='y', padx=(12, 0))
        ttk.Button(side, text='重命名', command=self._rename_selected).pack(fill='x', pady=(0, 8))
        ttk.Button(side, text='删除', command=self._delete_selected).pack(fill='x', pady=(0, 8))
        ttk.Button(side, text='打开目录', command=self._open_script_dir).pack(fill='x')

        # 启动时按配置置顶（固定最上层）
        if self.cfg.get('always_on_top', True):
            self.root.attributes('-topmost', True)

        # 启动尺寸按 DPI 与内容自适应：高 DPI 下固定 720x600 会让底部内容溢出，
        # 这里改用实际请求尺寸，保证「控制热键」状态栏及其下方日志区完整可见，
        # 同时限制在屏幕可用范围内。
        self.root.update_idletasks()
        req_w = self.root.winfo_reqwidth()
        req_h = self.root.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = max(760, min(req_w + 24, int(sw * 0.9)))
        h = max(660, min(req_h + 60, int(sh * 0.85)))
        self.root.geometry('%dx%d' % (w, h))
        self.root.minsize(min(680, w), min(h, 640))

    def _setup_tray(self):
        ico = resource_path('assets/app.ico')
        self.tray = tray.TrayIcon(APP_TITLE, icon_path=ico if os.path.exists(ico) else None)
        self.tray.set_menu([
            ('显示主界面', self.CMD_SHOW),
            ('开始/停止录制', self.CMD_RECORD),
            ('开始/停止回放', self.CMD_PLAY),
            ('紧急停止', self.CMD_STOP),
            (None, None),
            ('退出', self.CMD_QUIT),
        ])
        self.tray.start()

    def _start_show_event_listener(self):
        """监听二次启动发出的唤起事件，收到后显示主窗口。"""
        try:
            event = singleinstance.create_show_event()
            if not event:
                return

            def run_listener():
                while singleinstance.wait_and_reset(event):
                    self.q.put(('show_window',))

            threading.Thread(target=run_listener, daemon=True).start()
        except Exception:
            pass

    # ================================================================== 状态机
    def _update_ui_state(self):
        rec = self.recorder.is_recording()
        play = self.player.is_playing()
        self.btn_record.config(text='停止录制' if rec else '开始录制',
                               state='normal' if not play else 'disabled')
        self.btn_play.config(text='停止回放' if play else '回放',
                             state='normal' if not rec else 'disabled')
        self.btn_stop.config(state='normal' if (rec or play) else 'disabled')

        if rec:
            self.state_badge.config(text='● 正在录制', foreground=theme.DANGER)
        elif play:
            self.state_badge.config(text='● 正在回放', foreground=theme.ACCENT)
        else:
            self.state_badge.config(text='● 就绪', foreground=theme.TEXT_SECONDARY)

        if self.mini_bar is not None:
            self.mini_bar.update_state(rec, play)

        hk = self.cfg.data.get('hotkeys', {})
        self.status_var.set('控制热键   录制 %s   ·   回放 %s   ·   紧急停止 %s' % (
            hk.get('record_toggle', '?'),
            hk.get('play_toggle', '?'), hk.get('emergency_stop', '?')))

    def _set_state(self, state):
        self._update_ui_state()

    # ================================================================== 消息轮询
    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                self._handle_queue(item)
        except queue.Empty:
            pass
        # 托盘事件
        for ev in self.tray.drain():
            self._handle_tray(ev)
        self.root.after(100, self._poll)

    def _handle_queue(self, item):
        kind = item[0]
        if kind == 'status':
            self._log(item[1])
        elif kind == 'hotkey':
            self._handle_hotkey_action(item[1])
        elif kind == 'play_finished':
            aborted = item[1] if len(item) > 1 else False
            self._update_ui_state()
            if aborted:
                sounds.play_aborted()
            else:
                sounds.play_finished()
        elif kind == 'recorded':
            self._log('已录制 %d 个事件（尚未保存），请点「保存」保存脚本' % item[1])
            self._update_ui_state()
        elif kind == 'show_window':
            self._show_window()
        elif kind == 'hotkey_captured':
            self._on_hotkey_captured(*item[1:])

    def _handle_tray(self, ev):
        kind = ev[0]
        if kind == 'left_click':
            self._show_window()
        elif kind == 'command':
            cmd = ev[1]
            if cmd == self.CMD_SHOW:
                self._show_window()
            elif cmd == self.CMD_RECORD:
                self._toggle_record()
            elif cmd == self.CMD_PLAY:
                self._toggle_play()
            elif cmd == self.CMD_STOP:
                self._stop_all()
            elif cmd == self.CMD_QUIT:
                self._quit()

    # ================================================================== 热键回调（键盘监听线程）
    def _hotkey_record_toggle(self, name):
        self.q.put(('hotkey', 'record_toggle'))

    def _hotkey_play_toggle(self, name):
        self.q.put(('hotkey', 'play_toggle'))

    def _hotkey_emergency(self, name):
        # 紧急停止需要立即生效，直接在当前线程执行（线程安全）
        self.player.stop()
        if self.recorder.is_recording():
            evs = self.recorder.stop()
            if evs:
                self._keep_macro(evs)
                sounds.record_stop()
        self.q.put(('status', '已触发紧急停止，所有按键已释放'))

    def _hotkey_show_hide(self, name):
        self.q.put(('hotkey', 'show_hide'))

    def _handle_hotkey_action(self, name):
        if name == 'record_toggle':
            self._toggle_record()
        elif name == 'play_toggle':
            self._toggle_play()
        elif name == 'show_hide':
            self._toggle_visible()

    # ================================================================== 录制/回放
    def _toggle_record(self):
        if self.recorder.is_recording():
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self):
        if self.player.is_playing():
            self.player.stop()
        self.recorder.set_hotkey_codes(self.hotkeys.all_codes(),
                                       self.hotkeys.modifier_codes())
        ok = self.recorder.start(
            record_mouse_moves=self.cfg.get('record_mouse_moves', True),
            sample_interval_ms=self.cfg.get('sample_interval_ms', 15),
            min_distance=self.cfg.get('min_move_distance', 3))
        if ok:
            self._log('开始录制（%s）' % (
                '含鼠标移动' if self.cfg.get('record_mouse_moves', True) else '仅录点击'))
            sounds.record_start()
        self._update_ui_state()

    def _stop_record(self):
        evs = self.recorder.stop()
        if evs is not None:
            self._keep_macro(evs)
            self.q.put(('recorded', len(evs)))
            sounds.record_stop()
        self._update_ui_state()

    def _keep_macro(self, events):
        self.current_macro = {
            'version': 1,
            'name': '录制_%s' % datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3],
            'created_at': datetime.datetime.now().isoformat(timespec='seconds'),
            'duration_ms': int((events[-1]['ts'] - events[0]['ts']) * 1000) if events else 0,
            'settings': {
                'record_mouse_moves': self.cfg.get('record_mouse_moves', True),
                'sample_interval_ms': self.cfg.get('sample_interval_ms', 15),
                'min_move_distance': self.cfg.get('min_move_distance', 3),
            },
            'events': events,
        }
        # 录制完成后只保留在内存（current_macro），由用户点击「保存」手动写入磁盘。

    def _toggle_play(self):
        if self.player.is_playing():
            self.player.stop()
            self._update_ui_state()
            return
        if self.recorder.is_recording():
            self._stop_record()
        macro = self.current_macro
        if not macro or not macro.get('events'):
            self._log('没有可回放的脚本，请先录制或加载')
            messagebox.showinfo('提示', '没有可回放的脚本，请先录制或加载脚本。')
            return
        loop = self._get_loop()
        speed = self._get_speed()
        self.player.play(macro['events'], loop_count=loop, speed=speed)
        self._log('开始回放（%s 次，%.2gx）' % ('无限' if loop <= 0 else loop, speed))
        sounds.play_start()
        self._update_ui_state()

    def _stop_all(self):
        if self.player.is_playing():
            self.player.stop()
        if self.recorder.is_recording():
            evs = self.recorder.stop()
            if evs:
                self._keep_macro(evs)
                self.q.put(('recorded', len(evs)))
                sounds.record_stop()
        self._update_ui_state()

    def _get_loop(self):
        try:
            return max(0, int(float(self.var_loop.get())))
        except Exception:
            return 1

    def _get_speed(self):
        s = self.var_speed.get().replace('x', '').strip()
        try:
            v = float(s)
            return v if v > 0 else 1.0
        except Exception:
            return 1.0

    @staticmethod
    def _fmt_speed(v):
        try:
            v = float(v)
        except Exception:
            v = 1.0
        if abs(v - int(v)) < 1e-9:
            return '%dx' % int(v)
        return '%.2gx' % v

    # ================================================================== 文件管理
    def _refresh_scripts(self):
        self.script_list.delete(0, 'end')
        for fn in self.store.list():
            self.script_list.insert('end', fn)

    def _selected_script(self):
        sel = self.script_list.curselection()
        if not sel:
            return None
        return self.script_list.get(sel[0])

    def _save_macro(self):
        if not self.current_macro or not self.current_macro.get('events'):
            messagebox.showinfo('提示', '当前没有可保存的录制内容。')
            return
        name = simpledialog.askstring('保存脚本', '脚本名称：',
                                      initialvalue=self.current_macro.get('name', ''))
        if not name:
            return
        try:
            saved = self._resolve_save(name)
            if saved is None:
                return  # 用户取消
            self.current_macro['name'] = saved
            self._refresh_scripts()
            self._log('已保存: %s' % saved)
        except Exception as exc:
            messagebox.showerror('保存失败', str(exc))

    def _resolve_save(self, name):
        """保存时处理文件名重复：覆盖 / 自动重命名 / 取消。返回保存后的文件名，取消返回 None。"""
        clean = self.store.sanitize(name)
        if self.store.exists(clean):
            choice = messagebox.askyesnocancel(
                '文件名重复',
                '脚本「%s」已存在。\n\n「是」= 覆盖  「否」= 自动重命名  「取消」= 放弃保存' % clean)
            if choice is None:
                return None
            if choice:
                return self.store.save(clean, self.current_macro, overwrite=True)
            clean = self.store.unique_name(clean)
        return self.store.save(clean, self.current_macro)

    def _load_selected(self):
        fn = self._selected_script()
        if not fn:
            self._log('请先在列表中选择一个脚本')
            return
        try:
            self.current_macro = self.store.load(fn)
            n = len(self.current_macro.get('events', []))
            self._log('已加载: %s（%d 个事件）' % (fn, n))
            # 回放参数跟随脚本设置（若存在）
            st = self.current_macro.get('settings') or {}
            if st.get('record_mouse_moves') is not None:
                self.cfg.set('record_mouse_moves', bool(st['record_mouse_moves']), save=False)
        except Exception as exc:
            messagebox.showerror('加载失败', str(exc))

    def _rename_selected(self):
        fn = self._selected_script()
        if not fn:
            return
        new = simpledialog.askstring('重命名', '新名称：', initialvalue=fn)
        if not new:
            return
        try:
            renamed = self.store.rename(fn, new)
            self._refresh_scripts()
            self._log('已重命名为: %s' % renamed)
        except Exception as exc:
            messagebox.showerror('重命名失败', str(exc))

    def _delete_selected(self):
        fn = self._selected_script()
        if not fn:
            return
        if messagebox.askyesno('确认删除', '确定删除脚本「%s」吗？' % fn):
            try:
                self.store.delete(fn)
                self._refresh_scripts()
                self._log('已删除: %s' % fn)
            except Exception as exc:
                messagebox.showerror('删除失败', str(exc))

    def _open_script_dir(self):
        try:
            os.startfile(self.store.dir)  # noqa: 仅在 Windows 可用
        except Exception:
            messagebox.showinfo('脚本目录', self.store.dir)

    # ================================================================== 设置
    def _open_settings(self):
        if self.recorder.is_recording() or self.player.is_playing():
            messagebox.showinfo('提示', '请先停止录制/回放，再修改设置。')
            return
        # 设置期间注销控制热键，避免按键被旧热键抢走
        self.hotkeys.unregister_all()
        SettingsDialog(self)

    def _reload_hotkeys(self):
        self.hotkeys.register_all()
        self.recorder.set_hotkey_codes(self.hotkeys.all_codes(),
                                       self.hotkeys.modifier_codes())
        sounds.set_enabled(self.cfg.get('sound_feedback', True))
        self._update_ui_state()

    def _capture_hotkey(self, name, entry, btn):
        self._capture_cancelled.pop(name, None)
        btn.config(state='disabled', text='请按键…')
        entry.config(state='normal')
        entry.delete(0, 'end')
        entry.insert(0, '正在检测…')

        def run():
            try:
                # 先清理上次检测残留的按键状态，再读取新组合键
                _clear_pressed_state()
                combo = keyboard.read_hotkey(suppress=True)
                if self._capture_cancelled.get(name):
                    return
                self.q.put(('hotkey_captured', name, combo, entry, btn))
            except Exception as exc:
                self.q.put(('status', '检测失败: %s' % exc))

        threading.Thread(target=run, daemon=True).start()

    def _on_hotkey_captured(self, name, combo, entry, btn):
        try:
            if not entry.winfo_exists():
                return
            entry.config(state='normal')
            entry.delete(0, 'end')
            entry.insert(0, combo)
            btn.config(state='normal', text='检测')
        except Exception:
            return
        err = hotkeys.HotkeyManager.validate_combo(combo)
        if err:
            messagebox.showwarning('热键无效', err)
            return
        conf = self.hotkeys.conflict_with_other_hotkey(name, combo)
        if conf:
            other, desc = conf
            messagebox.showwarning('热键冲突', '%s\n\n建议更换其他热键。' % desc)
            return
        mconf = hotkeys.HotkeyManager.conflict_with_macro_keys(combo, self.current_macro)
        if mconf:
            messagebox.showwarning('提示', mconf)

    # ================================================================== 窗口/托盘
    def _toggle_visible(self):
        if self.root.state() == 'withdrawn':
            self._show_window()
        else:
            self._hide_to_tray()

    def _hide_to_tray(self):
        self.root.withdraw()
        self.tray.notify(APP_TITLE, '程序已最小化到系统托盘')

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _apply_topmost(self):
        try:
            self.root.attributes('-topmost', bool(self.var_topmost.get()))
            self.cfg.set('always_on_top', bool(self.var_topmost.get()))
            self._log('窗口置顶：%s' % ('开' if self.var_topmost.get() else '关'))
        except Exception:
            pass

    def _toggle_minibar(self):
        try:
            on = bool(self.var_minibar.get())
            self.cfg.set('mini_bar_enabled', on)
            if on:
                self.mini_bar.show()
            else:
                self.mini_bar.hide()
        except Exception:
            pass

    def _on_close(self):
        self._hide_to_tray()

    def _quit(self):
        try:
            self._stop_all()
            self.hotkeys.unregister_all()
            self.tray.stop()
            if self.mini_bar is not None:
                self.mini_bar.destroy()
        finally:
            self.root.destroy()
            os._exit(0)  # noqa: 确保托盘线程与钩子一并退出

    # ================================================================== 日志
    def _enqueue_status(self, msg):
        self.q.put(('status', msg))

    def _log(self, msg):
        try:
            self.log.info(msg)
        except Exception:
            pass
        try:
            self.log_text.config(state='normal')
            self.log_text.insert('end', '[%s] %s\n' % (
                datetime.datetime.now().strftime('%H:%M:%S'), msg))
            self.log_text.see('end')
            self.log_text.config(state='disabled')
        except Exception:
            pass


class SettingsDialog:
    """设置对话框：自定义控制热键（检测按键捕获）、录制参数、回放默认值。"""

    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title('设置')
        self.win.transient(app.root)

        self._build()
        self.win.protocol('WM_DELETE_WINDOW', self._on_close)

        # 按内容自适应尺寸并居中到主窗口（避免固定尺寸在高 DPI 下裁剪文字）
        self.win.update_idletasks()
        w = self.win.winfo_reqwidth()
        h = self.win.winfo_reqheight()
        rx = app.root.winfo_rootx()
        ry = app.root.winfo_rooty()
        rw = app.root.winfo_width()
        rh = app.root.winfo_height()
        self.win.geometry('%dx%d+%d+%d' % (
            w, h, rx + max(0, (rw - w) // 2), ry + max(0, (rh - h) // 2)))
        self.win.resizable(False, False)
        self.win.grab_set()

    def _build(self):
        pad = {'padx': 6, 'pady': 4}
        frm = ttk.Frame(self.win)
        frm.pack(fill='both', expand=True, **pad)

        ttk.Label(frm, text='控制热键（点击「检测」后按下想要的组合键）',
                  font=theme.FONT_BOLD).pack(anchor='w', pady=(0, 4))
        self.entries = {}
        for name, label in config.HOTKEY_LABELS.items():
            row = ttk.Frame(frm)
            row.pack(fill='x', pady=2)
            ttk.Label(row, text=label, width=16).pack(side='left')
            entry = ttk.Entry(row, width=22)
            entry.insert(0, self.app.cfg.hotkey(name))
            entry.pack(side='left', padx=4)
            btn = ttk.Button(row, text='检测',
                             command=lambda n=name, e=entry, b=None: self._bind_capture(n, e))
            btn.pack(side='left')
            self.entries[name] = (entry, btn)

        ttk.Separator(frm).pack(fill='x', pady=8)
        ttk.Label(frm, text='录制参数', font=theme.FONT_BOLD).pack(anchor='w', pady=(0, 4))

        self.var_move = tk.BooleanVar(value=self.app.cfg.get('record_mouse_moves', True))
        ttk.Checkbutton(frm, text='录制鼠标移动轨迹（关闭则只录点击/滚轮，脚本更小）',
                        variable=self.var_move).pack(anchor='w')

        r1 = ttk.Frame(frm)
        r1.pack(fill='x', pady=2)
        ttk.Label(r1, text='移动采样间隔(ms)', width=16).pack(side='left')
        self.var_interval = tk.StringVar(value=str(self.app.cfg.get('sample_interval_ms', 15)))
        ttk.Entry(r1, textvariable=self.var_interval, width=20).pack(side='left', padx=4)
        ttk.Label(frm, text='越小越精细，文件越大', style='Secondary.TLabel').pack(
            anchor='w', padx=20, pady=(0, 2))

        r2 = ttk.Frame(frm)
        r2.pack(fill='x', pady=2)
        ttk.Label(r2, text='最小移动距离(px)', width=16).pack(side='left')
        self.var_distance = tk.StringVar(value=str(self.app.cfg.get('min_move_distance', 3)))
        ttk.Entry(r2, textvariable=self.var_distance, width=20).pack(side='left', padx=4)
        ttk.Label(frm, text='低于该距离的移动被丢弃', style='Secondary.TLabel').pack(
            anchor='w', padx=20, pady=(0, 2))

        ttk.Separator(frm).pack(fill='x', pady=8)
        ttk.Label(frm, text='回放默认值', font=theme.FONT_BOLD).pack(anchor='w', pady=(0, 4))

        r3 = ttk.Frame(frm)
        r3.pack(fill='x', pady=2)
        ttk.Label(r3, text='默认回放次数', width=16).pack(side='left')
        self.var_loop = tk.StringVar(value=str(self.app.cfg.get('default_loop_count', 1)))
        ttk.Entry(r3, textvariable=self.var_loop, width=20).pack(side='left', padx=4)
        ttk.Label(frm, text='0=无限循环', style='Secondary.TLabel').pack(
            anchor='w', padx=20, pady=(0, 2))

        r4 = ttk.Frame(frm)
        r4.pack(fill='x', pady=2)
        ttk.Label(r4, text='默认速度', width=16).pack(side='left')
        self.var_speed = tk.StringVar(value=App._fmt_speed(self.app.cfg.get('default_speed', 1.0)))
        ttk.Combobox(r4, textvariable=self.var_speed, width=20, state='readonly',
                     values=('0.5x', '1x', '2x', '4x')).pack(side='left', padx=4)

        ttk.Separator(frm).pack(fill='x', pady=8)
        ttk.Label(frm, text='提示', font=theme.FONT_BOLD).pack(anchor='w', pady=(0, 4))
        self.var_sound = tk.BooleanVar(value=self.app.cfg.get('sound_feedback', True))
        ttk.Checkbutton(frm, text='声音提示（开始/停止录制、回放结束提示音）',
                        variable=self.var_sound).pack(anchor='w')

        btns = ttk.Frame(frm)
        btns.pack(fill='x', pady=12)
        ttk.Button(btns, text='保存', command=self._save).pack(side='right', padx=4)
        ttk.Button(btns, text='取消', command=self._on_close).pack(side='right', padx=4)

    def _bind_capture(self, name, entry):
        entry, btn = self.entries[name]
        self.app._capture_hotkey(name, entry, btn)

    def _save(self):
        hk = {}
        for name, (entry, _btn) in self.entries.items():
            combo = entry.get().strip()
            err = hotkeys.HotkeyManager.validate_combo(combo)
            if err:
                messagebox.showwarning('热键无效', '「%s」%s' % (config.HOTKEY_LABELS[name], err))
                return
            conf = self.app.hotkeys.conflict_with_other_hotkey(name, combo)
            if conf:
                other, desc = conf
                if not messagebox.askyesno('热键冲突', '%s\n\n仍要保存吗？' % desc):
                    return
            hk[name] = combo
        self.app.cfg.data['hotkeys'] = hk

        try:
            self.app.cfg.set('record_mouse_moves', bool(self.var_move.get()), save=False)
            self.app.cfg.set('sample_interval_ms', int(self.var_interval.get()), save=False)
            self.app.cfg.set('min_move_distance', int(self.var_distance.get()), save=False)
            self.app.cfg.set('default_loop_count', int(self.var_loop.get()), save=False)
            v = float(self.var_speed.get().replace('x', '').strip())
            self.app.cfg.set('default_speed', v if v > 0 else 1.0, save=False)
        except ValueError:
            messagebox.showerror('输入错误', '录制/回放参数必须为数字。')
            return
        self.app.cfg.set('sound_feedback', bool(self.var_sound.get()), save=False)
        self.app.cfg.save()
        self.app._reload_hotkeys()
        self.app._log('设置已保存')
        self._on_close()

    def _on_close(self):
        try:
            self.app.hotkeys.register_all()
            self.app._update_ui_state()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass


def run():
    try:
        app = App()
        app.root.mainloop()
    except Exception:
        traceback.print_exc()
        try:
            messagebox.showerror('启动失败', traceback.format_exc())
        except Exception:
            pass
        sys.exit(1)
