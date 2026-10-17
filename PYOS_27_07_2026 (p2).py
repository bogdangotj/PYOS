#!/usr/bin/env python3
"""PyOS v16.2p build 27.07.2026 — BitSoft Studios (no-frames, full-manual, fixed apps)"""

import os, sys, json, time, hashlib, random, datetime, shlex, math, re, shutil
import textwrap, calendar, difflib, traceback as tb_module, threading
from collections import deque
from pathlib import Path

# ═══ FIX КОДИРОВКИ WINDOWS ═══
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ═══ ЦВЕТА ═══
def _uc():
    if 'idlelib' in sys.modules:
        return False
    if sys.platform == 'win32':
        os.system('')
        return True
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

UC = _uc()

class C:
    RST = '\033[0m' if UC else ''
    B   = '\033[1m' if UC else ''
    DIM = '\033[2m' if UC else ''
    R   = '\033[91m' if UC else ''
    G   = '\033[92m' if UC else ''
    Y   = '\033[93m' if UC else ''
    BL  = '\033[94m' if UC else ''
    M   = '\033[95m' if UC else ''
    CY  = '\033[96m' if UC else ''
    W   = '\033[97m' if UC else ''
    BG_BLUE = '\033[44m' if UC else ''
    BG_RED  = '\033[41m' if UC else ''

    @staticmethod
    def c(t, color):
        return f"{color}{t}{C.RST}" if UC else str(t)

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

# ═══ ПРОСТАЯ ТЕКСТОВАЯ РАЗМЕТКА (БЕЗ ПСЕВДОГРАФИКИ) ═══
class SimpleBox:
    """Замена Frames: надёжно работает во всех терминалах."""
    @staticmethod
    def header(title, width=50, char='='):
        line = char * width
        return f"{line}\n  {title}\n{line}"

    @staticmethod
    def section(title, content, width=50, char='-'):
        if isinstance(content, list):
            content = '\n'.join(str(l) for l in content)
        return f"-- {title} --\n{content}\n{char * width}"

    @staticmethod
    def kv_table(data, width=50):
        lines = []
        max_key = max((len(str(k)) for k in data.keys()), default=0) + 2
        for k, v in data.items():
            lines.append(f"  {str(k).ljust(max_key)} {v}")
        return '\n'.join(lines)

    @staticmethod
    def menu(title, items, width=50):
        lines = [f"  {title}"]
        lines.append('-' * width)
        for i, item in enumerate(items, 1):
            lines.append(f"  {i}. {item}")
        lines.append('-' * width)
        return '\n'.join(lines)

    @staticmethod
    def box(text, width=50, char='*'):
        line = char * width
        return f"{line}\n{text}\n{line}"

# ═══ BSOD ═══
class BSOD:
    @staticmethod
    def show(error_code='CRITICAL_DATA_DESTROYED',
             message='System data has been destroyed or is inaccessible.',
             details=''):
        clear()
        width = 60
        print('=' * width)
        print('  :(')
        print(f'  Error: {error_code}')
        print(f'  {message}')
        if details:
            print(f'  {details}')
        print('=' * width)
        print('  Press Enter to restart...')

    @staticmethod
    def crash_and_restart(error_code='CRITICAL_DATA_DESTROYED',
                          message='System data has been destroyed.',
                          details=''):
        BSOD.show(error_code, message, details)
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        return True

# ═══ FILESYSTEM HEALTH CHECK ═══
class FSHealthChecker:
    def __init__(self, fs, kernel_ref):
        self.fs = fs
        self.kernel = kernel_ref
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def check_now(self):
        if not self.fs.hostname_dir:
            return False
        return self.fs.hostname_dir.exists()

    def _monitor_loop(self):
        while self._running:
            if not self.check_now():
                self._running = False
                self.kernel._trigger_bsod('CRITICAL_DATA_DESTROYED',
                                          'System data folder has been deleted.',
                                          f'Missing: {self.fs.hostname_dir}')
                self.kernel.running = False
                return
            time.sleep(3.0)

# ═══ СИСТЕМА УВЕДОМЛЕНИЙ ═══
class NotificationCenter:
    def __init__(self):
        self.notifications = []
        self._next_id = 1
        self._lock = threading.Lock()

    def send(self, source, title, message, icon='info', priority='normal'):
        with self._lock:
            notif = {
                'id': self._next_id, 'source': source,
                'title': title, 'message': message,
                'icon': icon, 'priority': priority,
                'time': datetime.datetime.now().isoformat(),
                'read': False,
            }
            self._next_id += 1
            self.notifications.append(notif)
        return notif['id']

    def get_unread(self):
        with self._lock:
            return [n for n in self.notifications if not n['read']]

    def get_all(self):
        with self._lock:
            return list(self.notifications)

    def count_unread(self):
        with self._lock:
            return sum(1 for n in self.notifications if not n['read'])

    def mark_read(self, notif_id=None):
        with self._lock:
            if notif_id is None:
                for n in self.notifications:
                    n['read'] = True
            else:
                for n in self.notifications:
                    if n['id'] == notif_id:
                        n['read'] = True
                        break

    def delete(self, notif_id=None):
        with self._lock:
            if notif_id is None:
                self.notifications.clear()
                return True
            before = len(self.notifications)
            self.notifications = [n for n in self.notifications if n['id'] != notif_id]
            return len(self.notifications) < before

    def delete_by_source(self, source):
        with self._lock:
            self.notifications = [n for n in self.notifications if n['source'] != source]

    def delete_read(self):
        with self._lock:
            self.notifications = [n for n in self.notifications if not n['read']]

    def to_dict(self):
        with self._lock:
            return {'notifications': list(self.notifications), 'next_id': self._next_id}

    def from_dict(self, data):
        with self._lock:
            self.notifications = data.get('notifications', [])
            self._next_id = data.get('next_id', len(self.notifications) + 1)

    def format_badge(self):
        count = self.count_unread()
        if count == 0:
            return C.c("[0]", C.DIM)
        elif count <= 3:
            return C.c(f"[{count}]", C.Y)
        else:
            return C.c(f"[{count}!]", C.R + C.B)

    def format_panel(self, max_show=5):
        unread = self.get_unread()
        if not unread:
            return None
        lines = [C.c(f"  [Notifications ({len(unread)} new)]", C.Y + C.B)]
        shown = unread[-max_show:]
        if len(unread) > max_show:
            lines.append(C.c(f"  ... and {len(unread) - max_show} more", C.DIM))
        for n in shown:
            ico = {'info': '*', 'warn': '!', 'err': 'X', 'ok': '+', 'app': '#', 'timer': '@'}.get(n['icon'], '?')
            lines.append(f"  {ico} [{n['source'][:10]}] {n['title'][:25]}")
            if n['message']:
                lines.append(f"     {C.c(n['message'][:35], C.DIM)}")
        return '\n'.join(lines)

# ═══ ФОНОВЫЕ СЛУЖБЫ ═══
class BackgroundService:
    def __init__(self, name, notifications):
        self.name = name
        self.notifications = notifications
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def is_running(self):
        return self._running

    def _run(self):
        pass

class TimerService(BackgroundService):
    def __init__(self, notifications):
        super().__init__('timer', notifications)
        self.timers = []
        self._timer_lock = threading.Lock()
        self._next_timer_id = 1

    def add_timer(self, seconds, label='Timer'):
        if seconds <= 0:
            return None
        with self._timer_lock:
            timer_id = self._next_timer_id
            self._next_timer_id += 1
            end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            self.timers.append({
                'id': timer_id, 'label': label, 'seconds': seconds,
                'end_time': end_time, 'fired': False,
            })
            if not self._running:
                self.start()
            return timer_id

    def cancel_timer(self, timer_id):
        with self._timer_lock:
            before = len(self.timers)
            self.timers = [t for t in self.timers if t['id'] != timer_id]
            return len(self.timers) < before

    def get_active(self):
        with self._timer_lock:
            now = datetime.datetime.now()
            return [t for t in self.timers if not t['fired'] and t['end_time'] > now]

    def get_all(self):
        with self._timer_lock:
            return list(self.timers)

    def _run(self):
        while self._running:
            now = datetime.datetime.now()
            to_fire = []
            with self._timer_lock:
                for t in self.timers:
                    if not t['fired'] and now >= t['end_time']:
                        t['fired'] = True
                        to_fire.append(t)
                self.timers = [t for t in self.timers
                               if not t['fired'] or
                               t['end_time'] > now - datetime.timedelta(seconds=30)]
            for t in to_fire:
                self.notifications.send(
                    source='timer', title=f"Timer: {t['label']}",
                    message=f"Timer finished ({t['seconds']}s)",
                    icon='timer', priority='high',
                )
            time.sleep(0.5)

    def cleanup(self):
        with self._timer_lock:
            self.timers = [t for t in self.timers if not t['fired']]

    def to_dict(self):
        with self._timer_lock:
            result = []
            for t in self.timers:
                result.append({
                    'id': t['id'], 'label': t['label'], 'seconds': t['seconds'],
                    'end_time': t['end_time'].isoformat(), 'fired': t['fired'],
                })
            return {'timers': result, 'next_id': self._next_timer_id}

    def from_dict(self, data):
        with self._timer_lock:
            self._next_timer_id = data.get('next_id', 1)
            self.timers = []
            now = datetime.datetime.now()
            for t in data.get('timers', []):
                try:
                    end = datetime.datetime.fromisoformat(t['end_time'])
                    if end > now and not t.get('fired', False):
                        self.timers.append({
                            'id': t['id'], 'label': t['label'],
                            'seconds': t['seconds'], 'end_time': end, 'fired': False,
                        })
                except (ValueError, KeyError):
                    pass
            has_active = bool(self.timers)
        if has_active and not self._running:
            self.start()

class AppBackgroundManager:
    def __init__(self, notifications):
        self.notifications = notifications
        self.background_apps = {}
        self._lock = threading.Lock()

    def register(self, app_name, info=None):
        with self._lock:
            self.background_apps[app_name] = {
                'name': app_name, 'info': info or {},
                'registered': datetime.datetime.now().isoformat(), 'running': True,
            }

    def unregister(self, app_name):
        with self._lock:
            if app_name in self.background_apps:
                del self.background_apps[app_name]
                return True
            return False

    def is_background(self, app_name):
        with self._lock:
            return app_name in self.background_apps

    def get_all(self):
        with self._lock:
            return dict(self.background_apps)

    def to_dict(self):
        with self._lock:
            return dict(self.background_apps)

    def from_dict(self, data):
        with self._lock:
            self.background_apps = data if isinstance(data, dict) else {}

