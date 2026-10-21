from contextlib import redirect_stdout
import datetime
import difflib
import io
import json
import lzma
import math
import os
from pathlib import Path
import random
import re
import shlex
import shutil
import sys
import tarfile
import textwrap
import threading
import time
import traceback as tb_module

# ═══ ПОДКЛЮЧЕНИЕ ARGON2ID ═══
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerificationError, VerifyMismatchError
    from argon2.low_level import Type, hash_secret_raw
except ImportError:
    print("\n[PyOS] Критическая ошибка: требуется модуль 'argon2-cffi'.")
    print("Установите его командой: pip install argon2-cffi")
    sys.exit(1)

# Инициализация Argon2id
ARGON2_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19456,  # 19 MiB
    parallelism=1,
    hash_len=32,
    type=Type.ID
)

def argon2id_hash_bytes(data: bytes, salt: bytes = b'pyos_argon2_salt!') -> str:
    """Генерация хеша байтов через Argon2id"""
    raw = hash_secret_raw(
        secret=data,
        salt=salt,
        time_cost=2,
        memory_cost=19456,
        parallelism=1,
        hash_len=32,
        type=Type.ID
    )
    return raw.hex()

# ═══ FIX КОДИРОВКИ WINDOWS ═══
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
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

    @staticmethod
    def c(t, color):
        return f"{color}{t}{C.RST}" if UC else str(t)

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

# ═══ АВАРИЙНЫЙ ДАМП В LOGS.TXT ═══
def emergency_dump_logs(reason, details=""):
    try:
        log_file = Path("logs.txt").resolve()
        now = datetime.datetime.now().isoformat()
        content = [
            "=== PYOS EMERGENCY CRASH DUMP ===",
            f"Timestamp: {now}",
            f"Platform: {sys.platform}",
            f"Python Version: {sys.version}",
            f"Reason: {reason}",
            f"Details: {details}",
            "Callstack:",
            tb_module.format_exc(),
            "=" * 35
        ]
        log_file.write_text('\n'.join(content), encoding='utf-8')
    except (OSError, PermissionError):
        pass

# ═══ ХЭШ-КОНТРОЛЬ СИСТЕМНОГО ФАЙЛА (ARGON2ID) ═══
def get_script_path():
    try:
        p = Path(sys.argv[0] if sys.argv[0] else __file__).resolve()
        if p.is_file():
            return p
    except (OSError, PermissionError):
        pass
    return Path(__file__).resolve()

def compute_file_hash(filepath):
    try:
        p = Path(filepath)
        if not p.is_file():
            return ""
        return argon2id_hash_bytes(p.read_bytes())
    except (OSError, PermissionError):
        return ""

def get_code_hash_file(script_path):
    return script_path.parent / '.pyos_code_hash'

def save_code_hash(script_path, cur_hash=None, version='17.4', build='03.10.2026'):
    if cur_hash is None:
        cur_hash = compute_file_hash(script_path)
    hf = get_code_hash_file(script_path)
    data = {
        'hash': cur_hash,
        'algorithm': 'Argon2id',
        'version': version,
        'build': build,
        'updated': datetime.datetime.now().isoformat()
    }
    try:
        hf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        return True
    except (OSError, PermissionError):
        return False

# ═══ РЕЗЕРВНОЕ КОПИРОВАНИЕ (.BACKUP С ПРОВЕРКОЙ ЦЕЛОСТНОСТИ ARGON2ID) ═══
class BackupManager:
    @staticmethod
    def get_backup_dir():
        script_dir = get_script_path().parent
        bdir = script_dir / 'backups'
        bdir.mkdir(parents=True, exist_ok=True)
        return bdir

    @classmethod
    def create_backup(cls, name=None, kernel=None):
        bdir = cls.get_backup_dir()
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name) if name else f"pyos_backup_{ts}"
        if not clean_name.endswith('.backup'):
            clean_name += '.backup'
        backup_path = bdir / clean_name

        script_path = get_script_path()
        manifest = {
            'created': datetime.datetime.now().isoformat(),
            'version': kernel.VERSION if kernel else '17.4',
            'build': kernel.BUILD if kernel else '03.10.2026',
            'script_name': script_path.name,
            'script_hash': compute_file_hash(script_path),
            'hash_type': 'Argon2id',
            'hostname': kernel.hostname if kernel else 'pyos'
        }

        try:
            with open(backup_path, 'wb') as f_out:
                with lzma.open(f_out, 'wb', preset=9 | lzma.PRESET_EXTREME) as xz_out:
                    with tarfile.open(fileobj=xz_out, mode='w') as tar:
                        tar.add(script_path, arcname='pyos_source.py')

                        m_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode('utf-8')
                        ti = tarfile.TarInfo(name='manifest.json')
                        ti.size = len(m_bytes)
                        ti.mtime = int(time.time())
                        tar.addfile(ti, io.BytesIO(m_bytes))

                        hostname = kernel.hostname if kernel else 'pyos'
                        base_p = Path(kernel.base_path) if kernel else script_path.parent
                        hdir = (base_p / hostname).resolve()
                        if hdir.exists():
                            tar.add(hdir, arcname='data')
            return True, backup_path
        except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError) as e:
            if backup_path.exists():
                try:
                    backup_path.unlink()
                except OSError:
                    pass
            return False, str(e)

    @classmethod
    def verify_backup(cls, backup_path):
        bp = Path(backup_path)
        if not bp.is_file():
            return False, "File not found", None
        try:
            with open(bp, 'rb') as f_in:
                with lzma.open(f_in, 'rb') as xz_in:
                    with tarfile.open(fileobj=xz_in, mode='r') as tar:
                        manifest_member = tar.extractfile('manifest.json')
                        if not manifest_member:
                            return False, "Manifest missing", None
                        manifest = json.loads(manifest_member.read().decode('utf-8'))

                        src_member = tar.extractfile('pyos_source.py')
                        if not src_member:
                            return False, "Source missing", None
                        code_bytes = src_member.read()
                        actual_hash = argon2id_hash_bytes(code_bytes)

                        if manifest.get('script_hash') and actual_hash != manifest.get('script_hash'):
                            return False, "Code Argon2id mismatch", None

                        compile(code_bytes, 'pyos_source.py', 'exec')
                        return True, "Valid", manifest
        except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError, json.JSONDecodeError, SyntaxError) as e:
            return False, str(e), None

    @classmethod
    def list_backups(cls):
        bdir = cls.get_backup_dir()
        result = []
        if not bdir.exists():
            return result
        for f in sorted(bdir.glob('*.backup'), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                sz = f.stat().st_size
                mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                valid, err, mf = cls.verify_backup(f)
                result.append({
                    'name': f.name,
                    'path': f,
                    'size': sz,
                    'time': mtime,
                    'valid': valid,
                    'error': err,
                    'manifest': mf
                })
            except (OSError, PermissionError):
                pass
        return result

    @classmethod
    def get_valid_backups(cls):
        return [b for b in cls.list_backups() if b['valid']]

    @classmethod
    def restore_backup(cls, backup_path, kernel=None):
        bp = Path(backup_path)
        valid, err, manifest = cls.verify_backup(bp)
        if not valid:
            return False, f"Повреждённая копия: {err}"

        script_path = get_script_path()
        try:
            with open(bp, 'rb') as f_in:
                with lzma.open(f_in, 'rb') as xz_in:
                    with tarfile.open(fileobj=xz_in, mode='r') as tar:
                        src_member = tar.extractfile('pyos_source.py')
                        if src_member:
                            code_bytes = src_member.read()
                            with open(script_path, 'wb') as sf:
                                sf.write(code_bytes)
                            save_code_hash(script_path)

                        hostname = (manifest or {}).get('hostname', kernel.hostname if kernel else 'pyos')
                        dest_base = Path(kernel.base_path) if kernel else script_path.parent
                        target_host_dir = (dest_base / hostname).resolve()

                        for member in tar.getmembers():
                            if member.name.startswith('data/'):
                                rel = member.name[5:]
                                if not rel:
                                    continue
                                out_p = target_host_dir / rel
                                if member.isdir():
                                    out_p.mkdir(parents=True, exist_ok=True)
                                elif member.isfile():
                                    out_p.parent.mkdir(parents=True, exist_ok=True)
                                    ef = tar.extractfile(member)
                                    if ef:
                                        out_p.write_bytes(ef.read())
            return True, "Восстановление успешно завершено"
        except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError) as e:
            return False, str(e)

# ═══ ВЕРИФИКАЦИЯ ЦЕЛОСТНОСТИ И ВОССТАНОВЛЕНИЕ ═══
def handle_repair_or_dead_end(reason):
    emergency_dump_logs(reason)
    valid_backups = BackupManager.get_valid_backups()

    if not valid_backups:
        print()
        print(C.c("Внимание, код PYOS и резервные копии повреждены/отсутствуют", C.R + C.B))
        print("\nПоследние данные системы сохранены в logs.txt")
        try:
            input("\nНажмите Enter для завершения...")
        except (EOFError, KeyboardInterrupt):
            pass
        sys.exit(1)

    print()
    print(C.c("Внимание, код PYOS поврежден/отсутствует", C.Y + C.B))
    try:
        input("\nНажмите Enter чтобы восстановить систему из резервной копии...")
    except (EOFError, KeyboardInterrupt):
        sys.exit(1)

    print("\n" + "=" * 64)
    print("  Выбор проверенной резервной копии для восстановления:")
    print("=" * 64)
    for idx, b in enumerate(valid_backups, 1):
        sz_kb = b['size'] / 1024
        t_str = b['time'][:19].replace('T', ' ')
        print(f"  {idx}. {b['name']:<35} {sz_kb:>7.1f} KB | {t_str}")
    print("=" * 64)

    choice = 0
    while choice < 1 or choice > len(valid_backups):
        try:
            choice = int(input(f"  Выберите копию (1-{len(valid_backups)}): ").strip())
        except (ValueError, EOFError, KeyboardInterrupt):
            pass

    selected_backup = valid_backups[choice - 1]['path']
    print(C.c(f"\n  Восстановление из {selected_backup.name}...", C.CY))
    ok, msg = BackupManager.restore_backup(selected_backup)
    if ok:
        print(C.c("  [PYOS] Система и код успешно восстановлены! Перезапуск...\n", C.G))
        time.sleep(1.0)
        script_p = get_script_path()
        os.execv(sys.executable, [sys.executable, str(script_p)] + sys.argv[1:])
    else:
        print(C.c(f"  [PYOS] Критическая ошибка при восстановлении: {msg}", C.R))
        sys.exit(1)

def verify_pyos_integrity():
    script_p = get_script_path()
    if not script_p.exists() or script_p.stat().st_size == 0:
        handle_repair_or_dead_end("PYOS source file missing or zero bytes")

    try:
        compile(script_p.read_bytes(), str(script_p), 'exec')
    except (SyntaxError, ValueError) as e:
        handle_repair_or_dead_end(f"PYOS source syntax corrupted: {e}")

    hf = get_code_hash_file(script_p)
    cur_hash = compute_file_hash(script_p)

    if not hf.exists():
        save_code_hash(script_p, cur_hash)
        return True

    try:
        data = json.loads(hf.read_text(encoding='utf-8'))
        saved_hash = data.get('hash', '')
    except (json.JSONDecodeError, OSError):
        try:
            saved_hash = hf.read_text(encoding='utf-8').strip()
        except OSError:
            saved_hash = ''

    if cur_hash == saved_hash:
        return True

    print()
    print(C.c("  Внимание, код PYOS был изменён (Argon2id не совпадает)", C.Y + C.B))
    print(C.c("  Если это сделали вы, введите '1', если нет — '2'", C.W))
    choice = ''
    while choice not in ('1', '2'):
        try:
            choice = input(C.c("  > ", C.W)).strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)

    if choice == '1':
        save_code_hash(script_p, cur_hash)
        print(C.c("  [PYOS] Хэш Argon2id обновлён. Запуск...\n", C.G))
        time.sleep(0.3)
        return True
    handle_repair_or_dead_end("User detected unauthorized code modifications")
    return False

# ═══ УТИЛИТА ПРИМЕНЕНИЯ UNIFIED DIFF ПАТЧЕЙ ═══
def apply_unified_diff(source_text: str, patch_text: str) -> str:
    """Применяет unified git diff к тексту без внешних утилит patch/git"""
    lines = source_text.splitlines(keepends=True)
    patch_lines = patch_text.splitlines(keepends=True)
    
    chunks = []
    current_chunk = []
    in_chunk = False
    
    for line in patch_lines:
        if line.startswith('@@'):
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = [line]
            in_chunk = True
        elif in_chunk:
            if line.startswith(('---', '+++')):
                continue
            current_chunk.append(line)
    if current_chunk:
        chunks.append(current_chunk)

    if not chunks:
        raise ValueError("В патче не найдено ни одного блока @@ ... @@")

    chunks_data = []
    hunk_header_re = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
    for chunk in chunks:
        header = chunk[0]
        m = hunk_header_re.match(header)
        if not m:
            continue
        old_start = int(m.group(1))
        chunks_data.append((old_start, chunk[1:]))

    chunks_data.sort(key=lambda x: x[0], reverse=True)

    for old_start, hunk_lines in chunks_data:
        idx = old_start - 1
        removals = []
        additions = []
        for hline in hunk_lines:
            if hline.startswith('-'):
                removals.append(hline[1:])
            elif hline.startswith('+'):
                additions.append(hline[1:])
            elif hline.startswith(' ') or hline.strip() == '':
                if removals or additions:
                    lines[idx:idx + len(removals)] = additions
                    idx += len(additions)
                    removals = []
                    additions = []
                idx += 1
        if removals or additions:
            lines[idx:idx + len(removals)] = additions

    return "".join(lines)

# ═══ ПРОСТАЯ ТЕКСТОВАЯ РАЗМЕТКА ═══
class SimpleBox:
    @staticmethod
    def header(title, width=50, char='='):
        line = char * width
        return f"{line}\n  {title}\n{line}"

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
        if not self.fs or not self.fs.hostname_dir:
            return False
        return self.fs.hostname_dir.exists()

    def _monitor_loop(self):
        while self._running:
            time.sleep(2.5)
            if not self._running:
                break
            if not self.check_now():
                self._running = False
                self.kernel.trigger_bsod('CRITICAL_DATA_DESTROYED',
                                         'System data folder has been deleted.',
                                         f'Missing: {self.fs.hostname_dir if self.fs else "unknown"}')
                self.kernel.running = False
                return

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
        if count <= 3:
            return C.c(f"[{count}]", C.Y)
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

