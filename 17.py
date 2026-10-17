#!/usr/bin/env python3
"""PyOS v16.1 GUI — Windows 2000 Style — BitSoft Studios"""

import os
import sys
import json
import time
import hashlib
import random
import datetime
import math
import re
import shutil
import threading
import traceback as tb_module
from pathlib import Path
from collections import deque

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, font as tkfont

# ═══════════════════════════════════════════════════════════════
#  THEME — Windows 2000 Colors
# ═══════════════════════════════════════════════════════════════

class Win2kTheme:
    DESKTOP_BG = "#3A6EA5"
    TASKBAR_BG = "#C0C0C0"
    WINDOW_BG = "#C0C0C0"
    WINDOW_TITLE_ACTIVE = "#000080"
    WINDOW_TITLE_INACTIVE = "#808080"
    WINDOW_TITLE_TEXT = "#FFFFFF"
    WINDOW_BORDER_DARK = "#808080"

    BUTTON_BG = "#C0C0C0"
    BUTTON_ACTIVE = "#D4D0C8"

    TEXT_BG = "#FFFFFF"
    TEXT_FG = "#000000"
    TEXT_SELECT_BG = "#000080"
    TEXT_SELECT_FG = "#FFFFFF"

    MENU_BG = "#C0C0C0"
    MENU_FG = "#000000"
    MENU_HIGHLIGHT_BG = "#000080"
    MENU_HIGHLIGHT_FG = "#FFFFFF"

    START_BANNER_BG = "#000080"
    START_BANNER_FG = "#FFFFFF"
    START_BG = "#C0C0C0"

    ICON_COMPUTER = "🖥"
    ICON_FOLDER = "📁"
    ICON_FOLDER_OPEN = "📂"
    ICON_FILE = "📄"
    ICON_APP = "📦"
    ICON_TERMINAL = "⬛"
    ICON_NOTEPAD = "📝"
    ICON_SETTINGS = "⚙"
    ICON_TRASH = "🗑"
    ICON_INFO = "ℹ"
    ICON_WARN = "⚠"
    ICON_ERROR = "❌"
    ICON_OK = "✅"
    ICON_CALC = "🔢"
    ICON_PAINT = "🎨"
    ICON_CLOCK = "🕐"
    ICON_USER = "👤"
    ICON_LOCK = "🔒"
    ICON_SHUTDOWN = "⏻"
    ICON_GAMES = "🎮"
    ICON_SHIELD = "🛡"
    ICON_ALARM = "⏰"
    ICON_STOPWATCH = "⏱"
    ICON_TIMER = "⏲"
    ICON_INSTALL = "📥"
    ICON_PACKAGE = "📦"

    TITLEBAR_HEIGHT = 22
    TASKBAR_HEIGHT = 32
    DESKTOP_ICON_SPACING = 80

    @classmethod
    def apply_to_root(cls, root):
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', background=cls.WINDOW_BG, foreground=cls.TEXT_FG, font=('Tahoma', 8))
        style.configure('TButton', background=cls.BUTTON_BG, foreground=cls.TEXT_FG,
                        borderwidth=2, relief='raised', padding=(4, 2))
        style.map('TButton', background=[('active', cls.BUTTON_ACTIVE), ('pressed', cls.BUTTON_BG)])
        style.configure('TEntry', fieldbackground=cls.TEXT_BG, foreground=cls.TEXT_FG,
                        borderwidth=2, relief='sunken')
        style.configure('TLabel', background=cls.WINDOW_BG, foreground=cls.TEXT_FG)
        style.configure('TFrame', background=cls.WINDOW_BG)
        style.configure('Treeview', background=cls.TEXT_BG, foreground=cls.TEXT_FG,
                        fieldbackground=cls.TEXT_BG, borderwidth=2, relief='sunken')
        style.configure('Treeview.Heading', background=cls.BUTTON_BG, foreground=cls.TEXT_FG, relief='raised')
        style.configure('TNotebook', background=cls.WINDOW_BG)
        style.configure('TNotebook.Tab', background=cls.BUTTON_BG, padding=(8, 2))


# ═══════════════════════════════════════════════════════════════
#  REAL FILESYSTEM
# ═══════════════════════════════════════════════════════════════