# ═══ РЕАЛЬНАЯ ФАЙЛОВАЯ СИСТЕМА ═══
class RealFS:
    def __init__(self, base_path):
        self.base = Path(base_path).resolve()
        self.hostname_dir = None
        self.current_disk = 'C'

    def init_structure(self, hostname):
        self.hostname_dir = self.base / hostname
        self.hostname_dir.mkdir(parents=True, exist_ok=True)
        self._create_disk('C')
        self.current_disk = 'C'
        for d in ['home', 'sysdata', 'sysdata/config',
                   'apps', 'apps/installed', 'apps/data', 'apps/store', 'apps/logs']:
            self._disk_path('C', d).mkdir(parents=True, exist_ok=True)
        self.write_file('/sysdata/config/boot.cfg', 'autostart=true\ntheme=default\n')

    def _create_disk(self, name):
        (self.hostname_dir / name.upper()).mkdir(parents=True, exist_ok=True)

    def _disk_path(self, disk, rel_path=''):
        p = self.hostname_dir / disk.upper()
        if rel_path:
            p = p / rel_path.lstrip('/')
        return p

    def _parse_disk_prefix(self, path):
        if len(path) >= 2 and path[1] == ':' and path[0].isalpha():
            d = path[0].upper()
            if self.hostname_dir and (self.hostname_dir / d).exists():
                return d, path[2:] or '/'
        return None, path

    def _real_path(self, virtual_path, cwd='/', disk_override=None):
        disk = disk_override or self.current_disk
        explicit, virtual_path = self._parse_disk_prefix(virtual_path)
        if explicit:
            disk = explicit
        if not virtual_path.startswith('/'):
            virtual_path = cwd.rstrip('/') + '/' + virtual_path
        parts = []
        for p in virtual_path.split('/'):
            if p == '' or p == '.':
                continue
            elif p == '..':
                if parts:
                    parts.pop()
            else:
                parts.append(p)
        return self._disk_path(disk, '/'.join(parts)), disk

    def resolve(self, path, cwd='/'):
        explicit, path = self._parse_disk_prefix(path)
        if not path.startswith('/'):
            path = cwd.rstrip('/') + '/' + path
        parts = []
        for p in path.split('/'):
            if p == '' or p == '.':
                continue
            elif p == '..':
                if parts:
                    parts.pop()
            else:
                parts.append(p)
        resolved = '/' + '/'.join(parts)
        return (resolved, explicit) if explicit else (resolved, None)

    def exists(self, path, cwd='/'):
        rp, _ = self._real_path(path, cwd)
        return rp.exists()

    def is_dir(self, path, cwd='/'):
        rp, _ = self._real_path(path, cwd)
        return rp.is_dir()

    def is_file(self, path, cwd='/'):
        rp, _ = self._real_path(path, cwd)
        return rp.is_file()

    def mkdir(self, path, cwd='/'):
        try:
            rp, _ = self._real_path(path, cwd)
            rp.mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False

    def write_file(self, path, content, cwd='/', append=False):
        try:
            rp, _ = self._real_path(path, cwd)
            rp.parent.mkdir(parents=True, exist_ok=True)
            if append:
                with open(rp, 'a', encoding='utf-8') as f:
                    f.write(content)
            else:
                rp.write_text(content, encoding='utf-8')
            return True
        except (OSError, PermissionError):
            return False

    def read_file(self, path, cwd='/'):
        try:
            rp, _ = self._real_path(path, cwd)
            if not rp.is_file():
                return None
            return rp.read_text(encoding='utf-8')
        except (OSError, PermissionError, UnicodeDecodeError):
            return None

    def delete(self, path, cwd='/', recursive=False):
        try:
            rp, disk = self._real_path(path, cwd)
            if rp == self.hostname_dir or rp == self.base or rp == self._disk_path(disk):
                return False
            if not rp.exists():
                return False
            if rp.is_file():
                rp.unlink()
            elif rp.is_dir():
                if recursive:
                    shutil.rmtree(rp)
                else:
                    rp.rmdir()
            return True
        except (OSError, PermissionError):
            return False

    def copy(self, src, dst, cwd='/'):
        try:
            src_rp, _ = self._real_path(src, cwd)
            dst_rp, _ = self._real_path(dst, cwd)
            if not src_rp.exists():
                return False
            if src_rp.is_file():
                dst_rp.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_rp, dst_rp)
            else:
                dst_rp.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src_rp, dst_rp, dirs_exist_ok=True)
            return True
        except (OSError, PermissionError, shutil.Error):
            return False

    def move(self, src, dst, cwd='/'):
        try:
            src_rp, _ = self._real_path(src, cwd)
            dst_rp, _ = self._real_path(dst, cwd)
            if not src_rp.exists():
                return False
            dst_rp.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_rp), str(dst_rp))
            return True
        except (OSError, PermissionError, shutil.Error):
            return False

    def rename(self, src, new_name, cwd='/'):
        try:
            src_rp, _ = self._real_path(src, cwd)
            if not src_rp.exists():
                return False
            src_rp.rename(src_rp.parent / new_name)
            return True
        except (OSError, PermissionError):
            return False

    def list_dir(self, path, cwd='/'):
        try:
            rp, _ = self._real_path(path, cwd)
            if not rp.is_dir():
                return None
            items = []
            for entry in sorted(rp.iterdir()):
                try:
                    items.append({
                        'name': entry.name, 'is_dir': entry.is_dir(),
                        'size': entry.stat().st_size if entry.is_file() else self._dir_size(entry),
                        'modified': datetime.datetime.fromtimestamp(
                            entry.stat().st_mtime).isoformat(),
                    })
                except (OSError, PermissionError):
                    pass
            return items
        except (OSError, PermissionError):
            return None

    def _dir_size(self, path):
        total = 0
        try:
            for f in path.rglob('*'):
                try:
                    if f.is_file():
                        total += f.stat().st_size
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            pass
        return total

    def find(self, path, pattern, cwd='/'):
        results = []
        if not pattern:
            return results
        try:
            rp, _ = self._real_path(path, cwd)
            if not rp.is_dir():
                return results
            for f in rp.rglob('*'):
                if pattern in f.name:
                    results.append('/' + str(f.relative_to(rp)).replace('\\', '/'))
        except (OSError, PermissionError):
            pass
        return results

    def touch(self, path, cwd='/'):
        try:
            rp, _ = self._real_path(path, cwd)
            rp.parent.mkdir(parents=True, exist_ok=True)
            if rp.exists():
                os.utime(rp, None)
            else:
                rp.write_text('', encoding='utf-8')
            return True
        except (OSError, PermissionError):
            return False

    def disk_usage(self, disk=None):
        disk = disk or self.current_disk
        dp = self.hostname_dir / disk
        return self._dir_size(dp) if dp.exists() else 0

    def get_disks(self):
        disks = []
        if not self.hostname_dir or not self.hostname_dir.exists():
            return disks
        try:
            for d in sorted(self.hostname_dir.iterdir()):
                if d.is_dir() and len(d.name) == 1 and d.name.isalpha():
                    disks.append(d.name.upper())
        except (OSError, PermissionError):
            pass
        return disks

    def tree(self, path='/', cwd='/', max_depth=4):
        rp, _ = self._real_path(path, cwd)
        if not rp.exists():
            return "Not found"
        lines = []
        self._tree_r(rp, lines, '', True, True, 0, max_depth)
        return '\n'.join(lines)

    def _tree_r(self, path, lines, prefix, is_last, is_root, depth, max_depth):
        if depth > max_depth:
            return
        conn = '' if is_root else ('└── ' if is_last else '├── ')
        col = C.BL if path.is_dir() else (C.M if path.name.endswith('.x4') else C.W)
        lines.append(prefix + conn + C.c(
            path.name + ('/' if path.is_dir() and not is_root else ''), col))
        if path.is_dir():
            try:
                items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
                for i, child in enumerate(items):
                    np = prefix + ('' if is_root else ('    ' if is_last else '│   '))
                    self._tree_r(child, lines, np, i == len(items) - 1,
                                 False, depth + 1, max_depth)
            except (OSError, PermissionError):
                pass

    def get_all_files_sorted_by_size(self, disk=None):
        disk = disk or self.current_disk
        dp = self.hostname_dir / disk
        files = []
        try:
            for f in dp.rglob('*'):
                if f.is_file():
                    files.append({
                        'path': '/' + str(f.relative_to(dp)).replace('\\', '/'),
                        'size': f.stat().st_size, 'name': f.name
                    })
        except (OSError, PermissionError):
            pass
        files.sort(key=lambda x: x['size'], reverse=True)
        return files

    def dir_size_at(self, path, cwd='/'):
        rp, _ = self._real_path(path, cwd)
        return self._dir_size(rp) if rp.exists() and rp.is_dir() else 0

    def migrate_user(self, username, from_disk, to_disk):
        try:
            src = self.hostname_dir / from_disk / 'home' / username
            dst_home = self.hostname_dir / to_disk / 'home'
            dst_home.mkdir(parents=True, exist_ok=True)
            dst = dst_home / username
            if not src.exists():
                return False
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            shutil.rmtree(src)
            return True
        except (OSError, PermissionError, shutil.Error):
            return False

# ═══ ПОЛЬЗОВАТЕЛИ ═══
class UserManager:
    HIDDEN_FIELDS = {'pw', 'salt'}

    def __init__(self):
        self.users = {}

    def _gen_salt(self):
        return os.urandom(16).hex()

    def _hash(self, pw, salt):
        return hashlib.sha256((salt + pw).encode()).hexdigest()

    def create(self, name, pw=None, hint=''):
        if name in self.users:
            return False, "User exists"
        salt = self._gen_salt()
        existing_uids = [u['uid'] for u in self.users.values()]
        new_uid = max(existing_uids) + 1 if existing_uids else 0
        self.users[name] = {
            'pw': self._hash(pw, salt) if pw else '',
            'salt': salt,
            'has_password': pw is not None and pw != '',
            'uid': new_uid,
            'home': f'/home/{name}',
            'hint': hint,
            'created': datetime.datetime.now().isoformat(),
            'disk': 'C'
        }
        return True, ""

    def auth(self, name, pw):
        if name not in self.users:
            return False
        u = self.users[name]
        if not u.get('has_password', True):
            return True
        if not pw:
            return not u.get('has_password', True)
        return u['pw'] == self._hash(pw, u['salt'])

    def has_password(self, name):
        if name not in self.users:
            return False
        return self.users[name].get('has_password', True)

    def change_password(self, name, new_pw):
        if name not in self.users:
            return False
        if new_pw is None or new_pw == '':
            self.users[name]['pw'] = ''
            self.users[name]['has_password'] = False
        else:
            salt = self._gen_salt()
            self.users[name]['salt'] = salt
            self.users[name]['pw'] = self._hash(new_pw, salt)
            self.users[name]['has_password'] = True
        return True

    def get_hint(self, name):
        return self.users.get(name, {}).get('hint', '')

    def set_hint(self, name, hint):
        if name in self.users:
            self.users[name]['hint'] = hint

    def get_disk(self, name):
        return self.users.get(name, {}).get('disk', 'C')

    def set_disk(self, name, disk):
        if name in self.users:
            self.users[name]['disk'] = disk

    def delete(self, name):
        if name not in self.users:
            return False
        del self.users[name]
        return True

    def list_users(self):
        return list(self.users.keys())

    def get_public_info(self, name):
        if name not in self.users:
            return None
        return {k: v for k, v in self.users[name].items() if k not in self.HIDDEN_FIELDS}

    def get_all_public(self):
        result = {}
        for name, data in self.users.items():
            result[name] = {k: v for k, v in data.items() if k not in self.HIDDEN_FIELDS}
        return result

# ═══ GUARDIAN ═══
class Guardian:
    def __init__(self):
        self.session_start = datetime.datetime.now()
        self.daily_limit = None
        self.warned_today = False
        self.app_folder_limit = 1 * 1024 * 1024
        self.suggest_commands = True

    def session_seconds(self):
        return int((datetime.datetime.now() - self.session_start).total_seconds())

    def session_str(self):
        s = self.session_seconds()
        h, r = divmod(s, 3600)
        m, sec = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def check_limit(self):
        if self.daily_limit is None:
            return None
        if self.session_seconds() / 60 >= self.daily_limit and not self.warned_today:
            self.warned_today = True
            return True
        return None

    def set_limit(self, minutes):
        self.daily_limit = minutes
        self.warned_today = False

    def set_app_folder_limit(self, size_bytes):
        self.app_folder_limit = size_bytes

    def suggest(self, wrong_cmd, available_cmds):
        if not self.suggest_commands:
            return []
        return difflib.get_close_matches(wrong_cmd, available_cmds, n=3, cutoff=0.4)

    def check_app_folder(self, fs, app_name):
        current = fs.dir_size_at(f'/apps/data/{app_name}')
        overflow = current > self.app_folder_limit if self.app_folder_limit else False
        return current, self.app_folder_limit, overflow

    def cleanup_app_folder(self, fs, app_name):
        current, limit, overflow = self.check_app_folder(fs, app_name)
        if not overflow:
            return []
        deleted = []
        rp, _ = fs._real_path(f'/apps/data/{app_name}')
        if not rp.exists():
            return []
        files = []
        try:
            for f in rp.rglob('*'):
                if f.is_file():
                    files.append((f, f.stat().st_size))
        except (OSError, PermissionError):
            pass
        files.sort(key=lambda x: x[1], reverse=True)
        for fpath, fsize in files:
            if current <= limit:
                break
            try:
                fpath.unlink()
                deleted.append((fpath.name, fsize))
                current -= fsize
            except (OSError, PermissionError):
                pass
        return deleted

    def check_all_apps(self, fs):
        results = []
        items = fs.list_dir('/apps/data')
        if not items:
            return results
        for item in items:
            if item['is_dir']:
                cur, lim, over = self.check_app_folder(fs, item['name'])
                results.append({
                    'name': item['name'], 'size': cur, 'limit': lim, 'over': over})
        return results

    def cleanup_all_apps(self, fs):
        total = []
        items = fs.list_dir('/apps/data')
        if not items:
            return total
        for item in items:
            if item['is_dir']:
                deleted = self.cleanup_app_folder(fs, item['name'])
                if deleted:
                    total.append((item['name'], deleted))
        return total

    def disk_report(self, fs):
        files = fs.get_all_files_sorted_by_size()
        return {'total': fs.disk_usage(), 'count': len(files), 'largest': files[:10]}

    def fmt_size(self, size):
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

# ═══ CRASH LOG ═══
class CrashLogger:
    def __init__(self, fs, debug_logger=None):
        self.fs = fs
        self.debug = debug_logger

    def log_crash(self, app_name, error, trace_str, code_line=''):
        self.fs.mkdir('/apps/logs')
        log_num = 1
        while self.fs.exists(f'/apps/logs/{app_name}_log{log_num}.json'):
            log_num += 1
        crash_data = {
            'app': app_name, 'error': str(error), 'type': type(error).__name__,
            'traceback': trace_str, 'code_line': code_line,
            'time': datetime.datetime.now().isoformat(), 'log_number': log_num,
        }
        path = f'/apps/logs/{app_name}_log{log_num}.json'
        self.fs.write_file(path, json.dumps(crash_data, indent=2, ensure_ascii=False))
        if self.debug:
            self.debug.log('app_crash', str(error), trace_str, app_name, code_line)
        return path, log_num

# ═══ SETTINGS / DEBUG LOGGER ═══
class SettingsManager:
    def __init__(self):
        self.time_mode = 'auto'
        self.time_offset = 0.0
        self.debug_mode = False

    def get_now(self):
        now = datetime.datetime.now()
        if self.time_mode == 'manual':
            return now + datetime.timedelta(seconds=self.time_offset)
        return now

    def set_manual_datetime(self, dt):
        self.time_offset = (dt - datetime.datetime.now()).total_seconds()
        self.time_mode = 'manual'

    def set_auto(self):
        self.time_mode = 'auto'
        self.time_offset = 0.0

    def to_dict(self):
        return {'time_mode': self.time_mode, 'time_offset': self.time_offset,
                'debug_mode': self.debug_mode}

    def from_dict(self, data):
        self.time_mode = data.get('time_mode', 'auto')
        self.time_offset = data.get('time_offset', 0.0)
        self.debug_mode = data.get('debug_mode', False)

class DebugLogger:
    def __init__(self, fs):
        self.fs = fs
        self.errors = []
        self._next_id = 1
        self._lock = threading.Lock()

    def log(self, error_type, message, traceback_str='', source='system', line=''):
        with self._lock:
            entry = {
                'id': self._next_id, 'type': error_type,
                'message': str(message)[:500],
                'traceback': str(traceback_str)[:2000],
                'source': source, 'line': str(line)[:200],
                'time': datetime.datetime.now().isoformat(),
            }
            self._next_id += 1
            self.errors.append(entry)
            if len(self.errors) > 200:
                self.errors = self.errors[-200:]
            self.save()
            return entry

    def save(self):
        try:
            self.fs.write_file('/sysdata/errors.json',
                               json.dumps(self.errors, indent=2, ensure_ascii=False))
            return True
        except Exception:
            return False

    def load(self):
        try:
            content = self.fs.read_file('/sysdata/errors.json')
            if content:
                self.errors = json.loads(content)
                if self.errors:
                    self._next_id = max(e.get('id', 0) for e in self.errors) + 1
                return True
        except Exception:
            pass
        self.errors = []
        return False

    def clear(self):
        with self._lock:
            self.errors = []
            self.save()

    def get_all(self):
        with self._lock:
            return list(self.errors)

    def get_recent(self, n=20):
        with self._lock:
            return self.errors[-n:]

    def count(self):
        with self._lock:
            return len(self.errors)

# ═══ X4 ═══
class X4IndentError(Exception):
    pass

class X4Parser:
    @staticmethod
    def parse(content):
        result = {'info': {}, 'code': '', 'data': {}, 'other': ''}
        m = re.search(r'\[INFO\](.*?)(?=\[CODE\]|\[DATA\]|\[OTHER\]|\[END\])', content, re.DOTALL)
        if m:
            for line in m.group(1).strip().split('\n'):
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    k, v = line.split(':', 1)
                    result['info'][k.strip().lower()] = v.strip()
        m = re.search(r'\[CODE\](.*?)\[/CODE\]', content, re.DOTALL)
        if m:
            result['code'] = m.group(1)
        m = re.search(r'\[DATA\](.*?)\[/DATA\]', content, re.DOTALL)
        if m:
            for line in m.group(1).strip().split('\n'):
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    k, v = line.split(':', 1)
                    result['data'][k.strip().lower()] = v.strip()
        m = re.search(r'\[OTHER\](.*?)(?=\[END\]|\Z)', content, re.DOTALL)
        if m:
            result['other'] = m.group(1).strip()
        return result

    @staticmethod
    def template(name, author):
        return f"""[INFO]
name: {name}
description: New application
version: 1.0.0
author: {author}
tag: tool
background: false

[CODE]
print("=== {name} ===")
name = input("Your name: ")
print("Hello, " + name + "!")
[/CODE]

[DATA]
folder: /apps/data/{name}
[/DATA]

[OTHER]
Free License -- BitSoft Studios
[/OTHER]

[END]"""