# ═══ ТАЙМЕРЫ И ФОНОВЫЕ СЛУЖБЫ ═══
class TimerService:
    def __init__(self, notifications):
        self.notifications = notifications
        self.timers = []
        self._timer_lock = threading.Lock()
        self._next_timer_id = 1
        self._running = False
        self._thread = None

    def start(self):
        if self._running and self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

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
        if any(not t['fired'] for t in self.timers):
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
        self.hostname_dir = (self.base / hostname).resolve()
        self.hostname_dir.mkdir(parents=True, exist_ok=True)
        self.create_disk('C')
        self.current_disk = 'C'
        for d in ['home', 'sysdata', 'sysdata/trash', 'cache', 'cache/deleted_apps',
                  'cache/trash_archives', 'apps', 'apps/installed', 'apps/data', 'apps/store', 'apps/logs']:
            self.get_disk_path('C', d).mkdir(parents=True, exist_ok=True)

    def create_disk(self, name):
        if self.hostname_dir:
            (self.hostname_dir / name.upper()).mkdir(parents=True, exist_ok=True)

    def get_disk_path(self, disk, rel_path=''):
        if not self.hostname_dir:
            return self.base / disk.upper()
        p = self.hostname_dir / disk.upper()
        if rel_path:
            p = p / rel_path.lstrip('/')
        return p

    def parse_disk_prefix(self, path):
        if len(path) >= 2 and path[1] == ':' and path[0].isalpha():
            d = path[0].upper()
            if self.hostname_dir and (self.hostname_dir / d).exists():
                return d, path[2:] or '/'
        return None, path

    def to_real_path(self, virtual_path, cwd='/', disk_override=None):
        disk = disk_override or self.current_disk
        explicit, virtual_path = self.parse_disk_prefix(virtual_path)
        if explicit:
            disk = explicit
        if not virtual_path.startswith('/'):
            virtual_path = cwd.rstrip('/') + '/' + virtual_path
        parts = []
        for p in virtual_path.split('/'):
            if p in ('', '.'):
                continue
            if p == '..':
                if parts:
                    parts.pop()
            else:
                parts.append(p)
        return self.get_disk_path(disk, '/'.join(parts)), disk

    def resolve(self, path, cwd='/'):
        explicit, path = self.parse_disk_prefix(path)
        if not path.startswith('/'):
            path = cwd.rstrip('/') + '/' + path
        parts = []
        for p in path.split('/'):
            if p in ('', '.'):
                continue
            if p == '..':
                if parts:
                    parts.pop()
            else:
                parts.append(p)
        resolved = '/' + '/'.join(parts)
        return (resolved, explicit) if explicit else (resolved, None)

    def exists(self, path, cwd='/'):
        rp, _ = self.to_real_path(path, cwd)
        return rp.exists()

    def is_dir(self, path, cwd='/'):
        rp, _ = self.to_real_path(path, cwd)
        return rp.is_dir()

    def is_file(self, path, cwd='/'):
        rp, _ = self.to_real_path(path, cwd)
        return rp.is_file()

    def mkdir(self, path, cwd='/'):
        try:
            rp, _ = self.to_real_path(path, cwd)
            rp.mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False

    def write_file(self, path, content, cwd='/', append=False):
        try:
            rp, _ = self.to_real_path(path, cwd)
            rp.parent.mkdir(parents=True, exist_ok=True)
            if append:
                with open(rp, 'a', encoding='utf-8') as f:
                    f.write(content)
            else:
                rp.write_text(content, encoding='utf-8')
            return True
        except (OSError, PermissionError):
            return False

    def write_bytes(self, path, data, cwd='/'):
        try:
            rp, _ = self.to_real_path(path, cwd)
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_bytes(data)
            return True
        except (OSError, PermissionError):
            return False

    def read_file(self, path, cwd='/'):
        try:
            rp, _ = self.to_real_path(path, cwd)
            if not rp.is_file():
                return None
            return rp.read_text(encoding='utf-8')
        except (OSError, PermissionError, UnicodeDecodeError):
            return None

    def read_bytes(self, path, cwd='/'):
        try:
            rp, _ = self.to_real_path(path, cwd)
            if not rp.is_file():
                return None
            return rp.read_bytes()
        except (OSError, PermissionError):
            return None

    def delete(self, path, cwd='/', recursive=False):
        try:
            rp, disk = self.to_real_path(path, cwd)
            if not self.hostname_dir or rp in (self.hostname_dir, self.base, self.get_disk_path(disk)):
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
            src_rp, _ = self.to_real_path(src, cwd)
            dst_rp, _ = self.to_real_path(dst, cwd)
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
            src_rp, _ = self.to_real_path(src, cwd)
            dst_rp, _ = self.to_real_path(dst, cwd)
            if not src_rp.exists():
                return False
            dst_rp.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_rp), str(dst_rp))
            return True
        except (OSError, PermissionError, shutil.Error):
            return False

    def rename(self, src, new_name, cwd='/'):
        try:
            src_rp, _ = self.to_real_path(src, cwd)
            if not src_rp.exists():
                return False
            src_rp.rename(src_rp.parent / new_name)
            return True
        except (OSError, PermissionError):
            return False

    def list_dir(self, path, cwd='/'):
        try:
            rp, _ = self.to_real_path(path, cwd)
            if not rp.is_dir():
                return None
            items = []
            for entry in sorted(rp.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    is_d = entry.is_dir()
                    items.append({
                        'name': entry.name,
                        'is_dir': is_d,
                        'size': entry.stat().st_size if not is_d else 0,
                        'modified': datetime.datetime.fromtimestamp(entry.stat().st_mtime).isoformat(),
                    })
                except (OSError, PermissionError):
                    pass
            return items
        except (OSError, PermissionError):
            return None

    def _dir_size(self, path):
        total = 0
        try:
            for root, _, files in os.walk(path):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
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
            rp, _ = self.to_real_path(path, cwd)
            if not rp.is_dir():
                return results
            for root, _, files in os.walk(rp):
                for f in files:
                    if pattern in f:
                        rel = os.path.relpath(os.path.join(root, f), rp).replace('\\', '/')
                        results.append('/' + rel)
        except (OSError, PermissionError):
            pass
        return results

    def touch(self, path, cwd='/'):
        try:
            rp, _ = self.to_real_path(path, cwd)
            rp.parent.mkdir(parents=True, exist_ok=True)
            if rp.exists():
                os.utime(rp, None)
            else:
                rp.write_text('', encoding='utf-8')
            return True
        except (OSError, PermissionError):
            return False

    def disk_usage(self, disk=None):
        if not self.hostname_dir:
            return 0
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
        rp, _ = self.to_real_path(path, cwd)
        if not rp.exists():
            return "Not found"
        lines = []
        self._tree_r(rp, lines, '', True, True, 0, max_depth)
        return '\n'.join(lines)

    def _tree_r(self, path, lines, prefix, is_last, is_root, depth, max_depth):
        if depth > max_depth:
            return
        conn = '' if is_root else ('└── ' if is_last else '├── ')
        if path.is_dir():
            col = C.BL
        elif path.name.lower().endswith('.x4s'):
            col = C.CY + C.B
        elif path.name.endswith('.x4'):
            col = C.M
        elif path.name.endswith('.backup'):
            col = C.G
        elif path.name.endswith('.disabled'):
            col = C.DIM
        else:
            col = C.W
        lines.append(prefix + conn + C.c(
            path.name + ('/' if path.is_dir() and not is_root else ''), col))
        if path.is_dir():
            try:
                items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for i, child in enumerate(items):
                    np = prefix + ('' if is_root else ('    ' if is_last else '│   '))
                    self._tree_r(child, lines, np, i == len(items) - 1,
                                 False, depth + 1, max_depth)
            except (OSError, PermissionError):
                pass

    def get_all_files_sorted_by_size(self, disk=None):
        if not self.hostname_dir:
            return []
        disk = disk or self.current_disk
        dp = self.hostname_dir / disk
        files = []
        try:
            for root, _, fs in os.walk(dp):
                for f in fs:
                    full_p = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(full_p)
                        rel = os.path.relpath(full_p, dp).replace('\\', '/')
                        files.append({'path': '/' + rel, 'size': sz, 'name': f})
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass
        files.sort(key=lambda x: x['size'], reverse=True)
        return files

    def dir_size_at(self, path, cwd='/'):
        rp, _ = self.to_real_path(path, cwd)
        return self._dir_size(rp) if rp.exists() and rp.is_dir() else 0

# ═══ КОРЗИНА (RECYCLE BIN) ═══
class TrashManager:
    """Менеджер Корзины: сжатие в tar.xz при очистке, полное удаление одиночных файлов и восстановление"""
    def __init__(self, fs, guardian):
        self.fs = fs
        self.guardian = guardian
        self.index_path = '/sysdata/trash_index.json'
        self.trash_dir = '/sysdata/trash'
        self._lock = threading.Lock()

    def _load_index(self):
        content = self.fs.read_file(self.index_path)
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
        return {'items': [], 'next_id': 1}

    def _save_index(self, data):
        self.fs.write_file(self.index_path, json.dumps(data, indent=2, ensure_ascii=False))

    def put(self, virtual_path, cwd='/'):
        with self._lock:
            resolved, _ = self.fs.resolve(virtual_path, cwd)
            real_src, disk_used = self.fs.to_real_path(virtual_path, cwd)
            if not real_src.exists():
                return False, "Файл или папка не найдены"
            if real_src in (self.fs.hostname_dir, self.fs.base):
                return False, "Нельзя переместить системный корень в корзину"

            data = self._load_index()
            item_id = data.get('next_id', 1)
            data['next_id'] = item_id + 1

            is_dir = real_src.is_dir()
            sz = self.guardian.dir_size_at(virtual_path, cwd) if is_dir else real_src.stat().st_size
            trash_filename = f"{item_id}_{real_src.name}"
            trash_vpath = f"{self.trash_dir}/{trash_filename}"

            self.fs.mkdir(self.trash_dir)
            real_dst, _ = self.fs.to_real_path(trash_vpath)

            try:
                shutil.move(str(real_src), str(real_dst))
            except (OSError, PermissionError, shutil.Error) as e:
                return False, f"Ошибка перемещения в корзину: {e}"

            entry = {
                'id': item_id,
                'name': real_src.name,
                'orig_path': resolved,
                'disk': disk_used,
                'size': sz,
                'is_dir': is_dir,
                'trash_name': trash_filename,
                'deleted_at': datetime.datetime.now().isoformat()
            }
            data['items'].append(entry)
            self._save_index(data)
            return True, f"'{real_src.name}' перемещён в Корзину [ID #{item_id}]"

    def list_items(self):
        with self._lock:
            return self._load_index().get('items', [])

    def restore(self, target_id):
        with self._lock:
            data = self._load_index()
            items = data.get('items', [])
            target = None
            for it in items:
                if str(it['id']) == str(target_id) or it['name'] == str(target_id):
                    target = it
                    break
            if not target:
                return False, f"Элемент '{target_id}' не найден в корзине"

            trash_vpath = f"{self.trash_dir}/{target['trash_name']}"
            real_trash, _ = self.fs.to_real_path(trash_vpath)
            if not real_trash.exists():
                items.remove(target)
                self._save_index(data)
                return False, "Файл физически отсутствует в корзине"

            orig_disk = target.get('disk', self.fs.current_disk)
            real_dst = self.fs.get_disk_path(orig_disk, target['orig_path'])
            real_dst.parent.mkdir(parents=True, exist_ok=True)

            if real_dst.exists():
                return False, f"Целевой путь '{target['orig_path']}' уже существует. Переименуйте или удалите его."

            try:
                shutil.move(str(real_trash), str(real_dst))
            except (OSError, PermissionError, shutil.Error) as e:
                return False, f"Ошибка восстановления: {e}"

            items.remove(target)
            self._save_index(data)
            return True, f"'{target['name']}' успешно восстановлен в {orig_disk}:{target['orig_path']}"

    def delete_single(self, target_id):
        with self._lock:
            data = self._load_index()
            items = data.get('items', [])
            target = None
            for it in items:
                if str(it['id']) == str(target_id) or it['name'] == str(target_id):
                    target = it
                    break
            if not target:
                return False, f"Элемент '{target_id}' не найден в корзине"

            trash_vpath = f"{self.trash_dir}/{target['trash_name']}"
            real_trash, _ = self.fs.to_real_path(trash_vpath)
            if real_trash.exists():
                try:
                    if real_trash.is_dir():
                        shutil.rmtree(real_trash)
                    else:
                        real_trash.unlink()
                except (OSError, PermissionError) as e:
                    return False, f"Ошибка удаления: {e}"

            items.remove(target)
            self._save_index(data)
            return True, f"'{target['name']}' навсегда удалён из корзины"

    def empty(self, compress=True):
        with self._lock:
            data = self._load_index()
            items = data.get('items', [])
            if not items:
                return True, "Корзина уже пуста"

            archive_info = ""
            if compress:
                ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                self.fs.mkdir('/cache/trash_archives')
                archive_vpath = f"/cache/trash_archives/trash_dump_{ts}.tar.xz"
                real_archive, _ = self.fs.to_real_path(archive_vpath)
                real_trash_dir, _ = self.fs.to_real_path(self.trash_dir)

                try:
                    with lzma.open(real_archive, 'wb', preset=9 | lzma.PRESET_EXTREME) as xz_out:
                        with tarfile.open(fileobj=xz_out, mode='w') as tar:
                            m_bytes = json.dumps(items, indent=2, ensure_ascii=False).encode('utf-8')
                            ti = tarfile.TarInfo(name='manifest.json')
                            ti.size = len(m_bytes)
                            ti.mtime = int(time.time())
                            tar.addfile(ti, io.BytesIO(m_bytes))

                            for it in items:
                                tpath = real_trash_dir / it['trash_name']
                                if tpath.exists():
                                    tar.add(tpath, arcname=f"files/{it['name']}")
                    arch_sz = self.guardian.fmt_size(real_archive.stat().st_size)
                    archive_info = f" (Архив сохранён: {archive_vpath}, {arch_sz})"
                except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError) as e:
                    archive_info = f" (Ошибка сжатия: {e})"

            real_trash_dir, _ = self.fs.to_real_path(self.trash_dir)
            if real_trash_dir.exists():
                try:
                    for child in real_trash_dir.iterdir():
                        if child.is_dir():
                            shutil.rmtree(child)
                        else:
                            child.unlink()
                except (OSError, PermissionError):
                    pass

            count = len(items)
            data['items'] = []
            self._save_index(data)
            return True, f"Корзина очищена ({count} объектов удалено){archive_info}"