class RealFS:
    PROTECTED = {'/', '/home', '/sysdata', '/sysdata/config', '/apps',
                 '/apps/installed', '/apps/data', '/apps/logs', '/trash'}

    def __init__(self, base_path):
        self.base = Path(base_path).resolve()
        self.hostname_dir = None
        self.current_disk = 'C'
        self._lock = threading.Lock()

    def init_structure(self, hostname):
        self.hostname_dir = self.base / hostname
        self.hostname_dir.mkdir(parents=True, exist_ok=True)
        self._create_disk('C')
        self.current_disk = 'C'
        for d in ['home', 'sysdata', 'sysdata/config', 'apps', 'apps/installed',
                   'apps/data', 'apps/store', 'apps/logs', 'trash']:
            self._disk_path('C', d).mkdir(parents=True, exist_ok=True)

    def _create_disk(self, name):
        (self.hostname_dir / name.upper()).mkdir(parents=True, exist_ok=True)

    def _disk_path(self, disk, rel_path=''):
        p = self.hostname_dir / disk.upper()
        if rel_path:
            p = p / rel_path.lstrip('/')
        return p

    def _resolve_path(self, virtual_path, cwd='/'):
        disk = self.current_disk
        if len(virtual_path) >= 2 and virtual_path[1] == ':' and virtual_path[0].isalpha():
            d = virtual_path[0].upper()
            if self.hostname_dir and (self.hostname_dir / d).exists():
                disk = d
                virtual_path = virtual_path[2:] or '/'
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
        real_path = self._disk_path(disk, '/'.join(parts))
        try:
            real_path.resolve().relative_to(self.hostname_dir.resolve())
        except (ValueError, RuntimeError):
            return self._disk_path(disk), disk
        return real_path, disk

    def resolve_virtual(self, path, cwd='/'):
        if len(path) >= 2 and path[1] == ':':
            path = path[2:] or '/'
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
        return '/' + '/'.join(parts)

    def is_protected(self, path, cwd='/'):
        resolved = self.resolve_virtual(path, cwd)
        return resolved in self.PROTECTED

    def exists(self, path, cwd='/'):
        with self._lock:
            rp, _ = self._resolve_path(path, cwd)
            return rp.exists()

    def is_dir(self, path, cwd='/'):
        with self._lock:
            rp, _ = self._resolve_path(path, cwd)
            return rp.is_dir()

    def is_file(self, path, cwd='/'):
        with self._lock:
            rp, _ = self._resolve_path(path, cwd)
            return rp.is_file()

    def mkdir(self, path, cwd='/'):
        with self._lock:
            try:
                rp, _ = self._resolve_path(path, cwd)
                rp.mkdir(parents=True, exist_ok=True)
                return True
            except (OSError, PermissionError):
                return False

    def write_file(self, path, content, cwd='/', append=False):
        with self._lock:
            try:
                rp, _ = self._resolve_path(path, cwd)
                rp.parent.mkdir(parents=True, exist_ok=True)
                mode = 'a' if append else 'w'
                with open(rp, mode, encoding='utf-8') as f:
                    f.write(content)
                return True
            except (OSError, PermissionError):
                return False

    def read_file(self, path, cwd='/'):
        with self._lock:
            try:
                rp, _ = self._resolve_path(path, cwd)
                if not rp.is_file():
                    return None
                return rp.read_text(encoding='utf-8')
            except (OSError, PermissionError, UnicodeDecodeError):
                return None

    def delete(self, path, cwd='/', recursive=False):
        with self._lock:
            try:
                rp, _ = self._resolve_path(path, cwd)
                if not rp.exists():
                    return False
                if rp == self.hostname_dir or rp == self.base:
                    return False
                resolved_v = self.resolve_virtual(path, cwd)
                if resolved_v in self.PROTECTED:
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
        with self._lock:
            try:
                src_rp, _ = self._resolve_path(src, cwd)
                dst_rp, _ = self._resolve_path(dst, cwd)
                if not src_rp.exists():
                    return False
                dst_rp.parent.mkdir(parents=True, exist_ok=True)
                if src_rp.is_file():
                    shutil.copy2(src_rp, dst_rp)
                else:
                    shutil.copytree(src_rp, dst_rp)
                return True
            except (OSError, PermissionError, shutil.Error):
                return False

    def move(self, src, dst, cwd='/'):
        with self._lock:
            try:
                src_rp, _ = self._resolve_path(src, cwd)
                dst_rp, _ = self._resolve_path(dst, cwd)
                if not src_rp.exists():
                    return False
                dst_rp.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_rp), str(dst_rp))
                return True
            except (OSError, PermissionError, shutil.Error):
                return False

    def rename(self, path, new_name, cwd='/'):
        with self._lock:
            try:
                rp, _ = self._resolve_path(path, cwd)
                if not rp.exists():
                    return False
                rp.rename(rp.parent / new_name)
                return True
            except (OSError, PermissionError):
                return False

    def list_dir(self, path, cwd='/'):
        with self._lock:
            try:
                rp, _ = self._resolve_path(path, cwd)
                if not rp.is_dir():
                    return None
                items = []
                for entry in sorted(rp.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
                    try:
                        items.append({
                            'name': entry.name, 'is_dir': entry.is_dir(),
                            'size': entry.stat().st_size if entry.is_file() else 0,
                            'modified': datetime.datetime.fromtimestamp(
                                entry.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                        })
                    except (OSError, PermissionError):
                        pass
                return items
            except (OSError, PermissionError):
                return None

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

    def disk_usage(self, disk=None):
        disk = disk or self.current_disk
        dp = self.hostname_dir / disk
        return self._dir_size(dp) if dp.exists() else 0

    def _dir_size(self, path):
        total = 0
        try:
            for f in path.rglob('*'):
                if f.is_file():
                    total += f.stat().st_size
        except (OSError, PermissionError):
            pass
        return total

    def get_real_path(self, path, cwd='/'):
        rp, _ = self._resolve_path(path, cwd)
        return rp

    def get_all_files_sorted(self, disk=None):
        disk = disk or self.current_disk
        dp = self.hostname_dir / disk
        files = []
        try:
            for f in dp.rglob('*'):
                if f.is_file():
                    files.append({
                        'path': '/' + str(f.relative_to(dp)).replace('\\', '/'),
                        'size': f.stat().st_size, 'name': f.name,
                    })
        except (OSError, PermissionError):
            pass
        files.sort(key=lambda x: x['size'], reverse=True)
        return files

    @staticmethod
    def fmt_size(size):
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"


# ═══════════════════════════════════════════════════════════════
#  RECYCLE BIN
# ═══════════════════════════════════════════════════════════════

class RecycleBin:
    def __init__(self, fs):
        self.fs = fs
        self.manifest_path = '/trash/.manifest.json'
        self._items = []
        self._next_id = 1
        self._load()

    def _load(self):
        data = self.fs.read_file(self.manifest_path)
        if data:
            try:
                obj = json.loads(data)
                self._items = obj.get('items', [])
                self._next_id = obj.get('next_id', len(self._items) + 1)
                return
            except (json.JSONDecodeError, KeyError):
                pass
        self._items = []
        self._next_id = 1

    def _save(self):
        self.fs.write_file(self.manifest_path,
                           json.dumps({'items': self._items, 'next_id': self._next_id},
                                      indent=2, ensure_ascii=False))

    def trash(self, path, cwd='/'):
        resolved = self.fs.resolve_virtual(path, cwd)
        if self.fs.is_protected(resolved):
            return False, "Cannot delete protected path"
        name = Path(resolved).name
        if not name:
            return False, "Invalid path"

        trash_name = f"{self._next_id}_{name}"
        src_rp = self.fs.get_real_path(resolved)
        dst_rp = self.fs.get_real_path(f'/trash/{trash_name}')
        if not src_rp.exists():
            return False, "Not found"

        try:
            shutil.move(str(src_rp), str(dst_rp))
        except (OSError, PermissionError, shutil.Error) as e:
            return False, str(e)

        self._items.append({
            'id': self._next_id, 'original_name': name,
            'original_path': resolved, 'trash_name': trash_name,
            'is_dir': dst_rp.is_dir(),
            'size': dst_rp.stat().st_size if dst_rp.is_file() else self.fs._dir_size(dst_rp),
            'deleted': datetime.datetime.now().isoformat(),
        })
        self._next_id += 1
        self._save()
        return True, ""

    def restore(self, item_id):
        item = None
        for it in self._items:
            if it['id'] == item_id:
                item = it
                break
        if not item:
            return False, "Not found in trash"

        src_rp = self.fs.get_real_path(f'/trash/{item["trash_name"]}')
        dst_rp = self.fs.get_real_path(item['original_path'])
        if not src_rp.exists():
            self._items = [x for x in self._items if x['id'] != item_id]
            self._save()
            return False, "File missing from trash"

        dst_rp.parent.mkdir(parents=True, exist_ok=True)
        if dst_rp.exists():
            base = dst_rp.stem
            ext = dst_rp.suffix
            counter = 1
            while dst_rp.exists():
                dst_rp = dst_rp.parent / f"{base}_{counter}{ext}"
                counter += 1

        try:
            shutil.move(str(src_rp), str(dst_rp))
        except (OSError, PermissionError, shutil.Error) as e:
            return False, str(e)

        self._items = [x for x in self._items if x['id'] != item_id]
        self._save()
        return True, ""

    def delete_permanently(self, item_id):
        item = None
        for it in self._items:
            if it['id'] == item_id:
                item = it
                break
        if not item:
            return False
        src_rp = self.fs.get_real_path(f'/trash/{item["trash_name"]}')
        if src_rp.exists():
            try:
                if src_rp.is_file():
                    src_rp.unlink()
                else:
                    shutil.rmtree(src_rp)
            except (OSError, PermissionError):
                return False
        self._items = [x for x in self._items if x['id'] != item_id]
        self._save()
        return True

    def empty(self):
        count = 0
        for item in list(self._items):
            if self.delete_permanently(item['id']):
                count += 1
        return count

    def get_items(self):
        return list(self._items)

    def count(self):
        return len(self._items)

    def total_size(self):
        return sum(it.get('size', 0) for it in self._items)


# ═══════════════════════════════════════════════════════════════
#  USER MANAGER
# ═══════════════════════════════════════════════════════════════

class UserManager:
    def __init__(self):
        self.users = {}

    def _hash(self, pw, salt):
        return hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 100000).hex()

    def _gen_salt(self):
        return os.urandom(16).hex()

    def create(self, name, pw=None, hint=''):
        if name in self.users:
            return False, "User already exists"
        if not name or not re.match(r'^[a-zA-Z0-9_]+$', name):
            return False, "Invalid username"
        salt = self._gen_salt()
        self.users[name] = {
            'pw': self._hash(pw, salt) if pw else '', 'salt': salt,
            'has_password': pw is not None and pw != '', 'uid': len(self.users),
            'home': f'/home/{name}', 'hint': hint,
            'created': datetime.datetime.now().isoformat(), 'disk': 'C',
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
        return self.users.get(name, {}).get('has_password', False)

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

    def delete(self, name):
        if name in self.users:
            del self.users[name]
            return True
        return False

    def list_users(self):
        return list(self.users.keys())


# ═══════════════════════════════════════════════════════════════
#  GUARDIAN
# ═══════════════════════════════════════════════════════════════

class Guardian:
    DANGER_KEYWORDS = ['os.system', 'subprocess', 'eval(', 'exec(', '__import__',
                       'shutil.rmtree', 'rm -rf', 'backdoor', 'virus', 'malware',
                       'trojan', 'ransomware', 'keylog', 'reverse_shell']
    WARN_KEYWORDS = ['open(', 'import os', 'import sys', 'base64', 'compile(',
                     'globals(', 'setattr', 'pickle', 'socket']

    def __init__(self):
        self.session_start = datetime.datetime.now()
        self.daily_limit = None
        self.app_folder_limit = 1 * 1024 * 1024

    def session_seconds(self):
        return int((datetime.datetime.now() - self.session_start).total_seconds())

    def session_str(self):
        s = self.session_seconds()
        h, r = divmod(s, 3600)
        m, sec = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def check_limit(self):
        if self.daily_limit and self.session_seconds() / 60 >= self.daily_limit:
            return True
        return False

    def scan_content(self, content):
        if not content:
            return {'level': 'SAFE', 'score': 0, 'threats': []}
        cl = content.lower()
        threats = []
        score = 0
        for kw in self.DANGER_KEYWORDS:
            if kw.lower() in cl:
                threats.append(f"DANGER: '{kw}'")
                score += 30
        for kw in self.WARN_KEYWORDS:
            if kw.lower() in cl:
                threats.append(f"WARN: '{kw}'")
                score += 10
        score = min(score, 100)
        if score >= 60:
            level = 'DANGEROUS'
        elif score >= 30:
            level = 'SUSPICIOUS'
        elif score >= 10:
            level = 'LOW RISK'
        else:
            level = 'SAFE'
        return {'level': level, 'score': score, 'threats': threats}

    def scan_x5(self, parsed):
        issues = []
        info = parsed.get('info', {})
        code = parsed.get('code', '')
        if not info.get('name'):
            issues.append(('err', 'Missing name in [INFO]'))
        if not info.get('version'):
            issues.append(('warn', 'Missing version'))
        if not info.get('author'):
            issues.append(('warn', 'Missing author'))
        if not code.strip():
            issues.append(('err', 'Empty [CODE] section'))
        sec = self.scan_content(code)
        for t in sec['threats']:
            issues.append(('err' if 'DANGER' in t else 'warn', f'Security: {t}'))

        lines = code.split('\n')
        for i, raw in enumerate(lines, 1):
            s = raw.strip()
            if not s or s.startswith('#'):
                continue
            if 'print(' in s and s.count('(') != s.count(')'):
                issues.append(('err', f'Line {i}: unmatched parentheses'))

        errors = sum(1 for lv, _ in issues if lv == 'err')
        warnings = sum(1 for lv, _ in issues if lv == 'warn')
        return {'issues': issues, 'errors': errors, 'warnings': warnings,
                'score': min(100, errors * 20 + warnings * 5)}

    def disk_report(self, fs):
        files = fs.get_all_files_sorted()
        return {'total': fs.disk_usage(), 'count': len(files), 'largest': files[:15]}

    def check_app_folders(self, fs):
        results = []
        items = fs.list_dir('/apps/data')
        if not items:
            return results
        for item in items:
            if item['is_dir']:
                rp = fs.get_real_path(f'/apps/data/{item["name"]}')
                size = fs._dir_size(rp) if rp.exists() else 0
                results.append({
                    'name': item['name'], 'size': size,
                    'limit': self.app_folder_limit,
                    'over': size > self.app_folder_limit if self.app_folder_limit else False,
                })
        return results

    def to_dict(self):
        return {'daily_limit': self.daily_limit, 'app_folder_limit': self.app_folder_limit}

    def from_dict(self, data):
        self.daily_limit = data.get('daily_limit')
        self.app_folder_limit = data.get('app_folder_limit', 1048576)


# ═══════════════════════════════════════════════════════════════
#  NOTIFICATION CENTER
# ═══════════════════════════════════════════════════════════════

class NotificationCenter:
    def __init__(self):
        self.notifications = []
        self._next_id = 1
        self._lock = threading.Lock()
        self._callbacks = []

    def on_notify(self, callback):
        self._callbacks.append(callback)

    def send(self, source, title, message, icon='info', priority='normal'):
        with self._lock:
            notif = {
                'id': self._next_id, 'source': source, 'title': title,
                'message': message, 'icon': icon, 'priority': priority,
                'time': datetime.datetime.now().isoformat(), 'read': False,
            }
            self._next_id += 1
            self.notifications.append(notif)
        for cb in self._callbacks:
            try:
                cb(notif)
            except Exception:
                pass
        return notif['id']

    def get_unread(self):
        with self._lock:
            return [n for n in self.notifications if not n['read']]

    def count_unread(self):
        with self._lock:
            return sum(1 for n in self.notifications if not n['read'])

    def mark_all_read(self):
        with self._lock:
            for n in self.notifications:
                n['read'] = True

    def get_all(self):
        with self._lock:
            return list(self.notifications)

    def clear(self):
        with self._lock:
            self.notifications.clear()

    def to_dict(self):
        with self._lock:
            return {'notifications': list(self.notifications), 'next_id': self._next_id}

    def from_dict(self, data):
        with self._lock:
            self.notifications = data.get('notifications', [])
            self._next_id = data.get('next_id', len(self.notifications) + 1)


# ═══════════════════════════════════════════════════════════════
#  X5 FORMAT PARSER
# ═══════════════════════════════════════════════════════════════

class X5Parser:
    """
    Формат .x5 — GUI-приложения для PyOS.

    [INFO]
    name: MyApp
    version: 1.0.0
    author: Username
    description: My cool app
    icon: 🎯
    width: 400
    height: 300
    resizable: true

    [CODE]
    # Python-код с доступом к self.frame, self.kernel, self.desktop, self.window
    # Доступны: tk, ttk, messagebox, simpledialog
    # Запрещено: os, sys, subprocess, shutil и т.д.
    [/CODE]

    [END]
    """

    @staticmethod
    def parse(content):
        result = {'info': {}, 'code': '', 'raw': content}

        m = re.search(r'\[INFO\](.*?)(?=\[CODE\]|\[END\]|\Z)', content, re.DOTALL)
        if m:
            for line in m.group(1).strip().split('\n'):
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    k, v = line.split(':', 1)
                    result['info'][k.strip().lower()] = v.strip()

        m = re.search(r'\[CODE\](.*?)\[/CODE\]', content, re.DOTALL)
        if m:
            result['code'] = m.group(1)

        return result

    @staticmethod
    def validate(parsed):
        errors = []
        warnings = []
        info = parsed.get('info', {})
        code = parsed.get('code', '')

        if not info.get('name'):
            errors.append("Missing 'name' in [INFO]")
        elif not re.match(r'^[a-zA-Z0-9_\- ]+$', info['name']):
            errors.append("Invalid app name (letters, digits, _, - only)")

        if not info.get('version'):
            warnings.append("Missing 'version'")
        if not info.get('author'):
            warnings.append("Missing 'author'")
        if not code.strip():
            errors.append("Empty [CODE] section")

        return errors, warnings

    @staticmethod
    def template(name, author):
        return f"""[INFO]
name: {name}
version: 1.0.0
author: {author}
description: A new X5 application
icon: 📦
width: 400
height: 300
resizable: true

[CODE]
# X5 Application: {name}
# Available: self.frame (tk.Frame), self.kernel, self.desktop, self.window
# Modules: tk, ttk, messagebox, simpledialog

import tkinter as tk

label = tk.Label(self.frame, text="Hello from {name}!",
                 font=('Tahoma', 14, 'bold'), bg='#C0C0C0')
label.pack(pady=30)

btn = tk.Button(self.frame, text="Click me!", font=('Tahoma', 10),
                command=lambda: messagebox.showinfo("{name}", "It works!"))
btn.pack(pady=10)
[/CODE]

[END]"""


class X5Runtime:
    """Исполняет X5-приложения в окне PyOS."""

    BLOCKED_IMPORTS = {'os', 'sys', 'subprocess', 'shutil', 'socket',
                       'http', 'urllib', 'ctypes', 'signal', 'multiprocessing'}

    def __init__(self, frame, kernel, desktop, window, app_name='unknown'):
        self.frame = frame
        self.kernel = kernel
        self.desktop = desktop
        self.window = window
        self.app_name = app_name

    def execute(self, code):
        safe_globals = {
            '__builtins__': {
                'print': print, 'len': len, 'range': range, 'int': int,
                'float': float, 'str': str, 'bool': bool, 'list': list,
                'dict': dict, 'tuple': tuple, 'set': set, 'enumerate': enumerate,
                'zip': zip, 'map': map, 'filter': filter, 'sorted': sorted,
                'min': min, 'max': max, 'abs': abs, 'round': round, 'sum': sum,
                'True': True, 'False': False, 'None': None,
                'isinstance': isinstance, 'hasattr': hasattr, 'getattr': getattr,
                'type': type, 'chr': chr, 'ord': ord,
                'Exception': Exception, 'ValueError': ValueError,
                'TypeError': TypeError, 'KeyError': KeyError,
            },
            'tk': tk, 'ttk': ttk,
            'messagebox': messagebox, 'simpledialog': simpledialog,
            'self': self,
            'math': math, 'random': random, 'datetime': datetime,
            'json': json, 're': re, 'time': time,
            'Win2kTheme': Win2kTheme, 'Win2kButton': Win2kButton,
        }
        try:
            exec(code, safe_globals)
        except Exception as e:
            self._show_error(e)

    def _show_error(self, error):
        for w in self.frame.winfo_children():
            w.destroy()
        tk.Label(self.frame, text="❌ Application Error", bg='#C0C0C0',
                 fg='#FF0000', font=('Tahoma', 11, 'bold')).pack(pady=15)
        tk.Label(self.frame, text=f"{type(error).__name__}: {error}",
                 bg='#C0C0C0', fg='#800000', font=('Consolas', 9),
                 wraplength=350).pack(padx=10, pady=5)
        trace = tb_module.format_exc()
        txt = tk.Text(self.frame, bg='#FFFFFF', fg='#000000', font=('Consolas', 8),
                      height=8, wrap='word', bd=2, relief='sunken')
        txt.pack(fill='both', expand=True, padx=10, pady=5)
        txt.insert('1.0', trace)
        txt.configure(state='disabled')

    # API для X5 приложений
    def read_file(self, path):
        return self.kernel.fs.read_file(path, f'/apps/data/{self.app_name}')

    def write_file(self, path, content):
        return self.kernel.fs.write_file(path, content, f'/apps/data/{self.app_name}')

    def notify(self, title, message, priority='normal'):
        self.kernel.notifications.send(self.app_name, title, message, 'app', priority)

    def get_data_path(self):
        return f'/apps/data/{self.app_name}'


# ═══════════════════════════════════════════════════════════════
#  X5 APP MANAGER
# ═══════════════════════════════════════════════════════════════

class X5AppManager:
    def __init__(self, fs, guardian, notifications=None):
        self.fs = fs
        self.guardian = guardian
        self.notifications = notifications
        self.apps = {}

    def load_installed(self):
        self.apps.clear()
        items = self.fs.list_dir('/apps/installed')
        if not items:
            return
        for item in items:
            if item['name'].endswith('.x5') and not item['is_dir']:
                content = self.fs.read_file('/apps/installed/' + item['name'])
                if content:
                    p = X5Parser.parse(content)
                    name = p['info'].get('name', item['name'][:-3])
                    self.apps[name] = p

    def install(self, filepath, cwd='/'):
        content = self.fs.read_file(filepath, cwd)
        if not content:
            return False, "File not found", None
        parsed = X5Parser.parse(content)
        errors, warnings = X5Parser.validate(parsed)
        name = parsed['info'].get('name', '')

        scan = self.guardian.scan_x5(parsed) if self.guardian else {'issues': [], 'errors': 0, 'warnings': 0}

        if not name:
            name = Path(filepath).stem

        # Всегда возвращаем parsed для показа в установщике
        return True, "", {
            'parsed': parsed, 'name': name,
            'errors': errors, 'warnings': warnings,
            'scan': scan, 'content': content,
        }

    def confirm_install(self, install_data):
        parsed = install_data['parsed']
        name = install_data['name']
        content = install_data['content']

        if not re.match(r'^[a-zA-Z0-9_\- ]+$', name):
            return False, "Invalid app name"

        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        self.fs.write_file(f'/apps/installed/{safe_name}.x5', content)
        self.fs.mkdir(f'/apps/data/{safe_name}')
        self.apps[name] = parsed

        if self.notifications:
            self.notifications.send('system', f"Installed: {name}",
                                    f"v{parsed['info'].get('version', '?')} by {parsed['info'].get('author', '?')}",
                                    'ok', 'normal')
        return True, f"'{name}' installed successfully!"

    def uninstall(self, name):
        if name not in self.apps:
            return False
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        del self.apps[name]
        self.fs.delete(f'/apps/installed/{safe_name}.x5')
        self.fs.delete(f'/apps/data/{safe_name}', recursive=True)
        if self.notifications:
            self.notifications.send('system', f"Removed: {name}", '', 'info', 'low')
        return True

    def get_app(self, name):
        return self.apps.get(name)

    def install_builtins(self):
        for name, content in self._builtins().items():
            self.fs.write_file(f'/apps/installed/{name}.x5', content)
            p = X5Parser.parse(content)
            an = p['info'].get('name', name)
            self.apps[an] = p
            self.fs.mkdir(f'/apps/data/{re.sub(r"[^a-zA-Z0-9_]", "_", an)}')

    def _builtins(self):
        return {
'hello_gui': """[INFO]
name: Hello GUI
version: 1.0.0
author: BitSoft Studios
description: Hello World GUI demo
icon: 👋
width: 350
height: 250
resizable: false

[CODE]
import tkinter as tk

tk.Label(self.frame, text="👋", font=('Segoe UI', 36), bg='#C0C0C0').pack(pady=15)
tk.Label(self.frame, text=f"Hello, {self.kernel.current_user}!",
         font=('Tahoma', 14, 'bold'), bg='#C0C0C0').pack()
tk.Label(self.frame, text=f"Welcome to PyOS {self.kernel.VERSION}",
         font=('Tahoma', 9), bg='#C0C0C0').pack(pady=5)

now = datetime.datetime.now()
tk.Label(self.frame, text=f"Time: {now.strftime('%H:%M:%S')}  Date: {now.strftime('%Y-%m-%d')}",
         font=('Tahoma', 8), bg='#C0C0C0', fg='#808080').pack(pady=10)

Win2kButton(self.frame, text="OK", width=80, height=25,
            command=self.window.close).pack(pady=10)
[/CODE]

[END]""",

'color_picker': """[INFO]
name: Color Picker
version: 1.0.0
author: BitSoft Studios
description: Pick and preview colors
icon: 🎨
width: 400
height: 350
resizable: false

[CODE]
import tkinter as tk

preview = tk.Canvas(self.frame, width=200, height=80, bg='#FF0000', bd=2, relief='sunken')
preview.pack(pady=10)

hex_var = tk.StringVar(value='#FF0000')
hex_label = tk.Label(self.frame, textvariable=hex_var, font=('Consolas', 12), bg='#C0C0C0')
hex_label.pack()

sliders_frame = tk.Frame(self.frame, bg='#C0C0C0')
sliders_frame.pack(pady=10, padx=20, fill='x')

r_var = tk.IntVar(value=255)
g_var = tk.IntVar(value=0)
b_var = tk.IntVar(value=0)

def update_color(*args):
    r, g, b = r_var.get(), g_var.get(), b_var.get()
    color = f'#{r:02x}{g:02x}{b:02x}'
    preview.configure(bg=color)
    hex_var.set(color.upper())

for label, var, fg in [('R:', r_var, '#FF0000'), ('G:', g_var, '#00AA00'), ('B:', b_var, '#0000FF')]:
    row = tk.Frame(sliders_frame, bg='#C0C0C0')
    row.pack(fill='x', pady=2)
    tk.Label(row, text=label, font=('Tahoma', 9, 'bold'), fg=fg, bg='#C0C0C0', width=3).pack(side='left')
    scale = tk.Scale(row, from_=0, to=255, orient='horizontal', variable=var,
                     command=update_color, bg='#C0C0C0', length=250, showvalue=True)
    scale.pack(side='left', fill='x', expand=True)

def copy_hex():
    try:
        self.frame.clipboard_clear()
        self.frame.clipboard_append(hex_var.get())
        self.notify("Color Picker", f"Copied: {hex_var.get()}")
    except Exception:
        pass

Win2kButton(self.frame, text="Copy HEX", width=90, height=25, command=copy_hex).pack(pady=10)
[/CODE]

[END]""",

'counter': """[INFO]
name: Counter
version: 1.0.0
author: BitSoft Studios
description: Simple click counter
icon: 🔢
width: 300
height: 200
resizable: false

[CODE]
import tkinter as tk

count = tk.IntVar(value=0)

tk.Label(self.frame, text="Click Counter", font=('Tahoma', 12, 'bold'), bg='#C0C0C0').pack(pady=10)

display = tk.Label(self.frame, textvariable=count, font=('Courier', 36, 'bold'),
                   bg='#FFFFFF', fg='#000080', bd=2, relief='sunken', width=8)
display.pack(pady=5)

btn_frame = tk.Frame(self.frame, bg='#C0C0C0')
btn_frame.pack(pady=10)

Win2kButton(btn_frame, text="-1", width=50, height=28,
            command=lambda: count.set(count.get() - 1)).pack(side='left', padx=4)
Win2kButton(btn_frame, text="+1", width=50, height=28,
            command=lambda: count.set(count.get() + 1)).pack(side='left', padx=4)
Win2kButton(btn_frame, text="Reset", width=60, height=28,
            command=lambda: count.set(0)).pack(side='left', padx=4)
[/CODE]

[END]""",
        }


# ═══════════════════════════════════════════════════════════════
#  KERNEL
# ═══════════════════════════════════════════════════════════════

class Kernel:
    VERSION = '16.1'
    BUILD = '2026.06.15'
    COMPANY = 'BitSoft Studios'

    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.hostname = 'PyOS'
        self.fs = None
        self.um = UserManager()
        self.notifications = NotificationCenter()
        self.guardian = Guardian()
        self.recycle_bin = None
        self.app_manager = None
        self.current_user = None
        self.boot_time = datetime.datetime.now()
        self.first_boot = True
        self._marker = Path(self.base_path) / '.pyos_host'

    def boot(self):
        self._load_hostname()
        if self._load_state():
            self.first_boot = False
            self.fs = RealFS(self.base_path)
            self.fs.hostname_dir = Path(self.base_path) / self.hostname
            self.fs.current_disk = 'C'
            self.recycle_bin = RecycleBin(self.fs)
            self.app_manager = X5AppManager(self.fs, self.guardian, self.notifications)
            self.app_manager.load_installed()
            return True
        self.first_boot = True
        return False

    def setup(self, hostname, username, password=None, hint=''):
        self.hostname = hostname or 'PyOS'
        self._save_hostname()
        self.fs = RealFS(self.base_path)
        self.fs.init_structure(self.hostname)
        ok, err = self.um.create(username, password, hint)
        if not ok:
            return False, err
        for d in [f'/home/{username}', f'/home/{username}/Desktop',
                  f'/home/{username}/Documents', f'/home/{username}/Pictures']:
            self.fs.mkdir(d)
        self.fs.write_file(f'/home/{username}/Documents/Welcome.txt',
                           f'Welcome to PyOS {self.VERSION}!\n\n'
                           f'This is your Documents folder.\n-- {self.COMPANY}\n')
        self.recycle_bin = RecycleBin(self.fs)
        self.app_manager = X5AppManager(self.fs, self.guardian, self.notifications)
        self.app_manager.install_builtins()
        self.save_state()
        return True, ""

    def login(self, username, password=''):
        if self.um.auth(username, password):
            self.current_user = username
            self.fs.current_disk = self.um.users[username].get('disk', 'C')
            return True
        return False

    def logout(self):
        self.save_state()
        self.current_user = None

    def get_home(self):
        if self.current_user:
            return self.um.users[self.current_user].get('home', '/')
        return '/'

    def uptime_str(self):
        s = int((datetime.datetime.now() - self.boot_time).total_seconds())
        h, r = divmod(s, 3600)
        m, sec = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

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

    def save_state(self):
        try:
            state = {
                'hostname': self.hostname, 'version': self.VERSION,
                'users': {'users': self.um.users},
                'notifications': self.notifications.to_dict(),
                'guardian': self.guardian.to_dict(),
            }
            sp = self._save_path()
            sp.parent.mkdir(parents=True, exist_ok=True)
            with open(sp, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            self._save_hostname()
            return True
        except (OSError, PermissionError):
            return False

    def _load_state(self):
        sp = self._save_path()
        if not sp.exists():
            return False
        try:
            with open(sp, 'r', encoding='utf-8') as f:
                st = json.load(f)
            self.hostname = st.get('hostname', 'PyOS')
            self.um.users = st.get('users', {}).get('users', {})
            if 'notifications' in st:
                self.notifications.from_dict(st['notifications'])
            if 'guardian' in st:
                self.guardian.from_dict(st['guardian'])
            return True
        except (json.JSONDecodeError, OSError):
            return False


# ═══════════════════════════════════════════════════════════════
#  WIN2K BUTTON
# ═══════════════════════════════════════════════════════════════

class Win2kButton(tk.Canvas):
    def __init__(self, parent, text="", command=None, width=75, height=23,
                 font_spec=('Tahoma', 8), icon=None, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=Win2kTheme.BUTTON_BG, highlightthickness=0,
                         cursor='hand2', **kwargs)
        self._command = command
        self._text = text
        self._icon = icon
        self._pressed = False
        self._width = width
        self._height = height
        self._font = font_spec
        self._draw()
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<Leave>', self._on_leave)

    def _draw(self):
        self.delete('all')
        w, h = self._width, self._height
        if self._pressed:
            self.create_line(0, 0, w, 0, fill='#404040')
            self.create_line(0, 0, 0, h, fill='#404040')
            self.create_line(1, 1, w - 1, 1, fill='#808080')
            self.create_line(1, 1, 1, h - 1, fill='#808080')
            self.create_line(0, h - 1, w, h - 1, fill='#FFFFFF')
            self.create_line(w - 1, 0, w - 1, h, fill='#FFFFFF')
            offset = 1
        else:
            self.create_line(0, 0, w, 0, fill='#FFFFFF')
            self.create_line(0, 0, 0, h, fill='#FFFFFF')
            self.create_line(1, 1, w - 2, 1, fill='#DFDFDF')
            self.create_line(1, 1, 1, h - 2, fill='#DFDFDF')
            self.create_line(0, h - 1, w, h - 1, fill='#404040')
            self.create_line(w - 1, 0, w - 1, h, fill='#404040')
            self.create_line(1, h - 2, w - 1, h - 2, fill='#808080')
            self.create_line(w - 2, 1, w - 2, h - 1, fill='#808080')
            offset = 0
        display = f"{self._icon} {self._text}" if self._icon and self._text else (self._icon or self._text)
        self.create_text(w // 2 + offset, h // 2 + offset,
                         text=display, font=self._font, fill='#000000')

    def _on_press(self, e):
        self._pressed = True
        self._draw()

    def _on_release(self, e):
        self._pressed = False
        self._draw()
        if self._command and 0 <= e.x <= self._width and 0 <= e.y <= self._height:
            self._command()

    def _on_leave(self, e):
        if self._pressed:
            self._pressed = False
            self._draw()

    def configure_text(self, text):
        self._text = text
        self._draw()


# ═══════════════════════════════════════════════════════════════
#  WIN2K WINDOW
# ═══════════════════════════════════════════════════════════════

class Win2kWindow(tk.Frame):
    _window_counter = 0

    def __init__(self, desktop, title="Window", width=450, height=350,
                 resizable=True, icon=None, on_close=None):
        Win2kWindow._window_counter += 1
        self.win_id = Win2kWindow._window_counter
        self.desktop = desktop
        self.title_text = title
        self._icon = icon or ""
        self._on_close_cb = on_close
        self._resizable = resizable
        self._minimized = False
        self.w = width
        self.h = height
        offset = (self.win_id % 10) * 25
        self.x = 50 + offset
        self.y = 30 + offset

        super().__init__(desktop.canvas, bd=0, highlightthickness=0)
        self._build()
        self._canvas_id = desktop.canvas.create_window(
            self.x, self.y, window=self, anchor='nw', width=self.w, height=self.h)
        self._drag_data = {'x': 0, 'y': 0}
        desktop.add_taskbar_entry(self)
        self.focus_window()

    def _build(self):
        T = Win2kTheme
        self.configure(bg=T.WINDOW_BORDER_DARK)
        inner = tk.Frame(self, bg=T.WINDOW_BG, bd=0)
        inner.pack(fill='both', expand=True, padx=2, pady=2)

        self.titlebar = tk.Frame(inner, bg=T.WINDOW_TITLE_ACTIVE, height=T.TITLEBAR_HEIGHT)
        self.titlebar.pack(fill='x', side='top')
        self.titlebar.pack_propagate(False)

        title_display = f" {self._icon} {self.title_text}" if self._icon else f" {self.title_text}"
        self.title_label = tk.Label(self.titlebar, text=title_display,
                                    bg=T.WINDOW_TITLE_ACTIVE, fg=T.WINDOW_TITLE_TEXT,
                                    font=('Tahoma', 8, 'bold'), anchor='w')
        self.title_label.pack(side='left', fill='x', expand=True, padx=2)

        btn_frame = tk.Frame(self.titlebar, bg=T.WINDOW_TITLE_ACTIVE)
        btn_frame.pack(side='right', padx=2)
        bs = {'width': 16, 'height': 14, 'font_spec': ('Marlett', 7)}
        Win2kButton(btn_frame, text="0", command=self.minimize, **bs).pack(side='left', padx=1)
        Win2kButton(btn_frame, text="1", command=self.maximize_toggle, **bs).pack(side='left', padx=1)
        Win2kButton(btn_frame, text="r", command=self.close, **bs).pack(side='left', padx=1)

        self.client = tk.Frame(inner, bg=T.WINDOW_BG)
        self.client.pack(fill='both', expand=True)

        if self._resizable:
            grip = tk.Label(inner, text="◢", bg=T.WINDOW_BG, fg='#808080',
                            font=('Arial', 8), cursor='bottom_right_corner')
            grip.place(relx=1.0, rely=1.0, anchor='se')
            grip.bind('<ButtonPress-1>', self._resize_start)
            grip.bind('<B1-Motion>', self._resize_motion)

        self.titlebar.bind('<ButtonPress-1>', self._drag_start)
        self.titlebar.bind('<B1-Motion>', self._drag_motion)
        self.title_label.bind('<ButtonPress-1>', self._drag_start)
        self.title_label.bind('<B1-Motion>', self._drag_motion)
        self.titlebar.bind('<Double-Button-1>', lambda e: self.maximize_toggle())
        self.bind('<ButtonPress-1>', lambda e: self.focus_window())
        self.client.bind('<ButtonPress-1>', lambda e: self.focus_window())

    def _drag_start(self, e):
        self._drag_data['x'] = e.x_root - self.x
        self._drag_data['y'] = e.y_root - self.y
        self.focus_window()

    def _drag_motion(self, e):
        self.x = e.x_root - self._drag_data['x']
        self.y = max(0, e.y_root - self._drag_data['y'])
        self.desktop.canvas.coords(self._canvas_id, self.x, self.y)

    def _resize_start(self, e):
        self._resize_data = {'x': e.x_root, 'y': e.y_root, 'w': self.w, 'h': self.h}

    def _resize_motion(self, e):
        if hasattr(self, '_resize_data') and self._resize_data:
            self.w = max(200, self._resize_data['w'] + e.x_root - self._resize_data['x'])
            self.h = max(100, self._resize_data['h'] + e.y_root - self._resize_data['y'])
            self.desktop.canvas.itemconfig(self._canvas_id, width=self.w, height=self.h)

    def focus_window(self):
        self.desktop.canvas.tag_raise(self._canvas_id)
        T = Win2kTheme
        self.titlebar.configure(bg=T.WINDOW_TITLE_ACTIVE)
        self.title_label.configure(bg=T.WINDOW_TITLE_ACTIVE, fg=T.WINDOW_TITLE_TEXT)
        for win in self.desktop.windows:
            if win is not self and not win._minimized:
                win.titlebar.configure(bg=T.WINDOW_TITLE_INACTIVE)
                win.title_label.configure(bg=T.WINDOW_TITLE_INACTIVE)

    def minimize(self):
        self._minimized = True
        self.desktop.canvas.itemconfig(self._canvas_id, state='hidden')
        self.desktop.update_taskbar()

    def restore(self):
        self._minimized = False
        self.desktop.canvas.itemconfig(self._canvas_id, state='normal')
        self.focus_window()
        self.desktop.update_taskbar()

    def maximize_toggle(self):
        if hasattr(self, '_maximized') and self._maximized:
            self.x, self.y = self._prev_pos
            self.w, self.h = self._prev_size
            self._maximized = False
        else:
            self._prev_pos = (self.x, self.y)
            self._prev_size = (self.w, self.h)
            self.x, self.y = 0, 0
            self.w = self.desktop.canvas.winfo_width()
            self.h = self.desktop.canvas.winfo_height()
            self._maximized = True
        self.desktop.canvas.coords(self._canvas_id, self.x, self.y)
        self.desktop.canvas.itemconfig(self._canvas_id, width=self.w, height=self.h)

    def close(self):
        if self._on_close_cb:
            self._on_close_cb()
        self.desktop.remove_window(self)
        self.desktop.canvas.delete(self._canvas_id)
        self.destroy()

    def set_title(self, title):
        self.title_text = title
        display = f" {self._icon} {title}" if self._icon else f" {title}"
        self.title_label.configure(text=display)
        self.desktop.update_taskbar()


# ═══════════════════════════════════════════════════════════════
#  DESKTOP
# ═══════════════════════════════════════════════════════════════

class Desktop:
    def __init__(self, root, kernel):
        self.root = root
        self.kernel = kernel
        self.windows = []
        self._taskbar_buttons = {}
        self._build()
        self._create_desktop_icons()
        self._start_clock()

    def _build(self):
        T = Win2kTheme
        self.canvas = tk.Canvas(self.root, bg=T.DESKTOP_BG, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, side='top')

        self.taskbar = tk.Frame(self.root, bg=T.TASKBAR_BG, height=T.TASKBAR_HEIGHT, bd=0)
        self.taskbar.pack(fill='x', side='bottom')
        self.taskbar.pack_propagate(False)

        tk.Frame(self.taskbar, bg='#DFDFDF', height=1).pack(fill='x', side='top')
        tk.Frame(self.taskbar, bg='#FFFFFF', height=1).pack(fill='x', side='top')

        self.start_btn = Win2kButton(self.taskbar, text="Start", icon="🪟",
                                     width=80, height=24, font_spec=('Tahoma', 8, 'bold'),
                                     command=self._toggle_start_menu)
        self.start_btn.pack(side='left', padx=(3, 0), pady=3)

        tk.Frame(self.taskbar, width=2, bg='#808080').pack(side='left', fill='y', padx=3, pady=4)

        self.taskbar_area = tk.Frame(self.taskbar, bg=T.TASKBAR_BG)
        self.taskbar_area.pack(side='left', fill='both', expand=True, pady=3)

        self.tray = tk.Frame(self.taskbar, bg=T.TASKBAR_BG, bd=1, relief='sunken')
        self.tray.pack(side='right', padx=3, pady=3)

        self.clock_label = tk.Label(self.tray, text="00:00", bg=T.TASKBAR_BG,
                                    fg=T.TEXT_FG, font=('Tahoma', 8), padx=8)
        self.clock_label.pack(side='right')

        self.notif_icon = tk.Label(self.tray, text="🔔", bg=T.TASKBAR_BG,
                                   font=('Segoe UI', 9), cursor='hand2')
        self.notif_icon.pack(side='right', padx=2)
        self.notif_icon.bind('<Button-1>', lambda e: self._show_notifications())

        self._start_menu_visible = False
        self._start_menu = None

    def _create_desktop_icons(self):
        T = Win2kTheme
        icons = [
            ("My Computer", T.ICON_COMPUTER, self.open_my_computer),
            ("My Documents", T.ICON_FOLDER, self.open_my_documents),
            ("Terminal", T.ICON_TERMINAL, self.open_terminal),
            ("Notepad", T.ICON_NOTEPAD, self.open_notepad),
            ("Calculator", T.ICON_CALC, self.open_calculator),
            ("Recycle Bin", T.ICON_TRASH, self.open_recycle_bin),
        ]
        x_start, y_start = 30, 20
        for i, (name, icon, action) in enumerate(icons):
            y = y_start + i * T.DESKTOP_ICON_SPACING
            icon_id = self.canvas.create_text(x_start, y, text=icon, font=('Segoe UI', 20),
                                              fill='white', anchor='n')
            text_id = self.canvas.create_text(x_start, y + 35, text=name, font=('Tahoma', 8),
                                              fill='white', anchor='n', width=70, justify='center')
            for item_id in (icon_id, text_id):
                self.canvas.tag_bind(item_id, '<Double-Button-1>', lambda e, a=action: a())
                self.canvas.tag_bind(item_id, '<Enter>',
                                     lambda e, tid=text_id: self.canvas.itemconfig(tid, fill='#AACCFF'))
                self.canvas.tag_bind(item_id, '<Leave>',
                                     lambda e, tid=text_id: self.canvas.itemconfig(tid, fill='white'))

    def _start_clock(self):
        now = datetime.datetime.now().strftime('%H:%M')
        self.clock_label.configure(text=now)
        unread = self.kernel.notifications.count_unread()
        self.notif_icon.configure(text="🔔" if unread == 0 else f"🔔{unread}")
        self.root.after(10000, self._start_clock)

    # ═══ Start Menu ═══

    def _toggle_start_menu(self):
        if self._start_menu_visible:
            self._close_start_menu()
        else:
            self._show_start_menu()

    def _show_start_menu(self):
        T = Win2kTheme
        self._start_menu_visible = True
        self._start_menu = tk.Frame(self.root, bg=T.WINDOW_BORDER_DARK, bd=0)
        inner = tk.Frame(self._start_menu, bg=T.START_BG, bd=0)
        inner.pack(fill='both', expand=True, padx=2, pady=2)

        banner = tk.Frame(inner, bg=T.START_BANNER_BG, width=25)
        banner.pack(side='left', fill='y')
        banner.pack_propagate(False)
        tk.Label(banner, text=f"Py\nOS", bg=T.START_BANNER_BG, fg=T.START_BANNER_FG,
                 font=('Tahoma', 7, 'bold'), justify='center').pack(side='bottom', pady=5)

        menu_frame = tk.Frame(inner, bg=T.START_BG)
        menu_frame.pack(side='left', fill='both', expand=True)

        # Собираем X5 приложения
        x5_items = []
        if self.kernel.app_manager:
            for name, data in self.kernel.app_manager.apps.items():
                icon = data['info'].get('icon', '📦')
                x5_items.append((icon, name, lambda n=name: self.open_x5_app(n)))

        items = [
            (T.ICON_FOLDER, "My Documents", self.open_my_documents),
            (T.ICON_COMPUTER, "My Computer", self.open_my_computer),
            (T.ICON_TERMINAL, "Command Prompt", self.open_terminal),
            (T.ICON_NOTEPAD, "Notepad", self.open_notepad),
            (T.ICON_CALC, "Calculator", self.open_calculator),
            (T.ICON_PAINT, "Paint", self.open_paint),
            (T.ICON_CLOCK, "Clock", self.open_clock),
            (T.ICON_GAMES, "Minesweeper", self.open_minesweeper),
            None,
        ]
        if x5_items:
            items.append(("header", "── Applications ──", None))
            items.extend(x5_items)
            items.append(None)
        items.extend([
            (T.ICON_SETTINGS, "Control Panel", self.open_control_panel),
            (T.ICON_SHIELD, "Guardian", self.open_guardian),
            (T.ICON_TRASH, "Recycle Bin", self.open_recycle_bin),
            (T.ICON_INFO, "About PyOS", self.open_about),
            None,
            (T.ICON_SHUTDOWN, "Shut Down...", self._shutdown_dialog),
        ])

        for item in items:
            if item is None:
                tk.Frame(menu_frame, bg='#808080', height=1).pack(fill='x', padx=3, pady=2)
                continue
            icon, label, action = item
            if icon == "header":
                tk.Label(menu_frame, text=label, bg=T.START_BG, fg='#808080',
                         font=('Tahoma', 7), anchor='w', padx=8).pack(fill='x')
                continue

            btn = tk.Frame(menu_frame, bg=T.START_BG, cursor='hand2')
            btn.pack(fill='x', padx=2)
            lbl = tk.Label(btn, text=f" {icon}  {label}", bg=T.START_BG, fg=T.MENU_FG,
                           font=('Tahoma', 9), anchor='w', padx=5, pady=2)
            lbl.pack(fill='x')

            def make_hover(widget, frame):
                def enter(e):
                    frame.configure(bg=T.MENU_HIGHLIGHT_BG)
                    widget.configure(bg=T.MENU_HIGHLIGHT_BG, fg=T.MENU_HIGHLIGHT_FG)
                def leave(e):
                    frame.configure(bg=T.START_BG)
                    widget.configure(bg=T.START_BG, fg=T.MENU_FG)
                return enter, leave

            enter_fn, leave_fn = make_hover(lbl, btn)
            for w in (btn, lbl):
                w.bind('<Enter>', enter_fn)
                w.bind('<Leave>', leave_fn)

            def make_click(a):
                def click(e):
                    self._close_start_menu()
                    if a:
                        a()
                return click
            for w in (btn, lbl):
                w.bind('<Button-1>', make_click(action))

        menu_h = min(500, sum(28 if i else 5 for i in items) + 10)
        taskbar_y = self.root.winfo_height() - Win2kTheme.TASKBAR_HEIGHT
        self._start_menu.place(x=0, y=max(0, taskbar_y - menu_h), width=220, height=menu_h)
        self.root.bind('<Button-1>', self._click_outside_start, add='+')

    def _close_start_menu(self):
        if self._start_menu:
            self._start_menu.destroy()
            self._start_menu = None
        self._start_menu_visible = False
        try:
            self.root.unbind('<Button-1>')
        except Exception:
            pass

    def _click_outside_start(self, event):
        if self._start_menu_visible and self._start_menu:
            widget = event.widget
            try:
                if not str(widget).startswith(str(self._start_menu)):
                    if widget != self.start_btn:
                        self._close_start_menu()
            except Exception:
                self._close_start_menu()

    # ═══ Window management ═══

    def add_taskbar_entry(self, window):
        self.windows.append(window)
        self.update_taskbar()

    def remove_window(self, window):
        if window in self.windows:
            self.windows.remove(window)
        self.update_taskbar()

    def update_taskbar(self):
        for widget in self.taskbar_area.winfo_children():
            widget.destroy()
        self._taskbar_buttons.clear()
        for win in self.windows:
            display = f"{win._icon} {win.title_text}" if win._icon else win.title_text
            if len(display) > 20:
                display = display[:18] + "…"
            btn = Win2kButton(self.taskbar_area, text=display, width=140, height=22,
                              font_spec=('Tahoma', 7), command=lambda w=win: self._taskbar_click(w))
            btn.pack(side='left', padx=1)
            self._taskbar_buttons[win.win_id] = btn

    def _taskbar_click(self, window):
        if window._minimized:
            window.restore()
        else:
            window.focus_window()

    # ═══ Notifications ═══

    def _show_notifications(self):
        win = Win2kWindow(self, title="Notifications", width=350, height=300, icon="🔔")
        frame = win.client
        T = Win2kTheme

        toolbar = tk.Frame(frame, bg=T.WINDOW_BG)
        toolbar.pack(fill='x', padx=4, pady=4)

        def refresh():
            for w in list_frame_inner.winfo_children():
                w.destroy()
            for n in reversed(self.kernel.notifications.get_all()):
                mark = "●" if not n['read'] else "○"
                t = n['time'][11:16]
                tk.Label(list_frame_inner, text=f" {mark} [{t}] {n['source']}: {n['title']}",
                         bg=T.TEXT_BG, font=('Tahoma', 8), anchor='w').pack(fill='x')

        Win2kButton(toolbar, text="Mark All Read", width=100, height=20, font_spec=('Tahoma', 7),
                    command=lambda: (self.kernel.notifications.mark_all_read(), refresh())).pack(side='left')
        Win2kButton(toolbar, text="Clear All", width=70, height=20, font_spec=('Tahoma', 7),
                    command=lambda: (self.kernel.notifications.clear(), refresh())).pack(side='left', padx=4)

        list_outer = tk.Frame(frame, bg=T.TEXT_BG, bd=2, relief='sunken')
        list_outer.pack(fill='both', expand=True, padx=4, pady=(0, 4))
        canvas_n = tk.Canvas(list_outer, bg=T.TEXT_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_outer, command=canvas_n.yview)
        list_frame_inner = tk.Frame(canvas_n, bg=T.TEXT_BG)
        list_frame_inner.bind('<Configure>', lambda e: canvas_n.configure(scrollregion=canvas_n.bbox('all')))
        canvas_n.create_window((0, 0), window=list_frame_inner, anchor='nw')
        canvas_n.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas_n.pack(fill='both', expand=True)
        refresh()

    # ═══ Shutdown ═══

    def _shutdown_dialog(self):
        win = Win2kWindow(self, title="Shut Down PyOS", width=300, height=180,
                          icon=Win2kTheme.ICON_SHUTDOWN, resizable=False)
        frame = win.client
        T = Win2kTheme
        tk.Label(frame, text="What do you want the computer to do?",
                 bg=T.WINDOW_BG, font=('Tahoma', 9)).pack(pady=15)
        bf = tk.Frame(frame, bg=T.WINDOW_BG)
        bf.pack(pady=10)

        def do_shutdown():
            win.close()
            self.kernel.save_state()
            self.root.quit()

        Win2kButton(bf, text="Shut Down", width=90, height=25, command=do_shutdown).pack(side='left', padx=5)
        Win2kButton(bf, text="Restart", width=90, height=25, command=do_shutdown).pack(side='left', padx=5)
        Win2kButton(bf, text="Cancel", width=70, height=25, command=win.close).pack(side='left', padx=5)

    # ═══════════════════════════════════════════════════════════
    #  APP LAUNCHERS
    # ═══════════════════════════════════════════════════════════

    def open_my_computer(self):
        win = Win2kWindow(self, title="My Computer", width=550, height=400, icon=Win2kTheme.ICON_COMPUTER)
        FileExplorer(win.client, self, self.kernel, '/')

    def open_my_documents(self):
        docs = f'/home/{self.kernel.current_user}/Documents'
        win = Win2kWindow(self, title="My Documents", width=550, height=400, icon=Win2kTheme.ICON_FOLDER)
        FileExplorer(win.client, self, self.kernel, docs)

    def open_terminal(self):
        win = Win2kWindow(self, title="Command Prompt", width=600, height=400, icon=Win2kTheme.ICON_TERMINAL)
        TerminalApp(win.client, self, self.kernel, win)

    def open_notepad(self, filepath=None):
        win = Win2kWindow(self, title="Notepad", width=500, height=400, icon=Win2kTheme.ICON_NOTEPAD)
        NotepadApp(win.client, self, self.kernel, win, filepath)

    def open_calculator(self):
        win = Win2kWindow(self, title="Calculator", width=250, height=300,
                          icon=Win2kTheme.ICON_CALC, resizable=False)
        CalculatorApp(win.client)

    def open_paint(self):
        win = Win2kWindow(self, title="Paint", width=600, height=450, icon=Win2kTheme.ICON_PAINT)
        PaintApp(win.client, win)

    def open_clock(self):
        win = Win2kWindow(self, title="Clock", width=420, height=480, icon=Win2kTheme.ICON_CLOCK)
        ClockApp(win.client, self, self.kernel, win)

    def open_minesweeper(self):
        win = Win2kWindow(self, title="Minesweeper", width=300, height=370,
                          icon=Win2kTheme.ICON_GAMES, resizable=False)
        MinesweeperApp(win.client)

    def open_control_panel(self):
        win = Win2kWindow(self, title="Control Panel", width=450, height=350, icon=Win2kTheme.ICON_SETTINGS)
        ControlPanelApp(win.client, self, self.kernel)

    def open_guardian(self):
        win = Win2kWindow(self, title="Guardian — System Monitor", width=500, height=450,
                          icon=Win2kTheme.ICON_SHIELD)
        GuardianApp(win.client, self, self.kernel)

    def open_recycle_bin(self):
        win = Win2kWindow(self, title="Recycle Bin", width=450, height=350, icon=Win2kTheme.ICON_TRASH)
        RecycleBinApp(win.client, self, self.kernel, win)

    def open_about(self):
        win = Win2kWindow(self, title="About PyOS", width=380, height=300,
                          icon=Win2kTheme.ICON_INFO, resizable=False)
        AboutApp(win.client, self.kernel)

    def open_x5_app(self, name):
        app_data = self.kernel.app_manager.get_app(name)
        if not app_data:
            messagebox.showerror("Error", f"App not found: {name}")
            return
        info = app_data['info']
        w = int(info.get('width', 400))
        h = int(info.get('height', 300))
        resizable = info.get('resizable', 'true').lower() == 'true'
        icon = info.get('icon', '📦')

        win = Win2kWindow(self, title=name, width=w, height=h, resizable=resizable, icon=icon)
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        self.kernel.fs.mkdir(f'/apps/data/{safe_name}')
        runtime = X5Runtime(win.client, self.kernel, self, win, safe_name)
        runtime.execute(app_data['code'])

    def open_x5_installer(self, filepath, cwd='/'):
        """Открыть установщик X5 для файла."""
        X5InstallerApp(self, self.kernel, filepath, cwd)

    def open_file_by_extension(self, path):
        """Открыть файл по расширению."""
        ext = Path(path).suffix.lower()
        if ext == '.x5':
            self.open_x5_installer(path)
        elif ext in ('.txt', '.json', '.cfg', '.md', '.log', '.py', '.x4', ''):
            self.open_notepad(path)
        else:
            self.open_notepad(path)


# ═══════════════════════════════════════════════════════════════
#  FILE EXPLORER
# ═══════════════════════════════════════════════════════════════

class FileExplorer:
    def __init__(self, parent, desktop, kernel, initial_path='/'):
        self.parent = parent
        self.desktop = desktop
        self.kernel = kernel
        self.current_path = initial_path
        self._build()
        self.navigate(initial_path)

    def _build(self):
        T = Win2kTheme
        toolbar = tk.Frame(self.parent, bg=T.WINDOW_BG, bd=1, relief='raised')
        toolbar.pack(fill='x')

        for text, cmd in [("⬆ Up", self._go_up), ("🏠 Home", self._go_home),
                          ("📁 New Folder", self._new_folder), ("📄 New File", self._new_file),
                          ("🗑 Trash", self._trash_selected)]:
            Win2kButton(toolbar, text=text, width=80 if 'Folder' in text else 60,
                        height=20, font_spec=('Tahoma', 7), command=cmd).pack(side='left', padx=2, pady=2)

        addr_frame = tk.Frame(self.parent, bg=T.WINDOW_BG)
        addr_frame.pack(fill='x', padx=4, pady=2)
        tk.Label(addr_frame, text="Address:", bg=T.WINDOW_BG, font=('Tahoma', 8)).pack(side='left')
        self.addr_entry = tk.Entry(addr_frame, font=('Tahoma', 8), bg=T.TEXT_BG, relief='sunken', bd=2)
        self.addr_entry.pack(side='left', fill='x', expand=True, padx=4)
        self.addr_entry.bind('<Return>', lambda e: self.navigate(self.addr_entry.get()))
        Win2kButton(addr_frame, text="Go", width=35, height=18, font_spec=('Tahoma', 7),
                    command=lambda: self.navigate(self.addr_entry.get())).pack(side='left')

        list_frame = tk.Frame(self.parent, bg=T.TEXT_BG, bd=2, relief='sunken')
        list_frame.pack(fill='both', expand=True, padx=4, pady=(0, 2))

        columns = ('name', 'size', 'type', 'modified')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', selectmode='browse')
        for col, text, w, anchor in [('name', 'Name', 200, 'w'), ('size', 'Size', 80, 'e'),
                                      ('type', 'Type', 80, 'w'), ('modified', 'Modified', 120, 'w')]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor=anchor)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', self._on_double_click)
        self.tree.bind('<Button-3>', self._context_menu)

        self.status = tk.Label(self.parent, text="Ready", bg=T.WINDOW_BG,
                               font=('Tahoma', 7), anchor='w', bd=1, relief='sunken')
        self.status.pack(fill='x', padx=4, pady=(0, 4))

    def navigate(self, path):
        resolved = self.kernel.fs.resolve_virtual(path, self.current_path)
        if not self.kernel.fs.is_dir(resolved):
            if self.kernel.fs.is_file(resolved):
                self.desktop.open_file_by_extension(resolved)
                return
            self.status.configure(text=f"Not found: {resolved}")
            return
        self.current_path = resolved
        self.addr_entry.delete(0, 'end')
        self.addr_entry.insert(0, f"{self.kernel.fs.current_disk}:{resolved}")

        for item in self.tree.get_children():
            self.tree.delete(item)
        items = self.kernel.fs.list_dir(resolved)
        if items is None:
            self.status.configure(text="Cannot read directory")
            return
        for item in items:
            icon = "📁" if item['is_dir'] else self._get_icon(item['name'])
            name = f"{icon} {item['name']}"
            size = "" if item['is_dir'] else RealFS.fmt_size(item['size'])
            ftype = "Folder" if item['is_dir'] else self._get_file_type(item['name'])
            self.tree.insert('', 'end', values=(name, size, ftype, item['modified']))
        self.status.configure(text=f"{len(items)} item(s)")

    def _get_icon(self, name):
        ext = Path(name).suffix.lower()
        icons = {'.x5': '📦', '.txt': '📄', '.json': '📋', '.py': '🐍', '.x4': '📦'}
        return icons.get(ext, '📄')

    def _get_file_type(self, name):
        ext = Path(name).suffix.lower()
        types = {'.txt': 'Text Document', '.json': 'JSON File', '.x5': 'X5 Application',
                 '.x4': 'X4 Application', '.py': 'Python Script', '.md': 'Markdown',
                 '.cfg': 'Config File', '.log': 'Log File'}
        return types.get(ext, f'{ext} File' if ext else 'File')

    def _get_selected_name(self):
        selection = self.tree.selection()
        if not selection:
            return None
        raw = self.tree.item(selection[0])['values'][0]
        return raw.split(' ', 1)[1] if ' ' in str(raw) else str(raw)

    def _on_double_click(self, event):
        name = self._get_selected_name()
        if not name:
            return
        target = self.current_path.rstrip('/') + '/' + name
        if self.kernel.fs.is_dir(target):
            self.navigate(target)
        elif self.kernel.fs.is_file(target):
            self.desktop.open_file_by_extension(target)

    def _go_up(self):
        if self.current_path != '/':
            self.navigate('/'.join(self.current_path.rstrip('/').split('/')[:-1]) or '/')

    def _go_home(self):
        self.navigate(self.kernel.get_home())

    def _new_folder(self):
        name = simpledialog.askstring("New Folder", "Folder name:")
        if name:
            if self.kernel.fs.mkdir(self.current_path.rstrip('/') + '/' + name):
                self.navigate(self.current_path)
            else:
                messagebox.showerror("Error", "Cannot create folder")

    def _new_file(self):
        name = simpledialog.askstring("New File", "File name:")
        if name:
            if self.kernel.fs.write_file(self.current_path.rstrip('/') + '/' + name, ''):
                self.navigate(self.current_path)
            else:
                messagebox.showerror("Error", "Cannot create file")

    def _trash_selected(self):
        name = self._get_selected_name()
        if not name:
            return
        if messagebox.askyesno("Move to Trash", f"Move '{name}' to Recycle Bin?"):
            path = self.current_path.rstrip('/') + '/' + name
            ok, err = self.kernel.recycle_bin.trash(path)
            if ok:
                self.navigate(self.current_path)
            else:
                messagebox.showerror("Error", f"Cannot delete: {err}")

    def _context_menu(self, event):
        menu = tk.Menu(self.parent, tearoff=0, bg=Win2kTheme.MENU_BG, fg=Win2kTheme.MENU_FG,
                       activebackground=Win2kTheme.MENU_HIGHLIGHT_BG,
                       activeforeground=Win2kTheme.MENU_HIGHLIGHT_FG, font=('Tahoma', 8))
        menu.add_command(label="📁 New Folder", command=self._new_folder)
        menu.add_command(label="📄 New File", command=self._new_file)
        menu.add_separator()
        menu.add_command(label="🔄 Refresh", command=lambda: self.navigate(self.current_path))
        menu.add_separator()
        menu.add_command(label="🗑 Move to Trash", command=self._trash_selected)
        menu.tk_popup(event.x_root, event.y_root)


# ═══════════════════════════════════════════════════════════════
#  X5 INSTALLER
# ═══════════════════════════════════════════════════════════════

class X5InstallerApp:
    """Установщик X5 приложений."""

    def __init__(self, desktop, kernel, filepath, cwd='/'):
        self.desktop = desktop
        self.kernel = kernel
        self.filepath = filepath
        self.cwd = cwd
        self._install_data = None

        # Загружаем и анализируем
        ok, err, data = kernel.app_manager.install(filepath, cwd)
        if not ok or not data:
            messagebox.showerror("X5 Installer", f"Cannot read file:\n{err or 'Unknown error'}")
            return

        self._install_data = data
        self._show()

    def _show(self):
        T = Win2kTheme
        data = self._install_data
        info = data['parsed']['info']
        name = data['name']
        errors = data['errors']
        warnings = data['warnings']
        scan = data['scan']

        win = Win2kWindow(self.desktop, title=f"Install — {name}", width=420, height=420,
                          icon=Win2kTheme.ICON_INSTALL, resizable=False)
        frame = win.client

        # Заголовок
        header = tk.Frame(frame, bg='#000080', height=50)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"  {Win2kTheme.ICON_INSTALL}  X5 Application Installer",
                 bg='#000080', fg='white', font=('Tahoma', 10, 'bold'), anchor='w').pack(fill='x', pady=12, padx=5)

        # Информация о приложении
        info_frame = tk.Frame(frame, bg=T.WINDOW_BG, bd=2, relief='groove')
        info_frame.pack(fill='x', padx=10, pady=8)

        icon = info.get('icon', '📦')
        app_icon = tk.Label(info_frame, text=icon, font=('Segoe UI', 28), bg=T.WINDOW_BG)
        app_icon.pack(side='left', padx=10, pady=8)

        details = tk.Frame(info_frame, bg=T.WINDOW_BG)
        details.pack(side='left', fill='both', expand=True, pady=5)

        tk.Label(details, text=name, bg=T.WINDOW_BG, font=('Tahoma', 11, 'bold'), anchor='w').pack(fill='x')
        tk.Label(details, text=f"Version: {info.get('version', '?')}   Author: {info.get('author', '?')}",
                 bg=T.WINDOW_BG, font=('Tahoma', 8), fg='#404040', anchor='w').pack(fill='x')
        desc = info.get('description', 'No description')
        tk.Label(details, text=desc, bg=T.WINDOW_BG, font=('Tahoma', 8), fg='#606060',
                 anchor='w', wraplength=250).pack(fill='x')

        # Результаты проверки
        check_frame = tk.Frame(frame, bg=T.WINDOW_BG)
        check_frame.pack(fill='both', expand=True, padx=10, pady=(0, 5))

        tk.Label(check_frame, text="Verification Results:", bg=T.WINDOW_BG,
                 font=('Tahoma', 8, 'bold'), anchor='w').pack(fill='x')

        results_box = tk.Text(check_frame, bg=T.TEXT_BG, fg=T.TEXT_FG, font=('Consolas', 8),
                              height=8, bd=2, relief='sunken', wrap='word')
        results_box.pack(fill='both', expand=True, pady=2)

        total_errors = scan['errors'] + len(errors)
        total_warnings = scan['warnings'] + len(warnings)

        if total_errors == 0 and total_warnings == 0:
            results_box.insert('end', '✅ No issues found!\n\n')
            results_box.insert('end', 'This application passed all checks.\n')
        else:
            if total_errors > 0:
                results_box.insert('end', f'❌ {total_errors} error(s) found:\n')
                for e in errors:
                    results_box.insert('end', f'  • {e}\n')
                for lvl, msg in scan['issues']:
                    if lvl == 'err':
                        results_box.insert('end', f'  • {msg}\n')
                results_box.insert('end', '\n')

            if total_warnings > 0:
                results_box.insert('end', f'⚠ {total_warnings} warning(s):\n')
                for w in warnings:
                    results_box.insert('end', f'  • {w}\n')
                for lvl, msg in scan['issues']:
                    if lvl == 'warn':
                        results_box.insert('end', f'  • {msg}\n')

        results_box.configure(state='disabled')

        # Статус
        if total_errors > 0:
            status_text = f"⚠ {total_errors} error(s), {total_warnings} warning(s) — Install at your own risk"
            status_color = '#CC0000'
        elif total_warnings > 0:
            status_text = f"⚠ {total_warnings} warning(s) — Review before installing"
            status_color = '#CC8800'
        else:
            status_text = "✅ All checks passed — Safe to install"
            status_color = '#008800'

        tk.Label(frame, text=status_text, bg=T.WINDOW_BG, fg=status_color,
                 font=('Tahoma', 8, 'bold')).pack(pady=2)

        # Кнопки
        btn_frame = tk.Frame(frame, bg=T.WINDOW_BG)
        btn_frame.pack(fill='x', padx=10, pady=(0, 10))

        def do_install():
            ok, msg = self.kernel.app_manager.confirm_install(data)
            if ok:
                messagebox.showinfo("X5 Installer", msg)
                win.close()
            else:
                messagebox.showerror("X5 Installer", msg)

        Win2kButton(btn_frame, text="Install", width=90, height=28,
                    font_spec=('Tahoma', 9, 'bold'), command=do_install).pack(side='left', padx=4)
        Win2kButton(btn_frame, text="Cancel", width=70, height=28,
                    command=win.close).pack(side='right', padx=4)


# ═══════════════════════════════════════════════════════════════
#  RECYCLE BIN APP
# ═══════════════════════════════════════════════════════════════

class RecycleBinApp:
    def __init__(self, parent, desktop, kernel, window):
        self.parent = parent
        self.desktop = desktop
        self.kernel = kernel
        self.window = window
        self._build()

    def _build(self):
        T = Win2kTheme
        toolbar = tk.Frame(self.parent, bg=T.WINDOW_BG, bd=1, relief='raised')
        toolbar.pack(fill='x')

        Win2kButton(toolbar, text="♻ Restore", width=75, height=20, font_spec=('Tahoma', 7),
                    command=self._restore).pack(side='left', padx=2, pady=2)
        Win2kButton(toolbar, text="🗑 Delete", width=65, height=20, font_spec=('Tahoma', 7),
                    command=self._delete_perm).pack(side='left', padx=2, pady=2)
        Win2kButton(toolbar, text="Empty Trash", width=80, height=20, font_spec=('Tahoma', 7),
                    command=self._empty_trash).pack(side='right', padx=2, pady=2)

        list_frame = tk.Frame(self.parent, bg=T.TEXT_BG, bd=2, relief='sunken')
        list_frame.pack(fill='both', expand=True, padx=4, pady=4)

        columns = ('name', 'original', 'size', 'deleted')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', selectmode='browse')
        for col, text, w in [('name', 'Name', 120), ('original', 'Original Location', 180),
                              ('size', 'Size', 70), ('deleted', 'Deleted', 120)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)

        rb = self.kernel.recycle_bin
        self.status = tk.Label(self.parent, text=f"{rb.count()} item(s), {RealFS.fmt_size(rb.total_size())}",
                               bg=T.WINDOW_BG, font=('Tahoma', 7), anchor='w', bd=1, relief='sunken')
        self.status.pack(fill='x', padx=4, pady=(0, 4))
        self._refresh()

    def _refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        rb = self.kernel.recycle_bin
        for it in rb.get_items():
            icon = "📁" if it.get('is_dir') else "📄"
            self.tree.insert('', 'end', iid=str(it['id']),
                             values=(f"{icon} {it['original_name']}",
                                     it['original_path'],
                                     RealFS.fmt_size(it.get('size', 0)),
                                     it['deleted'][:16]))
        self.status.configure(text=f"{rb.count()} item(s), {RealFS.fmt_size(rb.total_size())}")

    def _get_selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _restore(self):
        item_id = self._get_selected_id()
        if item_id is None:
            return
        ok, err = self.kernel.recycle_bin.restore(item_id)
        if ok:
            self._refresh()
        else:
            messagebox.showerror("Error", err)

    def _delete_perm(self):
        item_id = self._get_selected_id()
        if item_id is None:
            return
        if messagebox.askyesno("Delete Permanently", "This cannot be undone. Delete?"):
            self.kernel.recycle_bin.delete_permanently(item_id)
            self._refresh()

    def _empty_trash(self):
        rb = self.kernel.recycle_bin
        if rb.count() == 0:
            return
        if messagebox.askyesno("Empty Recycle Bin",
                               f"Permanently delete {rb.count()} item(s)?"):
            count = rb.empty()
            self._refresh()
            self.kernel.notifications.send('system', 'Recycle Bin emptied',
                                           f'{count} item(s) deleted', 'ok', 'low')


# ═══════════════════════════════════════════════════════════════
#  GUARDIAN APP
# ═══════════════════════════════════════════════════════════════

class GuardianApp:
    def __init__(self, parent, desktop, kernel):
        self.parent = parent
        self.desktop = desktop
        self.kernel = kernel
        self._build()

    def _build(self):
        T = Win2kTheme
        g = self.kernel.guardian

        # Заголовок
        header = tk.Frame(self.parent, bg='#004400', height=40)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"  {Win2kTheme.ICON_SHIELD}  Guardian — System Monitor",
                 bg='#004400', fg='white', font=('Tahoma', 10, 'bold'), anchor='w').pack(fill='x', pady=8, padx=5)

        # Notebook
        notebook = ttk.Notebook(self.parent)
        notebook.pack(fill='both', expand=True, padx=4, pady=4)

        # Tab 1: Overview
        tab1 = tk.Frame(notebook, bg=T.WINDOW_BG)
        notebook.add(tab1, text=' Overview ')
        self._build_overview(tab1)

        # Tab 2: Disk
        tab2 = tk.Frame(notebook, bg=T.WINDOW_BG)
        notebook.add(tab2, text=' Disk ')
        self._build_disk(tab2)

        # Tab 3: Apps
        tab3 = tk.Frame(notebook, bg=T.WINDOW_BG)
        notebook.add(tab3, text=' Apps ')
        self._build_apps(tab3)

        # Tab 4: Scanner
        tab4 = tk.Frame(notebook, bg=T.WINDOW_BG)
        notebook.add(tab4, text=' Scanner ')
        self._build_scanner(tab4)

    def _build_overview(self, parent):
        T = Win2kTheme
        g = self.kernel.guardian
        k = self.kernel
        now = datetime.datetime.now()

        info = [
            ("Date", now.strftime('%Y-%m-%d')),
            ("Time", now.strftime('%H:%M:%S')),
            ("Session", g.session_str()),
            ("Time Limit", f"{g.daily_limit} min" if g.daily_limit else "None"),
            ("Disk Used", RealFS.fmt_size(k.fs.disk_usage())),
            ("App Limit", f"{RealFS.fmt_size(g.app_folder_limit)}/app"),
            ("Trash", f"{k.recycle_bin.count()} items ({RealFS.fmt_size(k.recycle_bin.total_size())})"),
            ("Users", str(len(k.um.list_users()))),
            ("X5 Apps", str(len(k.app_manager.apps)) if k.app_manager else "0"),
        ]
        for label, value in info:
            row = tk.Frame(parent, bg=T.WINDOW_BG)
            row.pack(fill='x', padx=15, pady=2)
            tk.Label(row, text=f"{label}:", bg=T.WINDOW_BG, font=('Tahoma', 8, 'bold'),
                     width=14, anchor='w').pack(side='left')
            tk.Label(row, text=value, bg=T.WINDOW_BG, font=('Tahoma', 8), anchor='w').pack(side='left')

        btn_frame = tk.Frame(parent, bg=T.WINDOW_BG)
        btn_frame.pack(pady=10)

        def set_time_limit():
            val = simpledialog.askstring("Time Limit", "Minutes (empty to remove):")
            if val is None:
                return
            if val == '':
                g.daily_limit = None
            else:
                try:
                    g.daily_limit = int(val)
                except ValueError:
                    messagebox.showerror("Error", "Enter a number")
                    return
            k.save_state()
            messagebox.showinfo("Guardian", f"Time limit: {g.daily_limit or 'None'}")

        def set_app_limit():
            val = simpledialog.askstring("App Limit", "KB per app (e.g. 1024):")
            if val:
                try:
                    g.app_folder_limit = int(val) * 1024
                    k.save_state()
                    messagebox.showinfo("Guardian", f"Limit: {RealFS.fmt_size(g.app_folder_limit)}/app")
                except ValueError:
                    messagebox.showerror("Error", "Enter a number")

        Win2kButton(btn_frame, text="Set Time Limit", width=110, height=23,
                    command=set_time_limit).pack(side='left', padx=4)
        Win2kButton(btn_frame, text="Set App Limit", width=100, height=23,
                    command=set_app_limit).pack(side='left', padx=4)

    def _build_disk(self, parent):
        T = Win2kTheme
        g = self.kernel.guardian
        report = g.disk_report(self.kernel.fs)

        tk.Label(parent, text=f"Total: {RealFS.fmt_size(report['total'])}  |  {report['count']} files",
                 bg=T.WINDOW_BG, font=('Tahoma', 9, 'bold')).pack(pady=8)

        list_frame = tk.Frame(parent, bg=T.TEXT_BG, bd=2, relief='sunken')
        list_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        columns = ('size', 'path')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        tree.heading('size', text='Size')
        tree.heading('path', text='Path')
        tree.column('size', width=80, anchor='e')
        tree.column('path', width=350)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)

        for fi in report['largest']:
            tree.insert('', 'end', values=(RealFS.fmt_size(fi['size']), fi['path']))

    def _build_apps(self, parent):
        T = Win2kTheme
        g = self.kernel.guardian
        checks = g.check_app_folders(self.kernel.fs)

        tk.Label(parent, text="Application Data Folders", bg=T.WINDOW_BG,
                 font=('Tahoma', 9, 'bold')).pack(pady=8)

        list_frame = tk.Frame(parent, bg=T.TEXT_BG, bd=2, relief='sunken')
        list_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        columns = ('name', 'size', 'limit', 'status')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        for col, text, w in [('name', 'App', 120), ('size', 'Size', 80),
                              ('limit', 'Limit', 80), ('status', 'Status', 60)]:
            tree.heading(col, text=text)
            tree.column(col, width=w)

        tree.pack(fill='both', expand=True)

        for ac in checks:
            status = "⚠ OVER" if ac['over'] else "✅ OK"
            tree.insert('', 'end', values=(ac['name'], RealFS.fmt_size(ac['size']),
                                           RealFS.fmt_size(ac['limit']), status))

    def _build_scanner(self, parent):
        T = Win2kTheme

        tk.Label(parent, text="File Security Scanner", bg=T.WINDOW_BG,
                 font=('Tahoma', 9, 'bold')).pack(pady=8)

        input_frame = tk.Frame(parent, bg=T.WINDOW_BG)
        input_frame.pack(fill='x', padx=8)

        tk.Label(input_frame, text="File path:", bg=T.WINDOW_BG, font=('Tahoma', 8)).pack(side='left')
        path_entry = tk.Entry(input_frame, font=('Tahoma', 8), bg=T.TEXT_BG, bd=2, relief='sunken')
        path_entry.pack(side='left', fill='x', expand=True, padx=4)

        result_text = tk.Text(parent, bg=T.TEXT_BG, fg=T.TEXT_FG, font=('Consolas', 8),
                              height=12, bd=2, relief='sunken', wrap='word')
        result_text.pack(fill='both', expand=True, padx=8, pady=8)

        def do_scan():
            path = path_entry.get().strip()
            if not path:
                return
            content = self.kernel.fs.read_file(path)
            result_text.configure(state='normal')
            result_text.delete('1.0', 'end')
            if content is None:
                result_text.insert('end', f"Cannot read: {path}\n")
            else:
                scan = self.kernel.guardian.scan_content(content)
                result_text.insert('end', f"File: {path}\n")
                result_text.insert('end', f"Level: {scan['level']} (score: {scan['score']})\n\n")
                if scan['threats']:
                    for t in scan['threats']:
                        result_text.insert('end', f"  • {t}\n")
                else:
                    result_text.insert('end', "No threats found.\n")
            result_text.configure(state='disabled')

        Win2kButton(input_frame, text="Scan", width=50, height=20, font_spec=('Tahoma', 7),
                    command=do_scan).pack(side='left')