class X4Runtime:
    ALLOWED_BUILTINS = {
        'True': True, 'False': False, 'None': None,
        'int': int, 'str': str, 'float': float,
        'len': len, 'abs': abs, 'min': min, 'max': max,
        'round': round, 'bool': bool,
    }

    def __init__(self, shell, app_name='unknown'):
        self.shell = shell
        self.app_name = app_name
        now = shell.kernel.get_now()
        self.vars = {
            '__USER__': shell.user,
            '__TIME__': now.strftime('%H:%M:%S'),
            '__DATE__': now.strftime('%Y-%m-%d'),
            '__CWD__': shell.cwd,
            '__OS__': 'PyOS ' + shell.kernel.VERSION,
            '__VERSION__': shell.kernel.VERSION,
            '__APP__': app_name,
        }
        self.running = True
        self._current_line = ''

    @staticmethod
    def _extract_args(s, start_idx):
        depth = 1
        i = start_idx
        in_single = False
        in_double = False
        while i < len(s) and depth > 0:
            ch = s[i]
            if ch == '\\':
                i += 2
                continue
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == '(' and not in_single and not in_double:
                depth += 1
            elif ch == ')' and not in_single and not in_double:
                depth -= 1
                if depth == 0:
                    return s[start_idx:i], i
            i += 1
        return None, -1

    def execute(self, code):
        lines = code.split('\n')
        try:
            self._run_block(lines, 0, len(lines), 0)
        except KeyboardInterrupt:
            print("\n  [Interrupted]")
        except X4IndentError as e:
            self._handle_crash(e, str(e))
        except Exception as e:
            self._handle_crash(e, tb_module.format_exc())

    def _handle_crash(self, error, trace_str):
        print(C.c(f"  [Error] {error}", C.R))
        debug_logger = self.shell.kernel.debug if (
            self.shell.kernel.settings.debug_mode and self.shell.kernel.debug
        ) else None
        crasher = CrashLogger(self.shell.kernel.fs, debug_logger)
        path, num = crasher.log_crash(self.app_name, error, trace_str, self._current_line)
        print(C.c(f"  [Crash log saved: {path}]", C.Y))
        self.shell.kernel.notifications.send(
            source=self.app_name, title=f"Crash: {self.app_name}",
            message=str(error)[:50], icon='err', priority='high',
        )

    def _run_block(self, lines, start, end, bi):
        i = start
        while i < end and self.running:
            raw = lines[i]
            s = raw.strip()
            if not s or s.startswith('#'):
                i += 1
                continue
            indent = len(raw) - len(raw.lstrip())
            self._current_line = s
            if indent < bi:
                return
            if s.startswith('while ') and s.endswith(':'):
                cond = s[6:-1]
                bs = i + 1
                be = self._be(lines, i, indent, end)
                safety = 0
                while self.running and self._eb(cond) and safety < 10000:
                    self._run_block(lines, bs, be, indent + 4)
                    safety += 1
                i = be
                continue
            if s.startswith('for ') and ' in ' in s and s.endswith(':'):
                m = re.match(r'for\s+(\w+)\s+in\s+range\((.+)\)\s*:', s)
                if m:
                    vn = m.group(1)
                    bs = i + 1
                    be = self._be(lines, i, indent, end)
                    try:
                        args = [int(self._ev(x.strip())) for x in m.group(2).split(',')]
                        for val in range(*args):
                            if not self.running:
                                break
                            self.vars[vn] = val
                            self._run_block(lines, bs, be, indent + 4)
                    except (ValueError, TypeError) as e:
                        print(C.c(f"  [for error] {e}", C.R))
                    i = be
                    continue
                m2 = re.match(r'for\s+(\w+)\s+in\s+(\w+)\s*:', s)
                if m2:
                    vn = m2.group(1)
                    iterable = self.vars.get(m2.group(2), [])
                    bs = i + 1
                    be = self._be(lines, i, indent, end)
                    if isinstance(iterable, str):
                        iterable = list(iterable)
                    try:
                        for val in iterable:
                            if not self.running:
                                break
                            self.vars[vn] = val
                            self._run_block(lines, bs, be, indent + 4)
                    except TypeError:
                        print(C.c(f"  [for error] not iterable: {m2.group(2)}", C.R))
                    i = be
                    continue
            if s.startswith('if ') and s.endswith(':'):
                i = self._hif(lines, i, indent, end)
                continue
            self._exec_line(s)
            i += 1

    def _be(self, lines, start, bi, limit):
        i = start + 1
        while i < limit:
            s = lines[i].strip()
            if not s:
                i += 1
                continue
            if len(lines[i]) - len(lines[i].lstrip()) <= bi:
                return i
            i += 1
        return limit

    def _hif(self, lines, start, bi, limit):
        s = lines[start].strip()
        cond = s[3:-1]
        be = self._be(lines, start, bi, limit)
        branches = []
        bs = start + 1
        i = bs
        while i < be:
            ss = lines[i].strip()
            ci = len(lines[i]) - len(lines[i].lstrip()) if ss else 999
            if ci <= bi and (ss.startswith('elif ') or ss == 'else:'):
                break
            i += 1
        branches.append((cond, bs, i))
        while i < be:
            ss = lines[i].strip()
            ci = len(lines[i]) - len(lines[i].lstrip()) if ss else 999
            if ci <= bi:
                if ss.startswith('elif ') and ss.endswith(':'):
                    ec = ss[5:-1]
                    ebs = i + 1
                    j = ebs
                    while j < be:
                        sj = lines[j].strip()
                        cj = len(lines[j]) - len(lines[j].lstrip()) if sj else 999
                        if cj <= bi and (sj.startswith('elif ') or sj == 'else:'):
                            break
                        j += 1
                    branches.append((ec, ebs, j))
                    i = j
                    continue
                elif ss == 'else:':
                    branches.append((None, i + 1, be))
                    break
            i += 1
        for bc, bs2, be2 in branches:
            if bc is None or self._eb(bc):
                self._run_block(lines, bs2, be2, bi + 4)
                break
        return be

    def _eb(self, cond):
        try:
            safe = {"__builtins__": {}}
            safe.update(self.ALLOWED_BUILTINS)
            safe.update(self.vars)
            return bool(eval(cond, safe))
        except Exception:
            return False

    def _ev(self, expr):
        try:
            safe = {"__builtins__": {}}
            safe.update(self.ALLOWED_BUILTINS)
            safe.update(self.vars)
            return eval(expr, safe)
        except Exception:
            return expr

    def _es(self, expr):
        safe = {"__builtins__": {}}
        safe.update(self.ALLOWED_BUILTINS)
        safe.update(self.vars)
        try:
            return eval(expr, safe)
        except Exception:
            return expr

    def _exec_frame(self, line):
        # Вместо сложных рамок выводим текст как есть
        m = re.match(r'frame_(\w+)\((.*)\)', line)
        if m:
            func = m.group(1)
            args = m.group(2)
            print(f"  [{func}] {args}")
            return
        print(f"  [Unknown frame: {line}]")

    def _exec_line(self, line):
        if not self.running:
            return
        self._current_line = line

        if line.startswith('frame_'):
            self._exec_frame(line)
            return

        m = re.match(r'launch\((.+),\s*(.+)\)$', line)
        if m:
            self._do_launch(str(self._es(m.group(1))), str(self._es(m.group(2))))
            return
        m = re.match(r'launch\((.+)\)$', line)
        if m:
            self._do_launch(str(self._es(m.group(1))))
            return

        m = re.match(r'notify\((.+),\s*(.+)\)$', line)
        if m:
            try:
                self.shell.kernel.notifications.send(
                    source=self.app_name, title=str(self._es(m.group(1))),
                    message=str(self._es(m.group(2))), icon='app', priority='normal')
            except Exception as e:
                print(C.c(f"  [notify error] {e}", C.R))
            return

        m = re.match(r'notify_high\((.+),\s*(.+)\)$', line)
        if m:
            try:
                self.shell.kernel.notifications.send(
                    source=self.app_name, title=str(self._es(m.group(1))),
                    message=str(self._es(m.group(2))), icon='app', priority='high')
            except Exception as e:
                print(C.c(f"  [notify error] {e}", C.R))
            return

        if line == 'background()':
            self.shell.kernel.app_bg.register(self.app_name)
            return

        m = re.match(r'print\((.+)\)$', line)
        if m:
            try:
                print(f"  {self._es(m.group(1))}")
            except Exception as e:
                print(f"  {e}")
            return

        m = re.match(r'color\((.+),\s*["\'](\w+)["\']\)$', line)
        if m:
            try:
                cols = {'red': C.R, 'green': C.G, 'yellow': C.Y, 'blue': C.BL,
                        'cyan': C.CY, 'magenta': C.M, 'white': C.W, 'bold': C.B}
                print(f"  {C.c(str(self._es(m.group(1))), cols.get(m.group(2).lower(), C.W))}")
            except Exception:
                pass
            return

        m = re.match(r'(\w+)\s*=\s*input\((.+)\)$', line)
        if m:
            try:
                self.vars[m.group(1)] = input(f"  {self._es(m.group(2))}")
            except (EOFError, KeyboardInterrupt):
                self.running = False
            return

        m = re.match(r'(\w+)\s*=\s*calc\((.+)\)$', line)
        if m:
            er = m.group(2).strip()
            es = er[1:-1] if (er.startswith('"') and er.endswith('"')) or \
                             (er.startswith("'") and er.endswith("'")) else str(self.vars.get(er, er))
            try:
                al = {'__builtins__': {}, 'abs': abs, 'round': round, 'min': min, 'max': max,
                      'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
                      'log': math.log, 'log10': math.log10, 'log2': math.log2,
                      'pi': math.pi, 'e': math.e, 'pow': pow, 'ceil': math.ceil,
                      'floor': math.floor, 'factorial': math.factorial, 'int': int, 'float': float}
                self.vars[m.group(1)] = eval(es, al)
            except Exception:
                self.vars[m.group(1)] = "ERROR"
            return

        m = re.match(r'(\w+)\s*=\s*random\((.+),\s*(.+)\)$', line)
        if m:
            try:
                self.vars[m.group(1)] = random.randint(int(self._ev(m.group(2))), int(self._ev(m.group(3))))
            except (ValueError, TypeError):
                self.vars[m.group(1)] = 0
            return

        m = re.match(r'(\w+)\s*=\s*int\((.+)\)$', line)
        if m:
            try: self.vars[m.group(1)] = int(self._es(m.group(2)))
            except (ValueError, TypeError): self.vars[m.group(1)] = 0
            return

        m = re.match(r'(\w+)\s*=\s*str\((.+)\)$', line)
        if m:
            self.vars[m.group(1)] = str(self._es(m.group(2)))
            return

        m = re.match(r'(\w+)\s*=\s*len\((.+)\)$', line)
        if m:
            try: self.vars[m.group(1)] = len(self._es(m.group(2)))
            except (TypeError, AttributeError): self.vars[m.group(1)] = 0
            return

        m = re.match(r'fwrite\((.+),\s*(.+)\)$', line)
        if m:
            self.shell.kernel.fs.write_file(str(self._es(m.group(1))), str(self._es(m.group(2))), self.shell.cwd)
            return
        m = re.match(r'fappend\((.+),\s*(.+)\)$', line)
        if m:
            self.shell.kernel.fs.write_file(str(self._es(m.group(1))), str(self._es(m.group(2))), self.shell.cwd, append=True)
            return
        m = re.match(r'(\w+)\s*=\s*fread\((.+)\)$', line)
        if m:
            self.vars[m.group(1)] = self.shell.kernel.fs.read_file(str(self._es(m.group(2))), self.shell.cwd) or ''
            return
        m = re.match(r'(\w+)\s*=\s*fexists\((.+)\)$', line)
        if m:
            self.vars[m.group(1)] = self.shell.kernel.fs.exists(str(self._es(m.group(2))), self.shell.cwd)
            return
        m = re.match(r'fdelete\((.+)\)$', line)
        if m:
            self.shell.kernel.fs.delete(str(self._es(m.group(1))), self.shell.cwd)
            return
        m = re.match(r'fmkdir\((.+)\)$', line)
        if m:
            self.shell.kernel.fs.mkdir(str(self._es(m.group(1))), self.shell.cwd)
            return
        m = re.match(r'(\w+)\s*=\s*flist\((.+)\)$', line)
        if m:
            items = self.shell.kernel.fs.list_dir(str(self._es(m.group(2))), self.shell.cwd)
            self.vars[m.group(1)] = [i['name'] for i in items] if items else []
            return

        m = re.match(r'sleep\((.+)\)$', line)
        if m:
            try: time.sleep(float(self._ev(m.group(1))))
            except (ValueError, TypeError): pass
            return

        if line == 'clear()':
            clear()
            return
        if line == 'exit()':
            self.running = False
            return
        if line == 'sysinfo()':
            now = self.shell.kernel.get_now()
            print(f"  OS: {self.vars['__OS__']} | User: {self.shell.user} | "
                  f"Session: {self.shell.kernel.guardian.session_str()} | "
                  f"Time: {now.strftime('%H:%M:%S')}")
            return

        m = re.match(r'(\w+)\s*=\s*(.+)$', line)
        if m:
            var = m.group(1)
            if var not in ('if', 'while', 'for', 'else', 'elif', 'print', 'color'):
                try: self.vars[var] = self._es(m.group(2))
                except Exception: self.vars[var] = m.group(2)

    def _do_launch(self, script_path, file_arg=None):
        import subprocess as _sp
        try:
            rp, _ = self.shell.kernel.fs._real_path(script_path, self.shell.cwd)
            if not rp.exists():
                print(C.c(f"  [launch] not found: {script_path}", C.R))
                return
            if not str(rp).endswith('.py'):
                print(C.c(f"  [launch] not a .py file: {rp.name}", C.R))
                return

            cmd = [sys.executable, str(rp)]
            if file_arg:
                frp, _ = self.shell.kernel.fs._real_path(file_arg, self.shell.cwd)
                cmd.append(str(frp) if frp.exists() else file_arg)

            proc = _sp.Popen(cmd, stdout=_sp.DEVNULL, stderr=_sp.PIPE)
            def read_stderr():
                try:
                    _ = proc.stderr.read()
                except:
                    pass
            t = threading.Thread(target=read_stderr, daemon=True)
            t.start()
            time.sleep(0.8)
            if proc.poll() is not None:
                t.join(timeout=1)
                err = proc.stderr.read().decode('utf-8', errors='replace')
                print(C.c(f"  [launch] crashed!", C.R))
                if err:
                    for el in err.strip().split('\n')[:5]:
                        print(C.c(f"    {el}", C.R))
            else:
                print(C.c(f"  [launch] started PID {proc.pid}", C.G))
                self.shell.kernel.notifications.send(
                    source=self.app_name, title='Script launched',
                    message=f'{rp.name} PID {proc.pid}', icon='app', priority='low')
        except Exception as e:
            print(C.c(f"  [launch] error: {e}", C.R))