# ═══ МЕНЕДЖЕР ПОЛЬЗОВАТЕЛЕЙ (ARGON2ID) ═══
class UserManager:
    HIDDEN_FIELDS = {'pw'}

    def __init__(self):
        self.users = {}

    def create(self, name, pw=None, hint=''):
        if name in self.users:
            return False, "User exists"
        existing_uids = [u['uid'] for u in self.users.values()]
        new_uid = max(existing_uids) + 1 if existing_uids else 0
        self.users[name] = {
            'pw': ARGON2_HASHER.hash(pw) if pw else '',
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
        try:
            return ARGON2_HASHER.verify(u['pw'], pw)
        except (VerificationError, VerifyMismatchError):
            return False
        except Exception:
            return False

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
            self.users[name]['pw'] = ARGON2_HASHER.hash(new_pw)
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

# ═══ GUARDIAN & ОПТИМИЗАЦИЯ & ЦЕНТР ОБНОВЛЕНИЙ И УДАЛЕНИЯ ═══
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
        rp, _ = fs.to_real_path(f'/apps/data/{app_name}')
        if not rp.exists():
            return []
        files = []
        try:
            for root, _, fs_names in os.walk(rp):
                for f in fs_names:
                    p = os.path.join(root, f)
                    try:
                        files.append((p, os.path.getsize(p), f))
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        files.sort(key=lambda x: x[1], reverse=True)
        for fpath, fsize, fname in files:
            if current <= limit:
                break
            try:
                os.remove(fpath)
                deleted.append((fname, fsize))
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

    def disk_report(self, fs):
        files = fs.get_all_files_sorted_by_size()
        return {'total': fs.disk_usage(), 'count': len(files), 'largest': files[:10]}

    def fmt_size(self, size):
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    # ═══ ЦЕНТР ОБНОВЛЕНИЙ PYOS (UPDATE CENTER) ═══
    def parse_patch_package(self, raw_patch_str: str):
        """Парсит структурированный пакет [BEGIN PYOS PATCH] ... [END PYOS PATCH]"""
        raw_patch_str = raw_patch_str.strip()
        if not raw_patch_str.startswith("[BEGIN PYOS PATCH]") or not raw_patch_str.endswith("[END PYOS PATCH]"):
            return None, "Некорректный заголовок или подвал пакета обновления"

        body = raw_patch_str[len("[BEGIN PYOS PATCH]"): -len("[END PYOS PATCH]")].strip()
        diff_marker = "[BEGIN DIFF]"
        diff_end_marker = "[END DIFF]"

        if diff_marker not in body or diff_end_marker not in body:
            return None, "В пакете обновления отсутствует блок диффа [BEGIN DIFF]"

        header_part, rest = body.split(diff_marker, 1)
        diff_part, _ = rest.split(diff_end_marker, 1)

        base_hash = ""
        target_hash = ""
        lines = header_part.strip().split('\n')
        json_lines = []
        json_started = False

        for line in lines:
            sline = line.strip()
            if sline.startswith("Base-Hash:"):
                base_hash = sline.split(":", 1)[1].strip()
            elif sline.startswith("Target-Hash:"):
                target_hash = sline.split(":", 1)[1].strip()
            elif sline.startswith("{") or json_started:
                json_started = True
                json_lines.append(line)

        meta = {}
        if json_lines:
            try:
                meta = json.loads("\n".join(json_lines))
            except json.JSONDecodeError:
                pass

        return {
            'base_hash': base_hash,
            'target_hash': target_hash,
            'meta': meta,
            'diff': diff_part.strip()
        }, None

    def apply_patch_update(self, patch_content: str, kernel):
        pkg, err = self.parse_patch_package(patch_content)
        if err:
            return False, f"Ошибка разбора патча: {err}"

        script_p = get_script_path()
        current_bytes = script_p.read_bytes()
        current_hash = argon2id_hash_bytes(current_bytes)

        if pkg['base_hash'] and pkg['base_hash'] != current_hash:
            return False, f"Base-Hash не совпадает с текущим ядром!\nТекущий: {current_hash}\nВ патче:  {pkg['base_hash']}"

        try:
            current_text = current_bytes.decode('utf-8')
            updated_text = apply_unified_diff(current_text, pkg['diff'])
            compile(updated_text, 'pyos_patched.py', 'exec')
        except Exception as e:
            return False, f"Ошибка применения/компиляции диффа: {e}"

        updated_bytes = updated_text.encode('utf-8')
        new_hash = argon2id_hash_bytes(updated_bytes)

        if pkg['target_hash'] and pkg['target_hash'] != new_hash:
            return False, f"Целевой Target-Hash не сошёлся!\nПолучен: {new_hash}\nОжидался: {pkg['target_hash']}"

        # Создание автоматической резервной копии перед патчингом
        BackupManager.create_backup("pre_patch_update", kernel)

        script_p.write_bytes(updated_bytes)
        new_ver = pkg['meta'].get('version', kernel.VERSION)
        new_build = pkg['meta'].get('build', kernel.BUILD)
        save_code_hash(script_p, cur_hash=new_hash, version=new_ver, build=new_build)

        return True, f"Патч успешно применён! Версия обновлена до {new_ver} (build {new_build})"

    def apply_full_code_update(self, new_code_str: str, kernel):
        try:
            compile(new_code_str, 'pyos_new.py', 'exec')
        except SyntaxError as e:
            return False, f"Синтаксическая ошибка в новом коде: {e}"

        script_p = get_script_path()
        BackupManager.create_backup("pre_full_update", kernel)

        new_bytes = new_code_str.encode('utf-8')
        script_p.write_bytes(new_bytes)
        new_hash = argon2id_hash_bytes(new_bytes)

        # Вытаскиваем версию из шапки нового кода
        ver_match = re.search(r'PyOS v(\d+\.\d+)', new_code_str)
        build_match = re.search(r'build (\d+\.\d+\.\d+)', new_code_str)
        ver = ver_match.group(1) if ver_match else kernel.VERSION
        bld = build_match.group(1) if build_match else kernel.BUILD

        save_code_hash(script_p, cur_hash=new_hash, version=ver, build=bld)
        return True, f"Код успешно обновлён. Сгенерирован новый Argon2id хеш: {new_hash[:16]}..."

    # ═══ ДЕИНСТАЛЛЯТОР PYOS ═══
    def uninstall_pyos(self, mode: str, kernel):
        """
        mode: 'full' — полное удаление без остатка
              'backup' — удаление с сохранением копии в отдельную папку вне системы
        """
        script_p = get_script_path()
        base_dir = Path(kernel.base_path).resolve()
        backup_folder_created = ""

        if mode == 'backup':
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            external_backup_dir = base_dir.parent / f"pyos_uninstalled_backup_{ts}"
            external_backup_dir.mkdir(parents=True, exist_ok=True)
            # Копируем скрипт ОС
            shutil.copy2(script_p, external_backup_dir / script_p.name)
            # Копируем системный каталог данных
            hdir = (base_dir / kernel.hostname).resolve()
            if hdir.exists():
                shutil.copytree(hdir, external_backup_dir / kernel.hostname, dirs_exist_ok=True)
            bdir = base_dir / 'backups'
            if bdir.exists():
                shutil.copytree(bdir, external_backup_dir / 'backups', dirs_exist_ok=True)
            backup_folder_created = str(external_backup_dir)

        # Остановка сервисов
        if kernel._fs_checker:
            kernel._fs_checker.stop()
        kernel.timer_service.stop()

        # Удаление файлов хоста и данных
        hdir = (base_dir / kernel.hostname).resolve()
        if hdir.exists():
            shutil.rmtree(hdir, ignore_errors=True)

        for meta_file in ('.pyos_host', '.pyos_code_hash', 'logs.txt'):
            mf = base_dir / meta_file
            if mf.exists():
                try:
                    mf.unlink()
                except OSError:
                    pass

        bdir = base_dir / 'backups'
        if bdir.exists() and mode == 'full':
            shutil.rmtree(bdir, ignore_errors=True)

        # Создание файла самоудаления для самого pyos.py
        try:
            script_p.unlink()
        except OSError:
            pass

        return True, backup_folder_created

# ═══ CRASH LOGGER ═══
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
    VALID_AUTOBACKUP = ('off', 'at_start', 'at_shutdown', 'hourly')

    def __init__(self):
        self.time_mode = 'auto'
        self.time_offset = 0.0
        self.debug_mode = False
        self.smart_memory = False
        self.auto_backup = 'at_start'
        self.lang = 'ru'

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
        return {
            'time_mode': self.time_mode,
            'time_offset': self.time_offset,
            'debug_mode': self.debug_mode,
            'smart_memory': self.smart_memory,
            'auto_backup': self.auto_backup,
            'lang': self.lang,
        }

    def from_dict(self, data):
        self.time_mode = data.get('time_mode', 'auto')
        self.time_offset = data.get('time_offset', 0.0)
        self.debug_mode = data.get('debug_mode', False)
        self.smart_memory = data.get('smart_memory', False)
        self.auto_backup = data.get('auto_backup', 'at_start')
        self.lang = data.get('lang', 'ru')

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
        except (OSError, PermissionError):
            return False

    def load(self):
        try:
            content = self.fs.read_file('/sysdata/errors.json')
            if content:
                self.errors = json.loads(content)
                if self.errors:
                    self._next_id = max(e.get('id', 0) for e in self.errors) + 1
                return True
        except (json.JSONDecodeError, OSError):
            pass
        self.errors = []
        return False

    def clear(self):
        with self._lock:
            self.errors = []
            self.save()

    def get_recent(self, n=20):
        with self._lock:
            return self.errors[-n:]

    def count(self):
        with self._lock:
            return len(self.errors)

# ═══ X4 ПАРСЕР И PYTHON РАНТАЙМ ═══
class X4Parser:
    @staticmethod
    def parse(content):
        result = {'info': {}, 'code': '', 'data': {}, 'other': ''}
        m = re.search(r'\[INFO\](.*?)(?=\[CODE\]|\[DATA\]|\[OTHER\]|\[END\])', content, re.DOTALL | re.IGNORECASE)
        if m:
            for line in m.group(1).strip().split('\n'):
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    k, v = line.split(':', 1)
                    result['info'][k.strip().lower()] = v.strip()
        m = re.search(r'\[CODE\](.*?)\[/CODE\]', content, re.DOTALL | re.IGNORECASE)
        if m:
            result['code'] = m.group(1)
        m = re.search(r'\[DATA\](.*?)\[/DATA\]', content, re.DOTALL | re.IGNORECASE)
        if m:
            for line in m.group(1).strip().split('\n'):
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    k, v = line.split(':', 1)
                    result['data'][k.strip().lower()] = v.strip()
        m = re.search(r'\[OTHER\](.*?)(?=\[END\]|\Z)', content, re.DOTALL | re.IGNORECASE)
        if m:
            result['other'] = m.group(1).strip()
        return result

    @staticmethod
    def template(name, author, tag="Technical"):
        return f"""[INFO]
name: {name}
description: New application
version: 1.0.0
author: {author}
tag: {tag}
background: false

[CODE]
print("=== {name} ===")
name = input("Ваше имя: ")
print("Привет, " + name + "!")
[/CODE]

[DATA]
folder: /apps/data/{name}
[/DATA]

[OTHER]
Free License -- Kostyl Studios
[/OTHER]

[END]"""

class X4Runtime:
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
            '__CACHE__': '/cache',
        }

    def _color_print(self, text, color_name="white"):
        cols = {'red': C.R, 'green': C.G, 'yellow': C.Y, 'blue': C.BL,
                'cyan': C.CY, 'magenta': C.M, 'white': C.W, 'bold': C.B}
        print(C.c(str(text), cols.get(str(color_name).lower(), C.W)))

    def execute(self, code):
        clean_code = textwrap.dedent(code).strip()
        env = {
            '__builtins__': __builtins__,
            'math': math,
            'random': random,
            'time': time,
            'json': json,
            'os': os,
            'sys': sys,
            're': re,
            'datetime': datetime,
            'clear': clear,
            'C': C,
            'color': self._color_print,
            'print_color': self._color_print,
            'notify': lambda title, msg: self.shell.kernel.notifications.send(
                source=self.app_name, title=str(title), message=str(msg), icon='app', priority='normal'),
            'notify_high': lambda title, msg: self.shell.kernel.notifications.send(
                source=self.app_name, title=str(title), message=str(msg), icon='app', priority='high'),
            'cache_write': lambda k, v: self.shell.kernel.fs.write_file(f'/cache/{str(k).strip("/")}', str(v)),
            'cache_read': lambda k: self.shell.kernel.fs.read_file(f'/cache/{str(k).strip("/")}') or '',
            'cache_has': lambda k: self.shell.kernel.fs.exists(f'/cache/{str(k).strip("/")}'),
            'cache_del': lambda k: self.shell.kernel.fs.delete(f'/cache/{str(k).strip("/")}'),
            'cache_clear': lambda: [self.shell.kernel.fs.delete(f"/cache/{it['name']}", recursive=True) for it in (self.shell.kernel.fs.list_dir('/cache') or [])],
            'fwrite': lambda p, c: self.shell.kernel.fs.write_file(str(p), str(c), self.shell.cwd),
            'fappend': lambda p, c: self.shell.kernel.fs.write_file(str(p), str(c), self.shell.cwd, append=True),
            'fread': lambda p: self.shell.kernel.fs.read_file(str(p), self.shell.cwd) or '',
            'fexists': lambda p: self.shell.kernel.fs.exists(str(p), self.shell.cwd),
            'fdelete': lambda p: self.shell.kernel.fs.delete(str(p), self.shell.cwd),
            'fmkdir': lambda p: self.shell.kernel.fs.mkdir(str(p), self.shell.cwd),
            'flist': lambda p: [i['name'] for i in (self.shell.kernel.fs.list_dir(str(p), self.shell.cwd) or [])],
            'sleep': time.sleep,
            'sysinfo': lambda: print(f"  OS: {self.vars['__OS__']} | User: {self.shell.user} | App: {self.app_name}"),
            'background': lambda: self.shell.kernel.app_bg.register(self.app_name),
            'shell': self.shell,
            'kernel': self.shell.kernel,
            'fs': self.shell.kernel.fs,
        }
        env.update(self.vars)

        try:
            exec(clean_code, env)
        except KeyboardInterrupt:
            print("\n  [Прервано пользователем]")
        except Exception as e:
            self._handle_crash(e, tb_module.format_exc())

    def _handle_crash(self, error, trace_str):
        print(C.c(f"\n  [Ошибка приложения] {error}", C.R))
        debug_logger = self.shell.kernel.debug if (
            self.shell.kernel.settings.debug_mode and self.shell.kernel.debug
        ) else None
        crasher = CrashLogger(self.shell.kernel.fs, debug_logger)
        path, _ = crasher.log_crash(self.app_name, error, trace_str, "X4 Native Exec")
        print(C.c(f"  [Лог сбоя сохранён: {path}]", C.Y))
        self.shell.kernel.notifications.send(
            source=self.app_name, title=f"Crash: {self.app_name}",
            message=str(error)[:50], icon='err', priority='high',
        )

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
            name = item['name']
            if item['is_dir']:
                continue
            if name.endswith('.x4'):
                content = self.fs.read_file('/apps/installed/' + name)
                if content:
                    p = X4Parser.parse(content)
                    p['format'] = 'x4'
                    app_key = p['info'].get('name', name[:-3])
                    self.apps[app_key] = p
            elif name.lower().endswith('.x4s'):
                raw = self.fs.read_bytes('/apps/installed/' + name)
                if raw:
                    try:
                        if raw.startswith(b'X4S\x01'):
                            decomp = lzma.decompress(raw[4:]).decode('utf-8', errors='replace')
                        else:
                            decomp = lzma.decompress(raw).decode('utf-8', errors='replace')
                        p = X4Parser.parse(decomp)
                        p['format'] = 'x4s'
                        clean_n = name[:-4] if name.lower().endswith('.x4s') else name
                        app_key = p['info'].get('name', clean_n)
                        self.apps[app_key] = p
                    except (lzma.LZMAError, UnicodeDecodeError):
                        pass

    def install_builtins(self):
        for name, content in self._builtins().items():
            self.fs.write_file(f'/apps/installed/{name}.x4', content)
            p = X4Parser.parse(content)
            p['format'] = 'x4'
            an = p['info'].get('name', name)
            self.apps[an] = p
            self.fs.mkdir(p['data'].get('folder', f'/apps/data/{an}'))

    def install(self, filename, cwd='/', home_dir=None):
        content = None
        is_x4s = False
        if filename.lower().endswith('.x4s'):
            raw = self.fs.read_bytes(filename, cwd)
            if raw:
                try:
                    if raw.startswith(b'X4S\x01'):
                        content = lzma.decompress(raw[4:]).decode('utf-8')
                    else:
                        content = lzma.decompress(raw).decode('utf-8')
                    is_x4s = True
                except (lzma.LZMAError, UnicodeDecodeError):
                    pass
        else:
            content = self.fs.read_file(filename, cwd)
            if not content and home_dir:
                content = self.fs.read_file(f"{home_dir}/Documents/{filename}")
            if not content:
                content = self.fs.read_file(f'/apps/store/{filename}')

        if not content:
            return False, f"Файл '{filename}' не найден или поврежден"
        p = X4Parser.parse(content)
        name = p['info'].get('name', '')
        if not name:
            return False, "Отсутствует имя в [INFO]"
        if not p['code']:
            return False, "Отсутствует секция [CODE]"

        if is_x4s:
            raw_orig = self.fs.read_bytes(filename, cwd)
            self.fs.write_bytes(f'/apps/installed/{name}.x4s', raw_orig)
            p['format'] = 'x4s'
        else:
            self.fs.write_file(f'/apps/installed/{name}.x4', content)
            p['format'] = 'x4'

        df = p['data'].get('folder', f'/apps/data/{name}')
        self.fs.mkdir(df)
        self.apps[name] = p
        if self.notifications:
            self.notifications.send(
                source='system', title=f"Приложение установлено: {name}",
                message=f"v{p['info'].get('version', '?')} от {p['info'].get('author', '?')}",
                icon='ok', priority='normal')
        return True, f"'{name}' v{p['info'].get('version', '?')} успешно установлено!"

    def run(self, name, shell):
        if name not in self.apps:
            return False, f"Приложение '{name}' не найдено"
        app = self.apps[name]
        info = app['info']
        fmt = app.get('format', 'x4').upper()
        if fmt == 'X4S':
            print(C.c(f"  [X4 SUPER: распаковка '{name}' в RAM...]", C.CY + C.DIM))
            time.sleep(0.05)
        print(C.c(f"  [{info.get('name', name)} v{info.get('version', '?')} ({fmt}) — Тег: {info.get('tag', 'None')}]", C.DIM))
        if info.get('background', '').lower() == 'true' and self.app_bg:
            self.app_bg.register(name, info)
        X4Runtime(shell, app_name=name).execute(app['code'])
        deleted = self.guardian.cleanup_app_folder(self.fs, name)
        if deleted:
            print(C.c(f"  [Guardian] Данные '{name}' оптимизированы:", C.Y))
            for fname, fsize in deleted:
                print(C.c(f"    Удалено: {fname} ({self.guardian.fmt_size(fsize)})", C.Y))
        print()
        print(C.c("  Приложение завершило свою работу.", C.DIM))
        try:
            input(C.c("  Нажмите Enter для возврата в систему...", C.DIM))
        except (EOFError, KeyboardInterrupt):
            pass
        return True, ""

    def remove(self, name, backup_data_to_cache=True):
        if name not in self.apps:
            return False, "Приложение не найдено"

        data_path = f'/apps/data/{name}'
        has_data = self.fs.exists(data_path) and bool(self.fs.list_dir(data_path))
        cached_info = ""

        if backup_data_to_cache and has_data:
            self.fs.mkdir('/cache/deleted_apps')
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_cache_file = f"/cache/deleted_apps/{name}_data_{ts}.tar.xz"
            real_data_dir, _ = self.fs.to_real_path(data_path)
            real_cache_file, _ = self.fs.to_real_path(backup_cache_file)
            try:
                with lzma.open(real_cache_file, 'wb') as xz_out:
                    with tarfile.open(fileobj=xz_out, mode='w') as tar:
                        tar.add(real_data_dir, arcname='data')
                cached_info = f" (Данные сохранены в {backup_cache_file})"
            except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError):
                pass

        del self.apps[name]
        self.fs.delete(f'/apps/installed/{name}.x4')
        self.fs.delete(f'/apps/installed/{name}.x4s')
        self.fs.delete(f'/apps/installed/{name}.X4S')
        self.fs.delete(data_path, recursive=True)

        if self.app_bg:
            self.app_bg.unregister(name)
        if self.notifications:
            self.notifications.delete_by_source(name)

        return True, f"Приложение '{name}' удалено{cached_info}."

    def update_app(self, name, new_file_path, cwd='/'):
        if name not in self.apps:
            return False, f"Приложение '{name}' не установлено"
        content = self.fs.read_file(new_file_path, cwd)
        if not content:
            return False, f"Файл обновления '{new_file_path}' не найден или пуст"
        parsed = X4Parser.parse(content)
        if not parsed['code']:
            return False, "Файл не содержит валидной секции [CODE]"

        self.fs.write_file(f'/apps/installed/{name}.x4', content)
        parsed['format'] = 'x4'
        self.apps[name] = parsed
        new_ver = parsed['info'].get('version', 'новый')
        return True, f"Приложение '{name}' успешно обновлено до версии {new_ver}!"

    def disable(self, name):
        if name not in self.apps:
            return False, f"Приложение '{name}' не найдено"

        app_orig_file = None
        for ext in ('.x4', '.x4s', '.X4S'):
            candidate = f'/apps/installed/{name}{ext}'
            if self.fs.exists(candidate):
                app_orig_file = candidate
                break

        if not app_orig_file:
            return False, "Исполняемый файл приложения не найден"

        archive_vpath = f'/apps/installed/{name}.disabled'
        real_archive_path, _ = self.fs.to_real_path(archive_vpath)
        real_app_file, _ = self.fs.to_real_path(app_orig_file)
        real_data_dir, _ = self.fs.to_real_path(f'/apps/data/{name}')

        meta = {
            'name': name,
            'orig_file_name': Path(app_orig_file).name,
            'disabled_at': datetime.datetime.now().isoformat(),
            'info': self.apps[name]['info']
        }

        try:
            with lzma.open(real_archive_path, 'wb', preset=9 | lzma.PRESET_EXTREME) as xz_out:
                with tarfile.open(fileobj=xz_out, mode='w') as tar:
                    tar.add(real_app_file, arcname='app_binary')
                    if real_data_dir.exists():
                        tar.add(real_data_dir, arcname='data')
                    m_bytes = json.dumps(meta, indent=2, ensure_ascii=False).encode('utf-8')
                    ti = tarfile.TarInfo(name='disabled_meta.json')
                    ti.size = len(m_bytes)
                    ti.mtime = int(time.time())
                    tar.addfile(ti, io.BytesIO(m_bytes))

            self.fs.delete(app_orig_file)
            self.fs.delete(f'/apps/data/{name}', recursive=True)
            del self.apps[name]
            if self.app_bg:
                self.app_bg.unregister(name)

            comp_sz = self.guardian.fmt_size(real_archive_path.stat().st_size)
            return True, f"Приложение '{name}' отключено и сжато в {archive_vpath} ({comp_sz})"
        except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError) as e:
            if real_archive_path.exists():
                try:
                    real_archive_path.unlink()
                except OSError:
                    pass
            return False, f"Ошибка отключения: {e}"

    def enable(self, name):
        archive_vpath = f'/apps/installed/{name}.disabled'
        if not self.fs.exists(archive_vpath):
            return False, f"Отключенное приложение '{name}' не найдено"

        real_archive_path, _ = self.fs.to_real_path(archive_vpath)
        try:
            with lzma.open(real_archive_path, 'rb') as xz_in:
                with tarfile.open(fileobj=xz_in, mode='r') as tar:
                    meta_member = tar.extractfile('disabled_meta.json')
                    meta = json.loads(meta_member.read().decode('utf-8')) if meta_member else {}
                    orig_fname = meta.get('orig_file_name', f"{name}.x4")

                    app_bin = tar.extractfile('app_binary')
                    if app_bin:
                        self.fs.write_bytes(f'/apps/installed/{orig_fname}', app_bin.read())

                    for member in tar.getmembers():
                        if member.name.startswith('data/'):
                            rel = member.name[5:]
                            if not rel:
                                continue
                            out_p = f'/apps/data/{name}/{rel}'
                            if member.isdir():
                                self.fs.mkdir(out_p)
                            elif member.isfile():
                                ef = tar.extractfile(member)
                                if ef:
                                    self.fs.write_bytes(out_p, ef.read())

            self.fs.delete(archive_vpath)
            self.load_installed()
            return True, f"Приложение '{name}' успешно включено и готово к работе!"
        except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError, json.JSONDecodeError) as e:
            return False, f"Ошибка восстановления: {e}"

    def list_disabled(self):
        items = self.fs.list_dir('/apps/installed') or []
        res = []
        for i in items:
            if i['name'].endswith('.disabled'):
                res.append(i['name'][:-9])
        return res

    def get_info(self, name):
        return self.apps.get(name, {}).get('info', {})

    def _builtins(self):
        return {
'calc': """[INFO]
name: calc
description: Удобный калькулятор
version: 1.2.0
author: Kostyl Studios
tag: Technical
background: false

[CODE]
print("=== Калькулятор (Technical) ===")
color("Введите математическое выражение или 'exit' для выхода", "cyan")
while True:
    expr = input("calc> ").strip()
    if expr.lower() in ('exit', 'quit', 'q'):
        break
    if not expr:
        continue
    try:
        res = eval(expr, {"__builtins__": {}, "math": math, "abs": abs, "round": round, "pow": pow, "sqrt": math.sqrt})
        color("= " + str(res), "green")
    except Exception as e:
        color("Ошибка: " + str(e), "red")
[/CODE]

[DATA]
folder: /apps/data/calc
[/DATA]

[OTHER]
Free License -- Kostyl Studios
[/OTHER]
[END]""",

'guess': """[INFO]
name: guess
description: Игра 'Угадай число'
version: 2.0.0
author: Kostyl Studios
tag: Game
background: false

[CODE]
print("=== Угадай число (Game) ===")
target = random.randint(1, 100)
attempts = 0
color("Я загадал число от 1 до 100. Попробуй угадать!", "yellow")

while True:
    val = input("Ваша догадка (или 'exit'): ").strip()
    if val.lower() in ('exit', 'q'):
        color("Игра прервана. Было загадано: " + str(target), "magenta")
        break
    if not val.isdigit():
        color("Пожалуйста, введите целое число!", "red")
        continue
    num = int(val)
    attempts += 1
    if num < target:
        color("Больше! Попробуй еще раз.", "cyan")
    elif num > target:
        color("Меньше! Попробуй еще раз.", "cyan")
    else:
        color("ПОЗДРАВЛЯЕМ! Вы угадали число " + str(target) + " за " + str(attempts) + " попыток!", "green")
        notify("Game: Guess", "Победа! Угадано за " + str(attempts) + " попыток")
        break
[/CODE]

[DATA]
folder: /apps/data/guess
[/DATA]

[OTHER]
Free License -- Kostyl Studios
[/OTHER]
[END]""",

'notes': """[INFO]
name: notes
description: Блокнот и заметки
version: 4.3.0
author: Kostyl Studios
tag: Technical
background: false

[CODE]
print("=== Заметки (Technical) ===")
notes_dir = "/apps/data/notes"
fmkdir(notes_dir)

while True:
    print("")
    color("-- Меню Заметок --", "cyan")
    print("1. Создать новую заметку")
    print("2. Прочитать заметку")
    print("3. Список всех заметок")
    print("4. Удалить заметку")
    print("5. Выход")
    choice = input("Выберите (1-5): ").strip()

    if choice == "1":
        name = input("Имя заметки: ").strip()
        if name:
            text = input("Текст заметки: ")
            fwrite(notes_dir + "/" + name + ".txt", text)
            color("Заметка '" + name + "' успешно сохранена!", "green")
    elif choice == "2":
        name = input("Имя заметки для чтения: ").strip()
        data = fread(notes_dir + "/" + name + ".txt")
        if data:
            color("-- " + name + " --", "yellow")
            print(data)
        else:
            color("Заметка не найдена или пуста.", "red")
    elif choice == "3":
        files = flist(notes_dir)
        color("Список заметок:", "yellow")
        for f in files:
            print("  * " + str(f))
    elif choice == "4":
        name = input("Имя заметки для удаления: ").strip()
        fdelete(notes_dir + "/" + name + ".txt")
        color("Удалено (если существовала).", "yellow")
    elif choice in ("5", "exit", "q"):
        break
[/CODE]

[DATA]
folder: /apps/data/notes
[/DATA]

[OTHER]
Free License -- Kostyl Studios
[/OTHER]
[END]""",

'hello': """[INFO]
name: hello
description: Демонстрация системы
version: 3.1.0
author: Kostyl Studios
tag: Demo
background: false

[CODE]
color("=== Привет, " + __USER__ + "! ===", "green")
print("Добро пожаловать в " + __OS__)
print("Текущая системная дата: " + __DATE__ + " " + __TIME__)
print("Быстрый системный кэш: " + __CACHE__)
cache_write("last_user.txt", __USER__)
color("Приложение работает на чистом Python!", "cyan")
notify("Hello App", "Запущено пользователем " + __USER__)
[/CODE]

[DATA]
folder: /apps/data/hello
[/DATA]

[OTHER]
Free License -- Kostyl Studios
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
        except (OSError, PermissionError):
            return False

    def load(self):
        try:
            content = self.fs.read_file('/sysdata/history.json')
            if content:
                self.entries = json.loads(content)[-self.max_size:]
                return True
        except (json.JSONDecodeError, OSError):
            pass
        self.entries = []
        return False

# ═══ ЯДРО PYOS V17.4 ═══
class Kernel:
    VERSION = '17.4'
    BUILD = '03.10.2026'
    COMPANY = 'Kostyl Studios'

    def __init__(self):
        self.boot_time = datetime.datetime.now()
        self.fs = None
        self.um = UserManager()
        self.guardian = Guardian()
        self.trash = None
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
        self._hourly_timer = None
        self._bsod_pending = False
        self._bsod_lock = threading.Lock()
        self._bsod_error_code = ''
        self._bsod_message = ''
        self._bsod_details = ''

    def get_now(self):
        return self.settings.get_now()

    def t(self, ru, en):
        return ru if self.settings.lang == 'ru' else en

    def get_save_path(self):
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

    def trigger_bsod(self, error_code, message, details=''):
        with self._bsod_lock:
            if self._bsod_pending:
                return
            self._bsod_pending = True
            self._bsod_error_code = error_code
            self._bsod_message = message
            self._bsod_details = details
        self.running = False

    def is_bsod_pending(self):
        with self._bsod_lock:
            return self._bsod_pending

    def get_bsod_info(self):
        with self._bsod_lock:
            return self._bsod_error_code, self._bsod_message, self._bsod_details

    def restart_after_bsod(self):
        if self._fs_checker:
            self._fs_checker.stop()
        self.timer_service.stop()
        self.running = False
        self.first_boot = True
        self.fs = None
        self.trash = None
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
        self._bsod_pending = False
        try:
            if self._marker.exists():
                self._marker.unlink()
        except (OSError, PermissionError):
            pass

    def run_smart_memory_cleanup(self):
        if not self.settings.smart_memory or not self.fs:
            return 0, 0
        del_dirs = 0
        del_files = 0

        target_dirs = ['/apps/store', '/apps/logs']
        for td in target_dirs:
            if self.fs.exists(td) and self.fs.is_dir(td):
                items = self.fs.list_dir(td)
                if items is not None and len(items) == 0:
                    if self.fs.delete(td):
                        del_dirs += 1

        for scan_p in ['/apps/logs']:
            if self.fs.exists(scan_p) and self.fs.is_dir(scan_p):
                items = self.fs.list_dir(scan_p)
                if items:
                    for it in items:
                        if not it['is_dir'] and it['size'] == 0:
                            if self.fs.delete(f"{scan_p}/{it['name']}"):
                                del_files += 1

        return del_dirs, del_files

    def _start_hourly_autobackup_worker(self):
        def worker():
            while self.running:
                time.sleep(60)
                if not self.running:
                    break
                if self.settings.auto_backup == 'hourly':
                    BackupManager.create_backup("auto_hourly", self)
        self._hourly_timer = threading.Thread(target=worker, daemon=True)
        self._hourly_timer.start()

    def boot(self):
        clear()
        self.boot_anim()
        self._load_hostname()
        loaded = self.load_state()
        if loaded:
            self.first_boot = False
            self.fs = RealFS(self.base_path)
            self.fs.hostname_dir = (Path(self.base_path) / self.hostname).resolve()
            self.fs.current_disk = 'C'
            self.trash = TrashManager(self.fs, self.guardian)
            self.debug = DebugLogger(self.fs)
            self.debug.load()
            self.apps = AppManager(self.fs, self.guardian, self.notifications, self.app_bg)
            self.apps.load_installed()
            self.history = HistoryManager(self.fs)
            self.history.load()
            self.fs.mkdir('/apps/logs')
            self.fs.mkdir('/cache')
            self.fs.mkdir('/cache/deleted_apps')
            self.fs.mkdir('/cache/trash_archives')
            self.fs.mkdir('/sysdata/trash')
            if self.timer_service.get_active():
                self.timer_service.start()
            self._fs_checker = FSHealthChecker(self.fs, self)
            self._fs_checker.start()
            self.run_smart_memory_cleanup()
            self._start_hourly_autobackup_worker()

            if self.settings.auto_backup == 'at_start':
                BackupManager.create_backup("auto_boot", self)
        else:
            self.first_boot = True

    def boot_anim(self):
        logo = [
            f"  PyOS v{self.VERSION}",
            f"  build {self.BUILD}",
            f"  {self.COMPANY} [Argon2id]",
        ]
        print(SimpleBox.box('\n'.join(logo), 46, '='))
        print()

        stages = [
            "Kernel", "Argon2id Subsystem", "Filesystem", "Trash Subsystem",
            "Guardian & Updater", "Integrity Check", "Smart Memory", "Notifications",
            "AutoBackup", "Cache Manager", "App Manager"
        ]
        total = len(stages)
        bar_width = 24

        for i, stage in enumerate(stages, 1):
            ratio = i / total
            filled = int(bar_width * ratio)
            bar = '#' * filled + '.' * (bar_width - filled)
            pct = int(ratio * 100)
            status = f"[{bar}] {pct:3d}% {stage}..."
            print(f"\r  {C.c(status, C.G)}          ", end='', flush=True)
            time.sleep(0.02)

        final_bar = '#' * bar_width
        print(f"\r  {C.c(f'[{final_bar}] 100%', C.G)} {C.c('Готово!', C.G + C.B)}          \n")

    def setup(self):
        print(SimpleBox.header(f"PyOS {self.VERSION} build {self.BUILD} (Argon2id)", 46))
        print(f"  {self.t('Первоначальная настройка', 'First Time Setup')}")
        print("=" * 46)
        print()
        auto = input(f"  {self.t('Включить автонастройку? (yes/no): ', 'Enable auto setup? (yes/no): ')}").strip().lower()
        if auto in ('yes', 'y', 'да', 'д'):
            self._auto_setup()
            return
        self._manual_setup()

    def _auto_setup(self):
        print(C.c(f"\n  [Auto Setup] {self.t('Настройка...', 'Configuring...')}", C.CY))
        self.hostname = 'Computer'
        self._save_hostname()
        self.fs = RealFS(self.base_path)
        self.fs.init_structure(self.hostname)
        self.trash = TrashManager(self.fs, self.guardian)
        self.debug = DebugLogger(self.fs)
        un = 'User'
        self.um.create(un, None, '')
        for d in [f'/home/{un}', f'/home/{un}/Desktop', f'/home/{un}/Documents']:
            self.fs.mkdir(d)
        self.guardian.set_app_folder_limit(1024 * 1024)
        self.apps = AppManager(self.fs, self.guardian, self.notifications, self.app_bg)
        self.apps.install_builtins()
        self.history = HistoryManager(self.fs)
        self._fs_checker = FSHealthChecker(self.fs, self)
        self._fs_checker.start()
        self._start_hourly_autobackup_worker()

        script_p = get_script_path()
        save_code_hash(script_p)
        BackupManager.create_backup("initial_setup", self)
        print(C.c(f"\n  {self.t('Настройка завершена!', 'Auto setup complete!')}", C.G))
        self.save_state()

    def _manual_setup(self):
        self.hostname = input("  Имя компьютера [pyos]: ").strip() or 'pyos'
        self._save_hostname()
        self.fs = RealFS(self.base_path)
        self.fs.init_structure(self.hostname)
        self.trash = TrashManager(self.fs, self.guardian)
        self.debug = DebugLogger(self.fs)

        print("\n  " + self.t("Создание аккаунта:", "Account creation:"))
        while True:
            un = input("  Имя пользователя: ").strip()
            if un and un.isalnum():
                break
            print(C.c("  Только буквы и цифры!", C.R))

        add_pw = input("  Установить пароль? (y/n): ").strip().lower()
        if add_pw in ('y', 'yes', 'да'):
            while True:
                up = input("  Пароль: ").strip()
                if len(up) < 2:
                    print(C.c("  Слишком короткий (мин 2)", C.R))
                    continue
                if input("  Подтвердите: ").strip() != up:
                    print(C.c("  Пароли не совпадают", C.R))
                    continue
                break
            uh = input("  Подсказка (Enter = без подсказки): ").strip()
            self.um.create(un, up, uh)
        else:
            self.um.create(un, None, '')

        for d in [f'/home/{un}', f'/home/{un}/Desktop', f'/home/{un}/Documents']:
            self.fs.mkdir(d)

        self.apps = AppManager(self.fs, self.guardian, self.notifications, self.app_bg)
        self.apps.install_builtins()
        self.history = HistoryManager(self.fs)
        self._fs_checker = FSHealthChecker(self.fs, self)
        self._fs_checker.start()
        self._start_hourly_autobackup_worker()

        script_p = get_script_path()
        save_code_hash(script_p)
        BackupManager.create_backup("initial_setup", self)
        print(C.c(f"\n  {self.t('Настройка завершена!', 'Setup complete!')}\n", C.G))
        self.save_state()

    def save_state(self):
        try:
            self.run_smart_memory_cleanup()
            state = {
                'hostname': self.hostname, 'base_path': self.base_path,
                'version': self.VERSION, 'build': self.BUILD, 'company': self.COMPANY,
                'hash_algo': 'Argon2id',
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
            sp = self.get_save_path()
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

    def load_state(self):
        sp = self.get_save_path()
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
        print(C.c(f"\n  Сессия: {self.guardian.session_str()}", C.CY))
        if self.settings.auto_backup == 'at_shutdown':
            print(C.c("  [AutoBackup] Создание резервной копии перед выходом...", C.CY))
            BackupManager.create_backup("auto_shutdown", self)
        if self._fs_checker:
            self._fs_checker.stop()
        self.timer_service.stop()
        self.run_smart_memory_cleanup()
        self.save_state()
        print(C.c(f"  {self.COMPANY} -- PyOS {self.VERSION}", C.DIM))
        print(C.c(f"  {self.t('До свидания!', 'Goodbye!')}\n", C.G))
        self.running = False

    def check_fs_health(self):
        if self.fs and self.fs.hostname_dir:
            if not self.fs.hostname_dir.exists():
                self.trigger_bsod('CRITICAL_DATA_DESTROYED',
                                  'System data folder has been deleted.',
                                  f'Missing: {self.fs.hostname_dir}')
                return False
        return True

# ═══ КОНСОЛЬНАЯ ОБОЛОЧКА ═══
class Shell:
    def __init__(self, kernel):
        self.kernel = kernel
        self.cwd = '/'
        self.user = None
        self.env = {'HOME': '/', 'CACHE': '/cache'}
        self.aliases = {'ll': 'ls -l', 'la': 'ls -a', 'cls': 'clear',
                        '..': 'cd ..', 'q': 'exit', 'recycle': 'trash', 'bin': 'trash'}
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
        lim = f"{g.daily_limit} мин" if g.daily_limit else self.kernel.t("Без лимита", "No limit")
        has_pw = self.kernel.t("Да", "Yes") if self.kernel.um.has_password(self.user) else self.kernel.t("Нет", "No")
        notif_badge = self.kernel.notifications.format_badge()
        active_timers = len(self.kernel.timer_service.get_active())
        bg_apps = len(self.kernel.app_bg.get_all())
        debug_on = self.kernel.settings.debug_mode
        smart_mem_on = self.kernel.settings.smart_memory
        autobackup = self.kernel.settings.auto_backup
        lang_str = self.kernel.settings.lang.upper()

        disabled_cnt = len(self.kernel.apps.list_disabled()) if self.kernel.apps else 0
        trash_cnt = len(self.kernel.trash.list_items()) if self.kernel.trash else 0

        print("=" * 56)
        print(f"  PyOS v{Kernel.VERSION} build {Kernel.BUILD} -- {hn} [Argon2id]")
        print("=" * 56)
        print(f"  {self.kernel.t('Пользователь', 'User')}:       {C.c(self.user, C.G)}")
        print(f"  {self.kernel.t('Пароль', 'Password')}:           {has_pw} (Argon2id)")
        print(f"  {self.kernel.t('Язык', 'Language')}:             {lang_str}")
        print(f"  {self.kernel.t('Время', 'Time')}:                 {now.strftime('%H:%M:%S')}")
        print(f"  {self.kernel.t('Сессия', 'Session')}:              {g.session_str()} (лимит: {lim})")
        print("-" * 56)
        print(f"  {self.kernel.t('Диски', 'Disks')}:                {' '.join(d + ':' for d in disks)} (Current: {dk}:)")
        print(f"  {self.kernel.t('Занято', 'Disk used')}:            {g.fmt_size(usage)}")
        print(f"  {self.kernel.t('Приложения', 'Apps')}:             {len(self.kernel.apps.apps) if self.kernel.apps else '0'} (Отключено: {disabled_cnt})")
        print(f"  {self.kernel.t('Корзина', 'Trash Bin')}:          {trash_cnt} элементов ('trash' для управления)")
        print(f"  {self.kernel.t('Автобэкап', 'AutoBackup')}:       {C.c(autobackup, C.CY)}")
        print(f"  Smart Memory:         {C.c('ON', C.G) if smart_mem_on else C.c('OFF', C.DIM)}")
        if debug_on:
            err_count = self.kernel.debug.count() if self.kernel.debug else 0
            print(f"  Debug:                {C.c('ON', C.Y)} ({err_count} errors)")
        print("-" * 56)
        status_parts = [f"Notif: {notif_badge}"]
        if active_timers > 0:
            status_parts.append(C.c(f"Timers: {active_timers}", C.CY))
        if bg_apps > 0:
            status_parts.append(C.c(f"Bg: {bg_apps}", C.M))
        print('  ' + ' | '.join(status_parts))
        print("-" * 56)
        print("  guardian -- Центр Обновлений, оптимизация и удаление OS")
        print("  trash -- Корзина (сжатие/очистка) | app tags / app manager")
        print("=" * 56)
        print()
        panel = self.kernel.notifications.format_panel(max_show=4)
        if panel:
            print(panel)
            print()

    def login(self):
        if not self.kernel.um.users:
            self.kernel.um.create('User', None, '')
            self.kernel.fs.mkdir('/home/User')
            self.kernel.save_state()

        users = self.kernel.um.list_users()
        print("=" * 44)
        print(f"  {self.kernel.t('Выберите пользователя', 'Select User')}")
        print("=" * 44)
        for u in users:
            info = self.kernel.um.get_public_info(u) or {}
            has_pw = "[Argon2id]" if info.get('has_password', True) else "[open]"
            disk = info.get('disk', 'C')
            print(f"  {has_pw} {u:<16} disk={disk}:")
        print("-" * 44)
        print()
        fail = {}
        while True:
            try:
                un = input(C.c("  login: ", C.W)).strip()
                if not un:
                    continue
            except (EOFError, KeyboardInterrupt):
                self.kernel.shutdown()
                return False
            if un not in self.kernel.um.users:
                print(C.c("  User not found.\n", C.R))
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
            print(C.c("  Неверный пароль (Argon2id verification failed).", C.R))
            if fail.get(un, 0) >= 3:
                hint = self.kernel.um.get_hint(un)
                if hint:
                    print(C.c(f"  Подсказка: {hint}", C.CY))
            print()

    def _do_login(self, un):
        self.user = un
        info = self.kernel.um.users[un]
        self.kernel.fs.current_disk = info.get('disk', 'C')
        self.env['HOME'] = info['home']
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
                print(SimpleBox.box(self.kernel.t("Лимит времени исчерпан!\nОтдохните.", "Time limit reached!\nConsider taking a break."), 42, '!'))
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

            redir_op = None
            if '>>' in line:
                idx = self._find_redirect_op(line, '>>')
                if idx >= 0:
                    redir_op = ('>>', idx)
            if not redir_op and '>' in line:
                idx = self._find_redirect_op(line, '>')
                if idx >= 0:
                    redir_op = ('>', idx)

            if redir_op:
                op, idx = redir_op
                cmd = line[:idx].strip()
                fp = line[idx + len(op):].strip().strip('"\'')
                self._redir(cmd, fp, op == '>>')
                continue

            for k, v in self.env.items():
                line = re.sub(r'\$' + re.escape(k) + r'\b', str(v), line)

            first = line.split()[0] if line.split() else ''
            if first in self.aliases:
                line = self.aliases[first] + line[len(first):]
            self._exec(line)

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
            'trash': self.c_trash, 'recycle': self.c_trash, 'bin': self.c_trash,
            'clear': lambda _args: self._do_desktop(),
            'desktop': lambda _args: self._do_desktop(),
            'whoami': lambda _args: print(f"  {self.user}"),
            'id': self.c_id, 'su': self.c_su,
            'useradd': self.c_useradd, 'userdel': self.c_userdel,
            'passwd': self.c_passwd, 'users': self.c_users,
            'date': lambda _args: print(f"  {self.kernel.get_now().strftime('%Y-%m-%d %H:%M:%S')}"),
            'uptime': lambda _args: print(f"  Session: {self.kernel.guardian.session_str()}"),
            'hostname': lambda _args: print(f"  {self.kernel.hostname}"),
            'neofetch': self.c_neofetch, 'history': self.c_history,
            'alias': self.c_alias, 'export': self.c_export,
            'env': lambda _args: [print(f"  {k}={v}") for k, v in sorted(self.env.items())],
            'edit': self.c_edit, 'nano': self.c_edit,
            'guardian': self.c_guardian,
            'app': self.c_app, 'tags': lambda _args: self.c_app(['tags']),
            'newapp': self.c_newapp, 'disk': self.c_disk,
            'man': self.c_man, 'realpath': self.c_realpath,
            'suggest': self.c_suggest, 'logs': self.c_logs,
            'notif': self.c_notif, 'timer': self.c_timer,
            'settings': self.c_settings, 'debug': self.c_debug,
            'backup': self.c_backup, 'cache': self.c_cache,
            'smartmem': self.c_smartmem,
            'shutdown': self.c_shutdown, 'reboot': self.c_reboot,
            'exit': self.c_exit, 'logout': self.c_exit,
            'save': self.c_save,
        }

    def _exec(self, line):
        try:
            parts = shlex.split(line, posix=(sys.platform != 'win32'))
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
                print(C.c(f"  [Ошибка команды] {e}", C.R))
                if self.kernel.settings.debug_mode and self.kernel.debug:
                    self.kernel.debug.log('command_error', str(e), tb_module.format_exc(), f'cmd:{cmd}', line)
        elif self.kernel.apps and cmd in self.kernel.apps.apps:
            ok, err = self.kernel.apps.run(cmd, self)
            if not ok:
                print(C.c(f"  {err}", C.R))
            self._do_desktop()
        else:
            if self.kernel.fs and self.kernel.fs.is_file(cmd, self.cwd):
                content = self.kernel.fs.read_file(cmd, self.cwd)
                if content:
                    p = X4Parser.parse(content)
                    if p['code']:
                        X4Runtime(self, app_name=p['info'].get('name', Path(cmd).stem)).execute(p['code'])
                        try:
                            input(C.c("\n  Нажмите Enter для возврата...", C.DIM))
                        except (EOFError, KeyboardInterrupt):
                            pass
                        self._do_desktop()
                        return
            print(C.c(f"  Команда не найдена: {cmd}", C.R))
            all_known = list(cmds.keys()) + (list(self.kernel.apps.apps.keys()) if self.kernel.apps else [])
            suggestions = self.kernel.guardian.suggest(cmd, all_known)
            if suggestions:
                print(C.c(f"  Возможно, вы имели в виду: {', '.join(suggestions)}?", C.Y))

    def _do_desktop(self):
        self.desktop()

    def c_reload(self, _args):
        if self.kernel.apps:
            self.kernel.apps.apps.clear()
            self.kernel.apps.load_installed()
            print(C.c(f"  Перезагружено: {len(self.kernel.apps.apps)} приложений", C.G))

    # ═══ КОРЗИНА ═══
    def c_trash(self, a):
        t = self.kernel.trash
        if not a or a[0] in ('list', 'ls'):
            items = t.list_items()
            print("=" * 64)
            print("  Корзина PyOS (Recycle Bin)")
            print("=" * 64)
            if not items:
                print(C.c("  Корзина пуста.", C.DIM))
            else:
                for it in items:
                    sz_str = self.kernel.guardian.fmt_size(it['size']) if not it['is_dir'] else '<DIR>'
                    t_str = it['deleted_at'][:19].replace('T', ' ')
                    print(f"  #{it['id']:<3} {it['name']:<22} {sz_str:>9} | {t_str} | {it['disk']}:{it['orig_path']}")
            print("-" * 64)
            print("  trash restore <id>       -- восстановить файл на прежнее место")
            print("  trash rm / delete <id>   -- полностью удалить ОДИН файл навсегда")
            print("  trash empty / clear      -- сжать в .tar.xz и очистить корзину")
            print("=" * 64)
            return

        sub = a[0].lower()
        if sub in ('empty', 'clear'):
            print(C.c("  Сжатие содержимого корзины в архив и очистка...", C.CY))
            ok, msg = t.empty(compress=True)
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif sub in ('rm', 'delete', 'del'):
            if len(a) < 2:
                print(C.c("  Использование: trash rm <id>", C.R))
                return
            ok, msg = t.delete_single(a[1])
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif sub in ('restore', 'undel'):
            if len(a) < 2:
                print(C.c("  Использование: trash restore <id>", C.R))
                return
            ok, msg = t.restore(a[1])
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif sub == 'put':
            if len(a) < 2:
                print(C.c("  Использование: trash put <путь>", C.R))
                return
            ok, msg = t.put(a[1], self.cwd)
            print(C.c(f"  {msg}", C.G if ok else C.R))

    # ═══ ФАЙЛОВЫЕ ОПЕРАЦИИ ═══
    def c_rm(self, a):
        perm = '-f' in a or '--perm' in a or '--permanent' in a
        recursive = '-r' in a or '-rf' in a or '-fr' in a
        paths = [x for x in a if not x.startswith('-')]

        if not paths:
            print("  rm [-f] [-r] <file|dir>")
            return

        for p in paths:
            if perm:
                if self.kernel.fs.delete(p, self.cwd, recursive):
                    print(C.c(f"  [Навсегда] Удалено: {p}", C.Y))
                else:
                    print(C.c(f"  Ошибка удаления: {p}", C.R))
            else:
                ok, msg = self.kernel.trash.put(p, self.cwd)
                if ok:
                    print(C.c(f"  [Корзина] {msg} (восстановить: 'trash restore')", C.G))
                else:
                    print(C.c(f"  {msg}", C.R))

    def c_ls(self, a):
        sa = '-a' in a
        lf = '-l' in a or '-la' in a
        paths = [x for x in a if not x.startswith('-')]
        items = self.kernel.fs.list_dir(paths[0] if paths else '.', self.cwd)
        if items is None:
            print(C.c("  Не найдено", C.R))
            return
        if not sa:
            items = [i for i in items if not i['name'].startswith('.')]
        g = self.kernel.guardian
        if lf:
            for it in items:
                tc = 'd' if it['is_dir'] else '-'
                if it['is_dir']:
                    col = C.BL+C.B
                elif it['name'].lower().endswith('.x4s'):
                    col = C.CY+C.B
                elif it['name'].endswith('.x4'):
                    col = C.M
                elif it['name'].endswith('.backup'):
                    col = C.G
                elif it['name'].endswith('.disabled'):
                    col = C.DIM
                else:
                    col = C.W
                sz_str = g.fmt_size(it['size']) if not it['is_dir'] else '<DIR>'
                print(f"  {tc} {sz_str:>10}  {it['modified'][:16]}  {C.c(it['name']+('/' if it['is_dir'] else ''), col)}")
        else:
            ln = '  '
            for it in items:
                if it['is_dir']:
                    col = C.BL+C.B
                elif it['name'].lower().endswith('.x4s'):
                    col = C.CY+C.B
                elif it['name'].endswith('.x4'):
                    col = C.M
                elif it['name'].endswith('.backup'):
                    col = C.G
                elif it['name'].endswith('.disabled'):
                    col = C.DIM
                else:
                    col = C.W
                ln += C.c(it['name']+('/' if it['is_dir'] else ''), col) + '  '
            if ln.strip():
                print(ln)

    def c_cd(self, a):
        if not a:
            self.cwd = self.env.get('HOME', '/')
            return
        p = a[0]
        if p == '-':
            old = self._oldpwd
            self.kernel.fs.current_disk = old['disk']
            p = old['path']
        elif p == '~' or p.startswith('~/'):
            home = self.env.get('HOME', '/')
            p = home if p == '~' else home.rstrip('/') + '/' + p[2:]

        explicit, rest = self.kernel.fs.parse_disk_prefix(p)
        if explicit:
            self.kernel.fs.current_disk = explicit
            p = rest
        resolved, _ = self.kernel.fs.resolve(p, self.cwd)
        if self.kernel.fs.is_dir(resolved):
            self._oldpwd = {'path': self.cwd, 'disk': self.kernel.fs.current_disk}
            self.cwd = resolved
        else:
            print(C.c(f"  Папка не найдена: {a[0]}", C.R))

    def c_pwd(self, _args):
        print(f"  {self.kernel.fs.current_disk}:{self.cwd}")

    def c_mkdir(self, a):
        for p in [x for x in a if not x.startswith('-')]:
            r, _ = self.kernel.fs.resolve(p, self.cwd)
            self.kernel.fs.mkdir(r)

    def c_rmdir(self, a):
        paths = [x for x in a if not x.startswith('-')]
        for p in paths:
            ok, msg = self.kernel.trash.put(p, self.cwd)
            if ok:
                print(C.c(f"  [Корзина] {msg}", C.G))
            else:
                print(C.c(f"  {msg}", C.R))

    def c_touch(self, a):
        for p in a:
            self.kernel.fs.touch(p, self.cwd)

    def c_cat(self, a):
        for p in a:
            content = self.kernel.fs.read_file(p, self.cwd)
            if content is None:
                print(C.c(f"  Не найден: {p}", C.R))
                continue
            print(content)

    def c_echo(self, a):
        print(' '.join(a).encode('utf-8').decode('unicode_escape', errors='replace'))

    def c_cp(self, a):
        if len(a) < 2:
            print("  cp <src> <dst>")
            return
        print(C.c(f"  Скопировано: {a[0]} -> {a[1]}", C.G) if self.kernel.fs.copy(a[0], a[1], self.cwd) else C.c("  Ошибка", C.R))

    def c_mv(self, a):
        if len(a) < 2:
            print("  mv <src> <dst>")
            return
        print(C.c(f"  Перемещено: {a[0]} -> {a[1]}", C.G) if self.kernel.fs.move(a[0], a[1], self.cwd) else C.c("  Ошибка", C.R))

    def c_rename(self, a):
        if len(a) < 2:
            print("  rename <file> <new_name>")
            return
        print(C.c("  Переименовано", C.G) if self.kernel.fs.rename(a[0], a[1], self.cwd) else C.c("  Ошибка", C.R))

    def c_find(self, a):
        if not a:
            print("  find [path] <pattern>")
            return
        p = a[0] if len(a) > 1 else '.'
        pat = a[1] if len(a) > 1 else a[0]
        for r in self.kernel.fs.find(p, pat, self.cwd):
            print(f"  {r}")

    def c_grep(self, a):
        if len(a) < 2:
            print("  grep <pattern> <file>")
            return
        c = self.kernel.fs.read_file(a[1], self.cwd)
        if c is None:
            print(C.c("  Файл не найден", C.R))
            return
        for i, l in enumerate(c.split('\n'), 1):
            if a[0] in l:
                print(f"  {i}: {l.replace(a[0], C.c(a[0], C.R + C.B))}")

    def c_wc(self, a):
        if not a:
            return
        c = self.kernel.fs.read_file(a[0], self.cwd)
        if c is None:
            print(C.c("  Не найден", C.R))
        else:
            lines = c.count('\n') + (1 if c and not c.endswith('\n') else 0)
            words = len(c.split())
            chars = len(c)
            print(f"  {lines:>6} строк {words:>6} слов {chars:>6} байт {a[0]}")

    def c_tree(self, a):
        print(self.kernel.fs.tree(a[0] if a else '.', self.cwd))

    def c_du(self, a):
        p = a[0] if a else '.'
        sz = self.kernel.fs.dir_size_at(p, self.cwd) if self.kernel.fs.is_dir(p, self.cwd) else (
            self.kernel.fs.to_real_path(p, self.cwd)[0].stat().st_size if self.kernel.fs.exists(p, self.cwd) else 0)
        print(f"  {self.kernel.guardian.fmt_size(sz)}  {p}")

    def c_df(self, _args):
        g = self.kernel.guardian
        for d in self.kernel.fs.get_disks():
            u = self.kernel.fs.disk_usage(d)
            cur = " <--" if d == self.kernel.fs.current_disk else ""
            print(f"  {d}: {g.fmt_size(u)}{cur}")

    # ═══ ПОЛЬЗОВАТЕЛИ ═══
    def c_id(self, a):
        u = a[0] if a else self.user
        info = self.kernel.um.get_public_info(u)
        if not info:
            print(C.c(f"  Пользователь не найден: {u}", C.R))
            return
        print(f"  uid={info['uid']}({u}) disk={info.get('disk','C')}: pw={'Argon2id' if info.get('has_password',True) else 'no'}")

    def c_su(self, a):
        if not a:
            print("  su <user>")
            return
        t = a[0]
        if t not in self.kernel.um.users:
            print(C.c("  Пользователь не найден", C.R))
            return
        if not self.kernel.um.has_password(t):
            self._do_login(t)
            return
        if self.kernel.um.auth(t, input("  Пароль: ")):
            self._do_login(t)
        else:
            print(C.c("  Неверный пароль", C.R))

    def c_useradd(self, a):
        if not a:
            print("  useradd <name>")
            return
        name = a[0]
        pw = None
        hint = ''
        if input(f"  Установить пароль для {name}? (y/n): ").strip().lower() in ('y', 'yes', 'да'):
            pw = input("  Пароль: ")
            if input("  Добавить подсказку? (y/n): ").strip().lower() in ('y', 'yes', 'да'):
                hint = input("  Подсказка: ")
        ok, err = self.kernel.um.create(name, pw, hint)
        if ok:
            for d in [f'/home/{name}', f'/home/{name}/Desktop', f'/home/{name}/Documents']:
                self.kernel.fs.mkdir(d)
            print(C.c(f"  Создан пользователь '{name}' (защищен Argon2id)", C.G))
            self.kernel.save_state()
        else:
            print(C.c(f"  {err}", C.R))

    def c_userdel(self, a):
        if not a:
            print("  userdel <name>")
            return
        if a[0] == self.user:
            print(C.c("  Нельзя удалить текущего пользователя", C.R))
            return
        if len(self.kernel.um.users) <= 1:
            print(C.c("  Нельзя удалить последнего пользователя", C.R))
            return
        user_disk = self.kernel.um.get_disk(a[0])
        if self.kernel.um.delete(a[0]):
            home_path = f'/home/{a[0]}'
            old_disk = self.kernel.fs.current_disk
            self.kernel.fs.current_disk = user_disk
            self.kernel.fs.delete(home_path, recursive=True)
            self.kernel.fs.current_disk = old_disk
            print(C.c("  Пользователь удален", C.G))
            self.kernel.save_state()
        else:
            print(C.c("  Ошибка", C.R))

    def c_passwd(self, a):
        t = a[0] if a else self.user
        if t != self.user:
            print(C.c("  Можно менять пароль только для себя", C.R))
            return
        n = input("  Новый пароль (Enter = убрать): ").strip()
        if n == '':
            self.kernel.um.change_password(t, None)
            self.kernel.um.set_hint(t, '')
            print(C.c("  Пароль удален", C.Y))
        else:
            if n != input("  Подтвердите пароль: "):
                print(C.c("  Пароли не совпадают", C.R))
                return
            self.kernel.um.change_password(t, n)
            print(C.c("  Пароль обновлен (Argon2id)", C.G))
            h = input("  Новая подсказка (Enter = оставить): ").strip()
            if h:
                self.kernel.um.set_hint(t, h)
        self.kernel.save_state()

    def c_users(self, _args):
        print("=" * 56)
        print("  Пользователи системы (Защита: Argon2id)")
        print("=" * 56)
        for u in self.kernel.um.list_users():
            info = self.kernel.um.get_public_info(u) or {}
            cur = " <-- вы" if u == self.user else ""
            has_pw = "Argon2id" if info.get('has_password', True) else "открыт"
            print(f"  {u:<14} uid={info.get('uid', '?')} [{has_pw}] диск={info.get('disk','C')}: {info.get('created','?')[:10]}{cur}")
        print("-" * 56)
        print(f"  Всего: {len(self.kernel.um.users)}")
        print("=" * 56)

    # ═══ РЕЗЕРВНЫЕ КОПИИ ═══
    def c_backup(self, a):
        if not a or a[0] == 'list':
            backups = BackupManager.list_backups()
            print("=" * 66)
            print("  Резервные копии (.backup — LZMA Extreme, Argon2id)")
            print("=" * 66)
            if not backups:
                print(C.c("  Резервных копий пока нет.", C.DIM))
            else:
                for b in backups:
                    sz_str = self.kernel.guardian.fmt_size(b['size'])
                    t_str = b['time'][:19].replace('T', ' ')
                    v_badge = C.c("[Argon2id: OK]", C.G) if b['valid'] else C.c("[ПОВРЕЖДЕНА!]", C.R + C.B)
                    print(f"  {b['name']:<30} {sz_str:>9} {v_badge} {t_str}")
            print("-" * 66)
            print("  backup create [name] | backup restore <name> | backup rm <name>")
            print("=" * 66)
            return

        sub = a[0]
        if sub == 'create':
            name = a[1] if len(a) > 1 else None
            print(C.c("  Создание резервной копии и подсчёт хеша Argon2id...", C.CY))
            ok, res = BackupManager.create_backup(name, self.kernel)
            if ok:
                sz = self.kernel.guardian.fmt_size(res.stat().st_size)
                print(C.c(f"  Копия создана: {res.name} ({sz})", C.G))
            else:
                print(C.c(f"  Ошибка создания: {res}", C.R))

        elif sub == 'restore':
            if len(a) < 2:
                print(C.c("  Использование: backup restore <name>", C.R))
                return
            bdir = BackupManager.get_backup_dir()
            fname = a[1] if a[1].endswith('.backup') else a[1] + '.backup'
            bp = bdir / fname
            if not bp.exists():
                print(C.c(f"  Копия не найдена: {fname}", C.R))
                return
            valid, err, _ = BackupManager.verify_backup(bp)
            if not valid:
                print(C.c(f"  Внимание: Выбранная копия повреждена! ({err})", C.R + C.B))
                return
            ans = input(C.c(f"  Восстановить систему из '{fname}'? (y/n): ", C.Y)).strip().lower()
            if ans not in ('y', 'yes', 'да'):
                print("  Отменено.")
                return
            print(C.c("  Восстановление файлов ядра и данных...", C.CY))
            ok, msg = BackupManager.restore_backup(bp, self.kernel)
            if ok:
                print(C.c(f"  {msg}! Перезапуск системы...", C.G))
                time.sleep(1.0)
                script_p = get_script_path()
                os.execv(sys.executable, [sys.executable, str(script_p)] + sys.argv[1:])
            else:
                print(C.c(f"  Ошибка восстановления: {msg}", C.R))

        elif sub in ('rm', 'delete'):
            if len(a) < 2:
                print(C.c("  backup rm <name>", C.R))
                return
            bdir = BackupManager.get_backup_dir()
            fname = a[1] if a[1].endswith('.backup') else a[1] + '.backup'
            bp = bdir / fname
            if bp.exists():
                try:
                    bp.unlink()
                    print(C.c(f"  Удалено: {fname}", C.G))
                except (OSError, PermissionError) as e:
                    print(C.c(f"  Ошибка: {e}", C.R))
            else:
                print(C.c(f"  Не найдено: {fname}", C.R))

    # ═══ ХРАНИЛИЩЕ /CACHE ═══
    def c_cache(self, a):
        if not a or a[0] == 'list':
            items = self.kernel.fs.list_dir('/cache')
            print("=" * 52)
            print("  Системный кэш (/cache)")
            print("=" * 52)
            if not items:
                print(C.c("  Кэш пуст.", C.DIM))
            else:
                total_sz = 0
                for it in items:
                    sz_str = self.kernel.guardian.fmt_size(it['size']) if not it['is_dir'] else '<DIR>'
                    total_sz += it['size']
                    print(f"  {it['name']:<28} {sz_str:>10}  {it['modified'][:16]}")
                print("-" * 52)
                print(f"  Всего в кэше: {self.kernel.guardian.fmt_size(total_sz)}")
            print("-" * 52)
            print("  cache clear | cache cat <file> | cache rm <file>")
            print("=" * 52)
            return

        sub = a[0]
        if sub in ('clear', 'clean'):
            items = self.kernel.fs.list_dir('/cache')
            cnt = 0
            if items:
                for it in items:
                    self.kernel.fs.delete(f"/cache/{it['name']}", recursive=True)
                    cnt += 1
            print(C.c(f"  Очищено {cnt} объектов из кэша.", C.G))
        elif sub == 'cat':
            if len(a) < 2:
                print(C.c("  cache cat <filename>", C.R))
                return
            c = self.kernel.fs.read_file(f"/cache/{a[1]}")
            if c is not None:
                print(c)
            else:
                print(C.c(f"  Файл не найден в кэше: {a[1]}", C.R))
        elif sub == 'rm':
            if len(a) < 2:
                print(C.c("  cache rm <filename>", C.R))
                return
            if self.kernel.fs.delete(f"/cache/{a[1]}", recursive=True):
                print(C.c(f"  Удалено: {a[1]}", C.G))
            else:
                print(C.c(f"  Не найдено: {a[1]}", C.R))

    # ═══ УМНЫЙ КОНТРОЛЬ ПАМЯТИ ═══
    def c_smartmem(self, a):
        s = self.kernel.settings
        if not a:
            st = C.c('ON', C.G) if s.smart_memory else C.c('OFF', C.DIM)
            print("=" * 50)
            print("  Контроль Smart Memory")
            print("=" * 50)
            print(f"  Статус: {st}")
            print("-" * 50)
            print("  smartmem on | smartmem off | smartmem clean")
            print("=" * 50)
            return
        if a[0] == 'on':
            s.smart_memory = True
            print(C.c("  Smart Memory: ON", C.G))
            self.kernel.run_smart_memory_cleanup()
            self.kernel.save_state()
        elif a[0] == 'off':
            s.smart_memory = False
            print(C.c("  Smart Memory: OFF", C.Y))
            self.kernel.save_state()
        elif a[0] == 'clean':
            prev = s.smart_memory
            s.smart_memory = True
            d, f = self.kernel.run_smart_memory_cleanup()
            s.smart_memory = prev
            print(C.c(f"  Очищено: {d} пустых папок, {f} пустых файлов.", C.G))

    # ═══ ИСТОРИЯ И ЛОГИ ═══
    def c_history(self, a):
        if not self.kernel.history:
            return
        if a and a[0] == 'clear':
            self.kernel.history.clear()
            print(C.c("  История очищена", C.G))
            return
        if a and a[0] == 'search':
            pat = ' '.join(a[1:])
            for e in self.kernel.history.search(pat):
                print(f"  {C.c(e['time'][:19], C.DIM)}  {e['cmd']}")
            return
        for i, e in enumerate(self.kernel.history.get_all(), 1):
            print(f"  {i:>4}  {C.c(e['time'][:19], C.DIM)}  {e['cmd']}")

    def c_logs(self, a):
        if not a:
            items = self.kernel.fs.list_dir('/apps/logs')
            logs = [i for i in (items or []) if i['name'].endswith('.json')]
            if not logs:
                print(C.c("  Логов падений нет.", C.G))
                return
            for item in logs:
                print(f"  {item['name']:<35} {self.kernel.guardian.fmt_size(item['size']):>8}")
            return
        if a[0] == 'clear':
            items = self.kernel.fs.list_dir('/apps/logs')
            count = 0
            if items:
                for item in items:
                    if item['name'].endswith('.json'):
                        self.kernel.fs.delete(f"/apps/logs/{item['name']}")
                        count += 1
            print(C.c(f"  Удалено логов: {count}", C.G))
            return
        fname = a[0] if a[0].endswith('.json') else a[0] + '.json'
        content = self.kernel.fs.read_file(f'/apps/logs/{fname}')
        if content:
            print(content)
        else:
            print(C.c(f"  Не найден: {fname}", C.R))

    # ═══ NEOFETCH ═══
    def c_neofetch(self, _args):
        k = self.kernel
        g = k.guardian
        data = {
            'OS': f'PyOS v{Kernel.VERSION}', 'Build': Kernel.BUILD,
            'Company': Kernel.COMPANY, 'Security': 'Argon2id (RFC 9106)',
            'Computer': k.hostname,
            'User': self.user, 'Language': k.settings.lang.upper(),
            'AutoBackup': k.settings.auto_backup,
            'Session': g.session_str(),
            'Time': k.get_now().strftime('%H:%M:%S'),
            'Disks': ' '.join(d + ':' for d in k.fs.get_disks()),
            'Apps': str(len(k.apps.apps)) if k.apps else '0',
            'SmartMem': 'ON' if k.settings.smart_memory else 'OFF',
            'Python': sys.version.split()[0],
        }
        print("=" * 48)
        print("  Информация о системе")
        print("=" * 48)
        for key, value in data.items():
            print(f"  {key:<15}: {value}")
        print("=" * 48)

    def c_suggest(self, a):
        g = self.kernel.guardian
        if not a:
            print(f"  Подсказки: {'ON' if g.suggest_commands else 'OFF'}")
            return
        if a[0] == 'on':
            g.suggest_commands = True
            print(C.c("  Включены", C.G))
        elif a[0] == 'off':
            g.suggest_commands = False
            print(C.c("  Отключены", C.Y))
        self.kernel.save_state()

    # ═══ GUARDIAN: МОНИТОРИНГ, ОБНОВЛЕНИЯ И УДАЛЕНИЕ ═══
    def c_guardian(self, a):
        if a and a[0] in ('update', 'updates'):
            self._ui_update_center()
            return
        if a and a[0] in ('uninstall', 'destroy'):
            self._ui_uninstall_center()
            return
        self._guardian_screen()

    def _guardian_screen(self):
        while True:
            clear()
            g = self.kernel.guardian
            report = g.disk_report(self.kernel.fs)
            lim = f"{g.daily_limit} мин" if g.daily_limit else "Без лимита"
            app_checks = g.check_all_apps(self.kernel.fs)
            print("=" * 56)
            print("  Guardian — Центр Безопасности & Оптимизации")
            print("=" * 56)
            print(f"  Сессия:          {g.session_str()} (лимит: {lim})")
            print(f"  Диск занято:     {g.fmt_size(report['total'])}")
            print(f"  Автобэкап:       {C.c(self.kernel.settings.auto_backup, C.CY)}")
            print(f"  Лимит на app:    {g.fmt_size(g.app_folder_limit)}")
            if app_checks:
                print("-" * 56)
                print("  Состояние приложений:")
                for ac in app_checks:
                    status = C.c("ПЕРЕПОЛНЕНИЕ!", C.R) if ac['over'] else C.c("OK", C.G)
                    print(f"    {ac['name']:<16} {g.fmt_size(ac['size']):>8} {status}")
            print("-" * 56)
            print("  1. Центр обновлений PyOS (патчи и новый код)")
            print("  2. Оптимизация памяти всех приложений")
            print("  3. Удаление / Деинсталляция PyOS")
            print("  0. Назад на рабочий стол")
            print("=" * 56)

            try:
                choice = input(C.c("  Выберите действие (0-3): ", C.W)).strip()
            except (EOFError, KeyboardInterrupt):
                break

            if choice in ('0', 'q', 'exit', ''):
                break
            elif choice == '1':
                self._ui_update_center()
            elif choice == '2':
                print()
                cleaned_any = False
                for it in self.kernel.fs.list_dir('/apps/data') or []:
                    if it['is_dir']:
                        dels = g.cleanup_app_folder(self.kernel.fs, it['name'])
                        if dels:
                            cleaned_any = True
                            print(C.c(f"  Очищено в {it['name']}: {len(dels)} файлов", C.G))
                if not cleaned_any:
                    print(C.c("  Все приложения в пределах нормы памяти.", C.G))
                input(C.c("\n  Нажмите Enter...", C.DIM))
            elif choice == '3':
                if self._ui_uninstall_center():
                    return

        self._do_desktop()

    def _ui_update_center(self):
        clear()
        script_p = get_script_path()
        cur_hash = compute_file_hash(script_p)
        print("=" * 64)
        print("  Guardian: Центр Обновлений PyOS")
        print("=" * 64)
        print(f"  Текущая версия: v{Kernel.VERSION} (build {Kernel.BUILD})")
        print(f"  Текущий Argon2id хеш:")
        print(f"  {C.c(cur_hash, C.CY)}")
        print("-" * 64)
        print("  1. Применить патч обновления (файл .patch формата PyOS/Git Diff)")
        print("  2. Вставить текст патча вручную через консоль")
        print("  3. Установить из нового файла исходного кода (pyos.py)")
        print("  0. Отмена / Назад")
        print("=" * 64)

        try:
            choice = input(C.c("  Выберите действие (0-3): ", C.W)).strip()
        except (EOFError, KeyboardInterrupt):
            return

        if choice in ('0', 'q', 'exit', ''):
            return

        if choice == '1':
            patch_path = input("  Укажите путь к файлу патча (в системе или на диске): ").strip()
            if not patch_path:
                return
            content = self.kernel.fs.read_file(patch_path, self.cwd)
            if not content:
                p_real = Path(patch_path)
                if p_real.is_file():
                    content = p_real.read_text(encoding='utf-8', errors='replace')
            if not content:
                print(C.c("  Файл патча не найден или пуст!", C.R))
                time.sleep(1.5)
                return
            self._execute_patch(content)

        elif choice == '2':
            print(C.c("\n  Вставьте пакет патча (включая [BEGIN PYOS PATCH] и [END PYOS PATCH]).", C.Y))
            print(C.c("  Для завершения ввода отправьте пустую строку или слово 'EOF':", C.DIM))
            lines = []
            while True:
                try:
                    l = input()
                    if l.strip() == 'EOF' or (lines and l == '' and lines[-1].strip() == '[END PYOS PATCH]'):
                        if l.strip() != 'EOF' and l:
                            lines.append(l)
                        break
                    lines.append(l)
                except (EOFError, KeyboardInterrupt):
                    break
            raw_patch = "\n".join(lines).strip()
            if raw_patch:
                self._execute_patch(raw_patch)

        elif choice == '3':
            code_file = input("  Укажите путь к новому файлу с кодом (.py): ").strip()
            if not code_file:
                return
            content = self.kernel.fs.read_file(code_file, self.cwd)
            if not content:
                p_real = Path(code_file)
                if p_real.is_file():
                    content = p_real.read_text(encoding='utf-8', errors='replace')
            if not content:
                print(C.c("  Файл с кодом не найден!", C.R))
                time.sleep(1.5)
                return
            print(C.c("  Верификация синтаксиса и генерация Argon2id хэша...", C.CY))
            ok, msg = self.kernel.guardian.apply_full_code_update(content, self.kernel)
            if ok:
                print(C.c(f"  {msg}", C.G))
                print(C.c("  Перезапуск системы для активации обновления...", C.CY))
                time.sleep(1.2)
                script_p = get_script_path()
                os.execv(sys.executable, [sys.executable, str(script_p)] + sys.argv[1:])
            else:
                print(C.c(f"  Ошибка обновления: {msg}", C.R))
                input(C.c("\n  Нажмите Enter...", C.DIM))

    def _execute_patch(self, patch_str: str):
        print(C.c("\n  Проверка контрольных хешей и наложение Git Diff...", C.CY))
        ok, msg = self.kernel.guardian.apply_patch_update(patch_str, self.kernel)
        if ok:
            print(C.c(f"  {msg}", C.G))
            print(C.c("  Перезапуск PyOS...", C.CY))
            time.sleep(1.2)
            script_p = get_script_path()
            os.execv(sys.executable, [sys.executable, str(script_p)] + sys.argv[1:])
        else:
            print(C.c(f"  Ошибка обновления:\n{msg}", C.R))
            input(C.c("\n  Нажмите Enter...", C.DIM))

    def _ui_uninstall_center(self):
        clear()
        print("=" * 64)
        print(C.c("  ВНИМАНИЕ: МАСТЕР УДАЛЕНИЯ PYOS", C.R + C.B))
        print("=" * 64)
        print("  Выберите вариант деинсталляции:")
        print("  1. Полное удаление (стирает саму PyOS, все диски, файлы и настройки)")
        print("  2. Обычное удаление с резервной копией (сохраняет бэкап в отдельную")
        print("     папку во внешней системе и начисто удаляет саму PyOS)")
        print("  0. Отмена")
        print("=" * 64)

        try:
            choice = input(C.c("  Выберите режим (0-2): ", C.W)).strip()
        except (EOFError, KeyboardInterrupt):
            return False

        if choice not in ('1', '2'):
            return False

        mode = 'full' if choice == '1' else 'backup'
        warn_text = "ПОЛНОЕ УНИЧТОЖЕНИЕ СИСТЕМЫ" if mode == 'full' else "УДАЛЕНИЕ С СОЗДАНИЕМ ВНЕШНЕГО БЭКАПА"
        print(C.c(f"\n  Выбрано: {warn_text}", C.Y + C.B))
        conf = input(C.c("  Чтобы подтвердить, введите заглавными 'DELETE': ", C.R)).strip()
        if conf != 'DELETE':
            print("  Удаление отменено.")
            time.sleep(1.0)
            return False

        print(C.c("\n  Выполняется процедура удаления системы...", C.Y))
        ok, backup_path = self.kernel.guardian.uninstall_pyos(mode, self.kernel)
        if ok:
            clear()
            print("=" * 60)
            print(C.c("  PyOS была успешно деинсталлирована и удалена.", C.G + C.B))
            if backup_path:
                print(f"  Резервная копия ваших файлов сохранена в:\n  {backup_path}")
            print("=" * 60)
            print("  Сессия завершена.")
            sys.exit(0)
        return False

    # ═══ ТЕГИ ПРИЛОЖЕНИЙ ═══
    def _ui_app_tags(self):
        apps = self.kernel.apps.apps
        if not apps:
            print(C.c("  Установленных приложений нет.", C.DIM))
            return

        tag_map = {}
        for app_name, app_data in apps.items():
            t = app_data.get('info', {}).get('tag', 'Other').strip()
            if not t:
                t = 'Other'
            t = t.capitalize()
            tag_map.setdefault(t, []).append(app_name)

        sorted_tags = sorted(tag_map.keys(), key=lambda x: len(tag_map[x]), reverse=True)

        print()
        print("=" * 50)
        print("  Теги приложений (App Tags)")
        print("=" * 50)
        for idx, tag in enumerate(sorted_tags, 1):
            count = len(tag_map[tag])
            print(f"  {idx}. {tag} ({count})")
        print("=" * 50)
        print("  0. Отмена / Назад")
        print()

        try:
            choice = input(C.c("  Выберите тег: ", C.W)).strip()
        except (EOFError, KeyboardInterrupt):
            return

        if not choice or choice in ('0', 'q', 'exit'):
            return

        if not choice.isdigit() or not (1 <= int(choice) <= len(sorted_tags)):
            print(C.c("  Неверный выбор тега.", C.R))
            return

        chosen_tag = sorted_tags[int(choice) - 1]
        apps_in_tag = sorted(tag_map[chosen_tag])

        print()
        print("=" * 50)
        print(f"  Приложения в категории [{chosen_tag}]")
        print("=" * 50)
        for idx, app_name in enumerate(apps_in_tag, 1):
            info = self.kernel.apps.get_info(app_name)
            desc = info.get('description', '')
            ver = info.get('version', '1.0')
            print(f"  {idx}. {app_name:<14} v{ver:<5} - {desc}")
        print("=" * 50)
        print("  0. Назад")
        print()

        try:
            app_choice = input(C.c("  Выберите приложение для запуска: ", C.G)).strip()
        except (EOFError, KeyboardInterrupt):
            return

        if not app_choice or app_choice in ('0', 'q', 'exit'):
            return

        if not app_choice.isdigit() or not (1 <= int(app_choice) <= len(apps_in_tag)):
            print(C.c("  Неверный выбор приложения.", C.R))
            return

        selected_app = apps_in_tag[int(app_choice) - 1]
        clear()
        self.kernel.apps.run(selected_app, self)
        self._do_desktop()

    # ═══ МЕНЕДЖЕР ПРОГРАММ ═══
    def _ui_app_manager(self):
        while True:
            clear()
            apps = self.kernel.apps.apps
            disabled_apps = self.kernel.apps.list_disabled()
            print("=" * 56)
            print("  Менеджер Программ (App Manager)")
            print("=" * 56)
            print(f"  Активных приложений: {len(apps)}")
            print(f"  Отключенных (сжатых): {len(disabled_apps)}")
            print("-" * 56)
            print("  1. Удалить приложение (с сохранением данных в cache)")
            print("  2. Обновить приложение (выбор новой версии x4)")
            print("  3. Отключить приложение (сжать в архив, освободив место)")
            print("  4. Включить приложение обратно (распаковать архив)")
            print("  5. Список всех приложений и их размер")
            print("  0. Вернуться на рабочий стол")
            print("=" * 56)

            try:
                choice = input(C.c("  Выберите действие (0-5): ", C.W)).strip()
            except (EOFError, KeyboardInterrupt):
                break

            if choice in ('0', 'q', 'exit', ''):
                break

            if choice == '1':
                print()
                print("--- Удаление приложения ---")
                app_list = sorted(apps.keys())
                if not app_list:
                    print(C.c("  Нет установленных приложений для удаления.", C.Y))
                    time.sleep(1.2)
                    continue
                for idx, an in enumerate(app_list, 1):
                    print(f"  {idx}. {an}")
                print("  0. Отмена")
                sub = input("  Выберите номер приложения для удаления: ").strip()
                if sub.isdigit() and 1 <= int(sub) <= len(app_list):
                    del_app = app_list[int(sub) - 1]
                    confirm = input(C.c(f"  Точно удалить '{del_app}'? Папка данных будет сохранена в /cache (y/n): ", C.Y)).lower()
                    if confirm in ('y', 'yes', 'да'):
                        ok, msg = self.kernel.apps.remove(del_app, backup_data_to_cache=True)
                        print(C.c(f"  {msg}", C.G if ok else C.R))
                input(C.c("\n  Нажмите Enter для продолжения...", C.DIM))

            elif choice == '2':
                print()
                print("--- Обновление приложения ---")
                app_list = sorted(apps.keys())
                if not app_list:
                    print(C.c("  Нет установленных приложений для обновления.", C.Y))
                    time.sleep(1.2)
                    continue
                for idx, an in enumerate(app_list, 1):
                    ver = self.kernel.apps.get_info(an).get('version', '?')
                    print(f"  {idx}. {an} (текущая: v{ver})")
                print("  0. Отмена")
                sub = input("  Выберите приложение для обновления: ").strip()
                if sub.isdigit() and 1 <= int(sub) <= len(app_list):
                    up_app = app_list[int(sub) - 1]
                    new_path = input("  Укажите путь к новому .x4 файлу: ").strip()
                    if new_path:
                        ok, msg = self.kernel.apps.update_app(up_app, new_path, self.cwd)
                        print(C.c(f"  {msg}", C.G if ok else C.R))
                input(C.c("\n  Нажмите Enter для продолжения...", C.DIM))

            elif choice == '3':
                print()
                print("--- Отключение (сжатие) приложения ---")
                app_list = sorted(apps.keys())
                if not app_list:
                    print(C.c("  Нет активных приложений для отключения.", C.Y))
                    time.sleep(1.2)
                    continue
                for idx, an in enumerate(app_list, 1):
                    print(f"  {idx}. {an}")
                print("  0. Отмена")
                sub = input("  Выберите номер приложения для отключения: ").strip()
                if sub.isdigit() and 1 <= int(sub) <= len(app_list):
                    freeze_app = app_list[int(sub) - 1]
                    print(C.c(f"  Сжатие приложения '{freeze_app}' и его папки данных...", C.CY))
                    ok, msg = self.kernel.apps.disable(freeze_app)
                    print(C.c(f"  {msg}", C.G if ok else C.R))
                input(C.c("\n  Нажмите Enter для продолжения...", C.DIM))

            elif choice == '4':
                print()
                print("--- Включение ранее отключенного приложения ---")
                dis_list = sorted(disabled_apps)
                if not dis_list:
                    print(C.c("  Нет отключенных приложений.", C.DIM))
                    time.sleep(1.2)
                    continue
                for idx, an in enumerate(dis_list, 1):
                    print(f"  {idx}. {an} [отключено]")
                print("  0. Отмена")
                sub = input("  Выберите приложение для включения: ").strip()
                if sub.isdigit() and 1 <= int(sub) <= len(dis_list):
                    unfreeze_app = dis_list[int(sub) - 1]
                    print(C.c(f"  Восстановление приложения '{unfreeze_app}' из архива...", C.CY))
                    ok, msg = self.kernel.apps.enable(unfreeze_app)
                    print(C.c(f"  {msg}", C.G if ok else C.R))
                input(C.c("\n  Нажмите Enter для продолжения...", C.DIM))

            elif choice == '5':
                self.c_app(['list'])
                input(C.c("\n  Нажмите Enter для продолжения...", C.DIM))

        self._do_desktop()

    def c_app(self, a):
        if not self.kernel.apps:
            print(C.c("  Приложения недоступны", C.R))
            return
        if not a:
            print("  app tags — запуск через удобные категории/теги")
            print("  app manager — интерактивный менеджер программ")
            print("  app <run|list|info|install|remove|disable|enable> [name]")
            return

        act = a[0].lower()
        if act == 'tags':
            self._ui_app_tags()
        elif act in ('manager', 'manage'):
            self._ui_app_manager()
        elif act == 'run':
            if len(a) < 2:
                print("  app run <name>")
                return
            ok, err = self.kernel.apps.run(a[1], self)
            if not ok:
                print(C.c(f"  {err}", C.R))
            self._do_desktop()
        elif act == 'list':
            apps = self.kernel.apps.apps
            g = self.kernel.guardian
            print("=" * 66)
            print("  Установленные приложения (.x4 / .x4s)")
            print("=" * 66)
            for name, data in apps.items():
                info = data.get('info', {})
                fmt = data.get('format', 'x4').upper()
                fmt_badge = C.c("[X4S]", C.CY + C.B) if fmt == 'X4S' else C.c("[x4]", C.M)
                tag = f"[{info.get('tag','Other')}]"
                cur, _, _ = g.check_app_folder(self.kernel.fs, name)
                print(f"  {name:<12} {fmt_badge} v{info.get('version','?'):<5} {g.fmt_size(cur):>6}  {tag:<12} {info.get('description','')[:16]}")

            dis = self.kernel.apps.list_disabled()
            if dis:
                print("-" * 66)
                print(C.c(f"  Отключенные приложения (сжатые в архив): {', '.join(dis)}", C.DIM))
            print("-" * 66)
            print(f"  Всего активно: {len(apps)} | Всего отключено: {len(dis)}")
            print("=" * 66)
        elif act == 'info':
            if len(a) < 2:
                return
            info = self.kernel.apps.get_info(a[1])
            if info:
                print("=" * 44)
                print(f"  Информация о приложении: {a[1]}")
                print("=" * 44)
                for k, v in info.items():
                    print(f"  {k}: {v}")
                print("=" * 44)
            else:
                print(C.c("  Приложение не найдено", C.R))
        elif act == 'install':
            if len(a) < 2:
                print("  app install <file.x4|file.x4s>")
                return
            ok, msg = self.kernel.apps.install(a[1], self.cwd, home_dir=self.env['HOME'])
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif act == 'remove':
            if len(a) < 2:
                return
            ok, msg = self.kernel.apps.remove(a[1], backup_data_to_cache=True)
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif act == 'disable':
            if len(a) < 2:
                return
            ok, msg = self.kernel.apps.disable(a[1])
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif act == 'enable':
            if len(a) < 2:
                return
            ok, msg = self.kernel.apps.enable(a[1])
            print(C.c(f"  {msg}", C.G if ok else C.R))

    def c_newapp(self, a):
        if not a:
            print("  newapp <name> [tag]")
            return
        name = a[0]
        tag = a[1] if len(a) > 1 else "Technical"
        docs = self._docs()
        self.kernel.fs.write_file(f'{docs}/{name}.x4', X4Parser.template(name, self.user, tag=tag))
        print(C.c(f"  Создан шаблон x4 приложения: {docs}/{name}.x4 (Тег: {tag})", C.G))

    # ═══ ДИСКИ ═══
    def c_disk(self, a):
        g = self.kernel.guardian
        if not a:
            for d in self.kernel.fs.get_disks():
                u = self.kernel.fs.disk_usage(d)
                cur = " <--" if d == self.kernel.fs.current_disk else ""
                print(f"  {d}: {g.fmt_size(u)}{cur}")
            return
        if a[0] == 'add':
            if len(a) < 2:
                print("  disk add <буква>")
                return
            l = a[1].upper()
            if len(l) != 1 or not l.isalpha():
                print(C.c("  Только одна буква A-Z", C.R))
                return
            if l in self.kernel.fs.get_disks():
                print(C.c(f"  Диск {l}: уже существует", C.R))
                return
            self.kernel.fs.create_disk(l)
            print(C.c(f"  Диск {l}: создан", C.G))
            self.kernel.save_state()

    # ═══ РЕДАКТОР ═══
    def c_edit(self, a):
        if not a:
            print("  edit <file>")
            return
        p = a[0]
        docs = self._docs()
        fp = f"{docs}/{p}" if '/' not in p and not p.startswith('/') and ':' not in p else p
        c = self.kernel.fs.read_file(fp, self.cwd)
        if c is not None and '\0' in c:
            print(C.c("  Бинарный файл не поддерживается для редактирования.", C.R))
            return
        new = (c or '').split('\n') if c else ['']
        print(C.c(f"  === PyEdit: {fp} ===", C.CY))
        for i, l in enumerate(new):
            print(f"  {C.c(str(i+1).rjust(3), C.DIM)} | {l}")
        while True:
            try:
                inp = input(C.c("  edit> ", C.G))
            except (EOFError, KeyboardInterrupt):
                if input("\n  Сохранить? (y/n): ").strip().lower() in ('y', 'yes', 'да'):
                    self.kernel.fs.write_file(fp, '\n'.join(new), self.cwd)
                    print("  Сохранено")
                break
            if inp == ':q':
                self._do_desktop()
                return
            if inp == ':wq':
                self.kernel.fs.write_file(fp, '\n'.join(new), self.cwd)
                print(f"  Сохранено: {fp}")
                self._do_desktop()
                return
            if inp in (':w', ':s'):
                self.kernel.fs.write_file(fp, '\n'.join(new), self.cwd)
                print("  Сохранено")
                continue
            if inp == ':p':
                for i, l in enumerate(new):
                    print(f"  {C.c(str(i+1).rjust(3), C.DIM)} | {l}")
                continue
            new.append(inp)
            print(f"  {C.c(str(len(new)).rjust(3), C.DIM)} | {inp}")

    # ═══ НАСТРОЙКИ, ЯЗЫК, DEBUG, NOTIF, TIMER ═══
    def c_settings(self, a):
        s = self.kernel.settings
        now = self.kernel.get_now()
        if not a:
            print("=" * 52)
            print(f"  Настройки -- PyOS {Kernel.VERSION} (Argon2id)")
            print("=" * 52)
            print(f"  Язык:         {s.lang.upper()} (ru / en)")
            print(f"  AutoBackup:   {C.c(s.auto_backup, C.CY)}")
            print(f"  Режим времени:{s.time_mode.upper()}")
            print(f"  Время:        {now.strftime('%H:%M:%S')}")
            print(f"  Дата:         {now.strftime('%Y-%m-%d')}")
            print(f"  Debug:        {C.c('ON',C.Y) if s.debug_mode else C.c('OFF',C.DIM)}")
            print(f"  Smart Memory: {C.c('ON',C.G) if s.smart_memory else C.c('OFF',C.DIM)}")
            print("-" * 52)
            print("  settings lang ru|en")
            print("  settings autobackup off|at_start|at_shutdown|hourly")
            print("  settings time auto|set HH:MM:SS|date YYYY-MM-DD")
            print("  settings debug on|off|clear")
            print("  settings smartmem on|off|clean")
            print("=" * 52)
            return

        sub = a[0]
        if sub == 'lang':
            if len(a) > 1 and a[1].lower() in ('ru', 'en'):
                s.lang = a[1].lower()
                print(C.c(f"  Язык изменен на {s.lang.upper()}", C.G))
                self.kernel.save_state()
            else:
                print(C.c("  Использование: settings lang ru | settings lang en", C.R))
        elif sub == 'autobackup':
            if len(a) > 1 and a[1].lower() in SettingsManager.VALID_AUTOBACKUP:
                s.auto_backup = a[1].lower()
                print(C.c(f"  AutoBackup: {s.auto_backup}", C.G))
                self.kernel.save_state()
            else:
                print(C.c("  Допустимо: off, at_start, at_shutdown, hourly", C.R))
        elif sub == 'smartmem':
            self.c_smartmem(a[1:])
        elif sub == 'debug':
            if len(a) < 2:
                return
            if a[1] == 'on':
                s.debug_mode = True
                print(C.c("  Debug ON", C.Y))
                self.kernel.save_state()
            elif a[1] == 'off':
                s.debug_mode = False
                print(C.c("  Debug OFF", C.G))
                self.kernel.save_state()

    def c_alias(self, a):
        if not a:
            for k, v in self.aliases.items():
                print(f"  {k}='{v}'")
            return
        s = ' '.join(a)
        if '=' in s:
            n, v = s.split('=', 1)
            self.aliases[n.strip()] = v.strip("'\"")

    def c_export(self, a):
        if not a:
            for k, v in sorted(self.env.items()):
                print(f"  {k}={v}")
            return
        for x in a:
            if '=' in x:
                k, v = x.split('=', 1)
                self.env[k] = v

    def c_realpath(self, a):
        p = a[0] if a else '.'
        rp, dk = self.kernel.fs.to_real_path(p, self.cwd)
        print(f"  {dk}:{self.kernel.fs.resolve(p, self.cwd)[0]} -> {rp}")

    def c_debug(self, a):
        if not self.kernel.settings.debug_mode:
            print(C.c("  Debug выключен. Включить: 'settings debug on'", C.Y))
            return
        if not self.kernel.debug:
            print(C.c("  Не инициализирован", C.R))
            return
        if not a:
            errors = self.kernel.debug.get_recent(15)
            if not errors:
                print(C.c("  Ошибок нет", C.DIM))
                return
            for e in errors:
                t = e.get('time', '')[11:19]
                print(f"  #{e.get('id','?'):<3} [{e.get('source','?')[:10]}] {e.get('message','')[:35]} {C.c(t, C.DIM)}")
            return
        if a[0] == 'clear':
            self.kernel.debug.clear()
            print(C.c("  Лог ошибок очищен", C.G))

    def c_notif(self, a):
        nc = self.kernel.notifications
        if not a:
            all_n = nc.get_all()
            if not all_n:
                print(C.c("  Нет уведомлений", C.DIM))
                return
            for n in all_n[-15:]:
                rm = C.c('+', C.G) if n['read'] else C.c('*', C.Y)
                print(f"  {rm} #{n['id']:<3} [{n['source'][:10]}] {n['title'][:25]} {C.c(n['time'][11:16], C.DIM)}")
            return
        if a[0] == 'read':
            nc.mark_read(int(a[1]) if len(a) > 1 and a[1].isdigit() else None)
            print(C.c("  Отмечено прочитанным", C.G))
        elif a[0] == 'clear':
            nc.delete()
            print(C.c("  Очищено", C.G))

    def c_timer(self, a):
        ts = self.kernel.timer_service
        if not a:
            all_t = ts.get_all()
            now = datetime.datetime.now()
            if not all_t:
                print(C.c("  Таймеров нет", C.DIM))
                return
            for t in all_t:
                if t['fired']:
                    print(f"  + #{t['id']:<3} {t['label'][:20]} ЗАВЕРШЕН")
                else:
                    rem = max(0, int((t['end_time'] - now).total_seconds()))
                    m2, s = divmod(rem, 60)
                    h, m2 = divmod(m2, 60)
                    print(f"  @ #{t['id']:<3} {t['label'][:20]} {h}:{m2:02d}:{s:02d} осталось")
            return
        if a[0] in ('add', 'set'):
            if len(a) < 2:
                print("  timer add <сек> [метка]")
                return
            try:
                secs = int(a[1])
                label = ' '.join(a[2:]) if len(a) > 2 else 'Таймер'
                tid = ts.add_timer(secs, label)
                print(C.c(f"  Таймер #{tid}: {label} ({secs}с)", C.G) if tid else C.c("  Ошибка", C.R))
            except ValueError:
                print(C.c("  Неверное число секунд", C.R))
        elif a[0] in ('cancel', 'rm'):
            if len(a) > 1 and a[1].isdigit():
                print(C.c("  Отменен", C.G) if ts.cancel_timer(int(a[1])) else C.c("  Не найден", C.R))
        elif a[0] == 'clear':
            ts.cleanup()
            print(C.c("  Очищено", C.G))

    def c_man(self, a):
        print("  Используйте help для просмотра списка доступных команд.")

    def c_help(self, _args):
        cats = [
            ('Файлы',     'ls cd pwd mkdir rmdir touch rm cat cp mv rename find grep wc tree du df'),
            ('Корзина',   'trash (list, empty [со сжатием в tar.xz], rm <id>, restore <id>)'),
            ('Пользователи', 'whoami id su useradd userdel passwd users (Argon2id)'),
            ('Система',   'date uptime hostname neofetch reboot shutdown'),
            ('Оболочка',  'echo clear desktop history alias export env edit save reload'),
            ('Бэкапы',    'backup (create, list, restore, rm) — защита Argon2id'),
            ('Кэш',       'cache (list, clear, cat, rm)'),
            ('SmartMem',  'smartmem (on, off, clean)'),
            ('Guardian',  'guardian (update, uninstall, оптимизация)'),
            ('Программы', 'app (tags, manager, list, run, install, remove, disable, enable) | newapp'),
            ('Диски',     'disk (add)'),
            ('Уведомления', 'notif | timer'),
            ('Настройки', 'settings (lang, autobackup, time, debug, smartmem)'),
            ('Другое',    'realpath help exit'),
        ]
        print("=" * 90)
        print(f"  PyOS v{Kernel.VERSION} Справка [Безопасность: Argon2id]")
        print("=" * 90)
        for cat, clist in cats:
            print(f"  {C.c(cat + ':', C.Y)} {clist}")
        print("-" * 90)
        print(C.c(f"  {Kernel.COMPANY} -- PyOS {Kernel.VERSION}", C.DIM))
        print("=" * 90)

    def c_save(self, _args):
        print(C.c("  Сохранено", C.G) if self.kernel.save_state() else C.c("  Ошибка", C.R))

    def c_shutdown(self, _args):
        self.kernel.shutdown()

    def c_reboot(self, _args):
        self.kernel.save_state()
        self.kernel.boot_time = datetime.datetime.now()
        self.kernel.guardian.session_start = datetime.datetime.now()
        if self.kernel.apps:
            self.kernel.apps.apps.clear()
            self.kernel.apps.load_installed()
        clear()
        self.kernel.boot_anim()
        self._do_desktop()

    def c_exit(self, _args):
        self.kernel.shutdown()

# ═══ ТОЧКА ВХОДА ═══
def main():
    verify_pyos_integrity()

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
            print(C.c(f"\n  [Критический сбой] {e}", C.R))
            tb_module.print_exc()
            if kernel.settings.debug_mode and kernel.debug:
                kernel.debug.log('panic', str(e), tb_module.format_exc(), 'kernel', '')
            kernel.save_state()
        if kernel.is_bsod_pending():
            err_code, msg, details = kernel.get_bsod_info()
            BSOD.crash_and_restart(err_code, msg, details)
            kernel.restart_after_bsod()
            continue
        break

if __name__ == '__main__':
    main()