# ═══════════════════════════════════════════════════════════════
#  CLOCK APP (with Stopwatch, Timers, Alarms)
# ═══════════════════════════════════════════════════════════════

class ClockApp:
    def __init__(self, parent, desktop, kernel, window):
        self.parent = parent
        self.desktop = desktop
        self.kernel = kernel
        self.window = window
        self._alarms = []
        self._timers = []
        self._timer_id_counter = 0
        self._stopwatch_running = False
        self._stopwatch_ms = 0
        self._stopwatch_start = None
        self._build()
        self._tick()

    def _build(self):
        T = Win2kTheme
        notebook = ttk.Notebook(self.parent)
        notebook.pack(fill='both', expand=True)

        # Tab 1: Clock
        tab_clock = tk.Frame(notebook, bg=T.WINDOW_BG)
        notebook.add(tab_clock, text=' 🕐 Clock ')
        self._build_clock(tab_clock)

        # Tab 2: Stopwatch
        tab_sw = tk.Frame(notebook, bg=T.WINDOW_BG)
        notebook.add(tab_sw, text=' ⏱ Stopwatch ')
        self._build_stopwatch(tab_sw)

        # Tab 3: Timer
        tab_timer = tk.Frame(notebook, bg=T.WINDOW_BG)
        notebook.add(tab_timer, text=' ⏲ Timer ')
        self._build_timers(tab_timer)

        # Tab 4: Alarm
        tab_alarm = tk.Frame(notebook, bg=T.WINDOW_BG)
        notebook.add(tab_alarm, text=' ⏰ Alarm ')
        self._build_alarms(tab_alarm)

    # ═══ Clock ═══

    def _build_clock(self, parent):
        T = Win2kTheme
        self.clock_time = tk.Label(parent, text="", bg=T.WINDOW_BG,
                                   font=('Consolas', 36, 'bold'), fg='#000080')
        self.clock_time.pack(pady=20)

        self.clock_date = tk.Label(parent, text="", bg=T.WINDOW_BG,
                                   font=('Tahoma', 12), fg='#404040')
        self.clock_date.pack()

        self.clock_day = tk.Label(parent, text="", bg=T.WINDOW_BG,
                                  font=('Tahoma', 10), fg='#808080')
        self.clock_day.pack(pady=5)

        # Analog clock canvas
        self.analog = tk.Canvas(parent, width=180, height=180, bg=T.WINDOW_BG, highlightthickness=0)
        self.analog.pack(pady=10)

    def _draw_analog(self):
        c = self.analog
        c.delete('all')
        cx, cy, r = 90, 90, 80

        # Face
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill='white', outline='#404040', width=2)

        # Hour marks
        for i in range(12):
            angle = math.radians(i * 30 - 90)
            x1 = cx + (r - 10) * math.cos(angle)
            y1 = cy + (r - 10) * math.sin(angle)
            x2 = cx + (r - 3) * math.cos(angle)
            y2 = cy + (r - 3) * math.sin(angle)
            w = 2 if i % 3 == 0 else 1
            c.create_line(x1, y1, x2, y2, fill='#000000', width=w)

        now = datetime.datetime.now()
        h, m, s = now.hour % 12, now.minute, now.second

        # Hour hand
        h_angle = math.radians((h + m / 60) * 30 - 90)
        c.create_line(cx, cy, cx + 45 * math.cos(h_angle), cy + 45 * math.sin(h_angle),
                      fill='#000000', width=3)
        # Minute hand
        m_angle = math.radians(m * 6 - 90)
        c.create_line(cx, cy, cx + 60 * math.cos(m_angle), cy + 60 * math.sin(m_angle),
                      fill='#000080', width=2)
        # Second hand
        s_angle = math.radians(s * 6 - 90)
        c.create_line(cx, cy, cx + 65 * math.cos(s_angle), cy + 65 * math.sin(s_angle),
                      fill='#FF0000', width=1)
        # Center dot
        c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill='#000000')

    # ═══ Stopwatch ═══

    def _build_stopwatch(self, parent):
        T = Win2kTheme

        self.sw_display = tk.Label(parent, text="00:00:00.000", bg='#000000', fg='#00FF00',
                                   font=('Consolas', 28, 'bold'), bd=3, relief='sunken')
        self.sw_display.pack(pady=20, padx=20, fill='x')

        btn_frame = tk.Frame(parent, bg=T.WINDOW_BG)
        btn_frame.pack(pady=10)

        self.sw_start_btn = Win2kButton(btn_frame, text="▶ Start", width=90, height=30,
                                        font_spec=('Tahoma', 9, 'bold'), command=self._sw_start)
        self.sw_start_btn.pack(side='left', padx=5)

        self.sw_stop_btn = Win2kButton(btn_frame, text="⏹ Stop", width=80, height=30,
                                       font_spec=('Tahoma', 9), command=self._sw_stop)
        self.sw_stop_btn.pack(side='left', padx=5)

        Win2kButton(btn_frame, text="↺ Reset", width=80, height=30,
                    font_spec=('Tahoma', 9), command=self._sw_reset).pack(side='left', padx=5)

        # Lap list
        self.lap_listbox = tk.Listbox(parent, bg=T.TEXT_BG, fg=T.TEXT_FG, font=('Consolas', 9),
                                      bd=2, relief='sunken', height=8)
        self.lap_listbox.pack(fill='both', expand=True, padx=15, pady=(5, 10))

        Win2kButton(parent, text="📋 Lap", width=70, height=25,
                    font_spec=('Tahoma', 8), command=self._sw_lap).pack(pady=(0, 10))

        self._lap_count = 0

    def _sw_start(self):
        if not self._stopwatch_running:
            self._stopwatch_running = True
            self._stopwatch_start = time.time() - (self._stopwatch_ms / 1000)

    def _sw_stop(self):
        if self._stopwatch_running:
            self._stopwatch_running = False
            self._stopwatch_ms = (time.time() - self._stopwatch_start) * 1000

    def _sw_reset(self):
        self._stopwatch_running = False
        self._stopwatch_ms = 0
        self._stopwatch_start = None
        self.sw_display.configure(text="00:00:00.000")
        self.lap_listbox.delete(0, 'end')
        self._lap_count = 0

    def _sw_lap(self):
        if self._stopwatch_running or self._stopwatch_ms > 0:
            self._lap_count += 1
            self.lap_listbox.insert('end', f"  Lap {self._lap_count:>3}   {self._format_sw_time()}")
            self.lap_listbox.see('end')

    def _format_sw_time(self):
        ms = self._stopwatch_ms
        h = int(ms // 3600000)
        m = int((ms % 3600000) // 60000)
        s = int((ms % 60000) // 1000)
        millis = int(ms % 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{millis:03d}"

    # ═══ Timers ═══

    def _build_timers(self, parent):
        T = Win2kTheme

        input_frame = tk.Frame(parent, bg=T.WINDOW_BG)
        input_frame.pack(fill='x', padx=10, pady=8)

        tk.Label(input_frame, text="Minutes:", bg=T.WINDOW_BG, font=('Tahoma', 8)).pack(side='left')
        self.timer_min = tk.Entry(input_frame, font=('Tahoma', 9), width=5, bd=2, relief='sunken')
        self.timer_min.insert(0, "5")
        self.timer_min.pack(side='left', padx=4)

        tk.Label(input_frame, text="Sec:", bg=T.WINDOW_BG, font=('Tahoma', 8)).pack(side='left')
        self.timer_sec = tk.Entry(input_frame, font=('Tahoma', 9), width=5, bd=2, relief='sunken')
        self.timer_sec.insert(0, "0")
        self.timer_sec.pack(side='left', padx=4)

        tk.Label(input_frame, text="Label:", bg=T.WINDOW_BG, font=('Tahoma', 8)).pack(side='left')
        self.timer_label = tk.Entry(input_frame, font=('Tahoma', 9), width=12, bd=2, relief='sunken')
        self.timer_label.insert(0, "Timer")
        self.timer_label.pack(side='left', padx=4)

        Win2kButton(input_frame, text="+ Add", width=55, height=22, font_spec=('Tahoma', 7),
                    command=self._add_timer).pack(side='left', padx=4)

        self.timer_list_frame = tk.Frame(parent, bg=T.WINDOW_BG)
        self.timer_list_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

    def _add_timer(self):
        try:
            mins = int(self.timer_min.get() or 0)
            secs = int(self.timer_sec.get() or 0)
        except ValueError:
            messagebox.showerror("Error", "Enter valid numbers")
            return
        total = mins * 60 + secs
        if total <= 0:
            messagebox.showerror("Error", "Timer must be > 0")
            return
        label = self.timer_label.get().strip() or "Timer"
        self._timer_id_counter += 1
        timer = {
            'id': self._timer_id_counter, 'label': label,
            'total': total, 'remaining': total,
            'running': True, 'fired': False,
        }
        self._timers.append(timer)
        self._refresh_timers()

    def _refresh_timers(self):
        for w in self.timer_list_frame.winfo_children():
            w.destroy()
        T = Win2kTheme
        for timer in self._timers:
            row = tk.Frame(self.timer_list_frame, bg=T.WINDOW_BG, bd=1, relief='groove')
            row.pack(fill='x', pady=2)

            remaining = max(0, timer['remaining'])
            m, s = divmod(remaining, 60)
            h, m = divmod(m, 60)
            time_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

            if timer['fired']:
                fg = '#FF0000'
                status = "🔔 DONE"
            elif timer['running']:
                fg = '#008000'
                status = time_str
            else:
                fg = '#808080'
                status = f"⏸ {time_str}"

            tk.Label(row, text=f"  {Win2kTheme.ICON_TIMER} {timer['label']}", bg=T.WINDOW_BG,
                     font=('Tahoma', 9), anchor='w').pack(side='left', padx=4)
            tk.Label(row, text=status, bg=T.WINDOW_BG, font=('Consolas', 10, 'bold'),
                     fg=fg, anchor='e').pack(side='right', padx=8)

            def make_toggle(t):
                def toggle():
                    t['running'] = not t['running']
                    self._refresh_timers()
                return toggle

            def make_delete(t):
                def delete():
                    self._timers = [x for x in self._timers if x['id'] != t['id']]
                    self._refresh_timers()
                return delete

            if not timer['fired']:
                Win2kButton(row, text="⏸" if timer['running'] else "▶", width=24, height=18,
                            font_spec=('Tahoma', 7), command=make_toggle(timer)).pack(side='right', padx=1)
            Win2kButton(row, text="✕", width=24, height=18,
                        font_spec=('Tahoma', 7), command=make_delete(timer)).pack(side='right', padx=1)

    # ═══ Alarms ═══

    def _build_alarms(self, parent):
        T = Win2kTheme

        input_frame = tk.Frame(parent, bg=T.WINDOW_BG)
        input_frame.pack(fill='x', padx=10, pady=8)

        tk.Label(input_frame, text="Time (HH:MM):", bg=T.WINDOW_BG, font=('Tahoma', 8)).pack(side='left')
        self.alarm_time = tk.Entry(input_frame, font=('Tahoma', 9), width=6, bd=2, relief='sunken')
        self.alarm_time.insert(0, "07:00")
        self.alarm_time.pack(side='left', padx=4)

        tk.Label(input_frame, text="Label:", bg=T.WINDOW_BG, font=('Tahoma', 8)).pack(side='left')
        self.alarm_label = tk.Entry(input_frame, font=('Tahoma', 9), width=15, bd=2, relief='sunken')
        self.alarm_label.insert(0, "Wake Up")
        self.alarm_label.pack(side='left', padx=4)

        Win2kButton(input_frame, text="+ Add", width=55, height=22, font_spec=('Tahoma', 7),
                    command=self._add_alarm).pack(side='left', padx=4)

        self.alarm_list = tk.Listbox(parent, bg=T.TEXT_BG, fg=T.TEXT_FG, font=('Tahoma', 9),
                                     bd=2, relief='sunken')
        self.alarm_list.pack(fill='both', expand=True, padx=10, pady=(0, 5))

        btn_frame = tk.Frame(parent, bg=T.WINDOW_BG)
        btn_frame.pack(pady=(0, 10))
        Win2kButton(btn_frame, text="Delete Selected", width=110, height=23,
                    command=self._delete_alarm).pack(side='left', padx=4)

    def _add_alarm(self):
        time_str = self.alarm_time.get().strip()
        try:
            parts = time_str.split(':')
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Invalid time format. Use HH:MM")
            return

        label = self.alarm_label.get().strip() or "Alarm"
        alarm = {'time': f"{h:02d}:{m:02d}", 'label': label, 'enabled': True, 'fired_today': False}
        self._alarms.append(alarm)
        self._refresh_alarms()

    def _refresh_alarms(self):
        self.alarm_list.delete(0, 'end')
        for alarm in self._alarms:
            status = "🔔" if alarm['enabled'] else "🔇"
            fired = " (rang today)" if alarm.get('fired_today') else ""
            self.alarm_list.insert('end',
                                   f"  {status} {alarm['time']}  —  {alarm['label']}{fired}")

    def _delete_alarm(self):
        sel = self.alarm_list.curselection()
        if sel:
            idx = sel[0]
            if 0 <= idx < len(self._alarms):
                del self._alarms[idx]
                self._refresh_alarms()

    # ═══ Tick (1 second) ═══

    def _tick(self):
        try:
            if not self.parent.winfo_exists():
                return
        except tk.TclError:
            return

        now = datetime.datetime.now()

        # Update clock
        try:
            self.clock_time.configure(text=now.strftime('%H:%M:%S'))
            self.clock_date.configure(text=now.strftime('%d %B %Y'))
            self.clock_day.configure(text=now.strftime('%A'))
            self._draw_analog()
        except tk.TclError:
            return

        # Update stopwatch
        if self._stopwatch_running and self._stopwatch_start:
            self._stopwatch_ms = (time.time() - self._stopwatch_start) * 1000
            try:
                self.sw_display.configure(text=self._format_sw_time())
            except tk.TclError:
                return

        # Update timers
        need_refresh = False
        for timer in self._timers:
            if timer['running'] and not timer['fired']:
                timer['remaining'] -= 1
                if timer['remaining'] <= 0:
                    timer['fired'] = True
                    timer['running'] = False
                    self.kernel.notifications.send('clock', f"Timer: {timer['label']}",
                                                   'Timer has finished!', 'timer', 'high')
                    try:
                        messagebox.showinfo("Timer", f"⏲ {timer['label']} has finished!")
                    except Exception:
                        pass
                need_refresh = True
        if need_refresh:
            try:
                self._refresh_timers()
            except tk.TclError:
                return

        # Check alarms
        current_time = now.strftime('%H:%M')
        for alarm in self._alarms:
            if alarm['enabled'] and not alarm.get('fired_today') and alarm['time'] == current_time:
                alarm['fired_today'] = True
                self.kernel.notifications.send('clock', f"Alarm: {alarm['label']}",
                                               f"It is {current_time}!", 'alarm', 'critical')
                try:
                    messagebox.showinfo("Alarm", f"⏰ {alarm['label']}\n\nIt is {current_time}!")
                    self._refresh_alarms()
                except Exception:
                    pass

        # Reset fired_today at midnight
        if current_time == '00:00':
            for alarm in self._alarms:
                alarm['fired_today'] = False

        self.parent.after(1000, self._tick)


# ═══════════════════════════════════════════════════════════════
#  TERMINAL
# ═══════════════════════════════════════════════════════════════

class TerminalApp:
    COMMANDS = [
        'help', 'ls', 'dir', 'cd', 'pwd', 'mkdir', 'rmdir', 'touch', 'rm', 'del',
        'cat', 'type', 'echo', 'cp', 'copy', 'mv', 'move', 'rename', 'ren',
        'find', 'tree', 'clear', 'cls', 'whoami', 'date', 'time', 'hostname',
        'ver', 'exit', 'neofetch', 'df', 'du', 'trash', 'restore',
    ]

    def __init__(self, parent, desktop, kernel, window):
        self.parent = parent
        self.desktop = desktop
        self.kernel = kernel
        self.window = window
        self.cwd = kernel.get_home()
        self.history = []
        self.history_idx = -1
        self._build()
        self._print_banner()

    def _build(self):
        self.text = tk.Text(self.parent, bg='#000000', fg='#C0C0C0', font=('Consolas', 10),
                            insertbackground='#C0C0C0', selectbackground='#C0C0C0',
                            selectforeground='#000000', bd=0, wrap='word')
        self.text.pack(fill='both', expand=True)
        self.text.bind('<Return>', self._on_enter)
        self.text.bind('<Up>', self._history_up)
        self.text.bind('<Down>', self._history_down)
        for tag, color in [('prompt', '#C0C0C0'), ('output', '#C0C0C0'), ('error', '#FF6666'),
                           ('success', '#66FF66'), ('info', '#6666FF'), ('yellow', '#FFFF66')]:
            self.text.tag_configure(tag, foreground=color)
        self._show_prompt()

    def _print_banner(self):
        self._output(f"PyOS {Kernel.VERSION} [Version {Kernel.BUILD}]\n", 'info')
        self._output(f"(C) {Kernel.COMPANY}. All rights reserved.\n\n", 'output')

    def _get_prompt(self):
        return f"{self.kernel.fs.current_disk}:{self.cwd}> "

    def _show_prompt(self):
        self.text.insert('end', self._get_prompt(), 'prompt')
        self._cmd_start = self.text.index('end-1c')
        self.text.see('end')

    def _output(self, text, tag='output'):
        self.text.insert('end', text, tag)
        self.text.see('end')

    def _on_enter(self, event):
        try:
            cmd = self.text.get(self._cmd_start, 'end-1c').strip()
        except Exception:
            cmd = ''
        self.text.insert('end', '\n')
        if cmd:
            self.history.append(cmd)
            self.history_idx = len(self.history)
            self._execute(cmd)
        else:
            self._show_prompt()
        return 'break'

    def _history_up(self, event):
        if self.history and self.history_idx > 0:
            self.history_idx -= 1
            self._replace_input(self.history[self.history_idx])
        return 'break'

    def _history_down(self, event):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self._replace_input(self.history[self.history_idx])
        else:
            self.history_idx = len(self.history)
            self._replace_input('')
        return 'break'

    def _replace_input(self, text):
        try:
            self.text.delete(self._cmd_start, 'end-1c')
            self.text.insert(self._cmd_start, text)
        except Exception:
            pass

    def _execute(self, line):
        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]
        handlers = {
            'help': self._cmd_help, 'ls': self._cmd_ls, 'dir': self._cmd_ls,
            'cd': self._cmd_cd, 'pwd': self._cmd_pwd,
            'mkdir': self._cmd_mkdir, 'rmdir': self._cmd_rmdir,
            'touch': self._cmd_touch, 'rm': self._cmd_rm, 'del': self._cmd_rm,
            'cat': self._cmd_cat, 'type': self._cmd_cat, 'echo': self._cmd_echo,
            'cp': self._cmd_cp, 'copy': self._cmd_cp, 'mv': self._cmd_mv, 'move': self._cmd_mv,
            'rename': self._cmd_rename, 'ren': self._cmd_rename,
            'clear': self._cmd_clear, 'cls': self._cmd_clear,
            'whoami': lambda a: self._output(f"{self.kernel.current_user}\n"),
            'hostname': lambda a: self._output(f"{self.kernel.hostname}\n"),
            'date': lambda a: self._output(f"{datetime.datetime.now().strftime('%Y-%m-%d')}\n"),
            'time': lambda a: self._output(f"{datetime.datetime.now().strftime('%H:%M:%S')}\n"),
            'ver': lambda a: self._output(f"PyOS {Kernel.VERSION} build {Kernel.BUILD}\n", 'info'),
            'neofetch': self._cmd_neofetch, 'tree': self._cmd_tree,
            'df': self._cmd_df, 'du': self._cmd_du,
            'trash': self._cmd_trash, 'restore': self._cmd_restore,
            'exit': lambda a: self.window.close(),
        }
        if cmd in handlers:
            try:
                handlers[cmd](args)
            except Exception as e:
                self._output(f"Error: {e}\n", 'error')
        else:
            self._output(f"'{cmd}' is not recognized.\n", 'error')
            import difflib
            matches = difflib.get_close_matches(cmd, self.COMMANDS, n=3, cutoff=0.5)
            if matches:
                self._output(f"Did you mean: {', '.join(matches)}?\n", 'yellow')
        self._show_prompt()

    def _cmd_help(self, a):
        self._output("Commands:\n", 'info')
        for cat, cmds in [('Files', 'ls dir cd pwd mkdir rmdir touch rm del cat type echo cp mv rename'),
                           ('System', 'whoami hostname date time ver neofetch'),
                           ('Disk', 'df du tree'), ('Trash', 'trash restore'),
                           ('Other', 'clear cls help exit')]:
            self._output(f"  {cat}: ", 'yellow')
            self._output(f"{cmds}\n")

    def _cmd_ls(self, a):
        path = a[0] if a else '.'
        items = self.kernel.fs.list_dir(path, self.cwd)
        if items is None:
            self._output(f"Cannot list: {path}\n", 'error')
            return
        for it in items:
            if it['is_dir']:
                self._output(f"  <DIR>  {it['name']}\n", 'info')
            else:
                self._output(f"  {RealFS.fmt_size(it['size']):>10}  {it['name']}\n")
        self._output(f"\n  {len(items)} item(s)\n")

    def _cmd_cd(self, a):
        if not a:
            self.cwd = self.kernel.get_home()
            return
        resolved = self.kernel.fs.resolve_virtual(a[0], self.cwd)
        if self.kernel.fs.is_dir(resolved):
            self.cwd = resolved
        else:
            self._output(f"Not found: {a[0]}\n", 'error')

    def _cmd_pwd(self, a):
        self._output(f"{self.kernel.fs.current_disk}:{self.cwd}\n")

    def _cmd_mkdir(self, a):
        for name in a:
            if self.kernel.fs.mkdir(self.cwd.rstrip('/') + '/' + name):
                self._output(f"Created: {name}\n", 'success')
            else:
                self._output(f"Failed: {name}\n", 'error')

    def _cmd_rmdir(self, a):
        for name in a:
            path = self.cwd.rstrip('/') + '/' + name
            if self.kernel.fs.delete(path, recursive=True):
                self._output(f"Removed: {name}\n", 'success')
            else:
                self._output(f"Failed: {name}\n", 'error')

    def _cmd_touch(self, a):
        for name in a:
            path = self.cwd.rstrip('/') + '/' + name
            if not self.kernel.fs.exists(path):
                self.kernel.fs.write_file(path, '')
                self._output(f"Created: {name}\n", 'success')

    def _cmd_rm(self, a):
        recursive = '-r' in a or '-rf' in a
        files = [x for x in a if not x.startswith('-')]
        for name in files:
            path = self.cwd.rstrip('/') + '/' + name
            ok, err = self.kernel.recycle_bin.trash(path)
            if ok:
                self._output(f"Moved to trash: {name}\n", 'success')
            else:
                self._output(f"Failed: {name} ({err})\n", 'error')

    def _cmd_cat(self, a):
        for name in a:
            content = self.kernel.fs.read_file(name, self.cwd)
            if content is not None:
                self._output(content + '\n')
            else:
                self._output(f"Not found: {name}\n", 'error')

    def _cmd_echo(self, a):
        self._output(' '.join(a).replace('\\n', '\n').replace('\\t', '\t') + '\n')

    def _cmd_cp(self, a):
        if len(a) < 2:
            self._output("Usage: cp <src> <dst>\n", 'yellow')
            return
        if self.kernel.fs.copy(a[0], a[1], self.cwd):
            self._output(f"Copied: {a[0]} -> {a[1]}\n", 'success')
        else:
            self._output("Copy failed\n", 'error')

    def _cmd_mv(self, a):
        if len(a) < 2:
            self._output("Usage: mv <src> <dst>\n", 'yellow')
            return
        if self.kernel.fs.move(a[0], a[1], self.cwd):
            self._output(f"Moved: {a[0]} -> {a[1]}\n", 'success')
        else:
            self._output("Move failed\n", 'error')

    def _cmd_rename(self, a):
        if len(a) < 2:
            self._output("Usage: rename <file> <new_name>\n", 'yellow')
            return
        if self.kernel.fs.rename(a[0], a[1], self.cwd):
            self._output(f"Renamed\n", 'success')
        else:
            self._output("Failed\n", 'error')

    def _cmd_clear(self, a):
        self.text.delete('1.0', 'end')

    def _cmd_neofetch(self, a):
        k = self.kernel
        info = [f"{'OS:':<12} PyOS {Kernel.VERSION}", f"{'Build:':<12} {Kernel.BUILD}",
                f"{'Host:':<12} {k.hostname}", f"{'User:':<12} {k.current_user}",
                f"{'Uptime:':<12} {k.uptime_str()}", f"{'Python:':<12} {sys.version.split()[0]}",
                f"{'Platform:':<12} {sys.platform}"]
        logo = ["  ██████╗ ██╗   ██╗", "  ██╔══██╗╚██╗ ██╔╝", "  ██████╔╝ ╚████╔╝ ",
                "  ██╔═══╝   ╚██╔╝  ", "  ██║        ██║   ", "  ╚═╝        ╚═╝   "]
        for i, line in enumerate(logo):
            self._output(line, 'info')
            self._output(f"  {info[i]}\n" if i < len(info) else '\n')
        self._output('\n')

    def _cmd_tree(self, a):
        path = a[0] if a else '.'
        resolved = self.kernel.fs.resolve_virtual(path, self.cwd)
        self._print_tree(resolved, '', True)

    def _print_tree(self, path, prefix, is_root, depth=0):
        if depth > 4:
            return
        if is_root:
            self._output(f"{path}/\n", 'info')
        items = self.kernel.fs.list_dir(path)
        if not items:
            return
        for i, item in enumerate(items):
            is_last = (i == len(items) - 1)
            conn = '└── ' if is_last else '├── '
            if item['is_dir']:
                self._output(f"{prefix}{conn}{item['name']}/\n", 'info')
                self._print_tree(path.rstrip('/') + '/' + item['name'],
                                 prefix + ('    ' if is_last else '│   '), False, depth + 1)
            else:
                self._output(f"{prefix}{conn}{item['name']}\n")

    def _cmd_df(self, a):
        for d in self.kernel.fs.get_disks():
            u = self.kernel.fs.disk_usage(d)
            cur = " <-- current" if d == self.kernel.fs.current_disk else ""
            self._output(f"  {d}: {RealFS.fmt_size(u)}{cur}\n")

    def _cmd_du(self, a):
        path = a[0] if a else '.'
        rp = self.kernel.fs.get_real_path(path, self.cwd)
        if rp.exists():
            size = self.kernel.fs._dir_size(rp) if rp.is_dir() else rp.stat().st_size
            self._output(f"  {RealFS.fmt_size(size)}  {path}\n")

    def _cmd_trash(self, a):
        items = self.kernel.recycle_bin.get_items()
        if not items:
            self._output("Recycle Bin is empty.\n", 'success')
            return
        self._output(f"Recycle Bin ({len(items)} items):\n", 'info')
        for it in items:
            self._output(f"  #{it['id']:<4} {it['original_name']:<20} {it['deleted'][:16]}\n")

    def _cmd_restore(self, a):
        if not a:
            self._output("Usage: restore <id>\n", 'yellow')
            return
        try:
            ok, err = self.kernel.recycle_bin.restore(int(a[0]))
            self._output(f"Restored\n" if ok else f"Failed: {err}\n", 'success' if ok else 'error')
        except ValueError:
            self._output("Invalid ID\n", 'error')


# ═══════════════════════════════════════════════════════════════
#  NOTEPAD
# ═══════════════════════════════════════════════════════════════

class NotepadApp:
    def __init__(self, parent, desktop, kernel, window, filepath=None):
        self.parent = parent
        self.desktop = desktop
        self.kernel = kernel
        self.window = window
        self.filepath = filepath
        self._modified = False
        self._build()
        if filepath:
            self._open_file(filepath)

    def _build(self):
        T = Win2kTheme
        menubar = tk.Frame(self.parent, bg=T.WINDOW_BG)
        menubar.pack(fill='x')

        for label, commands in [("File", [("New", self._new), ("Open...", self._open_dialog),
                                          ("Save", self._save), ("Save As...", self._save_as),
                                          None, ("Exit", self.window.close)]),
                                ("Edit", [("Cut", lambda: self.text.event_generate('<<Cut>>')),
                                          ("Copy", lambda: self.text.event_generate('<<Copy>>')),
                                          ("Paste", lambda: self.text.event_generate('<<Paste>>')),
                                          None, ("Select All", lambda: self.text.tag_add('sel', '1.0', 'end'))]),
                                ("Help", [("About", lambda: messagebox.showinfo("Notepad", f"Notepad for PyOS {Kernel.VERSION}"))])]:
            mbtn = tk.Menubutton(menubar, text=label, bg=T.WINDOW_BG, fg=T.MENU_FG,
                                 font=('Tahoma', 8), activebackground=T.MENU_HIGHLIGHT_BG,
                                 activeforeground=T.MENU_HIGHLIGHT_FG, relief='flat')
            mbtn.pack(side='left')
            menu = tk.Menu(mbtn, tearoff=0, bg=T.MENU_BG, fg=T.MENU_FG,
                           activebackground=T.MENU_HIGHLIGHT_BG, activeforeground=T.MENU_HIGHLIGHT_FG,
                           font=('Tahoma', 8))
            for item in commands:
                if item is None:
                    menu.add_separator()
                else:
                    menu.add_command(label=item[0], command=item[1])
            mbtn.configure(menu=menu)

        text_frame = tk.Frame(self.parent, bd=2, relief='sunken')
        text_frame.pack(fill='both', expand=True, padx=2, pady=2)
        self.text = tk.Text(text_frame, bg=T.TEXT_BG, fg=T.TEXT_FG,
                            font=('Fixedsys', 10) if sys.platform == 'win32' else ('Courier', 10),
                            insertbackground=T.TEXT_FG, selectbackground=T.TEXT_SELECT_BG,
                            selectforeground=T.TEXT_SELECT_FG, undo=True, bd=0, wrap='word')
        sb = tk.Scrollbar(text_frame, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.text.pack(fill='both', expand=True)
        self.text.bind('<<Modified>>', self._on_modify)

        self.status = tk.Label(self.parent, text="Ready", bg=T.WINDOW_BG,
                               font=('Tahoma', 7), anchor='w', bd=1, relief='sunken')
        self.status.pack(fill='x')

    def _on_modify(self, event):
        if self.text.edit_modified():
            self._modified = True
            self._update_title()
            self.text.edit_modified(False)

    def _update_title(self):
        name = Path(self.filepath).name if self.filepath else "Untitled"
        self.window.set_title(f"{name}{' *' if self._modified else ''} - Notepad")

    def _new(self):
        if self._modified and not messagebox.askyesno("Notepad", "Discard changes?"):
            return
        self.text.delete('1.0', 'end')
        self.filepath = None
        self._modified = False
        self._update_title()

    def _open_dialog(self):
        path = simpledialog.askstring("Open", "File path:", initialvalue=self.kernel.get_home() + '/')
        if path:
            self._open_file(path)

    def _open_file(self, path):
        content = self.kernel.fs.read_file(path)
        if content is not None:
            self.text.delete('1.0', 'end')
            self.text.insert('1.0', content)
            self.filepath = path
            self._modified = False
            self._update_title()
            self.text.edit_modified(False)
        else:
            messagebox.showerror("Error", f"Cannot open: {path}")

    def _save(self):
        if not self.filepath:
            self._save_as()
            return
        if self.kernel.fs.write_file(self.filepath, self.text.get('1.0', 'end-1c')):
            self._modified = False
            self._update_title()
            self.status.configure(text=f"Saved: {self.filepath}")
        else:
            messagebox.showerror("Error", "Cannot save")

    def _save_as(self):
        path = simpledialog.askstring("Save As", "Save to:",
                                      initialvalue=self.filepath or self.kernel.get_home() + '/Untitled.txt')
        if path:
            self.filepath = path
            self._save()


# ═══════════════════════════════════════════════════════════════
#  CALCULATOR
# ═══════════════════════════════════════════════════════════════

class CalculatorApp:
    def __init__(self, parent):
        self.parent = parent
        self.expression = ""
        self._build()

    def _build(self):
        T = Win2kTheme
        df = tk.Frame(self.parent, bd=2, relief='sunken', bg=T.TEXT_BG)
        df.pack(fill='x', padx=6, pady=6)
        self.display = tk.Label(df, text="0", bg=T.TEXT_BG, fg=T.TEXT_FG,
                                font=('Courier', 16), anchor='e', padx=5, pady=5)
        self.display.pack(fill='x')

        bf = tk.Frame(self.parent, bg=T.WINDOW_BG)
        bf.pack(fill='both', expand=True, padx=6, pady=(0, 6))

        buttons = [['C', '←', '%', '/'], ['7', '8', '9', '*'],
                   ['4', '5', '6', '-'], ['1', '2', '3', '+'], ['±', '0', '.', '=']]
        for r, row in enumerate(buttons):
            for c, text in enumerate(row):
                Win2kButton(bf, text=text, width=48, height=32, font_spec=('Tahoma', 10, 'bold'),
                            command=lambda t=text: self._press(t)).grid(row=r, column=c, padx=2, pady=2)

    def _press(self, key):
        if key == 'C':
            self.expression = ""
            self.display.configure(text="0")
        elif key == '←':
            self.expression = self.expression[:-1]
            self.display.configure(text=self.expression or "0")
        elif key == '±':
            if self.expression and self.expression[0] == '-':
                self.expression = self.expression[1:]
            elif self.expression:
                self.expression = '-' + self.expression
            self.display.configure(text=self.expression or "0")
        elif key == '=':
            try:
                result = eval(self.expression, {'__builtins__': {}, 'abs': abs, 'round': round})
                result_str = str(result).rstrip('0').rstrip('.') if '.' in str(result) else str(result)
                self.display.configure(text=result_str)
                self.expression = result_str
            except Exception:
                self.display.configure(text="Error")
                self.expression = ""
        else:
            self.expression += key
            self.display.configure(text=self.expression)


# ═══════════════════════════════════════════════════════════════
#  PAINT
# ═══════════════════════════════════════════════════════════════

class PaintApp:
    def __init__(self, parent, window):
        self.parent = parent
        self.window = window
        self.color = '#000000'
        self.brush_size = 3
        self.tool = 'brush'
        self._last_x = self._last_y = None
        self._build()

    def _build(self):
        T = Win2kTheme
        toolbar = tk.Frame(self.parent, bg=T.WINDOW_BG, bd=1, relief='raised')
        toolbar.pack(fill='x')
        for text, tool in [('✏️ Brush', 'brush'), ('⬜ Rect', 'rect'), ('⭕ Oval', 'oval'),
                            ('📏 Line', 'line'), ('🧹 Eraser', 'eraser')]:
            Win2kButton(toolbar, text=text, width=60, height=20, font_spec=('Tahoma', 7),
                        command=lambda t=tool: setattr(self, 'tool', t)).pack(side='left', padx=1, pady=2)
        tk.Label(toolbar, text="Size:", bg=T.WINDOW_BG, font=('Tahoma', 7)).pack(side='left', padx=(8, 2))
        self.size_var = tk.IntVar(value=3)
        tk.Spinbox(toolbar, from_=1, to=20, textvariable=self.size_var, width=3, font=('Tahoma', 7)).pack(side='left')
        Win2kButton(toolbar, text="🗑 Clear", width=50, height=20, font_spec=('Tahoma', 7),
                    command=lambda: self.canvas.delete('all')).pack(side='right', padx=4, pady=2)

        palette = tk.Frame(self.parent, bg=T.WINDOW_BG)
        palette.pack(fill='x')
        for color in ['#000000', '#808080', '#800000', '#808000', '#008000', '#008080',
                       '#000080', '#800080', '#FFFFFF', '#C0C0C0', '#FF0000', '#FFFF00',
                       '#00FF00', '#00FFFF', '#0000FF', '#FF00FF']:
            c = tk.Canvas(palette, width=16, height=16, bg=color, highlightthickness=1,
                          highlightbackground='#808080', cursor='hand2')
            c.pack(side='left', padx=1, pady=2)
            c.bind('<Button-1>', lambda e, col=color: setattr(self, 'color', col))

        cf = tk.Frame(self.parent, bd=2, relief='sunken')
        cf.pack(fill='both', expand=True, padx=4, pady=4)
        self.canvas = tk.Canvas(cf, bg='#FFFFFF', cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        self._shape_start = None

    def _on_press(self, e):
        self.brush_size = self.size_var.get()
        self._last_x, self._last_y = e.x, e.y
        self._shape_start = (e.x, e.y)

    def _on_drag(self, e):
        if self.tool in ('brush', 'eraser'):
            color = '#FFFFFF' if self.tool == 'eraser' else self.color
            width = self.brush_size * 3 if self.tool == 'eraser' else self.brush_size
            self.canvas.create_line(self._last_x, self._last_y, e.x, e.y,
                                    fill=color, width=width, capstyle='round', smooth=True)
            self._last_x, self._last_y = e.x, e.y

    def _on_release(self, e):
        if self._shape_start and self.tool in ('rect', 'oval', 'line'):
            x1, y1 = self._shape_start
            if self.tool == 'rect':
                self.canvas.create_rectangle(x1, y1, e.x, e.y, outline=self.color, width=self.brush_size)
            elif self.tool == 'oval':
                self.canvas.create_oval(x1, y1, e.x, e.y, outline=self.color, width=self.brush_size)
            elif self.tool == 'line':
                self.canvas.create_line(x1, y1, e.x, e.y, fill=self.color, width=self.brush_size)
        self._shape_start = None


# ═══════════════════════════════════════════════════════════════
#  MINESWEEPER
# ═══════════════════════════════════════════════════════════════

class MinesweeperApp:
    COLORS = {1: '#0000FF', 2: '#008000', 3: '#FF0000', 4: '#000080',
              5: '#800000', 6: '#008080', 7: '#000000', 8: '#808080'}

    def __init__(self, parent, rows=9, cols=9, mines=10):
        self.parent = parent
        self.rows, self.cols, self.mine_count = rows, cols, mines
        self.game_over = self.first_click = False
        self.first_click = True
        self.flags = 0
        self._build()
        self._new_game()

    def _build(self):
        T = Win2kTheme
        top = tk.Frame(self.parent, bg=T.WINDOW_BG, bd=2, relief='sunken')
        top.pack(fill='x', padx=6, pady=6)
        self.mine_label = tk.Label(top, text=f"{self.mine_count:03d}", bg='#000', fg='#F00',
                                   font=('Courier', 14, 'bold'), width=4)
        self.mine_label.pack(side='left', padx=4, pady=2)
        self.face_btn = Win2kButton(top, text="😊", width=30, height=24, font_spec=('Segoe UI', 11),
                                    command=self._new_game)
        self.face_btn.pack(side='left', expand=True)
        self.time_label = tk.Label(top, text="000", bg='#000', fg='#F00',
                                   font=('Courier', 14, 'bold'), width=4)
        self.time_label.pack(side='right', padx=4, pady=2)

        ff = tk.Frame(self.parent, bd=3, relief='sunken', bg='#C0C0C0')
        ff.pack(padx=6, pady=(0, 6))
        self.buttons = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                btn = tk.Label(ff, width=2, height=1, bg=T.BUTTON_BG, relief='raised', bd=2,
                               font=('Tahoma', 9, 'bold'), cursor='hand2')
                btn.grid(row=r, column=c)
                btn.bind('<Button-1>', lambda e, r=r, c=c: self._left_click(r, c))
                btn.bind('<Button-3>', lambda e, r=r, c=c: self._right_click(r, c))
                row.append(btn)
            self.buttons.append(row)
        self._timer_running = False
        self._time = 0

    def _new_game(self):
        self.game_over = False
        self.first_click = True
        self.flags = self._time = 0
        self._timer_running = False
        self.grid = [[0] * self.cols for _ in range(self.rows)]
        self.revealed = [[False] * self.cols for _ in range(self.rows)]
        self.flagged = [[False] * self.cols for _ in range(self.rows)]
        for r in range(self.rows):
            for c in range(self.cols):
                self.buttons[r][c].configure(text='', bg=Win2kTheme.BUTTON_BG, relief='raised', bd=2, fg='#000')
        self.face_btn._text = "😊"
        self.face_btn._draw()
        self.mine_label.configure(text=f"{self.mine_count:03d}")
        self.time_label.configure(text="000")

    def _place_mines(self, sr, sc):
        positions = [(r, c) for r in range(self.rows) for c in range(self.cols)
                     if not (abs(r - sr) <= 1 and abs(c - sc) <= 1)]
        for r, c in random.sample(positions, min(self.mine_count, len(positions))):
            self.grid[r][c] = -1
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == -1:
                    continue
                self.grid[r][c] = sum(1 for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                                       if 0 <= r + dr < self.rows and 0 <= c + dc < self.cols
                                       and self.grid[r + dr][c + dc] == -1)

    def _left_click(self, r, c):
        if self.game_over or self.flagged[r][c]:
            return
        if self.first_click:
            self.first_click = False
            self._place_mines(r, c)
            self._start_timer()
        if self.grid[r][c] == -1:
            self._lose(r, c)
        else:
            self._reveal(r, c)
            self._check_win()

    def _right_click(self, r, c):
        if self.game_over or self.revealed[r][c]:
            return
        self.flagged[r][c] = not self.flagged[r][c]
        self.buttons[r][c].configure(text='🚩' if self.flagged[r][c] else '', fg='#F00')
        self.flags += 1 if self.flagged[r][c] else -1
        self.mine_label.configure(text=f"{self.mine_count - self.flags:03d}")

    def _reveal(self, r, c):
        if not (0 <= r < self.rows and 0 <= c < self.cols) or self.revealed[r][c] or self.flagged[r][c]:
            return
        self.revealed[r][c] = True
        v = self.grid[r][c]
        self.buttons[r][c].configure(relief='sunken', bd=1, bg='#D0D0D0')
        if v > 0:
            self.buttons[r][c].configure(text=str(v), fg=self.COLORS.get(v, '#000'))
        elif v == 0:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    self._reveal(r + dr, c + dc)

    def _lose(self, mr, mc):
        self.game_over = True
        self._timer_running = False
        self.face_btn._text = "😵"
        self.face_btn._draw()
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == -1:
                    bg = '#FF0000' if (r == mr and c == mc) else '#D0D0D0'
                    self.buttons[r][c].configure(text='💣', relief='sunken', bd=1, bg=bg)

    def _check_win(self):
        if all(self.grid[r][c] == -1 or self.revealed[r][c]
               for r in range(self.rows) for c in range(self.cols)):
            self.game_over = True
            self._timer_running = False
            self.face_btn._text = "😎"
            self.face_btn._draw()

    def _start_timer(self):
        self._timer_running = True
        self._tick()

    def _tick(self):
        if self._timer_running:
            self._time += 1
            self.time_label.configure(text=f"{min(self._time, 999):03d}")
            self.parent.after(1000, self._tick)


# ═══════════════════════════════════════════════════════════════
#  CONTROL PANEL (no hover highlights)
# ═══════════════════════════════════════════════════════════════

class ControlPanelApp:
    def __init__(self, parent, desktop, kernel):
        self.parent = parent
        self.desktop = desktop
        self.kernel = kernel
        self._build()

    def _build(self):
        T = Win2kTheme
        tk.Label(self.parent, text="⚙  Control Panel", bg=T.WINDOW_BG,
                 font=('Tahoma', 11, 'bold'), anchor='w', padx=10).pack(fill='x', pady=(8, 4))
        tk.Frame(self.parent, bg='#808080', height=1).pack(fill='x', padx=10)

        items_frame = tk.Frame(self.parent, bg=T.WINDOW_BG)
        items_frame.pack(fill='both', expand=True, padx=10, pady=10)

        items = [
            (Win2kTheme.ICON_USER, "User Accounts", self._users),
            (Win2kTheme.ICON_COMPUTER, "System Info", self._sysinfo),
            (Win2kTheme.ICON_FOLDER, "Disk Management", self._disks),
            (Win2kTheme.ICON_SHIELD, "Guardian", lambda: self.desktop.open_guardian()),
            (Win2kTheme.ICON_PACKAGE, "Applications", self._apps),
            (Win2kTheme.ICON_INFO, "About PyOS", lambda: self.desktop.open_about()),
        ]

        for i, (icon, label, action) in enumerate(items):
            row, col = i // 3, i % 3
            item_frame = tk.Frame(items_frame, bg=T.WINDOW_BG, cursor='hand2', padx=10, pady=10)
            item_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
            tk.Label(item_frame, text=icon, bg=T.WINDOW_BG, font=('Segoe UI', 22)).pack()
            tk.Label(item_frame, text=label, bg=T.WINDOW_BG, font=('Tahoma', 8), wraplength=80).pack()
            for w in item_frame.winfo_children():
                w.bind('<Button-1>', lambda e, a=action: a())
            item_frame.bind('<Button-1>', lambda e, a=action: a())

    def _users(self):
        win = Win2kWindow(self.desktop, title="User Accounts", width=400, height=300, icon=Win2kTheme.ICON_USER)
        frame = win.client
        T = Win2kTheme
        tk.Label(frame, text="User Accounts", bg=T.WINDOW_BG, font=('Tahoma', 10, 'bold')).pack(pady=8)
        lf = tk.Frame(frame, bd=2, relief='sunken', bg=T.TEXT_BG)
        lf.pack(fill='both', expand=True, padx=10, pady=5)
        for user in self.kernel.um.list_users():
            info = self.kernel.um.users[user]
            pw = "🔒" if info.get('has_password') else "🔓"
            cur = " ← current" if user == self.kernel.current_user else ""
            tk.Label(lf, text=f"  👤 {user}  {pw}  disk={info.get('disk', 'C')}:{cur}",
                     bg=T.TEXT_BG, font=('Tahoma', 9), anchor='w').pack(fill='x', padx=4, pady=2)
        bf = tk.Frame(frame, bg=T.WINDOW_BG)
        bf.pack(pady=8)

        def add_user():
            name = simpledialog.askstring("Add User", "Username:")
            if not name:
                return
            pw = simpledialog.askstring("Add User", "Password (empty for none):", show='*')
            ok, err = self.kernel.um.create(name, pw if pw else None)
            if ok:
                for d in [f'/home/{name}', f'/home/{name}/Desktop', f'/home/{name}/Documents']:
                    self.kernel.fs.mkdir(d)
                self.kernel.save_state()
                messagebox.showinfo("Success", f"User '{name}' created!")
                win.close()
                self._users()
            else:
                messagebox.showerror("Error", err)

        Win2kButton(bf, text="Add User", width=80, height=23, command=add_user).pack(side='left', padx=4)
        Win2kButton(bf, text="Change Password", width=110, height=23,
                    command=lambda: (self.kernel.um.change_password(
                        self.kernel.current_user,
                        simpledialog.askstring("Password", "New (empty=remove):", show='*') or None),
                        self.kernel.save_state(),
                        messagebox.showinfo("OK", "Updated"))).pack(side='left', padx=4)

    def _sysinfo(self):
        k = self.kernel
        win = Win2kWindow(self.desktop, title="System Properties", width=380, height=320,
                          icon=Win2kTheme.ICON_COMPUTER, resizable=False)
        T = Win2kTheme
        for label, value in [("System", f"PyOS v{Kernel.VERSION}"), ("Build", Kernel.BUILD),
                              ("Company", Kernel.COMPANY), ("Computer", k.hostname),
                              ("User", k.current_user), ("Uptime", k.uptime_str()),
                              ("Python", sys.version.split()[0]), ("Platform", sys.platform)]:
            row = tk.Frame(win.client, bg=T.WINDOW_BG)
            row.pack(fill='x', padx=15, pady=2)
            tk.Label(row, text=f"{label}:", bg=T.WINDOW_BG, font=('Tahoma', 8, 'bold'),
                     width=12, anchor='w').pack(side='left')
            tk.Label(row, text=value, bg=T.WINDOW_BG, font=('Tahoma', 8), anchor='w').pack(side='left')

    def _disks(self):
        win = Win2kWindow(self.desktop, title="Disk Management", width=400, height=280,
                          icon=Win2kTheme.ICON_COMPUTER)
        T = Win2kTheme
        tk.Label(win.client, text="Disk Management", bg=T.WINDOW_BG, font=('Tahoma', 10, 'bold')).pack(pady=8)
        for d in self.kernel.fs.get_disks():
            cur = " ← current" if d == self.kernel.fs.current_disk else ""
            tk.Label(win.client, text=f"  💾 Drive {d}:    {RealFS.fmt_size(self.kernel.fs.disk_usage(d))}{cur}",
                     bg=T.WINDOW_BG, font=('Tahoma', 9), anchor='w').pack(fill='x', padx=15, pady=3)

        def add_disk():
            l = simpledialog.askstring("Add Disk", "Drive letter (A-Z):")
            if l and len(l) == 1 and l.isalpha():
                l = l.upper()
                if l in self.kernel.fs.get_disks():
                    messagebox.showerror("Error", f"{l}: exists")
                else:
                    self.kernel.fs._create_disk(l)
                    self.kernel.save_state()
                    win.close()
                    self._disks()

        Win2kButton(win.client, text="Add Disk", width=80, height=23, command=add_disk).pack(pady=10)

    def _apps(self):
        win = Win2kWindow(self.desktop, title="Applications", width=450, height=350, icon=Win2kTheme.ICON_PACKAGE)
        T = Win2kTheme
        frame = win.client

        tk.Label(frame, text="Installed X5 Applications", bg=T.WINDOW_BG,
                 font=('Tahoma', 10, 'bold')).pack(pady=8)

        list_frame = tk.Frame(frame, bd=2, relief='sunken', bg=T.TEXT_BG)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        tree = ttk.Treeview(list_frame, columns=('name', 'version', 'author'), show='headings')
        tree.heading('name', text='Name')
        tree.heading('version', text='Version')
        tree.heading('author', text='Author')
        tree.column('name', width=150)
        tree.column('version', width=80)
        tree.column('author', width=120)
        tree.pack(fill='both', expand=True)

        if self.kernel.app_manager:
            for name, data in self.kernel.app_manager.apps.items():
                info = data.get('info', {})
                icon = info.get('icon', '📦')
                tree.insert('', 'end', iid=name,
                             values=(f"{icon} {name}", info.get('version', '?'), info.get('author', '?')))

        bf = tk.Frame(frame, bg=T.WINDOW_BG)
        bf.pack(pady=8)

        def run_selected():
            sel = tree.selection()
            if sel:
                win.close()
                self.desktop.open_x5_app(sel[0])

        def remove_selected():
            sel = tree.selection()
            if sel and messagebox.askyesno("Remove", f"Remove '{sel[0]}'?"):
                self.kernel.app_manager.uninstall(sel[0])
                tree.delete(sel[0])

        def new_app():
            name = simpledialog.askstring("New X5 App", "App name:")
            if name:
                docs = f'/home/{self.kernel.current_user}/Documents'
                self.kernel.fs.write_file(f'{docs}/{name}.x5',
                                          X5Parser.template(name, self.kernel.current_user))
                messagebox.showinfo("Created", f"Template saved to:\n{docs}/{name}.x5")

        Win2kButton(bf, text="▶ Run", width=60, height=23, command=run_selected).pack(side='left', padx=4)
        Win2kButton(bf, text="🗑 Remove", width=80, height=23, command=remove_selected).pack(side='left', padx=4)
        Win2kButton(bf, text="+ New App", width=80, height=23, command=new_app).pack(side='left', padx=4)


# ═══════════════════════════════════════════════════════════════
#  ABOUT
# ═══════════════════════════════════════════════════════════════

class AboutApp:
    def __init__(self, parent, kernel):
        T = Win2kTheme
        tk.Label(parent, text="🖥", bg=T.WINDOW_BG, font=('Segoe UI', 36)).pack(pady=(15, 5))
        tk.Label(parent, text="PyOS", bg=T.WINDOW_BG, font=('Tahoma', 16, 'bold')).pack()
        tk.Label(parent, text=f"Version {Kernel.VERSION} (Build {Kernel.BUILD})",
                 bg=T.WINDOW_BG, font=('Tahoma', 9)).pack(pady=2)
        tk.Frame(parent, bg='#808080', height=1).pack(fill='x', padx=20, pady=5)
        for line in [f"© {Kernel.COMPANY}", "", f"Computer: {kernel.hostname}",
                     f"User: {kernel.current_user}", f"Python {sys.version.split()[0]} on {sys.platform}",
                     "", "GUI designed in Windows 2000 style"]:
            tk.Label(parent, text=line, bg=T.WINDOW_BG, font=('Tahoma', 8)).pack()


# ═══════════════════════════════════════════════════════════════
#  LOGIN / SETUP / BOOT SCREENS
# ═══════════════════════════════════════════════════════════════

class LoginScreen:
    def __init__(self, root, kernel, on_success):
        self.root = root
        self.kernel = kernel
        self.on_success = on_success
        self._build()

    def _build(self):
        T = Win2kTheme
        self.frame = tk.Frame(self.root, bg=T.DESKTOP_BG)
        self.frame.pack(fill='both', expand=True)
        center = tk.Frame(self.frame, bg=T.WINDOW_BORDER_DARK)
        center.place(relx=0.5, rely=0.5, anchor='center')
        inner = tk.Frame(center, bg=T.WINDOW_BG, padx=20, pady=15)
        inner.pack(padx=2, pady=2)

        tb = tk.Frame(inner, bg=T.WINDOW_TITLE_ACTIVE)
        tb.pack(fill='x', pady=(0, 10))
        tk.Label(tb, text=" 🔒 Log On to PyOS", bg=T.WINDOW_TITLE_ACTIVE,
                 fg=T.WINDOW_TITLE_TEXT, font=('Tahoma', 9, 'bold'), anchor='w', padx=5, pady=3).pack(fill='x')

        tk.Label(inner, text="👤", bg=T.WINDOW_BG, font=('Segoe UI', 36)).pack(pady=5)
        tk.Label(inner, text="Welcome to PyOS", bg=T.WINDOW_BG, font=('Tahoma', 10, 'bold')).pack(pady=(0, 10))

        for label, key, show in [("User name:", 'user', ''), ("Password:", 'pass', '●')]:
            row = tk.Frame(inner, bg=T.WINDOW_BG)
            row.pack(fill='x', pady=3)
            tk.Label(row, text=label, bg=T.WINDOW_BG, font=('Tahoma', 8), width=12, anchor='w').pack(side='left')
            entry = tk.Entry(row, font=('Tahoma', 9), relief='sunken', bd=2, show=show)
            entry.pack(side='left', fill='x', expand=True)
            setattr(self, f'{key}_entry', entry)

        users = self.kernel.um.list_users()
        if users:
            self.user_entry.insert(0, users[0])
            r = tk.Frame(inner, bg=T.WINDOW_BG)
            r.pack(fill='x', pady=3)
            tk.Label(r, text=f"Users: {', '.join(users)}", bg=T.WINDOW_BG,
                     font=('Tahoma', 7), fg='#808080').pack(side='left')

        bf = tk.Frame(inner, bg=T.WINDOW_BG)
        bf.pack(fill='x', pady=(15, 5))
        Win2kButton(bf, text="OK", width=75, height=23, command=self._login).pack(side='left', padx=4)
        Win2kButton(bf, text="Cancel", width=75, height=23, command=self.root.quit).pack(side='left', padx=4)
        Win2kButton(bf, text="Shut Down", width=80, height=23, command=self.root.quit).pack(side='right', padx=4)

        self.error_label = tk.Label(inner, text="", bg=T.WINDOW_BG, fg='#FF0000', font=('Tahoma', 8))
        self.error_label.pack(pady=(5, 0))

        self.pass_entry.bind('<Return>', lambda e: self._login())
        self.user_entry.bind('<Return>', lambda e: self.pass_entry.focus())
        self.user_entry.focus()

    def _login(self):
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()
        if not username:
            self.error_label.configure(text="Please enter a username")
            return
        if username not in self.kernel.um.users:
            self.error_label.configure(text="User not found")
            return
        if self.kernel.login(username, password):
            self.frame.destroy()
            self.on_success()
        else:
            hint = self.kernel.um.get_hint(username)
            self.error_label.configure(text=f"Incorrect password{f' (Hint: {hint})' if hint else ''}")
            self.pass_entry.delete(0, 'end')


class SetupWizard:
    def __init__(self, root, kernel, on_complete):
        self.root = root
        self.kernel = kernel
        self.on_complete = on_complete
        self._build()

    def _build(self):
        T = Win2kTheme
        self.frame = tk.Frame(self.root, bg=T.DESKTOP_BG)
        self.frame.pack(fill='both', expand=True)
        center = tk.Frame(self.frame, bg=T.WINDOW_BORDER_DARK)
        center.place(relx=0.5, rely=0.5, anchor='center')
        inner = tk.Frame(center, bg=T.WINDOW_BG, padx=25, pady=20)
        inner.pack(padx=2, pady=2)

        tb = tk.Frame(inner, bg=T.WINDOW_TITLE_ACTIVE)
        tb.pack(fill='x', pady=(0, 15))
        tk.Label(tb, text=" ⚙ PyOS Setup Wizard", bg=T.WINDOW_TITLE_ACTIVE,
                 fg=T.WINDOW_TITLE_TEXT, font=('Tahoma', 9, 'bold'), anchor='w', padx=5, pady=3).pack(fill='x')

        tk.Label(inner, text=f"Welcome to PyOS {Kernel.VERSION}", bg=T.WINDOW_BG,
                 font=('Tahoma', 12, 'bold')).pack(pady=(0, 5))

        form = tk.Frame(inner, bg=T.WINDOW_BG)
        form.pack(fill='x')
        self.entries = {}
        for label, key, default, show in [("Computer Name:", 'hostname', 'PyOS', ''),
                                           ("Username:", 'username', '', ''),
                                           ("Password:", 'password', '', '●'),
                                           ("Password Hint:", 'hint', '', '')]:
            row = tk.Frame(form, bg=T.WINDOW_BG)
            row.pack(fill='x', pady=3)
            tk.Label(row, text=label, bg=T.WINDOW_BG, font=('Tahoma', 8), width=15, anchor='w').pack(side='left')
            entry = tk.Entry(row, font=('Tahoma', 9), relief='sunken', bd=2, show=show)
            entry.insert(0, default)
            entry.pack(side='left', fill='x', expand=True)
            self.entries[key] = entry

        bf = tk.Frame(inner, bg=T.WINDOW_BG)
        bf.pack(fill='x', pady=(20, 5))
        Win2kButton(bf, text="Install", width=80, height=25, font_spec=('Tahoma', 8, 'bold'),
                    command=self._install).pack(side='right', padx=4)
        Win2kButton(bf, text="Cancel", width=70, height=25, command=self.root.quit).pack(side='right', padx=4)

        self.error_label = tk.Label(inner, text="", bg=T.WINDOW_BG, fg='#FF0000', font=('Tahoma', 8))
        self.error_label.pack(pady=(5, 0))
        self.entries['username'].focus()

    def _install(self):
        hostname = self.entries['hostname'].get().strip() or 'PyOS'
        username = self.entries['username'].get().strip()
        password = self.entries['password'].get()
        hint = self.entries['hint'].get().strip()
        if not username:
            self.error_label.configure(text="Username is required!")
            return
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            self.error_label.configure(text="Letters, digits, _ only")
            return
        ok, err = self.kernel.setup(hostname, username, password if password else None, hint)
        if ok:
            self.frame.destroy()
            self.on_complete()
        else:
            self.error_label.configure(text=err)


class BootScreen:
    def __init__(self, root, on_complete):
        self.root = root
        self.on_complete = on_complete
        self._build()

    def _build(self):
        self.frame = tk.Frame(self.root, bg='#000000')
        self.frame.pack(fill='both', expand=True)
        tk.Label(self.frame, text="🖥", bg='#000', font=('Segoe UI', 48)).pack(pady=(60, 10))
        tk.Label(self.frame, text="PyOS", bg='#000', fg='#FFF', font=('Tahoma', 24, 'bold')).pack()
        tk.Label(self.frame, text=f"Version {Kernel.VERSION}", bg='#000', fg='#808080',
                 font=('Tahoma', 10)).pack(pady=5)
        tk.Label(self.frame, text=Kernel.COMPANY, bg='#000', fg='#808080', font=('Tahoma', 8)).pack(pady=(2, 30))

        pf = tk.Frame(self.frame, bg='#404040', width=300, height=18, bd=1, relief='sunken')
        pf.pack()
        pf.pack_propagate(False)
        self.pbar = tk.Frame(pf, bg='#0000AA', width=0)
        self.pbar.pack(side='left', fill='y')
        self.status = tk.Label(self.frame, text="Starting...", bg='#000', fg='#808080', font=('Tahoma', 8))
        self.status.pack(pady=10)
        self._p = 0
        self._stages = ["Loading kernel...", "Initializing filesystem...", "Loading user data...",
                         "Starting services...", "Preparing desktop..."]
        self._animate()

    def _animate(self):
        if self._p >= len(self._stages):
            self.frame.destroy()
            self.on_complete()
            return
        self.status.configure(text=self._stages[self._p])
        self._p += 1
        self.pbar.configure(width=int(300 * self._p / len(self._stages)))
        self.root.after(400, self._animate)


# ═══════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════

class PyOSApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PyOS")
        self.root.geometry("900x650")
        self.root.minsize(640, 480)
        self.root.configure(bg='#000000')
        Win2kTheme.apply_to_root(self.root)
        self.kernel = Kernel()
        self._start_boot()

    def _start_boot(self):
        BootScreen(self.root, self._after_boot)

    def _after_boot(self):
        loaded = self.kernel.boot()
        if loaded and self.kernel.um.list_users():
            self._show_login()
        else:
            self._show_setup()

    def _show_setup(self):
        SetupWizard(self.root, self.kernel, self._after_setup)

    def _after_setup(self):
        self._show_login()

    def _show_login(self):
        users = self.kernel.um.list_users()
        if len(users) == 1 and not self.kernel.um.has_password(users[0]):
            self.kernel.login(users[0])
            self._start_desktop()
        else:
            LoginScreen(self.root, self.kernel, self._start_desktop)

    def _start_desktop(self):
        self.desktop = Desktop(self.root, self.kernel)
        self.kernel.notifications.send('system', 'System Ready',
                                       f'Welcome, {self.kernel.current_user}!', 'ok', 'normal')

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            if self.kernel.fs:
                self.kernel.save_state()


def main():
    app = PyOSApp()
    app.run()


if __name__ == '__main__':
    main()