# ═══ APP MANAGER ═══
class AppManager:
    def __init__(self, fs, guardian, notifications=None, app_bg=None):
        self.fs = fs
        self.apps = {}
        self.guardian = guardian
        self.notifications = notifications
        self.app_bg = app_bg

    def load_installed(self):
        items = self.fs.list_dir('/apps/installed')
        if not items:
            return
        for item in items:
            if item['name'].endswith('.x4') and not item['is_dir']:
                content = self.fs.read_file('/apps/installed/' + item['name'])
                if content:
                    p = X4Parser.parse(content)
                    self.apps[p['info'].get('name', item['name'][:-3])] = p

    def install_builtins(self):
        for name, content in self._builtins().items():
            self.fs.write_file(f'/apps/installed/{name}.x4', content)
            p = X4Parser.parse(content)
            an = p['info'].get('name', name)
            self.apps[an] = p
            self.fs.mkdir(p['data'].get('folder', f'/apps/data/{an}'))

    def install(self, filename, cwd='/', home_dir=None):
        content = self.fs.read_file(filename, cwd)
        if not content and home_dir:
            content = self.fs.read_file(f"{home_dir}/Documents/{filename}")
        if not content:
            content = self.fs.read_file(f'/apps/store/{filename}')
        if not content:
            return False, f"'{filename}' not found"
        p = X4Parser.parse(content)
        name = p['info'].get('name', '')
        if not name:
            return False, "No valid name in [INFO]"
        if not p['code']:
            return False, "No [CODE] section"
        self.fs.write_file(f'/apps/installed/{name}.x4', content)
        df = p['data'].get('folder', f'/apps/data/{name}')
        self.fs.mkdir(df)
        self.apps[name] = p
        if self.notifications:
            self.notifications.send(
                source='system', title=f"App installed: {name}",
                message=f"v{p['info'].get('version', '?')} by {p['info'].get('author', '?')}",
                icon='ok', priority='normal')
        return True, f"'{name}' v{p['info'].get('version', '?')} installed!"

    def run(self, name, shell):
        if name not in self.apps:
            return False, f"'{name}' not found"
        app = self.apps[name]
        info = app['info']
        print(C.c(f"  [{info.get('name', name)} v{info.get('version', '?')}]", C.DIM))
        if info.get('background', '').lower() == 'true' and self.app_bg:
            self.app_bg.register(name, info)
        X4Runtime(shell, app_name=name).execute(app['code'])
        deleted = self.guardian.cleanup_app_folder(self.fs, name)
        if deleted:
            print(C.c(f"  [Guardian] '{name}' data cleaned:", C.Y))
            for fname, fsize in deleted:
                print(C.c(f"    Deleted: {fname} ({self.guardian.fmt_size(fsize)})", C.Y))
        print()
        print(C.c("  The application has shut down.", C.DIM))
        time.sleep(3)
        return True, ""

    def remove(self, name):
        if name not in self.apps:
            return False
        del self.apps[name]
        self.fs.delete(f'/apps/installed/{name}.x4')
        self.fs.delete(f'/apps/data/{name}', recursive=True)
        if self.app_bg:
            self.app_bg.unregister(name)
        if self.notifications:
            self.notifications.delete_by_source(name)
            self.notifications.send(source='system', title=f"App removed: {name}",
                                    message='', icon='info', priority='low')
        return True

    def get_info(self, name):
        return self.apps.get(name, {}).get('info', {})

    def get_other(self, name):
        return self.apps.get(name, {}).get('other', '')

    def _builtins(self):
        # Встроенные приложения переписаны без frame_ команд, используют SimpleBox или print
        return {
'hello': """[INFO]
name: hello
description: Hello World demo
version: 2.1.0
author: BitSoft Studios
tag: demo
background: false
[CODE]
print("=== Hello World ===")
print("")
print("Hello, " + __USER__ + "!")
print("Welcome to " + __OS__)
print("")
print("Time: " + __TIME__)
print("Date: " + __DATE__)
print("Version: " + __VERSION__)
print("")
color("Have a great day, " + __USER__ + "!", "green")
notify("Hello App", "Was launched by " + __USER__)
[/CODE]
[DATA]
folder: /apps/data/hello
[/DATA]
[OTHER]
Free License -- BitSoft Studios
[/OTHER]
[END]""",
'guess': """[INFO]
name: guess
description: Number guessing game
version: 1.2.0
author: BitSoft Studios
tag: game
background: true
[CODE]
print("=== Guess The Number ===")
target = random(1, 100)
attempts = 0
print("I picked 1-100...")
playing = 1
while playing == 1:
    g = input("Guess (quit to stop): ")
    if g == "quit":
        print("It was " + str(target))
        playing = 0
    if g != "quit":
        guess = int(g)
        attempts = attempts + 1
        if guess < target:
            print("Higher!")
        if guess > target:
            print("Lower!")
        if guess == target:
            color("Correct! " + str(attempts) + " tries!", "green")
            notify("Guess Game", __USER__ + " won in " + str(attempts) + " tries!")
            playing = 0
[/CODE]
[DATA]
folder: /apps/data/guess
[/DATA]
[OTHER]
Free License -- BitSoft Studios
[/OTHER]
[END]""",
'notes': """[INFO]
name: notes
description: Simple note manager
version: 4.0.0
author: BitSoft Studios
tag: tool
background: true
[CODE]
print("=== Notes v4.0 ===")
notes_dir = "/apps/data/notes"
running = 1
while running == 1:
    print("")
    print("-- Notes Menu --")
    print("1. Write new note")
    print("2. View note by name")
    print("3. List all notes")
    print("4. Delete note")
    print("5. Quit")
    print("----------------")
    choice = input("Choose (1-5): ")
    if choice == "1":
        name = input("Note name: ")
        if name != "":
            text = input("Note text: ")
            if text != "":
                fwrite(notes_dir + "/" + name + ".txt", text)
                color("Saved: " + name, "green")
                notify("Notes", "Saved note: " + name)
            if text == "":
                color("Empty text, not saved.", "yellow")
        if name == "":
            color("No name given.", "yellow")
    if choice == "2":
        name = input("Note name: ")
        if name != "":
            data = fread(notes_dir + "/" + name + ".txt")
            if data == "":
                print("Note not found: " + name)
            if data != "":
                print("-- " + name + " --")
                print(data)
                print("----------------")
    if choice == "3":
        files = flist(notes_dir)
        if len(files) == 0:
            print("No notes yet.")
        if len(files) > 0:
            print("Your notes:")
            for f in files:
                print("  - " + str(f))
    if choice == "4":
        name = input("Note name to delete: ")
        if name != "":
            exists = fexists(notes_dir + "/" + name + ".txt")
            if exists == True:
                fdelete(notes_dir + "/" + name + ".txt")
                color("Deleted: " + name, "red")
            if exists == False:
                color("Not found: " + name, "yellow")
    if choice == "5":
        running = 0
        print("Goodbye!")
[/CODE]
[DATA]
folder: /apps/data/notes
[/DATA]
[OTHER]
Free License -- BitSoft Studios
[/OTHER]
[END]""",
'rps': """[INFO]
name: rps
description: Rock Paper Scissors
version: 1.2.0
author: BitSoft Studios
tag: game
background: true
[CODE]
print("=== Rock Paper Scissors ===")
w = 0
l = 0
d = 0
playing = 1
while playing == 1:
    pick = input("rock/paper/scissors/quit: ")
    if pick == "quit":
        playing = 0
        notify_high("RPS", "Final: W:" + str(w) + " L:" + str(l) + " D:" + str(d))
    if pick != "quit":
        cpu = random(1, 3)
        if pick == "rock":
            if cpu == 1:
                print("PC: rock - Draw!")
                d = d + 1
            if cpu == 2:
                print("PC: paper - You lose!")
                l = l + 1
            if cpu == 3:
                print("PC: scissors - You win!")
                w = w + 1
        if pick == "paper":
            if cpu == 1:
                print("PC: rock - You win!")
                w = w + 1
            if cpu == 2:
                print("PC: paper - Draw!")
                d = d + 1
            if cpu == 3:
                print("PC: scissors - You lose!")
                l = l + 1
        if pick == "scissors":
            if cpu == 1:
                print("PC: rock - You lose!")
                l = l + 1
            if cpu == 2:
                print("PC: paper - You win!")
                w = w + 1
            if cpu == 3:
                print("PC: scissors - Draw!")
                d = d + 1
        print("W:" + str(w) + " L:" + str(l) + " D:" + str(d))
[/CODE]
[DATA]
folder: /apps/data/rps
[/DATA]
[OTHER]
Free License -- BitSoft Studios
[/OTHER]
[END]"""
        }

# ═══ HISTORY MANAGER ═══
class HistoryManager:
    def __init__(self, fs, max_size=500):
        self.fs = fs
        self.entries = []
        self.max_size = max_size

    def add(self, command):
        self.entries.append({'cmd': command, 'time': datetime.datetime.now().isoformat()})
        if len(self.entries) > self.max_size:
            self.entries = self.entries[-self.max_size:]
        self.save()

    def get_all(self):
        return list(self.entries)

    def search(self, pattern):
        return [e for e in self.entries if pattern.lower() in e['cmd'].lower()]

    def clear(self):
        self.entries = []
        self.save()

    def save(self):
        try:
            self.fs.write_file('/sysdata/history.json',
                               json.dumps(self.entries, indent=2, ensure_ascii=False))
            return True
        except Exception:
            return False

    def load(self):
        try:
            content = self.fs.read_file('/sysdata/history.json')
            if content:
                self.entries = json.loads(content)[-self.max_size:]
                return True
        except Exception:
            pass
        self.entries = []
        return False

# ═══ ЯДРО ═══
class Kernel:
    VERSION = '16.2'
    BUILD = '27.07.2026'
    COMPANY = 'BitSoft Studios'

    def __init__(self):
        self.boot_time = datetime.datetime.now()
        self.fs = None
        self.um = UserManager()
        self.guardian = Guardian()
        self.apps = None
        self.running = True
        self.first_boot = True
        self.hostname = 'pyos'
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.history = None
        self._marker = Path(self.base_path) / '.pyos_host'
        self.notifications = NotificationCenter()
        self.timer_service = TimerService(self.notifications)
        self.app_bg = AppBackgroundManager(self.notifications)
        self.settings = SettingsManager()
        self.debug = None
        self._fs_checker = None
        self._bsod_pending = False
        self._bsod_lock = threading.Lock()
        self._bsod_error_code = ''
        self._bsod_message = ''
        self._bsod_details = ''

    def get_now(self):
        return self.settings.get_now()

    def _save_path(self):
        return Path(self.base_path) / self.hostname / 'C' / 'sysdata' / 'pyos_state.json'

    def _load_hostname(self):
        try:
            if self._marker.exists():
                self.hostname = self._marker.read_text(encoding='utf-8').strip()
                return True
        except (OSError, PermissionError):
            pass
        return False

    def _save_hostname(self):
        try:
            self._marker.write_text(self.hostname, encoding='utf-8')
        except (OSError, PermissionError):
            pass

    def _trigger_bsod(self, error_code, message, details=''):
        with self._bsod_lock:
            if self._bsod_pending:
                return
            self._bsod_pending = True
            self._bsod_error_code = error_code
            self._bsod_message = message
            self._bsod_details = details
        self.running = False

    def _restart_after_bsod(self):
        self.running = False
        self.first_boot = True
        self.fs = None
        self.apps = None
        self.history = None
        self.debug = None
        self.um = UserManager()
        self.guardian = Guardian()
        self.notifications = NotificationCenter()
        self.timer_service = TimerService(self.notifications)
        self.app_bg = AppBackgroundManager(self.notifications)
        self.settings = SettingsManager()
        self.boot_time = datetime.datetime.now()
        self.guardian.session_start = datetime.datetime.now()
        try:
            if self._marker.exists():
                self._marker.unlink()
        except (OSError, PermissionError):
            pass

    def boot(self):
        clear()
        self._boot_anim()
        self._load_hostname()
        loaded = self._load()
        if loaded:
            self.first_boot = False
            self.fs = RealFS(self.base_path)
            self.fs.hostname_dir = Path(self.base_path) / self.hostname
            self.fs.current_disk = 'C'
            self.debug = DebugLogger(self.fs)
            self.debug.load()
            self.apps = AppManager(self.fs, self.guardian, self.notifications, self.app_bg)
            self.apps.load_installed()
            self.history = HistoryManager(self.fs)
            self.history.load()
            self.fs.mkdir('/apps/logs')
            if self.timer_service.get_active():
                self.timer_service.start()
            self._fs_checker = FSHealthChecker(self.fs, self)
            self._fs_checker.start()
        else:
            self.first_boot = True

    def _boot_anim(self):
        logo = [
            "  PyOS v" + self.VERSION,
            "  build " + self.BUILD,
            "  " + self.COMPANY,
        ]
        print(SimpleBox.box('\n'.join(logo), 44, '='))
        print()

        stages = [
            "Kernel", "Filesystem", "Settings", "Guardian",
            "Debug Logger", "Notifications",
            "Timer Service", "History", "Apps"
        ]
        total = len(stages)
        bar_width = 24

        for i, stage in enumerate(stages, 1):
            ratio = i / total
            filled = int(bar_width * ratio)
            bar = '#' * filled + '.' * (bar_width - filled)
            pct = int(ratio * 100)
            status = f"[{bar}] {pct:3d}% {stage}..."
            pad = ' ' * 10
            print(f"\r  {C.c(status, C.G)}{pad}", end='', flush=True)
            time.sleep(0.12)

        final_bar = '#' * bar_width
        final_status = f"[{final_bar}] 100%"
        final = f"\r  {C.c(final_status, C.G)} {C.c('Ready!', C.G + C.B)}          "
        print(final)
        print()

    def setup(self):
        print(SimpleBox.header(f"PyOS {self.VERSION} build {self.BUILD}", 44))
        print("  First Time Setup")
        print("=" * 44)
        print()
        auto = input("  Enable auto setup? (yes/no): ").strip().lower()
        if auto in ('yes', 'y'):
            self._auto_setup()
            return
        self._manual_setup()

    def _auto_setup(self):
        print(C.c("\n  [Auto Setup] Configuring...", C.CY))
        self.hostname = 'Computer'
        self._save_hostname()
        print(C.c(f"  -> Computer name: {self.hostname}", C.G))
        self.fs = RealFS(self.base_path)
        self.fs.init_structure(self.hostname)
        self.debug = DebugLogger(self.fs)
        print(C.c("  -> Disk C: created", C.G))
        un = 'User'
        self.um.create(un, None, '')
        print(C.c(f"  -> User: {un} (no password)", C.G))
        for d in [f'/home/{un}', f'/home/{un}/Desktop', f'/home/{un}/Documents']:
            self.fs.mkdir(d)
        self.guardian.set_app_folder_limit(1024 * 1024)
        print(C.c("  -> Time limit: none", C.G))
        print(C.c("  -> App limit: 1024 KB/app", C.G))
        self.apps = AppManager(self.fs, self.guardian, self.notifications, self.app_bg)
        self.apps.install_builtins()
        self.history = HistoryManager(self.fs)
        self._fs_checker = FSHealthChecker(self.fs, self)
        self._fs_checker.start()
        print(C.c(f"\n  Auto setup complete! {len(self.apps.apps)} apps installed.", C.G))
        print(C.c(f"  {self.COMPANY} -- PyOS {self.VERSION}\n", C.CY))
        self._save()

    def _manual_setup(self):
        self.hostname = input("  Computer name [pyos]: ").strip() or 'pyos'
        print(C.c(f"  -> {self.hostname}", C.G))
        self._save_hostname()
        self.fs = RealFS(self.base_path)
        self.fs.init_structure(self.hostname)
        self.debug = DebugLogger(self.fs)
        print(C.c("  -> Disk C: created", C.G))
        print("\n  Your account:")
        while True:
            un = input("  Username: ").strip()
            if un and un.isalnum():
                break
            print(C.c("  Alphanumeric only!", C.R))
        print()
        add_pw = input("  Add a password? (y/n): ").strip().lower()
        up = None
        if add_pw == 'y':
            while True:
                up = input("  Password: ").strip()
                if len(up) < 2:
                    print(C.c("  Too short (min 2)", C.R))
                    continue
                if input("  Confirm: ").strip() != up:
                    print(C.c("  Mismatch", C.R))
                    continue
                break
            print(C.c("  -> Password set (salted SHA-256)", C.G))
            uh = ''
            if input("  Add a hint? (y/n): ").strip().lower() == 'y':
                uh = input("  Hint: ").strip()
            self.um.create(un, up, uh)
        else:
            print(C.c("  -> No password (open access)", C.Y))
            self.um.create(un, None, '')
        for d in [f'/home/{un}', f'/home/{un}/Desktop', f'/home/{un}/Documents']:
            self.fs.mkdir(d)
        lim = input("\n  Daily time limit (minutes, empty=none): ").strip()
        if lim.isdigit() and int(lim) > 0:
            self.guardian.set_limit(int(lim))
        alim = input("  App limit per app (KB, default 1024): ").strip()
        if alim.isdigit() and int(alim) > 0:
            self.guardian.set_app_folder_limit(int(alim) * 1024)
        self.apps = AppManager(self.fs, self.guardian, self.notifications, self.app_bg)
        self.apps.install_builtins()
        self.history = HistoryManager(self.fs)
        self._fs_checker = FSHealthChecker(self.fs, self)
        self._fs_checker.start()
        print(C.c(f"\n  Setup complete! {len(self.apps.apps)} apps installed.", C.G))
        print(C.c(f"  {self.COMPANY} -- PyOS {self.VERSION}\n", C.CY))
        self._save()

    def _save(self):
        try:
            state = {
                'hostname': self.hostname, 'base_path': self.base_path,
                'version': self.VERSION, 'build': self.BUILD, 'company': self.COMPANY,
                'users': {'users': self.um.users},
                'guardian': {
                    'daily_limit': self.guardian.daily_limit,
                    'app_folder_limit': self.guardian.app_folder_limit,
                    'suggest_commands': self.guardian.suggest_commands,
                },
                'settings': self.settings.to_dict(),
                'notifications': self.notifications.to_dict(),
                'timers': self.timer_service.to_dict(),
                'background_apps': self.app_bg.to_dict(),
            }
            sp = self._save_path()
            sp.parent.mkdir(parents=True, exist_ok=True)
            with open(sp, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            self._save_hostname()
            if self.history:
                self.history.save()
            if self.debug:
                self.debug.save()
            return True
        except (OSError, PermissionError) as e:
            print(C.c(f"  [Save error] {e}", C.R))
            return False

    def _load(self):
        sp = self._save_path()
        if not sp.exists():
            return False
        try:
            with open(sp, 'r', encoding='utf-8') as f:
                st = json.load(f)
            self._apply_state(st)
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def _apply_state(self, st):
        self.hostname = st.get('hostname', 'pyos')
        self.base_path = st.get('base_path', self.base_path)
        self.um.users = st.get('users', {}).get('users', {})
        gd = st.get('guardian', {})
        self.guardian.daily_limit = gd.get('daily_limit')
        self.guardian.app_folder_limit = gd.get('app_folder_limit', 1048576)
        self.guardian.suggest_commands = gd.get('suggest_commands', True)
        if 'settings' in st:
            self.settings.from_dict(st['settings'])
        if 'notifications' in st:
            self.notifications.from_dict(st['notifications'])
        if 'timers' in st:
            self.timer_service.from_dict(st['timers'])
        if 'background_apps' in st:
            self.app_bg.from_dict(st['background_apps'])

    def shutdown(self):
        print(C.c(f"\n  Session: {self.guardian.session_str()}", C.CY))
        if self._fs_checker:
            self._fs_checker.stop()
        self.timer_service.stop()
        self._save()
        print(C.c(f"  {self.COMPANY} -- PyOS {self.VERSION}", C.DIM))
        print(C.c("  Goodbye!\n", C.G))
        self.running = False

    def check_fs_health(self):
        if self.fs and self.fs.hostname_dir:
            if not self.fs.hostname_dir.exists():
                self._trigger_bsod('CRITICAL_DATA_DESTROYED',
                                   'System data folder has been deleted.',
                                   f'Missing: {self.fs.hostname_dir}')
                return False
        return True

# ═══ ОБОЛОЧКА ═══
class Shell:
    ALL_COMMANDS = [
        'help', 'ls', 'cd', 'pwd', 'mkdir', 'rmdir', 'touch', 'rm', 'cat',
        'echo', 'cp', 'mv', 'rename', 'find', 'grep', 'wc', 'tree', 'du',
        'df', 'clear', 'desktop', 'whoami', 'id', 'su', 'useradd', 'userdel',
        'passwd', 'users', 'date', 'uptime', 'hostname', 'neofetch', 'history',
        'alias', 'export', 'env', 'edit', 'nano', 'guardian', 'app',
        'store', 'newapp', 'disk', 'man', 'realpath', 'shutdown', 'reboot',
        'exit', 'logout', 'save', 'suggest', 'logs', 'notif', 'reload',
        'timer', 'settings', 'debug',
    ]

    def __init__(self, kernel):
        self.kernel = kernel
        self.cwd = '/'
        self.user = None
        self.env = {'PATH': '/bin', 'HOME': '/', 'SHELL': '/bin/pysh'}
        self.aliases = {'ll': 'ls -l', 'la': 'ls -a', 'cls': 'clear',
                        '..': 'cd ..', 'q': 'exit'}
        self._oldpwd = {'path': self.cwd, 'disk': self.kernel.fs.current_disk if self.kernel.fs else 'C'}

    def _docs(self):
        return f'/home/{self.user}/Documents'

    def desktop(self):
        clear()
        if not self.kernel.check_fs_health():
            return
        now = self.kernel.get_now()
        g = self.kernel.guardian
        hn = self.kernel.hostname
        dk = self.kernel.fs.current_disk
        disks = self.kernel.fs.get_disks()
        usage = self.kernel.fs.disk_usage(dk)
        lim = f"{g.daily_limit} min" if g.daily_limit else "No limit"
        sug = "ON" if g.suggest_commands else "OFF"
        has_pw = "Yes" if self.kernel.um.has_password(self.user) else "No"
        notif_badge = self.kernel.notifications.format_badge()
        active_timers = len(self.kernel.timer_service.get_active())
        bg_apps = len(self.kernel.app_bg.get_all())
        debug_on = self.kernel.settings.debug_mode

        print("=" * 52)
        print(f"  PyOS v{Kernel.VERSION} build {Kernel.BUILD} -- {hn}")
        print("=" * 52)
        print(f"  User:          {C.c(self.user, C.G)}")
        print(f"  Password:      {has_pw}")
        print(f"  Date:          {now.strftime('%A, %d %B %Y')}")
        print(f"  Time:          {now.strftime('%H:%M:%S')}")
        print(f"  Session:       {g.session_str()}")
        print(f"  Time limit:    {lim}")
        print("-" * 52)
        print(f"  Disks:         {' '.join(d + ':' for d in disks)}")
        print(f"  Current:       {dk}:")
        print(f"  Disk used:     {g.fmt_size(usage)}")
        print(f"  Apps:          {len(self.kernel.apps.apps) if self.kernel.apps else '0'}")
        print(f"  App limit:     {g.fmt_size(g.app_folder_limit)}/app")
        print(f"  Suggest:       {sug}")
        if debug_on:
            err_count = self.kernel.debug.count() if self.kernel.debug else 0
            print(f"  Debug:         {C.c('ON', C.Y)} ({err_count} errors)")
        print("-" * 52)
        status_parts = [f"Notif: {notif_badge}"]
        if active_timers > 0:
            status_parts.append(C.c(f"Timers: {active_timers}", C.CY))
        if bg_apps > 0:
            status_parts.append(C.c(f"Bg: {bg_apps}", C.M))
        if debug_on:
            status_parts.append(C.c("DBG", C.Y))
        print('  ' + ' | '.join(status_parts))
        print("-" * 52)
        print("  help -- commands | app list -- apps")
        print("  notif -- notifications | timer -- timers")
        print("  settings -- configure")
        print("  guardian -- monitor")
        print(C.c(f"  {Kernel.COMPANY}", C.DIM))
        print("=" * 52)
        print()
        panel = self.kernel.notifications.format_panel(max_show=4)
        if panel:
            print(panel)
            print()

    def _guardian_screen(self):
        clear()
        g = self.kernel.guardian
        report = g.disk_report(self.kernel.fs)
        lim = f"{g.daily_limit} min" if g.daily_limit else "No limit"
        now = self.kernel.get_now()
        app_checks = g.check_all_apps(self.kernel.fs)
        print("=" * 52)
        print("  Guardian -- System Monitor")
        print("=" * 52)
        print(f"  Date:          {now.strftime('%Y-%m-%d')}")
        print(f"  Time:          {now.strftime('%H:%M:%S')}")
        print(f"  Session:       {g.session_str()}")
        print(f"  Time limit:    {lim}")
        print("-" * 52)
        print(f"  Disk used:     {g.fmt_size(report['total'])}")
        print(f"  Files:         {report['count']}")
        print(f"  App limit:     {g.fmt_size(g.app_folder_limit)}/app")
        if app_checks:
            print("-" * 52)
            print("  App Data Folders:")
            for ac in app_checks:
                status = C.c("OVER!", C.R) if ac['over'] else C.c("OK", C.G)
                print(f"    {ac['name']:<15} {g.fmt_size(ac['size']):>8} {status}")
        if report['largest']:
            print("-" * 52)
            print("  Largest Files:")
            for fi in report['largest'][:5]:
                print(f"    {g.fmt_size(fi['size']):>10}  {fi['name'][:28]}")
        print("-" * 52)
        print("  cleanup | limit | applimit | appclean")
        print("  suggest on|off | logs | q")
        print("=" * 52)
        print()

    def login(self):
        users = self.kernel.um.list_users()
        if users:
            print("=" * 44)
            print("  Select User")
            print("=" * 44)
            for u in users:
                info = self.kernel.um.get_public_info(u)
                has_pw = "[pw]" if info.get('has_password', True) else "[open]"
                disk = info.get('disk', 'C')
                print(f"  {has_pw} {u:<16} disk={disk}:")
            print("-" * 44)
            print("  Enter username below")
            print("=" * 44)
            print()
        fail = {}
        while True:
            try:
                un = input(C.c("  login: ", C.W))
                if not un:
                    continue
            except (EOFError, KeyboardInterrupt):
                self.kernel.shutdown()
                return False
            if un not in self.kernel.um.users:
                print(C.c("  User not found.", C.R))
                print()
                continue
            if not self.kernel.um.has_password(un):
                self._do_login(un)
                return True
            try:
                pw = input(C.c("  password: ", C.W))
            except (EOFError, KeyboardInterrupt):
                self.kernel.shutdown()
                return False
            if self.kernel.um.auth(un, pw):
                self._do_login(un)
                return True
            fail[un] = fail.get(un, 0) + 1
            print(C.c("  Incorrect.", C.R))
            if fail.get(un, 0) >= 3:
                print(C.c("  Too many attempts!", C.Y))
                if input("  Forgot password? (y/n): ").strip().lower() == 'y':
                    hint = self.kernel.um.get_hint(un)
                    print(C.c(f"  Hint: {hint}", C.CY) if hint else C.c("  No hint set.", C.R))
                    fail[un] = 0
            print()

    def _do_login(self, un):
        self.user = un
        info = self.kernel.um.users[un]
        self.kernel.fs.current_disk = info.get('disk', 'C')
        self.env['HOME'] = info['home']
        self.env['USER'] = un
        self.cwd = info['home']
        self.kernel.fs.mkdir(self.cwd)
        self._oldpwd = {'path': self.cwd, 'disk': self.kernel.fs.current_disk}
        self.desktop()

    def _prompt(self):
        w = self.cwd
        home = self.env.get('HOME', '/')
        if w.startswith(home) and home != '/':
            w = '~' + w[len(home):]
        dk = self.kernel.fs.current_disk
        unread = self.kernel.notifications.count_unread()
        badge = C.c(f"[{unread}] ", C.Y) if unread > 0 else ''
        dbg = C.c("[DBG] ", C.Y) if self.kernel.settings.debug_mode else ''
        return (f"{badge}{dbg}{C.c(dk + ':', C.Y)}{C.c(self.user, C.G)}@"
                f"{C.c(self.kernel.hostname, C.BL)}:{C.c(w, C.CY)}$ ")

    def run(self):
        while self.kernel.running:
            if not self.kernel.check_fs_health():
                return
            w = self.kernel.guardian.check_limit()
            if w:
                print(SimpleBox.box("Time limit reached!\nConsider taking a break.", 42, '!'))
            try:
                line = input(self._prompt()).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            if not line:
                continue
            if not self.kernel.check_fs_health():
                return
            if self.kernel.history:
                self.kernel.history.add(line)
            if self._has_redirect(line, '>>'):
                idx = self._find_redirect_op(line, '>>')
                if idx >= 0:
                    self._redir(line[:idx].strip(), line[idx+2:].strip(), True)
                    continue
            if self._has_redirect(line, '>'):
                idx = self._find_redirect_op(line, '>')
                if idx >= 0:
                    self._redir(line[:idx].strip(), line[idx+1:].strip(), False)
                    continue
            for k, v in sorted(self.env.items(), key=lambda x: -len(x[0])):
                line = line.replace(f'${k}', str(v))
            first = line.split()[0] if line.split() else ''
            if first in self.aliases:
                line = self.aliases[first] + line[len(first):]
            self._exec(line)

    def _has_redirect(self, line, op):
        in_s = in_d = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '\\':
                i += 2
                continue
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            elif line[i:i+len(op)] == op and not in_s and not in_d:
                return True
            i += 1
        return False

    def _find_redirect_op(self, line, op):
        in_s = in_d = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '\\':
                i += 2
                continue
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            elif line[i:i+len(op)] == op and not in_s and not in_d:
                return i
            i += 1
        return -1

    def _redir(self, cmd, fp, append):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._exec(cmd)
        clean = re.sub(r'\033\[[0-9;]*m', '', buf.getvalue())
        self.kernel.fs.write_file(fp, clean, self.cwd, append)

    def _get_cmd_map(self):
        return {
            'reload': self.c_reload, 'help': self.c_help,
            'ls': self.c_ls, 'cd': self.c_cd, 'pwd': self.c_pwd,
            'mkdir': self.c_mkdir, 'rmdir': self.c_rmdir,
            'touch': self.c_touch, 'rm': self.c_rm, 'cat': self.c_cat,
            'echo': self.c_echo, 'cp': self.c_cp, 'mv': self.c_mv,
            'rename': self.c_rename, 'find': self.c_find, 'grep': self.c_grep,
            'wc': self.c_wc, 'tree': self.c_tree, 'du': self.c_du, 'df': self.c_df,
            'clear': lambda a: self._do_desktop(),
            'desktop': lambda a: self._do_desktop(),
            'whoami': lambda a: print(f"  {self.user}"),
            'id': self.c_id, 'su': self.c_su,
            'useradd': self.c_useradd, 'userdel': self.c_userdel,
            'passwd': self.c_passwd, 'users': self.c_users,
            'date': lambda a: print(f"  {self.kernel.get_now().strftime('%Y-%m-%d %H:%M:%S')}"),
            'uptime': lambda a: print(f"  Session: {self.kernel.guardian.session_str()}"),
            'hostname': lambda a: print(f"  {self.kernel.hostname}"),
            'neofetch': self.c_neofetch, 'history': self.c_history,
            'alias': self.c_alias, 'export': self.c_export,
            'env': lambda a: [print(f"  {k}={v}") for k, v in sorted(self.env.items())],
            'edit': self.c_edit, 'nano': self.c_edit,
            'guardian': self.c_guardian,
            'app': self.c_app, 'store': lambda a: self.c_app(['list']),
            'newapp': self.c_newapp, 'disk': self.c_disk,
            'man': self.c_man, 'realpath': self.c_realpath,
            'suggest': self.c_suggest, 'logs': self.c_logs,
            'notif': self.c_notif, 'timer': self.c_timer,
            'settings': self.c_settings, 'debug': self.c_debug,
            'shutdown': self.c_shutdown, 'reboot': self.c_reboot,
            'exit': self.c_exit, 'logout': self.c_exit,
            'save': self.c_save,
        }

    def _exec(self, line):
        if sys.platform == 'win32':
            try:
                parts = shlex.split(line, posix=False)
                parts = [p.strip('"').strip("'") if (p.startswith('"') and p.endswith('"')) or
                                                   (p.startswith("'") and p.endswith("'")) else p
                         for p in parts]
            except ValueError:
                parts = line.split()
        else:
            try:
                parts = shlex.split(line)
            except ValueError:
                parts = line.split()
        if not parts:
            return
        cmd, args = parts[0], parts[1:]
        cmds = self._get_cmd_map()
        if cmd in cmds:
            try:
                cmds[cmd](args)
            except Exception as e:
                print(C.c(f"  [Error] {e}", C.R))
                if self.kernel.settings.debug_mode and self.kernel.debug:
                    self.kernel.debug.log('command_error', str(e), tb_module.format_exc(), f'cmd:{cmd}', line)
        elif self.kernel.apps and cmd in self.kernel.apps.apps:
            ok, err = self.kernel.apps.run(cmd, self)
            if not ok:
                print(C.c(f"  {err}", C.R))
            self._do_desktop()
        else:
            if self.kernel.fs and self.kernel.fs.is_file(cmd, self.cwd) and cmd.endswith('.x4'):
                content = self.kernel.fs.read_file(cmd, self.cwd)
                if content:
                    p = X4Parser.parse(content)
                    if p['code']:
                        X4Runtime(self, app_name=p['info'].get('name', cmd.replace('.x4', ''))).execute(p['code'])
                        print()
                        print(C.c("  The application has shut down.", C.DIM))
                        time.sleep(3)
                self._do_desktop()
            else:
                print(C.c(f"  not found: {cmd}", C.R))
                all_known = list(cmds.keys()) + (list(self.kernel.apps.apps.keys()) if self.kernel.apps else [])
                suggestions = self.kernel.guardian.suggest(cmd, all_known)
                if suggestions:
                    print(C.c(f"  Did you mean: {', '.join(suggestions)}?", C.Y))

    def _do_desktop(self):
        self.desktop()

    def c_reload(self, a):
        if self.kernel.apps:
            self.kernel.apps.apps.clear()
            self.kernel.apps.load_installed()
            print(C.c(f"  Reloaded: {len(self.kernel.apps.apps)} apps", C.G))

    # ═══ FS ═══
    def c_ls(self, a):
        sa = '-a' in a; lf = '-l' in a or '-la' in a
        paths = [x for x in a if not x.startswith('-')]
        items = self.kernel.fs.list_dir(paths[0] if paths else '.', self.cwd)
        if items is None: print(C.c("  Not found", C.R)); return
        if not sa: items = [i for i in items if not i['name'].startswith('.')]
        g = self.kernel.guardian
        if lf:
            for it in items:
                tc = 'd' if it['is_dir'] else '-'
                col = C.BL+C.B if it['is_dir'] else (C.M if it['name'].endswith('.x4') else C.W)
                print(f"  {tc} {g.fmt_size(it['size']):>10}  {it['modified'][:16]}  {C.c(it['name']+('/' if it['is_dir'] else ''), col)}")
        else:
            ln = '  '
            for it in items:
                col = C.BL+C.B if it['is_dir'] else (C.M if it['name'].endswith('.x4') else C.W)
                ln += C.c(it['name']+('/' if it['is_dir'] else ''), col) + '  '
            if ln.strip(): print(ln)

    def c_cd(self, a):
        if not a: self.cwd = self.env.get('HOME', '/'); return
        p = a[0]
        if p == '-':
            old = self._oldpwd
            self.kernel.fs.current_disk = old['disk']
            p = old['path']
        explicit, rest = self.kernel.fs._parse_disk_prefix(p)
        if explicit: self.kernel.fs.current_disk = explicit; p = rest
        resolved, _ = self.kernel.fs.resolve(p, self.cwd)
        if self.kernel.fs.is_dir(resolved):
            self._oldpwd = {'path': self.cwd, 'disk': self.kernel.fs.current_disk}
            self.cwd = resolved
        else:
            print(C.c(f"  Not found: {a[0]}", C.R))

    def c_pwd(self, a): print(f"  {self.kernel.fs.current_disk}:{self.cwd}")
    def c_mkdir(self, a):
        for p in [x for x in a if not x.startswith('-')]:
            r, _ = self.kernel.fs.resolve(p, self.cwd); self.kernel.fs.mkdir(r)
    def c_rmdir(self, a):
        r = '-r' in a or '-rf' in a
        paths = [x for x in a if not x.startswith('-')]
        if '--' in a:
            paths = a[a.index('--')+1:]
            r = '-r' in a[:a.index('--')] or '-rf' in a[:a.index('--')]
        for p in paths:
            if not self.kernel.fs.delete(p, self.cwd, r): print(C.c(f"  Failed: {p}", C.R))
    def c_touch(self, a):
        for p in a:
            self.kernel.fs.touch(p, self.cwd)
    def c_rm(self, a):
        r = '-r' in a or '-rf' in a
        paths = [x for x in a if not x.startswith('-')]
        if '--' in a:
            paths = a[a.index('--')+1:]
            r = '-r' in a[:a.index('--')] or '-rf' in a[:a.index('--')]
        for p in paths:
            if not self.kernel.fs.delete(p, self.cwd, r): print(C.c(f"  Failed: {p}", C.R))

    def c_cat(self, a):
        for p in a:
            content = self.kernel.fs.read_file(p, self.cwd)
            if content is None: print(C.c(f"  Not found: {p}", C.R)); continue
            resolved, _ = self.kernel.fs.resolve(p, self.cwd)
            if resolved.lower().endswith('pyos_state.json'):
                try:
                    data = json.loads(content)
                    if 'users' in data and 'users' in data['users']:
                        for ud in data['users']['users'].values():
                            for f in ('pw','salt'):
                                if f in ud: ud[f] = '********'
                    content = json.dumps(data, indent=2, ensure_ascii=False)
                except (json.JSONDecodeError, KeyError):
                    content = "[Protected]"
            print(content)

    def c_echo(self, a):
        raw = ' '.join(a); out = ''; i = 0
        while i < len(raw):
            if i+1 < len(raw) and raw[i] == '\\':
                n = raw[i+1]
                if n == 'n': out += '\n'; i += 2
                elif n == 't': out += '\t'; i += 2
                elif n == '\\': out += '\\'; i += 2
                else: out += raw[i]; i += 1
            else: out += raw[i]; i += 1
        print(out)

    def c_cp(self, a):
        if len(a)<2: print("  cp <src> <dst>"); return
        print(C.c(f"  Copied: {a[0]} -> {a[1]}", C.G) if self.kernel.fs.copy(a[0],a[1],self.cwd) else C.c("  Failed", C.R))
    def c_mv(self, a):
        if len(a)<2: print("  mv <src> <dst>"); return
        print(C.c(f"  Moved: {a[0]} -> {a[1]}", C.G) if self.kernel.fs.move(a[0],a[1],self.cwd) else C.c("  Failed", C.R))
    def c_rename(self, a):
        if len(a)<2: print("  rename <f> <new>"); return
        print(C.c(f"  Renamed", C.G) if self.kernel.fs.rename(a[0],a[1],self.cwd) else C.c("  Failed", C.R))
    def c_find(self, a):
        if not a: print("  find [path] <pat>"); return
        p = a[0] if len(a)>1 else '.'; pat = a[1] if len(a)>1 else a[0]
        for r in self.kernel.fs.find(p, pat, self.cwd): print(f"  {r}")
    def c_grep(self, a):
        if len(a)<2: print("  grep <pat> <file>"); return
        c = self.kernel.fs.read_file(a[1], self.cwd)
        if not c: print(C.c("  Not found", C.R)); return
        for i, l in enumerate(c.split('\n'),1):
            if a[0] in l: print(f"  {i}: {l.replace(a[0], C.c(a[0], C.R+C.B))}")
    def c_wc(self, a):
        if not a: return
        c = self.kernel.fs.read_file(a[0], self.cwd)
        if c is None:
            print(C.c("  Not found", C.R))
        else:
            lines = c.count('\n')
            if c == '':
                lines = 0
            elif not c.endswith('\n'):
                lines += 1
            print(f"  {lines:>6} {len(c.split()):>6} {len(c):>6} {a[0]}")
    def c_tree(self, a): print(self.kernel.fs.tree(a[0] if a else '.', self.cwd))
    def c_du(self, a):
        p = a[0] if a else '.'; rp, _ = self.kernel.fs._real_path(p, self.cwd)
        if rp.exists():
            sz = self.kernel.fs._dir_size(rp) if rp.is_dir() else rp.stat().st_size
            print(f"  {self.kernel.guardian.fmt_size(sz)}  {p}")
    def c_df(self, a):
        g = self.kernel.guardian
        for d in self.kernel.fs.get_disks():
            u = self.kernel.fs.disk_usage(d)
            cur = " <--" if d == self.kernel.fs.current_disk else ""
            print(f"  {d}: {g.fmt_size(u)}{cur}")

    # ═══ USERS ═══
    def c_id(self, a):
        u = a[0] if a else self.user; info = self.kernel.um.get_public_info(u)
        if not info: print(C.c(f"  No user: {u}", C.R)); return
        print(f"  uid={info['uid']}({u}) disk={info.get('disk','C')}: pw={'yes' if info.get('has_password',True) else 'no'}")
    def c_su(self, a):
        if not a: print("  su <user>"); return
        t = a[0]
        if t not in self.kernel.um.users: print(C.c("  Not found", C.R)); return
        if not self.kernel.um.has_password(t):
            self._do_login(t); return
        if self.kernel.um.auth(t, input("  Password: ")):
            self._do_login(t)
        else: print(C.c("  Auth failed", C.R))
    def c_useradd(self, a):
        if not a: print("  useradd <name>"); return
        name = a[0]; pw = None; hint = ''
        if input(f"  Add password for {name}? (y/n): ").strip().lower() == 'y':
            pw = input("  Password: ")
            if input("  Add hint? (y/n): ").strip().lower() == 'y':
                hint = input("  Hint: ")
        ok, err = self.kernel.um.create(name, pw, hint)
        if ok:
            for d in [f'/home/{name}', f'/home/{name}/Desktop', f'/home/{name}/Documents']:
                self.kernel.fs.mkdir(d)
            print(C.c(f"  Created '{name}'", C.G)); self.kernel._save()
        else: print(C.c(f"  {err}", C.R))
    def c_userdel(self, a):
        if not a: print("  userdel <name>"); return
        if a[0] == self.user: print(C.c("  Cannot delete yourself", C.R)); return
        user_disk = self.kernel.um.get_disk(a[0])
        if self.kernel.um.delete(a[0]):
            home_path = f'/home/{a[0]}'
            old_disk = self.kernel.fs.current_disk
            self.kernel.fs.current_disk = user_disk
            self.kernel.fs.delete(home_path, recursive=True)
            self.kernel.fs.current_disk = old_disk
            print(C.c("  Deleted", C.G)); self.kernel._save()
        else: print(C.c("  Failed", C.R))
    def c_passwd(self, a):
        t = a[0] if a else self.user
        if t != self.user: print(C.c("  Can only change own password", C.R)); return
        n = input("  New password (empty=remove): ").strip()
        if n == '':
            self.kernel.um.change_password(t, None); self.kernel.um.set_hint(t, '')
            print(C.c("  Password removed", C.Y))
        else:
            if n != input("  Confirm: "): print(C.c("  Mismatch", C.R)); return
            self.kernel.um.change_password(t, n); print(C.c("  Updated", C.G))
            h = input("  New hint (empty=keep): ").strip()
            if h: self.kernel.um.set_hint(t, h)
        self.kernel._save()
    def c_users(self, a):
        print("=" * 52)
        print("  Users")
        print("=" * 52)
        for u in self.kernel.um.list_users():
            info = self.kernel.um.get_public_info(u)
            cur = " <-- you" if u == self.user else ""
            has_pw = "pw" if info.get('has_password',True) else "open"
            print(f"  {u:<14} uid={info['uid']} {has_pw} disk={info.get('disk','C')}: {info.get('created','?')[:10]}{cur}")
        print("-" * 52)
        print(f"  Total: {len(self.kernel.um.users)} users")
        print("=" * 52)

    # ═══ HISTORY / LOGS ═══
    def c_history(self, a):
        if not self.kernel.history: return
        if a and a[0] == 'clear': self.kernel.history.clear(); print(C.c("  Cleared", C.G)); return
        if a and a[0] == 'search':
            pat = ' '.join(a[1:])
            for e in self.kernel.history.search(pat): print(f"  {C.c(e['time'][:19], C.DIM)}  {e['cmd']}")
            return
        for i, e in enumerate(self.kernel.history.get_all(), 1):
            print(f"  {i:>4}  {C.c(e['time'][:19], C.DIM)}  {e['cmd']}")

    def c_logs(self, a):
        if not a:
            items = self.kernel.fs.list_dir('/apps/logs')
            if not items or not [i for i in items if i['name'].endswith('.json')]:
                print(C.c("  No crash logs.", C.G)); return
            for item in items:
                if item['name'].endswith('.json'):
                    print(f"  {item['name']:<35} {self.kernel.guardian.fmt_size(item['size']):>8}")
            return
        if a[0] == 'clear':
            items = self.kernel.fs.list_dir('/apps/logs'); count = 0
            if items:
                for item in items:
                    if item['name'].endswith('.json'):
                        self.kernel.fs.delete(f"/apps/logs/{item['name']}"); count += 1
            print(C.c(f"  Deleted {count} log(s)", C.G)); return
        fname = a[0] if a[0].endswith('.json') else a[0]+'.json'
        content = self.kernel.fs.read_file(f'/apps/logs/{fname}')
        if content: print(content)
        else: print(C.c(f"  Not found: {fname}", C.R))

    # ═══ NEOFETCH ═══
    def c_neofetch(self, a):
        k = self.kernel; g = k.guardian
        data = {
            'OS': f'PyOS v{Kernel.VERSION}', 'Build': Kernel.BUILD,
            'Company': Kernel.COMPANY, 'Computer': k.hostname,
            'User': self.user, 'Session': g.session_str(),
            'Time': k.get_now().strftime('%H:%M:%S'),
            'Disks': ' '.join(d+':' for d in k.fs.get_disks()),
            'Apps': str(len(k.apps.apps)) if k.apps else '0',
            'Python': sys.version.split()[0],
        }
        print("=" * 48)
        print("  System Information")
        print("=" * 48)
        for key, value in data.items():
            print(f"  {key:<15}: {value}")
        print("=" * 48)

    def c_suggest(self, a):
        g = self.kernel.guardian
        if not a: print(f"  Suggestions: {'ON' if g.suggest_commands else 'OFF'}"); return
        if a[0] == 'on': g.suggest_commands = True; print(C.c("  ON", C.G))
        elif a[0] == 'off': g.suggest_commands = False; print(C.c("  OFF", C.Y))
        self.kernel._save()

    # ═══ GUARDIAN ═══
    def c_guardian(self, a):
        g = self.kernel.guardian
        guardian_cmds = ['cleanup','limit','applimit','appclean','suggest','logs','refresh','q']
        if not a or a[0] == 'status':
            self._guardian_screen()
            while True:
                try: cmd = input(C.c("  guardian> ", C.M)).strip()
                except (EOFError, KeyboardInterrupt): break
                if cmd in ('q','quit','exit','back'): break
                elif cmd == 'cleanup': self._g_cleanup()
                elif cmd.startswith('limit'): self._g_limit(cmd.split()[1:])
                elif cmd.startswith('applimit'): self._g_applimit(cmd.split()[1:])
                elif cmd.startswith('appclean'): self._g_appclean(cmd.split()[1:])
                elif cmd.startswith('suggest'): self.c_suggest(cmd.split()[1:] if len(cmd.split())>1 else [])
                elif cmd == 'logs': self.c_logs([])
                elif cmd == 'refresh': self._guardian_screen()
                elif cmd:
                    print(C.c(f"  Unknown: {cmd}", C.R))
                    s = g.suggest(cmd, guardian_cmds)
                    if s: print(C.c(f"  Did you mean: {', '.join(s)}?", C.Y))
            self._do_desktop(); return
        sub = {'cleanup': lambda: self._g_cleanup(), 'limit': lambda: self._g_limit(a[1:]),
               'applimit': lambda: self._g_applimit(a[1:]), 'appclean': lambda: self._g_appclean(a[1:]),
               'suggest': lambda: self.c_suggest(a[1:]), 'logs': lambda: self.c_logs(a[1:])}
        if a[0] in sub: sub[a[0]]()

    def _g_cleanup(self):
        g = self.kernel.guardian; report = g.disk_report(self.kernel.fs)
        if not report['largest']: print(C.c("  No files", C.Y)); return
        for i, fi in enumerate(report['largest'][:10]):
            print(f"  {i+1:>3}. {g.fmt_size(fi['size']):>10}  {fi['path']}")
        ans = input("\n  Delete? (1,3,5 or no): ").strip()
        if ans.lower() != 'no' and ans:
            try:
                for n in [int(x.strip())-1 for x in ans.split(',')]:
                    if 0 <= n < len(report['largest']):
                        if self.kernel.fs.delete(report['largest'][n]['path']):
                            print(C.c(f"  Deleted: {report['largest'][n]['path']}", C.G))
            except (ValueError, IndexError): print(C.c("  Invalid", C.R))

    def _g_limit(self, a):
        g = self.kernel.guardian
        if not a: print(f"  Time limit: {g.daily_limit or 'None'} min"); return
        if a[0] == 'off': g.set_limit(None); print(C.c("  Removed", C.G))
        else:
            try: g.set_limit(int(a[0])); print(C.c(f"  Limit: {a[0]} min", C.G))
            except ValueError: print(C.c("  limit <min>|off", C.R))
        self.kernel._save()

    def _g_applimit(self, a):
        g = self.kernel.guardian
        if not a:
            print(f"  App limit: {g.fmt_size(g.app_folder_limit)}/app")
            for ac in g.check_all_apps(self.kernel.fs):
                s = C.c("OVER!", C.R) if ac['over'] else C.c("OK", C.G)
                print(f"    {ac['name']:<15} {g.fmt_size(ac['size']):>8} {s}")
            return
        try: g.set_app_folder_limit(int(a[0])*1024); print(C.c(f"  Limit: {a[0]} KB/app", C.G)); self.kernel._save()
        except ValueError: print(C.c("  applimit <KB>", C.R))

    def _g_appclean(self, a):
        g = self.kernel.guardian
        if not a: print("  appclean <name>|all"); return
        if a[0] == 'all':
            total = g.cleanup_all_apps(self.kernel.fs)
            if not total: print(C.c("  All OK", C.G))
            else:
                for an, dl in total:
                    print(C.c(f"  [{an}]:", C.Y))
                    for fn, fs2 in dl: print(f"    {fn} ({g.fmt_size(fs2)})")
        else:
            dl = g.cleanup_app_folder(self.kernel.fs, a[0])
            if not dl:
                cur, lim2, _ = g.check_app_folder(self.kernel.fs, a[0])
                print(C.c(f"  '{a[0]}' OK ({g.fmt_size(cur)}/{g.fmt_size(lim2)})", C.G))
            else:
                for fn, fs2 in dl: print(f"    {fn} ({g.fmt_size(fs2)})")

    # ═══ APPS ═══
    def c_app(self, a):
        if not self.kernel.apps: print(C.c("  No apps", C.R)); return
        if not a: print("  app <run|list|info|install|remove|bg> [name]"); return
        act = a[0]
        if act == 'run':
            if len(a)<2: print("  app run <name>"); return
            ok, err = self.kernel.apps.run(a[1], self)
            if not ok: print(C.c(f"  {err}", C.R))
            self._do_desktop()
        elif act == 'list':
            apps = self.kernel.apps.apps; g = self.kernel.guardian
            print("=" * 54)
            print("  Applications (.x4)")
            print("=" * 54)
            for name, data in apps.items():
                info = data.get('info', {})
                tag = f"[{info.get('tag','')}]" if info.get('tag') else ''
                cur,_,_ = g.check_app_folder(self.kernel.fs, name)
                print(f"  {name:<12} v{info.get('version','?'):<5} {g.fmt_size(cur):>6} {info.get('description','')[:16]} {tag}")
            print("-" * 54)
            print(f"  Total: {len(apps)} | Limit: {g.fmt_size(g.app_folder_limit)}/app")
            print("=" * 54)
        elif act == 'info':
            if len(a)<2: return
            info = self.kernel.apps.get_info(a[1])
            if info:
                print("=" * 42)
                print(f"  {a[1]}")
                print("=" * 42)
                for k, v in info.items():
                    print(f"  {k}: {v}")
                print("=" * 42)
            else: print(C.c("  Not found", C.R))
        elif act == 'install':
            if len(a)<2: print("  app install <file.x4>"); return
            ok, msg = self.kernel.apps.install(a[1], self.cwd, home_dir=self.env['HOME'])
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif act == 'remove':
            if len(a)<2: return
            print(C.c("  Removed", C.G) if self.kernel.apps.remove(a[1]) else C.c("  Not found", C.R))
        elif act == 'bg':
            if len(a)>2 and a[1]=='stop':
                print(C.c(f"  Stopped", C.G) if self.kernel.app_bg.unregister(a[2]) else C.c("  Not found", C.R))
                return
            bg = self.kernel.app_bg.get_all()
            if not bg: print(C.c("  No bg apps", C.DIM)); return
            for name in bg: print(f"  # {name}")

    def c_newapp(self, a):
        if not a: print("  newapp <name>"); return
        docs = self._docs()
        self.kernel.fs.write_file(f'{docs}/{a[0]}.x4', X4Parser.template(a[0], self.user))
        print(C.c(f"  Created: {docs}/{a[0]}.x4", C.G))

    # ═══ DISK ═══
    def c_disk(self, a):
        g = self.kernel.guardian
        if not a:
            for d in self.kernel.fs.get_disks():
                u = self.kernel.fs.disk_usage(d)
                cur = " <--" if d == self.kernel.fs.current_disk else ""
                print(f"  {d}: {g.fmt_size(u)}{cur}")
            return
        if a[0] == 'add':
            if len(a)<2: print("  disk add <letter>"); return
            l = a[1].upper()
            if len(l)!=1 or not l.isalpha(): print(C.c("  A-Z", C.R)); return
            if l in self.kernel.fs.get_disks(): print(C.c(f"  {l}: exists", C.R)); return
            self.kernel.fs._create_disk(l)
            print(C.c(f"  Disk {l}: created", C.G)); self.kernel._save()
        elif a[0] in ('switch','sw'):
            if len(a)<2: print("  disk switch <letter>"); return
            target = a[1].upper()
            if target not in self.kernel.fs.get_disks(): print(C.c(f"  {target}: not found", C.R)); return
            old = self.kernel.fs.current_disk
            if target == old: print(C.c(f"  Already on {target}:", C.Y)); return
            dst_home = self.kernel.fs.hostname_dir / target / 'home' / self.user
            if dst_home.exists():
                ans = input(C.c(f"  Target home already exists. Overwrite? (y/n): ", C.Y)).strip().lower()
                if ans != 'y':
                    print("  Cancelled")
                    return
            if self.kernel.fs.migrate_user(self.user, old, target):
                self.kernel.fs.current_disk = target; self.kernel.um.set_disk(self.user, target)
                self.cwd = self.env['HOME']; self.kernel.fs.mkdir(self.cwd)
                print(C.c(f"  Migrated to {target}:", C.G)); self.kernel._save(); self._do_desktop()
            else: print(C.c(f"  Failed", C.R))

    # ═══ EDIT ═══
    def c_edit(self, a):
        if not a: print("  edit <file>"); return
        p = a[0]; docs = self._docs()
        fp = f"{docs}/{p}" if '/' not in p and not p.startswith('/') and ':' not in p else p
        c = self.kernel.fs.read_file(fp, self.cwd)
        if c is not None and '\0' in c:
            print(C.c("  Binary file detected. Edit aborted.", C.R))
            return
        new = (c or '').split('\n') if c else ['']
        print(C.c(f"  === PyEdit: {fp} ===", C.CY))
        for i, l in enumerate(new): print(f"  {C.c(str(i+1).rjust(3), C.DIM)} | {l}")
        while True:
            try: inp = input(C.c("  edit> ", C.G))
            except (EOFError, KeyboardInterrupt):
                if input("\n  Save? (y/n): ").strip().lower() == 'y':
                    self.kernel.fs.write_file(fp, '\n'.join(new), self.cwd); print("  Saved")
                break
            if inp == ':q': self._do_desktop(); return
            if inp == ':wq':
                self.kernel.fs.write_file(fp, '\n'.join(new), self.cwd)
                print(f"  Saved {fp}"); self._do_desktop(); return
            if inp in (':w',':s'):
                self.kernel.fs.write_file(fp, '\n'.join(new), self.cwd); print("  Saved"); continue
            if inp == ':p':
                for i, l in enumerate(new): print(f"  {C.c(str(i+1).rjust(3), C.DIM)} | {l}")
                continue
            if inp.startswith(':d '):
                try: del new[int(inp[3:])-1]; print("  Deleted")
                except: pass
                continue
            if inp.startswith(':i '):
                try: p2=inp[3:].split(' ',1); new.insert(int(p2[0])-1, p2[1] if len(p2)>1 else '')
                except: pass
                continue
            if inp.startswith(':') and len(inp)>1:
                try:
                    p2=inp[1:].split(' ',1); ln=int(p2[0])-1
                    while len(new)<=ln: new.append('')
                    new[ln] = p2[1] if len(p2)>1 else ''; continue
                except ValueError: pass
            new.append(inp)
            print(f"  {C.c(str(len(new)).rjust(3), C.DIM)} | {inp}")

    # ═══ MISC ═══
    def c_alias(self, a):
        if not a:
            for k,v in self.aliases.items(): print(f"  {k}='{v}'")
            return
        s = ' '.join(a)
        if '=' in s: n,v = s.split('=',1); self.aliases[n.strip()] = v.strip("'\"")
    def c_export(self, a):
        for x in a:
            if '=' in x: k,v = x.split('=',1); self.env[k] = v
    def c_realpath(self, a):
        p = a[0] if a else '.'; rp, dk = self.kernel.fs._real_path(p, self.cwd)
        print(f"  {dk}:{self.kernel.fs.resolve(p, self.cwd)[0]} -> {rp}")

    # ═══ SETTINGS / DEBUG / NOTIF / TIMER ═══
    def c_settings(self, a):
        if not a:
            s = self.kernel.settings; now = self.kernel.get_now()
            print("=" * 50)
            print(f"  Settings -- PyOS {Kernel.VERSION}")
            print("=" * 50)
            print(f"  Time mode: {s.time_mode.upper()}")
            print(f"  Time:      {now.strftime('%H:%M:%S')}")
            print(f"  Date:      {now.strftime('%Y-%m-%d')}")
            print(f"  Debug:     {C.c('ON',C.Y) if s.debug_mode else C.c('OFF',C.DIM)}")
            print("-" * 50)
            print("  settings time auto|set HH:MM:SS|date YYYY-MM-DD")
            print("  settings debug on|off|clear")
            print("=" * 50)
            return
        if a[0] == 'time':
            s = self.kernel.settings
            if len(a)<2: return
            if a[1] == 'auto': s.set_auto(); print(C.c("  AUTO", C.G)); self.kernel._save()
            elif a[1] == 'set' and len(a)>2:
                try:
                    tp = a[2].split(':'); h,m2,sec = int(tp[0]), int(tp[1]) if len(tp)>1 else 0, int(tp[2]) if len(tp)>2 else 0
                    t = datetime.datetime.now().replace(hour=h,minute=m2,second=sec,microsecond=0)
                    s.set_manual_datetime(t); print(C.c(f"  Set: {t.strftime('%H:%M:%S')}", C.G)); self.kernel._save()
                except: print(C.c("  HH:MM:SS", C.R))
            elif a[1] == 'date' and len(a)>2:
                try:
                    dp = a[2].split('-'); y,mo,d = int(dp[0]),int(dp[1]),int(dp[2])
                    t = (s.get_now() if s.time_mode=='manual' else datetime.datetime.now()).replace(year=y,month=mo,day=d)
                    s.set_manual_datetime(t); print(C.c(f"  Date: {t.strftime('%Y-%m-%d')}", C.G)); self.kernel._save()
                except: print(C.c("  YYYY-MM-DD", C.R))
        elif a[0] == 'debug':
            s = self.kernel.settings
            if len(a)<2: print(f"  Debug: {'ON' if s.debug_mode else 'OFF'}"); return
            if a[1] == 'on': s.debug_mode = True; print(C.c("  ON", C.Y)); self.kernel._save()
            elif a[1] == 'off': s.debug_mode = False; print(C.c("  OFF", C.G)); self.kernel._save()
            elif a[1] == 'clear' and self.kernel.debug: self.kernel.debug.clear(); print(C.c("  Cleared", C.G))

    def c_debug(self, a):
        if not self.kernel.settings.debug_mode: print(C.c("  Debug OFF. settings debug on", C.Y)); return
        if not self.kernel.debug: print(C.c("  Not initialized", C.R)); return
        if not a:
            errors = self.kernel.debug.get_recent(15)
            if not errors: print(C.c("  No errors", C.DIM)); return
            for e in errors:
                t = e.get('time','')[11:19]
                print(f"  #{e.get('id','?'):<3} [{e.get('source','?')[:10]}] {e.get('message','')[:35]} {C.c(t, C.DIM)}")
            return
        if a[0] == 'clear': self.kernel.debug.clear(); print(C.c("  Cleared", C.G))
        elif a[0] == 'test':
            self.kernel.debug.log('test_error','Test error','test trace','debug_test','test')
            print(C.c("  Test logged", C.Y))

    def c_notif(self, a):
        nc = self.kernel.notifications
        if not a:
            all_n = nc.get_all()
            if not all_n: print(C.c("  No notifications", C.DIM)); return
            for n in all_n[-15:]:
                rm = C.c('+',C.G) if n['read'] else C.c('*',C.Y)
                print(f"  {rm} #{n['id']:<3} [{n['source'][:10]}] {n['title'][:25]} {C.c(n['time'][11:16], C.DIM)}")
            return
        if a[0] == 'read':
            if len(a)>1:
                try: nc.mark_read(int(a[1])); print(C.c("  Read", C.G))
                except ValueError: print(C.c("  Invalid ID", C.R))
            else: nc.mark_read(); print(C.c("  All read", C.G))
        elif a[0] == 'clear':
            if len(a)>1 and a[1]=='read': nc.delete_read()
            else: nc.delete()
            print(C.c("  Cleared", C.G))
        elif a[0] == 'count':
            print(f"  Total: {len(nc.get_all())} | Unread: {nc.count_unread()}")

    def c_timer(self, a):
        ts = self.kernel.timer_service
        if not a:
            all_t = ts.get_all(); now = datetime.datetime.now()
            if not all_t: print(C.c("  No timers", C.DIM)); return
            for t in all_t:
                if t['fired']: print(f"  + #{t['id']:<3} {t['label'][:20]} DONE")
                else:
                    rem = max(0,int((t['end_time']-now).total_seconds()))
                    m2,s = divmod(rem,60); h,m2 = divmod(m2,60)
                    print(f"  @ #{t['id']:<3} {t['label'][:20]} {h}:{m2:02d}:{s:02d} left")
            return
        if a[0] in ('add','set'):
            if len(a)<2: print("  timer add <sec> [label]"); return
            try:
                secs = int(a[1])
                if secs <= 0:
                    print(C.c("  Seconds must be positive", C.R))
                    return
                label = ' '.join(a[2:]) if len(a)>2 else 'Timer'
                tid = ts.add_timer(secs, label)
                if tid is not None:
                    print(C.c(f"  Timer #{tid}: {label} ({secs}s)", C.G))
                else:
                    print(C.c("  Failed to create timer", C.R))
            except ValueError: print(C.c("  timer add <sec> [label]", C.R))
        elif a[0] in ('cancel','rm'):
            if len(a)<2: return
            try: print(C.c("  Cancelled",C.G) if ts.cancel_timer(int(a[1])) else C.c("  Not found",C.R))
            except ValueError: print(C.c("  Invalid ID", C.R))
        elif a[0] == 'clear': ts.cleanup(); print(C.c("  Cleared", C.G))

    # ═══ MAN (ПОЛНЫЙ) ═══
    def c_man(self, a):
        mans = {
            'help': 'help\n  Show all available commands by category.',
            'ls': 'ls [-l] [-a] [path]\n  List directory contents.\n  -l  long format (size, date)\n  -a  show hidden files',
            'cd': 'cd <path>|..|~|-\n  Change directory.\n  cd /     go to root\n  cd ..    go up\n  cd ~     go home\n  cd -     go to previous directory',
            'pwd': 'pwd\n  Print current working directory.',
            'mkdir': 'mkdir <path>\n  Create a new directory.',
            'rmdir': 'rmdir [-r] <path>\n  Remove empty directory (-r recursive).',
            'touch': 'touch <file>\n  Create empty file or update timestamp.',
            'rm': 'rm [-r] <path>\n  Remove file or directory (-r recursive).',
            'cat': 'cat <file>\n  Display file contents.',
            'echo': 'echo <text>\n  Print text (\\n newline, \\t tab). Supports > and >> redirect.',
            'cp': 'cp <src> <dst>\n  Copy file or directory.',
            'mv': 'mv <src> <dst>\n  Move/rename file or directory.',
            'rename': 'rename <old> <new>\n  Rename file or directory.',
            'find': 'find [path] <pattern>\n  Search for files by name (substring match).',
            'grep': 'grep <pattern> <file>\n  Search for text inside a file.',
            'wc': 'wc <file>\n  Count lines, words, and characters.',
            'tree': 'tree [path]\n  Show directory tree (max depth 4).',
            'du': 'du [path]\n  Estimate disk usage of a file or directory.',
            'df': 'df\n  Show disk free/used space for all disks.',
            'clear': 'clear\n  Clear the screen and show desktop.',
            'desktop': 'desktop\n  Show the main desktop view.',
            'whoami': 'whoami\n  Print current user name.',
            'id': 'id [user]\n  Show user ID, disk, password status.',
            'su': 'su <user>\n  Switch to another user (login).',
            'useradd': 'useradd <name>\n  Create a new user account.',
            'userdel': 'userdel <name>\n  Delete a user and their home directory.',
            'passwd': 'passwd\n  Change your password.',
            'users': 'users\n  List all users on the system.',
            'date': 'date\n  Show current date and time.',
            'uptime': 'uptime\n  Show session duration.',
            'hostname': 'hostname\n  Show computer name.',
            'neofetch': 'neofetch\n  Display system information.',
            'history': 'history [search <text>|clear]\n  Show command history. Optional: search or clear.',
            'alias': 'alias [name=command]\n  Set or list command aliases (e.g., alias ll=ls -l).',
            'export': 'export VAR=value\n  Set environment variable.',
            'env': 'env\n  List all environment variables.',
            'edit': 'edit <file>\n  Built-in text editor. Commands: :w save, :q quit, :wq save+quit, :p print, :d N delete line N, :i N text insert, :N text replace line N.',
            'nano': 'nano <file>\n  Same as edit.',
            'guardian': 'guardian [status|cleanup|limit|applimit|appclean|suggest|logs]\n  Open system monitor and cleanup tools.',
            'app': 'app <run|list|info|install|remove|bg> [args]\n  Manage X4 applications.\n  app run <name>   run app\n  app list         show installed\n  app info <name>  details\n  app install <file>  install .x4\n  app remove <name>\n  app bg          list background apps\n  app bg stop <name>',
            'store': 'store\n  Show installed applications (alias for app list).',
            'newapp': 'newapp <name>\n  Create a new .x4 app template in Documents.',
            'disk': 'disk [add|switch|sw] <letter>\n  Manage disks.\n  disk add D     create new disk\n  disk switch D  migrate your home to another disk',
            'man': 'man <command>\n  Show this manual for a command.',
            'realpath': 'realpath [path]\n  Resolve virtual path to real filesystem path.',
            'shutdown': 'shutdown\n  Save state and exit PyOS.',
            'reboot': 'reboot\n  Reboot PyOS (reload desktop).',
            'exit': 'exit\n  Alias for shutdown.',
            'logout': 'logout\n  Alias for shutdown.',
            'save': 'save\n  Force save system state.',
            'suggest': 'suggest [on|off]\n  Toggle command suggestions on typos.',
            'logs': 'logs [clear|file.json]\n  View crash logs of applications.',
            'notif': 'notif [read|clear|count|read ID]\n  Manage notifications.',
            'reload': 'reload\n  Reload installed apps from disk.',
            'timer': 'timer [add <sec> <label>|cancel <id>|clear]\n  Manage background timers.',
            'settings': 'settings [time auto|set HH:MM:SS|date YYYY-MM-DD] [debug on|off|clear]\n  Configure system settings.',
            'debug': 'debug [clear|test]\n  Show debug log (only when debug mode is on).',
        }
        if not a:
            print("=" * 50)
            print(f"  Manual -- PyOS {Kernel.VERSION}")
            print("=" * 50)
            print("  Available commands:")
            print('  ' + ', '.join(sorted(mans.keys())))
            print("-" * 50)
            print("  man <cmd> for details")
            print("=" * 50)
            return
        cmd = a[0]
        m = mans.get(cmd)
        if m:
            print("=" * 56)
            print(f"  man {cmd}")
            print("=" * 56)
            for line in m.split('\n'):
                print(f"  {line}")
            print("=" * 56)
        else:
            print(C.c(f"  No manual for '{cmd}'", C.R))
            s = self.kernel.guardian.suggest(cmd, list(mans.keys()))
            if s: print(C.c(f"  Did you mean: {', '.join(s)}?", C.Y))

    # ═══ HELP ═══
    def c_help(self, a):
        cats = [
            ('Files',    'ls cd pwd mkdir rmdir touch rm cat cp mv rename find grep wc tree du df'),
            ('Users',    'whoami id su useradd userdel passwd users'),
            ('System',   'date uptime hostname neofetch reboot shutdown'),
            ('Shell',    'echo clear desktop history alias export env edit save reload'),
            ('Guardian', 'guardian suggest logs'),
            ('Apps',     'app store newapp (or type app name)'),
            ('Disks',    'disk add switch (D:/path cross-disk)'),
            ('Notif',    'notif | timer'),
            ('Settings', 'settings (time/date, debug)'),
            ('Other',    'man realpath help exit'),
        ]
        print("=" * 90)
        print(f"  PyOS v{Kernel.VERSION} Help")
        print("=" * 90)
        for cat, cmds in cats:
            print(f"  {C.c(cat + ':', C.Y)} {cmds}")
        print("-" * 90)
        print("  man <cmd> -- detailed help")
        print(C.c(f"  {Kernel.COMPANY} -- PyOS {Kernel.VERSION}", C.DIM))
        print("=" * 90)

    def c_save(self, a):
        print(C.c("  Saved", C.G) if self.kernel._save() else C.c("  Failed", C.R))
    def c_shutdown(self, a): self.kernel.shutdown()
    def c_reboot(self, a):
        self.kernel._save()
        self.kernel.boot_time = datetime.datetime.now()
        self.kernel.guardian.session_start = datetime.datetime.now()
        clear(); self.kernel._boot_anim()
        self._do_desktop()
    def c_exit(self, a): self.kernel.shutdown()

# ═══ MAIN ═══
def main():
    kernel = Kernel()
    while True:
        kernel.boot()
        shell = Shell(kernel)
        if kernel.first_boot:
            kernel.setup()
        if not shell.login():
            return
        try:
            shell.run()
        except Exception as e:
            print(C.c(f"\n  [PANIC] {e}", C.R))
            tb_module.print_exc()
            if kernel.settings.debug_mode and kernel.debug:
                kernel.debug.log('panic', str(e), tb_module.format_exc(), 'kernel', '')
            kernel._save()
        if kernel._bsod_pending:
            BSOD.crash_and_restart(
                kernel._bsod_error_code,
                kernel._bsod_message,
                kernel._bsod_details
            )
            kernel._restart_after_bsod()
            continue
        else:
            break

if __name__ == '__main__':
    main()