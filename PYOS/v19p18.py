# ═══════════════════════════════════════════════════════════════
#  PyOS v19.1 "Nexus" — build 18.10.2026
#  Kostyl Studios | Argon2id+salt | Root/User/Program | UAC + GitHub AppStore
# ═══════════════════════════════════════════════════════════════
from contextlib import contextmanager, redirect_stdout
import ast
import datetime
import difflib
import io
import json
import lzma
import math
import operator as _op
import os
from pathlib import Path
import random
import re
import secrets
import shlex
import shutil
import sys
import tarfile
import textwrap
import threading
import time
import traceback as tb_module
import urllib.request
import urllib.error

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerificationError, VerifyMismatchError
    from argon2.low_level import Type, hash_secret_raw
except ImportError:
    print("\n[PyOS] Требуется argon2-cffi: pip install argon2-cffi")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
#  ПРАВА
# ═══════════════════════════════════════════════════════════════
class Perm:
    ROOT = 3
    USER = 2
    PROGRAM = 1
    NONE = 0


class PermissionContext:
    """Thread-local. Главный поток: ROOT. Прочие потоки: NONE."""
    _local = threading.local()
    _main_tid = None

    @classmethod
    def _state(cls):
        if cls._main_tid is None:
            cls._main_tid = threading.get_ident()
        if not hasattr(cls._local, 'level'):
            if threading.get_ident() == cls._main_tid:
                cls._local.level = Perm.ROOT
            else:
                cls._local.level = Perm.NONE
            cls._local.user = None
            cls._local.app = None
        return cls._local.level, cls._local.user, cls._local.app

    @classmethod
    def get(cls):
        return cls._state()[0]

    @classmethod
    def user(cls):
        return cls._state()[1]

    @classmethod
    def app(cls):
        return cls._state()[2]

    @classmethod
    def set(cls, level, user=None, app=None):
        cls._local.level = level
        cls._local.user = user
        cls._local.app = app

    @classmethod
    def reset(cls):
        cls._local.level = Perm.ROOT
        cls._local.user = None
        cls._local.app = None


@contextmanager
def perm_root():
    old = PermissionContext._state()
    PermissionContext.set(Perm.ROOT)
    try:
        yield
    finally:
        PermissionContext.set(*old)


@contextmanager
def perm_user(user):
    old = PermissionContext._state()
    PermissionContext.set(Perm.USER, user=user)
    try:
        yield
    finally:
        PermissionContext.set(*old)


@contextmanager
def perm_program(user, app):
    old = PermissionContext._state()
    PermissionContext.set(Perm.PROGRAM, user=user, app=app)
    try:
        yield
    finally:
        PermissionContext.set(*old)


def _spawn_thread_helper(fn, *args, **kwargs):
    """Создаёт поток, наследующий текущие права вызывающего."""
    parent = PermissionContext._state()

    def wrapper():
        PermissionContext.set(*parent)
        try:
            fn(*args, **kwargs)
        finally:
            PermissionContext.set(Perm.NONE)

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    return t


# ═══════════════════════════════════════════════════════════════
#  ARGON2ID
# ═══════════════════════════════════════════════════════════════
ARGON2_HASHER = PasswordHasher(
    time_cost=2, memory_cost=19456, parallelism=1,
    hash_len=32, type=Type.ID)


def argon2id_hash_bytes(data: bytes, salt: bytes) -> str:
    raw = hash_secret_raw(secret=data, salt=salt,
                          time_cost=2, memory_cost=19456, parallelism=1,
                          hash_len=32, type=Type.ID)
    return raw.hex()


# ═══════════════════════════════════════════════════════════════
#  БЕЗОПАСНЫЙ EVAL (AST)
# ═══════════════════════════════════════════════════════════════
_SAFE_BINOPS = {
    ast.Add: _op.add, ast.Sub: _op.sub, ast.Mult: _op.mul,
    ast.Div: _op.truediv, ast.FloorDiv: _op.floordiv,
    ast.Mod: _op.mod, ast.Pow: _op.pow,
    ast.BitAnd: _op.and_, ast.BitOr: _op.or_, ast.BitXor: _op.xor,
    ast.LShift: _op.lshift, ast.RShift: _op.rshift,
}
_SAFE_UNARYOPS = {
    ast.USub: _op.neg, ast.UAdd: _op.pos,
    ast.Invert: _op.invert, ast.Not: _op.not_,
}
_SAFE_CONSTS = {'True': True, 'False': False, 'None': None}
_SAFE_FUNCS = {'abs': abs, 'round': round, 'pow': pow, 'min': min,
               'max': max, 'sum': sum, 'len': len, 'int': int,
               'float': float, 'bool': bool}
_MATH_ALLOWED = {
    'sqrt', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2',
    'log', 'log2', 'log10', 'exp', 'floor', 'ceil', 'trunc',
    'fabs', 'degrees', 'radians', 'hypot', 'gcd', 'factorial',
    'pi', 'e', 'tau', 'inf', 'nan',
}


def _safe_eval_node(node, g, l):
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body, g, l)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex, bool)) or node.value is None:
            return node.value
        raise ValueError(f"Constant {type(node.value).__name__} not allowed")
    if isinstance(node, (ast.Num, ast.Str, ast.Bytes, ast.NameConstant)):
        v = getattr(node, 'n', getattr(node, 's', getattr(node, 'value', None)))
        if isinstance(v, (int, float, complex, bool, str)) or v is None:
            return v
        raise ValueError("Constant not allowed")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_BINOPS:
            raise ValueError(f"Operator {op_type.__name__} not allowed")
        return _SAFE_BINOPS[op_type](
            _safe_eval_node(node.left, g, l),
            _safe_eval_node(node.right, g, l))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_UNARYOPS:
            raise ValueError(f"Unary op {op_type.__name__} not allowed")
        return _SAFE_UNARYOPS[op_type](_safe_eval_node(node.operand, g, l))
    if isinstance(node, ast.Name):
        n = node.id
        if l and n in l:
            return l[n]
        if g and n in g:
            return g[n]
        if n in _SAFE_CONSTS:
            return _SAFE_CONSTS[n]
        if n in _SAFE_FUNCS:
            return _SAFE_FUNCS[n]
        raise ValueError(f"Name '{n}' not allowed")
    if isinstance(node, ast.Attribute):
        obj = _safe_eval_node(node.value, g, l)
        if obj is math and node.attr in _MATH_ALLOWED:
            return getattr(math, node.attr)
        raise ValueError(f"Attribute '{node.attr}' not allowed")
    if isinstance(node, ast.Call):
        func = _safe_eval_node(node.func, g, l)
        if not callable(func):
            raise ValueError("Not callable")
        allowed = (func in _SAFE_FUNCS.values() or
                   (getattr(func, '__module__', None) == 'math'
                    and getattr(func, '__name__', '') in _MATH_ALLOWED))
        if not allowed:
            raise ValueError("Function not in whitelist")
        if node.keywords:
            raise ValueError("Keyword args not allowed")
        args = [_safe_eval_node(a, g, l) for a in node.args]
        return func(*args)
    if isinstance(node, ast.Tuple):
        return tuple(_safe_eval_node(e, g, l) for e in node.elts)
    if isinstance(node, ast.List):
        return [_safe_eval_node(e, g, l) for e in node.elts]
    if isinstance(node, ast.Compare):
        left = _safe_eval_node(node.left, g, l)
        for op_node, comp in zip(node.ops, node.comparators):
            right = _safe_eval_node(comp, g, l)
            ok = {
                ast.Eq: _op.eq, ast.NotEq: _op.ne, ast.Lt: _op.lt,
                ast.LtE: _op.le, ast.Gt: _op.gt, ast.GtE: _op.ge,
                ast.Is: _op.is_, ast.IsNot: _op.is_not,
                ast.In: lambda a, b: a in b,
                ast.NotIn: lambda a, b: a not in b,
            }.get(type(op_node))
            if ok is None:
                raise ValueError("Compare op not allowed")
            if not ok(left, right):
                return False
            left = right
        return True
    raise ValueError(f"Node {type(node).__name__} not allowed")


def safe_eval(expr, globals_dict=None, locals_dict=None):
    try:
        tree = ast.parse(str(expr).strip(), mode='eval')
    except SyntaxError as e:
        raise ValueError(f"Syntax error: {e.msg}")
    g = globals_dict if isinstance(globals_dict, dict) else {}
    l = locals_dict if isinstance(locals_dict, dict) else {}
    return _safe_eval_node(tree, g, l)


# ═══════════════════════════════════════════════════════════════
#  AST SECURITY VALIDATOR
# ═══════════════════════════════════════════════════════════════
class X4SecurityError(Exception):
    pass


class X4ASTValidator(ast.NodeVisitor):
    FORBIDDEN_NODES = (
        ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal,
        ast.ClassDef, ast.AsyncFunctionDef, ast.Await,
        ast.AsyncFor, ast.AsyncWith,
    )
    FORBIDDEN_NAMES = {
        '__builtins__', '__import__', '__loader__', '__spec__',
        '__package__', '__name__', '__file__', '__doc__', '__cached__',
        'exec', 'compile', 'open',
        'globals', 'locals', 'vars', 'dir',
        'getattr', 'setattr', 'delattr', 'hasattr',
        'breakpoint', 'memoryview', 'super',
        'classmethod', 'staticmethod', 'property',
        'object', 'exit', 'quit', 'help',
        'copyright', 'credits', 'license',
    }
    FORBIDDEN_METHODS = {'format', 'format_map', 'mro'}

    def __init__(self):
        self.errors = []

    def _err(self, node, msg):
        self.errors.append(f"строка {getattr(node, 'lineno', '?')}: {msg}")

    def visit(self, node):
        if isinstance(node, self.FORBIDDEN_NODES):
            self._err(node, f"конструкция {type(node).__name__} запрещена")
        super().visit(node)

    def visit_Name(self, node):
        if node.id in self.FORBIDDEN_NAMES:
            self._err(node, f"имя '{node.id}' запрещено")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        a = node.attr
        if a.startswith('_'):
            self._err(node, f"доступ к '{a}' запрещён (dunder)")
        elif a in self.FORBIDDEN_METHODS:
            self._err(node, f"метод '{a}' запрещён")
        self.generic_visit(node)

    def validate(self, code: str):
        try:
            tree = ast.parse(code, mode='exec')
        except SyntaxError as e:
            self.errors.append(f"синтаксис: {e.msg}")
            return False, self.errors
        self.visit(tree)
        return len(self.errors) == 0, self.errors


# ═══════════════════════════════════════════════════════════════
#  КОДИРОВКА / ЦВЕТА
# ═══════════════════════════════════════════════════════════════
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


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
    B = '\033[1m' if UC else ''
    DIM = '\033[2m' if UC else ''
    R = '\033[91m' if UC else ''
    G = '\033[92m' if UC else ''
    Y = '\033[93m' if UC else ''
    BL = '\033[94m' if UC else ''
    M = '\033[95m' if UC else ''
    CY = '\033[96m' if UC else ''
    W = '\033[97m' if UC else ''

    @staticmethod
    def c(t, color):
        return f"{color}{t}{C.RST}" if UC else str(t)


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


# ═══════════════════════════════════════════════════════════════
#  УНИФИЦИРОВАННЫЙ .pyos ФАЙЛ (ХЕШ, СОЛЬ, ХОСТ, ВЕРСИЯ)
# ═══════════════════════════════════════════════════════════════
def get_script_path():
    try:
        p = Path(sys.argv[0] if sys.argv[0] else __file__).resolve()
        if p.is_file():
            return p
    except (OSError, PermissionError):
        pass
    return Path(__file__).resolve()


def _pyos_meta_file(sp):
    return sp.parent / '.pyos'


def _load_pyos_meta(sp) -> dict:
    mf = _pyos_meta_file(sp)
    if mf.exists():
        try:
            return json.loads(mf.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_pyos_meta(sp, data: dict):
    mf = _pyos_meta_file(sp)
    try:
        current = _load_pyos_meta(sp)
        current.update(data)
        mf.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding='utf-8')
        return True
    except (OSError, PermissionError):
        return False


def _load_or_create_salt(sp) -> bytes:
    meta = _load_pyos_meta(sp)
    if 'salt' in meta:
        try:
            s = bytes.fromhex(meta['salt'])
            if len(s) >= 8:
                return s
        except (ValueError, TypeError):
            pass
    salt = secrets.token_bytes(16)
    _save_pyos_meta(sp, {'salt': salt.hex()})
    return salt


def compute_file_hash(filepath) -> str:
    try:
        p = Path(filepath)
        if not p.is_file():
            return ""
        salt = _load_or_create_salt(p)
        return argon2id_hash_bytes(p.read_bytes(), salt)
    except (OSError, PermissionError):
        return ""


def save_code_hash(sp, cur_hash=None, version='19.1', build='18.10.2026'):
    if cur_hash is None:
        cur_hash = compute_file_hash(sp)
    _save_pyos_meta(sp, {
        'hash': cur_hash,
        'algorithm': 'Argon2id+salt',
        'version': version,
        'build': build,
        'filename': sp.name,
        'updated': datetime.datetime.now().isoformat()
    })
    return True


# ═══════════════════════════════════════════════════════════════
#  EMERGENCY DUMP
# ═══════════════════════════════════════════════════════════════
def emergency_dump_logs(reason, details=""):
    try:
        lf = Path("logs.txt").resolve()
        now = datetime.datetime.now().isoformat()
        content = [
            "=== PYOS EMERGENCY CRASH DUMP ===",
            f"Timestamp: {now}", f"Platform: {sys.platform}",
            f"Python: {sys.version}", f"Reason: {reason}",
            f"Details: {details}", "Callstack:",
            tb_module.format_exc(), "=" * 35]
        lf.write_text('\n'.join(content), encoding='utf-8')
    except (OSError, PermissionError):
        pass


# ═══════════════════════════════════════════════════════════════
#  BACKUP (tar-slip fix)
# ═══════════════════════════════════════════════════════════════
def _safe_join(base: Path, rel: str) -> Path:
    base_r = base.resolve()
    out = (base_r / rel).resolve()
    if not str(out).startswith(str(base_r) + os.sep) and out != base_r:
        raise ValueError(f"tar-slip: {rel}")
    return out


class BackupManager:
    @staticmethod
    def get_backup_dir():
        bdir = get_script_path().parent / 'backups'
        bdir.mkdir(parents=True, exist_ok=True)
        return bdir

    @classmethod
    def create_backup(cls, name=None, kernel=None):
        bdir = cls.get_backup_dir()
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', name) if name else f"pyos_backup_{ts}"
        if not clean.endswith('.backup'):
            clean += '.backup'
        bp = bdir / clean
        sp = get_script_path()
        manifest = {'created': datetime.datetime.now().isoformat(),
                    'version': kernel.VERSION if kernel else '19.1',
                    'build': kernel.BUILD if kernel else '18.10.2026',
                    'script_name': sp.name,
                    'script_hash': compute_file_hash(sp),
                    'hash_type': 'Argon2id+salt',
                    'hostname': kernel.hostname if kernel else 'pyos'}
        try:
            with open(bp, 'wb') as f_out:
                with lzma.open(f_out, 'wb', preset=9 | lzma.PRESET_EXTREME) as xz_out:
                    with tarfile.open(fileobj=xz_out, mode='w') as tar:
                        tar.add(sp, arcname='pyos_source.py')
                        mb = json.dumps(manifest, indent=2, ensure_ascii=False).encode('utf-8')
                        ti = tarfile.TarInfo(name='manifest.json')
                        ti.size = len(mb); ti.mtime = int(time.time())
                        tar.addfile(ti, io.BytesIO(mb))
                        hn = kernel.hostname if kernel else 'pyos'
                        base_p = Path(kernel.base_path) if kernel else sp.parent
                        hdir = (base_p / hn).resolve()
                        if hdir.exists():
                            tar.add(hdir, arcname='data')
            return True, bp
        except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError) as e:
            if bp.exists():
                try:
                    bp.unlink()
                except OSError:
                    pass
            return False, str(e)

    @classmethod
    def verify_backup(cls, bp):
        bp = Path(bp)
        if not bp.is_file():
            return False, "File not found", None
        try:
            with open(bp, 'rb') as f_in:
                with lzma.open(f_in, 'rb') as xz_in:
                    with tarfile.open(fileobj=xz_in, mode='r') as tar:
                        mm = tar.extractfile('manifest.json')
                        if not mm:
                            return False, "Manifest missing", None
                        manifest = json.loads(mm.read().decode('utf-8'))
                        sm = tar.extractfile('pyos_source.py')
                        if not sm:
                            return False, "Source missing", None
                        code = sm.read()
                        salt = _load_or_create_salt(get_script_path())
                        actual = argon2id_hash_bytes(code, salt)
                        if manifest.get('script_hash') and actual != manifest.get('script_hash'):
                            return False, "Hash mismatch", None
                        compile(code, 'pyos_source.py', 'exec')
                        return True, "Valid", manifest
        except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError,
                json.JSONDecodeError, SyntaxError) as e:
            return False, str(e), None

    @classmethod
    def list_backups(cls):
        bdir = cls.get_backup_dir()
        result = []
        if not bdir.exists():
            return result
        for f in sorted(bdir.glob('*.backup'),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                sz = f.stat().st_size
                mt = datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                v, err, mf = cls.verify_backup(f)
                result.append({'name': f.name, 'path': f, 'size': sz,
                               'time': mt, 'valid': v, 'error': err, 'manifest': mf})
            except (OSError, PermissionError):
                pass
        return result

    @classmethod
    def get_valid_backups(cls):
        return [b for b in cls.list_backups() if b['valid']]

    @classmethod
    def restore_backup(cls, bp, kernel=None):
        bp = Path(bp)
        v, err, manifest = cls.verify_backup(bp)
        if not v:
            return False, f"Повреждённая копия: {err}"
        sp = get_script_path()
        try:
            with open(bp, 'rb') as f_in:
                with lzma.open(f_in, 'rb') as xz_in:
                    with tarfile.open(fileobj=xz_in, mode='r') as tar:
                        sm = tar.extractfile('pyos_source.py')
                        if sm:
                            cb = sm.read()
                            with open(sp, 'wb') as f:
                                f.write(cb)
                            save_code_hash(sp)
                        hn = (manifest or {}).get('hostname',
                                                   kernel.hostname if kernel else 'pyos')
                        db = Path(kernel.base_path) if kernel else sp.parent
                        thd = (db / hn).resolve()
                        thd.mkdir(parents=True, exist_ok=True)
                        for m in tar.getmembers():
                            if not m.name.startswith('data/'):
                                continue
                            rel = m.name[5:]
                            if not rel:
                                continue
                            try:
                                outp = _safe_join(thd, rel)
                            except ValueError:
                                continue
                            if m.isdir():
                                outp.mkdir(parents=True, exist_ok=True)
                            elif m.isfile():
                                outp.parent.mkdir(parents=True, exist_ok=True)
                                ef = tar.extractfile(m)
                                if ef:
                                    outp.write_bytes(ef.read())
            return True, "Восстановление успешно"
        except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError) as e:
            return False, str(e)


def handle_repair_or_dead_end(reason):
    emergency_dump_logs(reason)
    valid = BackupManager.get_valid_backups()
    if not valid:
        print()
        print(C.c("Код и бэкапы повреждены/отсутствуют", C.R + C.B))
        try:
            input("\nEnter для выхода...")
        except (EOFError, KeyboardInterrupt):
            pass
        sys.exit(1)
    print()
    print(C.c("Код повреждён", C.Y + C.B))
    try:
        input("\nEnter для восстановления...")
    except (EOFError, KeyboardInterrupt):
        sys.exit(1)
    for idx, b in enumerate(valid, 1):
        print(f"  {idx}. {b['name']:<35} {b['size']/1024:>7.1f} KB | {b['time'][:19]}")
    choice = 0
    while choice < 1 or choice > len(valid):
        try:
            choice = int(input(f"  Выбор (1-{len(valid)}): ").strip())
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
    sel = valid[choice - 1]['path']
    ok, msg = BackupManager.restore_backup(sel)
    if ok:
        print(C.c("  Восстановлено. Перезапуск...\n", C.G))
        time.sleep(1.0)
        sp = get_script_path()
        os.execv(sys.executable, [sys.executable, str(sp)] + sys.argv[1:])
    else:
        print(C.c(f"  Ошибка: {msg}", C.R))
        sys.exit(1)


def verify_pyos_integrity():
    sp = get_script_path()
    if not sp.exists() or sp.stat().st_size == 0:
        handle_repair_or_dead_end("source missing")
    try:
        compile(sp.read_bytes(), str(sp), 'exec')
    except (SyntaxError, ValueError) as e:
        handle_repair_or_dead_end(f"source corrupted: {e}")
    meta = _load_pyos_meta(sp)
    saved = meta.get('hash', '')
    cur = compute_file_hash(sp)
    if not saved:
        save_code_hash(sp, cur)
        return True
    if cur == saved:
        return True
    print()
    print(C.c("  Код изменён (Argon2id mismatch)", C.Y + C.B))
    print(C.c("  Ввели вы — '1', нет — '2'", C.W))
    choice = ''
    while choice not in ('1', '2'):
        try:
            choice = input(C.c("  > ", C.W)).strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
    if choice == '1':
        save_code_hash(sp, cur)
        print(C.c("  Хеш обновлён\n", C.G))
        time.sleep(0.3)
        return True
    handle_repair_or_dead_end("unauthorized modification")
    return False


# ═══════════════════════════════════════════════════════════════
#  UNIFIED DIFF
# ═══════════════════════════════════════════════════════════════
def apply_unified_diff(source_text, patch_text):
    src = source_text.splitlines(keepends=True)
    pl = patch_text.splitlines(keepends=True)
    hunks = []
    i = 0
    while i < len(pl):
        line = pl[i]
        if line.startswith('@@'):
            m = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if not m:
                i += 1
                continue
            os_, oc = int(m.group(1)), int(m.group(2)) if m.group(2) else 1
            ns, nc = int(m.group(3)), int(m.group(4)) if m.group(4) else 1
            i += 1
            body = []
            while i < len(pl):
                l = pl[i]
                if l.startswith('@@'):
                    break
                if l.startswith(('---', '+++')):
                    i += 1
                    continue
                if l.startswith((' ', '+', '-')):
                    body.append(l)
                elif l.strip() == '':
                    body.append(' \n')
                i += 1
            hunks.append((os_, oc, ns, nc, body))
        else:
            i += 1
    if not hunks:
        raise ValueError("Не найдено ни одного @@ ... @@")
    result = list(src)
    for os_, oc, ns, nc, body in reversed(hunks):
        idx = os_ - 1
        new_lines = []
        consumed = 0
        produced = 0
        for bl in body:
            p = bl[0] if bl else ' '
            content = bl[1:] if len(bl) > 1 else ''
            if p == ' ':
                new_lines.append(content); consumed += 1; produced += 1
            elif p == '-':
                consumed += 1
            elif p == '+':
                new_lines.append(content); produced += 1
        if consumed != oc:
            raise ValueError(f"Удаляемых: {consumed} != {oc}")
        if produced != nc:
            raise ValueError(f"Добавляемых: {produced} != {nc}")
        result[idx:idx + consumed] = new_lines
    return ''.join(result)


# ═══════════════════════════════════════════════════════════════
#  UI / BSOD
# ═══════════════════════════════════════════════════════════════
class SimpleBox:
    @staticmethod
    def header(title, width=50, char='='):
        line = char * width
        return f"{line}\n  {title}\n{line}"

    @staticmethod
    def box(text, width=50, char='*'):
        line = char * width
        return f"{line}\n{text}\n{line}"


class BSOD:
    @staticmethod
    def show(code='CRITICAL_DATA_DESTROYED', msg='System data destroyed.', details=''):
        clear()
        w = 60
        print('=' * w)
        print('  :(')
        print(f'  Error: {code}')
        print(f'  {msg}')
        if details:
            print(f'  {details}')
        print('=' * w)
        print('  Press Enter to restart...')

    @staticmethod
    def crash_and_restart(code, msg, details=''):
        BSOD.show(code, msg, details)
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        return True


# ═══════════════════════════════════════════════════════════════
#  ФОНОВЫЕ СЛУЖБЫ
# ═══════════════════════════════════════════════════════════════
class FSHealthChecker:
    def __init__(self, fs, kernel):
        self.fs = fs
        self.kernel = kernel
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def check_now(self):
        return bool(self.fs and self.fs.hostname_dir and self.fs.hostname_dir.exists())

    def _loop(self):
        while self._running:
            time.sleep(2.5)
            if not self._running:
                break
            if not self.check_now():
                self._running = False
                self.kernel.trigger_bsod(
                    'CRITICAL_DATA_DESTROYED',
                    'System data folder deleted.',
                    f'Missing: {self.fs.hostname_dir if self.fs else "?"}')
                self.kernel.running = False
                return


class NotificationCenter:
    def __init__(self):
        self.notifications = []
        self._next_id = 1
        self._lock = threading.Lock()

    def send(self, source, title, message, icon='info', priority='normal'):
        with self._lock:
            n = {'id': self._next_id, 'source': source, 'title': title,
                 'message': message, 'icon': icon, 'priority': priority,
                 'time': datetime.datetime.now().isoformat(), 'read': False}
            self._next_id += 1
            self.notifications.append(n)
        return n['id']

    def get_unread(self):
        with self._lock:
            return [n for n in self.notifications if not n['read']]

    def get_all(self):
        with self._lock:
            return list(self.notifications)

    def count_unread(self):
        with self._lock:
            return sum(1 for n in self.notifications if not n['read'])

    def mark_read(self, nid=None):
        with self._lock:
            if nid is None:
                for n in self.notifications:
                    n['read'] = True
            else:
                for n in self.notifications:
                    if n['id'] == nid:
                        n['read'] = True
                        break

    def delete(self, nid=None):
        with self._lock:
            if nid is None:
                self.notifications.clear()
                return True
            b = len(self.notifications)
            self.notifications = [n for n in self.notifications if n['id'] != nid]
            return len(self.notifications) < b

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
        c = self.count_unread()
        if c == 0:
            return C.c("[0]", C.DIM)
        if c <= 3:
            return C.c(f"[{c}]", C.Y)
        return C.c(f"[{c}!]", C.R + C.B)

    def format_panel(self, max_show=5):
        unread = self.get_unread()
        if not unread:
            return None
        lines = [C.c(f"  [Notifications ({len(unread)} new)]", C.Y + C.B)]
        shown = unread[-max_show:]
        if len(unread) > max_show:
            lines.append(C.c(f"  ... and {len(unread)-max_show} more", C.DIM))
        for n in shown:
            ico = {'info': '*', 'warn': '!', 'err': 'X',
                   'ok': '+', 'app': '#', 'timer': '@'}.get(n['icon'], '?')
            lines.append(f"  {ico} [{n['source'][:10]}] {n['title'][:25]}")
            if n['message']:
                lines.append(f"     {C.c(n['message'][:35], C.DIM)}")
        return '\n'.join(lines)


class TimerService:
    def __init__(self, notifications):
        self.notifications = notifications
        self.timers = []
        self._lock = threading.Lock()
        self._next_id = 1
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
        with self._lock:
            tid = self._next_id
            self._next_id += 1
            end = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            self.timers.append({'id': tid, 'label': label, 'seconds': seconds,
                                'end_time': end, 'fired': False})
        self.start()
        return tid

    def cancel_timer(self, tid):
        with self._lock:
            b = len(self.timers)
            self.timers = [t for t in self.timers if t['id'] != tid]
            return len(self.timers) < b

    def get_active(self):
        with self._lock:
            now = datetime.datetime.now()
            return [t for t in self.timers if not t['fired'] and t['end_time'] > now]

    def get_all(self):
        with self._lock:
            return list(self.timers)

    def _run(self):
        while self._running:
            now = datetime.datetime.now()
            fired = []
            with self._lock:
                for t in self.timers:
                    if not t['fired'] and now >= t['end_time']:
                        t['fired'] = True
                        fired.append(t)
                self.timers = [t for t in self.timers
                               if not t['fired'] or
                               t['end_time'] > now - datetime.timedelta(seconds=30)]
            for t in fired:
                self.notifications.send(
                    source='timer', title=f"Timer: {t['label']}",
                    message=f"Finished ({t['seconds']}s)",
                    icon='timer', priority='high')
            time.sleep(0.5)

    def cleanup(self):
        with self._lock:
            self.timers = [t for t in self.timers if not t['fired']]

    def to_dict(self):
        with self._lock:
            res = [{'id': t['id'], 'label': t['label'], 'seconds': t['seconds'],
                    'end_time': t['end_time'].isoformat(), 'fired': t['fired']}
                   for t in self.timers]
            return {'timers': res, 'next_id': self._next_id}

    def from_dict(self, data):
        with self._lock:
            self._next_id = data.get('next_id', 1)
            self.timers = []
            now = datetime.datetime.now()
            for t in data.get('timers', []):
                try:
                    end = datetime.datetime.fromisoformat(t['end_time'])
                    if end > now and not t.get('fired', False):
                        self.timers.append({'id': t['id'], 'label': t['label'],
                                            'seconds': t['seconds'],
                                            'end_time': end, 'fired': False})
                except (ValueError, KeyError):
                    pass
        if any(not t['fired'] for t in self.timers):
            self.start()


class AppBackgroundManager:
    def __init__(self, notifications):
        self.notifications = notifications
        self.background_apps = {}
        self._lock = threading.Lock()

    def register(self, name, info=None):
        with self._lock:
            self.background_apps[name] = {
                'name': name, 'info': info or {},
                'registered': datetime.datetime.now().isoformat(), 'running': True}

    def unregister(self, name):
        with self._lock:
            if name in self.background_apps:
                del self.background_apps[name]
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


# ═══════════════════════════════════════════════════════════════
#  REAL FS (права)
# ═══════════════════════════════════════════════════════════════
class RealFS:
    def __init__(self, base_path):
        self.base = Path(base_path).resolve()
        self.hostname_dir = None
        self.current_disk = 'C'

    def _check_access(self, vpath, is_write):
        level = PermissionContext.get()
        if level == Perm.ROOT:
            return True
        vp = vpath if vpath.startswith('/') else '/' + vpath
        user = PermissionContext.user()
        app = PermissionContext.app()
        if level == Perm.USER:
            if vp == '/sysdata' or vp.startswith('/sysdata/'):
                return False
            if is_write and (vp == '/apps/installed' or vp.startswith('/apps/installed/')):
                return False
            if vp.startswith('/home/'):
                parts = vp.split('/')
                if len(parts) >= 3 and parts[2] and user and parts[2] != user:
                    return False
            return True
        if level == Perm.PROGRAM:
            if not app:
                return False
            own = f'/apps/data/{app}'
            if vp == own or vp.startswith(own + '/'):
                return True
            if vp.startswith('/cache/'):
                parts = vp.split('/')
                if len(parts) >= 3 and parts[2].startswith(app + '_'):
                    return True
            return False
        return False

    def _resolve_checked(self, path, cwd, write=False):
        vp, disk = self.resolve(path, cwd)
        explicit, _ = self.parse_disk_prefix(path)
        if explicit:
            disk = explicit
        if not self._check_access(vp, write):
            raise PermissionError(f"Access denied: {disk}:{vp}")
        rp, disk2 = self.to_real_path(path, cwd)
        return rp, disk2

    def init_structure(self, hostname):
        self.hostname_dir = (self.base / hostname).resolve()
        self.hostname_dir.mkdir(parents=True, exist_ok=True)
        self.create_disk('C')
        self.current_disk = 'C'
        for d in ['home', 'sysdata', 'sysdata/trash', 'cache',
                  'cache/deleted_apps', 'cache/trash_archives',
                  'apps', 'apps/installed', 'apps/data', 'apps/store', 'apps/logs']:
            self.get_disk_path('C', d).mkdir(parents=True, exist_ok=True)

    def create_disk(self, name):
        if self.hostname_dir:
            (self.hostname_dir / name.upper()).mkdir(parents=True, exist_ok=True)

    def get_disk_path(self, disk, rel=''):
        if not self.hostname_dir:
            return self.base / disk.upper()
        p = self.hostname_dir / disk.upper()
        if rel:
            p = p / rel.lstrip('/')
        return p

    def parse_disk_prefix(self, path):
        if len(path) >= 2 and path[1] == ':' and path[0].isalpha():
            d = path[0].upper()
            if self.hostname_dir and (self.hostname_dir / d).exists():
                return d, path[2:] or '/'
        return None, path

    def to_real_path(self, vpath, cwd='/', disk_override=None):
        disk = disk_override or self.current_disk
        explicit, vpath = self.parse_disk_prefix(vpath)
        if explicit:
            disk = explicit
        if not vpath.startswith('/'):
            vpath = cwd.rstrip('/') + '/' + vpath
        parts = []
        for p in vpath.split('/'):
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
        r = '/' + '/'.join(parts)
        return (r, explicit) if explicit else (r, None)

    def exists(self, path, cwd='/'):
        try:
            rp, _ = self._resolve_checked(path, cwd, write=False)
            return rp.exists()
        except (OSError, PermissionError):
            return False

    def is_dir(self, path, cwd='/'):
        try:
            rp, _ = self._resolve_checked(path, cwd, write=False)
            return rp.is_dir()
        except (OSError, PermissionError):
            return False

    def is_file(self, path, cwd='/'):
        try:
            rp, _ = self._resolve_checked(path, cwd, write=False)
            return rp.is_file()
        except (OSError, PermissionError):
            return False

    def mkdir(self, path, cwd='/'):
        try:
            rp, _ = self._resolve_checked(path, cwd, write=True)
            rp.mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False

    def write_file(self, path, content, cwd='/', append=False):
        try:
            rp, _ = self._resolve_checked(path, cwd, write=True)
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
            rp, _ = self._resolve_checked(path, cwd, write=True)
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_bytes(data)
            return True
        except (OSError, PermissionError):
            return False

    def read_file(self, path, cwd='/'):
        try:
            rp, _ = self._resolve_checked(path, cwd, write=False)
            if not rp.is_file():
                return None
            return rp.read_text(encoding='utf-8')
        except (OSError, PermissionError, UnicodeDecodeError):
            return None

    def read_bytes(self, path, cwd='/'):
        try:
            rp, _ = self._resolve_checked(path, cwd, write=False)
            if not rp.is_file():
                return None
            return rp.read_bytes()
        except (OSError, PermissionError):
            return None

    def delete(self, path, cwd='/', recursive=False):
        try:
            rp, disk = self._resolve_checked(path, cwd, write=True)
            if not self.hostname_dir:
                return False
            if rp in (self.hostname_dir, self.base, self.get_disk_path(disk)):
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
            sr, _ = self._resolve_checked(src, cwd, write=False)
            dr, _ = self._resolve_checked(dst, cwd, write=True)
            if not sr.exists():
                return False
            if sr.is_file():
                dr.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sr, dr)
            else:
                dr.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(sr, dr, dirs_exist_ok=True)
            return True
        except (OSError, PermissionError, shutil.Error):
            return False

    def move(self, src, dst, cwd='/'):
        try:
            sr, _ = self._resolve_checked(src, cwd, write=True)
            dr, _ = self._resolve_checked(dst, cwd, write=True)
            if not sr.exists():
                return False
            dr.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(sr), str(dr))
            return True
        except (OSError, PermissionError, shutil.Error):
            return False

    def rename(self, src, new_name, cwd='/'):
        try:
            sr, _ = self._resolve_checked(src, cwd, write=True)
            if not sr.exists():
                return False
            sr.rename(sr.parent / new_name)
            return True
        except (OSError, PermissionError):
            return False

    def list_dir(self, path, cwd='/'):
        try:
            rp, _ = self._resolve_checked(path, cwd, write=False)
            if not rp.is_dir():
                return None
            items = []
            for e in sorted(rp.iterdir(),
                            key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    st = e.stat()
                    is_d = e.is_dir()
                    items.append({'name': e.name, 'is_dir': is_d,
                                  'size': 0 if is_d else st.st_size,
                                  'modified': datetime.datetime.fromtimestamp(
                                      st.st_mtime).isoformat()})
                except (OSError, PermissionError, FileNotFoundError):
                    continue
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
            rp, _ = self._resolve_checked(path, cwd, write=False)
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
            rp, _ = self._resolve_checked(path, cwd, write=True)
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
        try:
            rp, _ = self._resolve_checked(path, cwd, write=False)
        except PermissionError:
            return "Access denied"
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
        elif path.name.lower().endswith('.x3'):
            col = C.Y + C.B
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
                items = sorted(path.iterdir(),
                               key=lambda x: (not x.is_dir(), x.name.lower()))
                for i, ch in enumerate(items):
                    np = prefix + ('' if is_root else ('    ' if is_last else '│   '))
                    self._tree_r(ch, lines, np, i == len(items) - 1,
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
                    fp = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(fp)
                        rel = os.path.relpath(fp, dp).replace('\\', '/')
                        files.append({'path': '/' + rel, 'size': sz, 'name': f})
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass
        files.sort(key=lambda x: x['size'], reverse=True)
        return files

    def dir_size_at(self, path, cwd='/'):
        try:
            rp, _ = self._resolve_checked(path, cwd, write=False)
        except PermissionError:
            return 0
        return self._dir_size(rp) if rp.exists() and rp.is_dir() else 0


# ═══════════════════════════════════════════════════════════════
#  X3 AUTOMATION RUNNER (Thread-safe Call Depth & Argument Handling)
# ═══════════════════════════════════════════════════════════════
class X3Runner:
    MAX_RECURSION = 10
    _local_state = threading.local()

    @classmethod
    def _get_depth(cls):
        if not hasattr(cls._local_state, 'depth'):
            cls._local_state.depth = 0
        return cls._local_state.depth

    @classmethod
    def _set_depth(cls, val):
        cls._local_state.depth = val

    @classmethod
    def execute_file(cls, shell, filepath, args=None, fast_mode=False):
        current_depth = cls._get_depth()
        if current_depth >= cls.MAX_RECURSION:
            print(C.c(f"  [X3] Превышен лимит рекурсивного вызова скриптов ({cls.MAX_RECURSION})!", C.R + C.B))
            return False

        args = args or []
        content = shell.kernel.fs.read_file(filepath, shell.cwd)
        if not content:
            if not filepath.endswith('.x3'):
                content = shell.kernel.fs.read_file(filepath + '.x3', shell.cwd)
                if content:
                    filepath = filepath + '.x3'
        if not content:
            docs = f"/home/{shell.user}/Documents/{filepath}"
            content = shell.kernel.fs.read_file(docs, shell.cwd)
            if not content and not filepath.endswith('.x3'):
                content = shell.kernel.fs.read_file(docs + '.x3', shell.cwd)
        
        if not content:
            print(C.c(f"  [X3] Файл автоматизации '{filepath}' не найден.", C.R))
            return False

        cls._set_depth(current_depth + 1)
        speed = shell.kernel.settings.x3_speed.lower()
        is_fast = fast_mode or (speed == 'fast')

        print(C.c(f"  ┌── [X3 Automation] Запуск: {filepath} ({'быстрый режим' if is_fast else 'нормальный'})", C.CY + C.B))
        lines = content.splitlines()

        try:
            for raw_line in lines:
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Подстановка аргументов с возможностью числовой интерпретации
                for idx, arg in enumerate(args, 1):
                    line = line.replace(f'${idx}', arg)
                line = line.replace('$@', ' '.join(args))

                print(shell._prompt() + C.c(line, C.W + C.B))
                if not is_fast:
                    time.sleep(0.35)
                
                if line.lower() in ('exit', 'quit', 'q'):
                    print(C.c("  [X3] Скрипт завершен по команде выхода.", C.Y))
                    break
                try:
                    shell._exec(line)
                except Exception as e:
                    print(C.c(f"  [X3 Ошибка выполнения] {e}", C.R))
                
                if not is_fast:
                    time.sleep(0.15)
        finally:
            cls._set_depth(cls._get_depth() - 1)

        print(C.c(f"  └── [X3 Automation] Скрипт успешно выполнен.", C.CY + C.B))
        return True

    @staticmethod
    def template(name):
        return f"""# PyOS X3 Automation Script: {name}
# Строки, начинающиеся с #, являются комментариями.
# Вы можете использовать аргументы $1, $2, $@ и переменную $USER.

echo "=== Автоматический запуск скрипта {name} ==="
echo "Пользователь: $USER"
echo "Аргументы: $@"
pwd
help
echo "=== Автоматизация завершена успешно ==="
"""


# ═══════════════════════════════════════════════════════════════
#  КОРЗИНА
# ═══════════════════════════════════════════════════════════════
class TrashManager:
    def __init__(self, fs, guardian):
        self.fs = fs
        self.guardian = guardian
        self.index_path = '/sysdata/trash_index.json'
        self.trash_dir = '/sysdata/trash'
        self._lock = threading.Lock()

    def _load_index(self):
        with perm_root():
            content = self.fs.read_file(self.index_path)
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
        return {'items': [], 'next_id': 1}

    def _save_index(self, data):
        with perm_root():
            self.fs.write_file(self.index_path,
                               json.dumps(data, indent=2, ensure_ascii=False))

    def _safe_orig(self, orig_path, disk):
        if not orig_path.startswith('/'):
            return None
        parts = []
        for p in orig_path.split('/'):
            if p in ('', '.'):
                continue
            if p == '..':
                if parts:
                    parts.pop()
                else:
                    return None
            else:
                parts.append(p)
        if parts and parts[0] == 'sysdata':
            return None
        return '/' + '/'.join(parts)

    def put(self, vpath, cwd='/'):
        with self._lock:
            resolved, _ = self.fs.resolve(vpath, cwd)
            try:
                rs, du = self.fs._resolve_checked(vpath, cwd, write=True)
            except PermissionError:
                return False, "Доступ запрещён"
            if not rs.exists():
                return False, "Не найдено"
            if rs in (self.fs.hostname_dir, self.fs.base):
                return False, "Системный корень нельзя"
            data = self._load_index()
            iid = data.get('next_id', 1)
            data['next_id'] = iid + 1
            is_dir = rs.is_dir()
            sz = self.fs.dir_size_at(vpath, cwd) if is_dir else rs.stat().st_size
            tfn = f"{iid}_{rs.name}"
            tvp = f"{self.trash_dir}/{tfn}"
            with perm_root():
                self.fs.mkdir(self.trash_dir)
                rd, _ = self.fs.to_real_path(tvp)
            try:
                shutil.move(str(rs), str(rd))
            except (OSError, PermissionError, shutil.Error) as e:
                return False, f"Ошибка: {e}"
            entry = {'id': iid, 'name': rs.name, 'orig_path': resolved,
                     'disk': du, 'size': sz, 'is_dir': is_dir,
                     'trash_name': tfn,
                     'deleted_at': datetime.datetime.now().isoformat()}
            data['items'].append(entry)
            self._save_index(data)
            return True, f"'{rs.name}' → Корзина [ID #{iid}]"

    def list_items(self):
        with self._lock:
            return self._load_index().get('items', [])

    def restore(self, tid):
        with self._lock:
            data = self._load_index()
            items = data.get('items', [])
            target = None
            for it in items:
                if str(it['id']) == str(tid) or it['name'] == str(tid):
                    target = it
                    break
            if not target:
                return False, f"'{tid}' не найден"
            safe = self._safe_orig(target.get('orig_path', ''), target.get('disk', 'C'))
            if safe is None:
                return False, "Некорректный orig_path"
            
            od = target.get('disk', self.fs.current_disk)
            try:
                self.fs._resolve_checked(f"{od}:{safe}", '/', write=True)
            except PermissionError:
                return False, f"Доступ запрещён для восстановления в '{od}:{safe}'"

            tvp = f"{self.trash_dir}/{target['trash_name']}"
            with perm_root():
                rt, _ = self.fs.to_real_path(tvp)
            if not rt.exists():
                items.remove(target)
                self._save_index(data)
                return False, "Файл отсутствует"

            rd = self.fs.get_disk_path(od, safe)
            rd.parent.mkdir(parents=True, exist_ok=True)
            if rd.exists():
                return False, f"'{safe}' уже существует"
            try:
                shutil.move(str(rt), str(rd))
            except (OSError, PermissionError, shutil.Error) as e:
                return False, f"Ошибка: {e}"
            items.remove(target)
            self._save_index(data)
            return True, f"'{target['name']}' → {od}:{safe}"

    def delete_single(self, tid):
        with self._lock:
            data = self._load_index()
            items = data.get('items', [])
            target = None
            for it in items:
                if str(it['id']) == str(tid) or it['name'] == str(tid):
                    target = it
                    break
            if not target:
                return False, f"'{tid}' не найден"
            tvp = f"{self.trash_dir}/{target['trash_name']}"
            with perm_root():
                rt, _ = self.fs.to_real_path(tvp)
            if rt.exists():
                try:
                    if rt.is_dir():
                        shutil.rmtree(rt)
                    else:
                        rt.unlink()
                except (OSError, PermissionError) as e:
                    return False, f"Ошибка: {e}"
            items.remove(target)
            self._save_index(data)
            return True, f"'{target['name']}' удалён навсегда"

    def empty(self, compress=True):
        with self._lock:
            data = self._load_index()
            items = data.get('items', [])
            if not items:
                return True, "Корзина пуста"
            ai = ""
            if compress:
                ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                with perm_root():
                    self.fs.mkdir('/cache/trash_archives')
                    avp = f"/cache/trash_archives/trash_dump_{ts}.tar.xz"
                    ra, _ = self.fs.to_real_path(avp)
                    rtd, _ = self.fs.to_real_path(self.trash_dir)
                try:
                    with lzma.open(ra, 'wb', preset=9 | lzma.PRESET_EXTREME) as xz_out:
                        with tarfile.open(fileobj=xz_out, mode='w') as tar:
                            mb = json.dumps(items, indent=2, ensure_ascii=False).encode('utf-8')
                            ti = tarfile.TarInfo(name='manifest.json')
                            ti.size = len(mb); ti.mtime = int(time.time())
                            tar.addfile(ti, io.BytesIO(mb))
                            for it in items:
                                tp = rtd / it['trash_name']
                                if tp.exists():
                                    tar.add(tp, arcname=f"files/{it['name']}")
                    ai = f" (Архив: {avp}, {self.guardian.fmt_size(ra.stat().st_size)})"
                except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError) as e:
                    ai = f" (Ошибка: {e})"
            with perm_root():
                rtd, _ = self.fs.to_real_path(self.trash_dir)
            if rtd.exists():
                try:
                    for ch in rtd.iterdir():
                        if ch.is_dir():
                            shutil.rmtree(ch)
                        else:
                            ch.unlink()
                except (OSError, PermissionError):
                    pass
            cnt = len(items)
            data['items'] = []
            self._save_index(data)
            return True, f"Корзина очищена ({cnt}){ai}"


# ═══════════════════════════════════════════════════════════════
#  USERS
# ═══════════════════════════════════════════════════════════════
class UserManager:
    HIDDEN_FIELDS = {'pw'}

    def __init__(self):
        self.users = {}

    def create(self, name, pw=None, hint=''):
        if name in self.users:
            return False, "User exists"
        ex = [u['uid'] for u in self.users.values()]
        uid = max(ex) + 1 if ex else 0
        has_pw = pw is not None and pw != ''
        self.users[name] = {'pw': ARGON2_HASHER.hash(pw) if has_pw else '',
                            'has_password': has_pw, 'uid': uid,
                            'home': f'/home/{name}', 'hint': hint,
                            'created': datetime.datetime.now().isoformat(),
                            'disk': 'C'}
        return True, ""

    def auth(self, name, pw):
        if name not in self.users:
            return False
        u = self.users[name]
        if not u.get('has_password', True):
            return True
        if not pw:
            return False
        try:
            return ARGON2_HASHER.verify(u['pw'], pw)
        except (VerificationError, VerifyMismatchError):
            return False
        except Exception:
            return False

    def has_password(self, name):
        return self.users.get(name, {}).get('has_password', False)

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


# ═══════════════════════════════════════════════════════════════
#  GUARDIAN & GITHUB INTEGRATION (Caching & Rate-limit Handling)
# ═══════════════════════════════════════════════════════════════
class Guardian:
    GITHUB_RAW_URL = "https://raw.githubusercontent.com/bogdangotj/PYOS/main/pyos.py"
    GITHUB_VER_URL = "https://raw.githubusercontent.com/bogdangotj/PYOS/main/version.json"
    GITHUB_APPS_API_URL = "https://api.github.com/repos/bogdangotj/PYOS/contents/Apps"
    GITHUB_RAW_APPS_BASE = "https://raw.githubusercontent.com/bogdangotj/PYOS/main/Apps"

    def __init__(self):
        self.session_start = datetime.datetime.now()
        self.daily_limit = None
        self.warned_today = False
        self.app_folder_limit = 1 * 1024 * 1024
        self.suggest_commands = True
        self._store_cache = None
        self._store_cache_time = 0.0

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

    def suggest(self, wrong, avail):
        if not self.suggest_commands:
            return []
        return difflib.get_close_matches(wrong, avail, n=3, cutoff=0.4)

    def check_app_folder(self, fs, app):
        cur = fs.dir_size_at(f'/apps/data/{app}')
        ov = cur > self.app_folder_limit if self.app_folder_limit else False
        return cur, self.app_folder_limit, ov

    def cleanup_app_folder(self, fs, app):
        cur, lim, ov = self.check_app_folder(fs, app)
        if not ov:
            return []
        deleted = []
        with perm_root():
            rp, _ = fs.to_real_path(f'/apps/data/{app}')
        if not rp.exists():
            return []
        files = []
        try:
            for root, _, names in os.walk(rp):
                for f in names:
                    p = os.path.join(root, f)
                    try:
                        files.append((p, os.path.getsize(p), f))
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        files.sort(key=lambda x: x[1], reverse=True)
        for fp, fsz, fn in files:
            if cur <= lim:
                break
            try:
                os.remove(fp)
                deleted.append((fn, fsz))
                cur -= fsz
            except (OSError, PermissionError):
                pass
        return deleted

    def check_all_apps(self, fs):
        results = []
        items = fs.list_dir('/apps/data')
        if not items:
            return results
        for it in items:
            if it['is_dir']:
                cur, lim, ov = self.check_app_folder(fs, it['name'])
                results.append({'name': it['name'], 'size': cur, 'limit': lim, 'over': ov})
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

    def parse_patch_package(self, raw):
        raw = raw.strip()
        if not raw.startswith("[BEGIN PYOS PATCH]") or not raw.endswith("[END PYOS PATCH]"):
            return None, "Некорректный заголовок/подвал"
        body = raw[len("[BEGIN PYOS PATCH]"):-len("[END PYOS PATCH]")].strip()
        dm, de = "[BEGIN DIFF]", "[END DIFF]"
        if dm not in body or de not in body:
            return None, "Нет [BEGIN DIFF]"
        hp, rest = body.split(dm, 1)
        dp, _ = rest.split(de, 1)
        bh = th = ""
        lines = hp.strip().split('\n')
        jl = []
        started = False
        for ln in lines:
            s = ln.strip()
            if s.startswith("Base-Hash:"):
                bh = s.split(":", 1)[1].strip()
            elif s.startswith("Target-Hash:"):
                th = s.split(":", 1)[1].strip()
            elif s.startswith("{") or started:
                started = True
                jl.append(ln)
        meta = {}
        if jl:
            try:
                meta = json.loads("\n".join(jl))
            except json.JSONDecodeError:
                pass
        return {'base_hash': bh, 'target_hash': th,
                'meta': meta, 'diff': dp.strip()}, None

    def apply_patch_update(self, patch_content, kernel):
        pkg, err = self.parse_patch_package(patch_content)
        if err:
            return False, f"Разбор: {err}"
        sp = get_script_path()
        cb = sp.read_bytes()
        salt = _load_or_create_salt(sp)
        ch = argon2id_hash_bytes(cb, salt)
        if pkg['base_hash'] and pkg['base_hash'] != ch:
            return False, f"Base-Hash не совпал!\nТекущий: {ch}\nВ патче:  {pkg['base_hash']}"
        try:
            ct = cb.decode('utf-8')
            ut = apply_unified_diff(ct, pkg['diff'])
            compile(ut, 'pyos_patched.py', 'exec')
        except Exception as e:
            return False, f"Ошибка применения/компиляции: {e}"
        ub = ut.encode('utf-8')
        nh = argon2id_hash_bytes(ub, salt)
        if pkg['target_hash'] and pkg['target_hash'] != nh:
            return False, f"Target-Hash не сошёлся!\nПолучен: {nh}\nОжидался: {pkg['target_hash']}"
        BackupManager.create_backup("pre_patch_update", kernel)
        sp.write_bytes(ub)
        nv = pkg['meta'].get('version', kernel.VERSION)
        nb = pkg['meta'].get('build', kernel.BUILD)
        save_code_hash(sp, cur_hash=nh, version=nv, build=nb)
        return True, f"Патч применён! Версия → {nv} (build {nb})"

    def apply_full_code_update(self, new_code, kernel):
        try:
            compile(new_code, 'pyos_new.py', 'exec')
        except SyntaxError as e:
            return False, f"Синтаксис: {e}"
        sp = get_script_path()
        BackupManager.create_backup("pre_full_update", kernel)
        nb = new_code.encode('utf-8')
        sp.write_bytes(nb)
        salt = _load_or_create_salt(sp)
        nh = argon2id_hash_bytes(nb, salt)
        vm = re.search(r'PyOS v(\d+\.\d+)', new_code)
        bm = re.search(r'build (\d+\.\d+\.\d+)', new_code)
        ver = vm.group(1) if vm else kernel.VERSION
        bld = bm.group(1) if bm else kernel.BUILD
        save_code_hash(sp, cur_hash=nh, version=ver, build=bld)
        return True, f"Код обновлён. Хеш: {nh[:16]}..."

    def check_github_update_async(self, current_version, callback):
        def _bg():
            res = self.check_github_update(current_version)
            callback(*res)
        threading.Thread(target=_bg, daemon=True).start()

    def check_github_update(self, current_version):
        try:
            req = urllib.request.Request(self.GITHUB_VER_URL, headers={'User-Agent': 'PyOS-Nexus'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                latest_ver = data.get("version", current_version)
                latest_build = data.get("build", "unknown")
                return True, latest_ver, latest_build
        except Exception:
            try:
                req = urllib.request.Request(self.GITHUB_RAW_URL, headers={'User-Agent': 'PyOS-Nexus'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    code = response.read().decode('utf-8', errors='replace')
                    vm = re.search(r'PyOS v(\d+\.\d+)', code)
                    bm = re.search(r'build (\d+\.\d+\.\d+)', code)
                    ver = vm.group(1) if vm else current_version
                    bld = bm.group(1) if bm else 'unknown'
                    return True, ver, bld
            except Exception as e:
                return False, str(e), ""

    def download_github_code(self):
        try:
            req = urllib.request.Request(self.GITHUB_RAW_URL, headers={'User-Agent': 'PyOS-Nexus'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Ошибка загрузки с GitHub: {e}")

    def fetch_store_apps(self, force_refresh=False):
        """Загрузка списка доступных приложений с GitHub Apps с кэшированием."""
        now = time.time()
        if not force_refresh and self._store_cache and (now - self._store_cache_time < 300):
            return True, self._store_cache
        try:
            req = urllib.request.Request(self.GITHUB_APPS_API_URL, headers={'User-Agent': 'PyOS-Nexus'})
            with urllib.request.urlopen(req, timeout=7) as response:
                items = json.loads(response.read().decode('utf-8'))
            apps = []
            for item in items:
                name = item.get('name', '')
                if item.get('type') in ('file', 'dir') and not name.startswith('.'):
                    apps.append(name)
            self._store_cache = apps
            self._store_cache_time = now
            return True, apps
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return False, "Превышен лимит запросов GitHub API (HTTP 403: Forbidden). Попробуйте позже."
            return False, f"HTTP Error {e.code}: {e.reason}"
        except Exception as e:
            return False, str(e)

    def fetch_app_versions(self, app_name):
        url = f"https://api.github.com/repos/bogdangotj/PYOS/contents/Apps/{app_name}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'PyOS-Nexus'})
            with urllib.request.urlopen(req, timeout=7) as response:
                items = json.loads(response.read().decode('utf-8'))
            versions = []
            for item in items:
                name = item.get('name', '')
                if name.endswith('.x4') or name.endswith('.x4s'):
                    versions.append(name)
            if not versions:
                return True, [f"{app_name}.x4"]
            return True, versions
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, [f"{app_name}.x4"]
            return False, [f"{app_name}.x4"]
        except Exception:
            return False, [f"{app_name}.x4"]

    def download_app_file(self, app_path):
        url = f"{self.GITHUB_RAW_APPS_BASE}/{app_path}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'PyOS-Nexus'})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read()
                # Проверка Content-Type или содержимого на HTML-ошибку 404
                if b"<!DOCTYPE html>" in content[:100] or b"<html" in content[:100]:
                    raise RuntimeError("Загруженный файл является HTML-страницей (возможно, ошибка 404).")
                return content
        except Exception as e:
            raise RuntimeError(f"Не удалось скачать приложение: {e}")

    def uninstall_pyos(self, mode, kernel):
        sp = get_script_path()
        bd = Path(kernel.base_path).resolve()
        bc = ""
        if mode == 'backup':
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            ext = bd.parent / f"pyos_uninstalled_backup_{ts}"
            ext.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, ext / sp.name)
            hdir = (bd / kernel.hostname).resolve()
            if hdir.exists():
                shutil.copytree(hdir, ext / kernel.hostname, dirs_exist_ok=True)
            bdir = bd / 'backups'
            if bdir.exists():
                shutil.copytree(bdir, ext / 'backups', dirs_exist_ok=True)
            bc = str(ext)
        if kernel._fs_checker:
            kernel._fs_checker.stop()
        kernel.timer_service.stop()
        hdir = (bd / kernel.hostname).resolve()
        if hdir.exists():
            shutil.rmtree(hdir, ignore_errors=True)
        # Удаляем единый .pyos файл и логи
        for mf in ('.pyos', 'logs.txt'):
            f = bd / mf
            if f.exists():
                try:
                    f.unlink()
                except OSError:
                    pass
        bdir = bd / 'backups'
        if bdir.exists() and mode == 'full':
            shutil.rmtree(bdir, ignore_errors=True)
        try:
            sp.unlink()
        except OSError:
            pass
        return True, bc


# ═══════════════════════════════════════════════════════════════
#  CRASH / SETTINGS / DEBUG / UAC
# ═══════════════════════════════════════════════════════════════
class CrashLogger:
    def __init__(self, fs, dbg=None):
        self.fs = fs
        self.debug = dbg

    def log_crash(self, app, error, trace_str, code_line=''):
        with perm_root():
            self.fs.mkdir('/apps/logs')
            n = 1
            while self.fs.exists(f'/apps/logs/{app}_log{n}.json'):
                n += 1
            cd = {'app': app, 'error': str(error), 'type': type(error).__name__,
                  'traceback': trace_str, 'code_line': code_line,
                  'time': datetime.datetime.now().isoformat(), 'log_number': n}
            p = f'/apps/logs/{app}_log{n}.json'
            self.fs.write_file(p, json.dumps(cd, indent=2, ensure_ascii=False))
        if self.debug:
            self.debug.log('app_crash', str(error), trace_str, app, code_line)
        return p, n


class SettingsManager:
    VALID_AUTOBACKUP = ('off', 'at_start', 'at_shutdown', 'hourly')
    
    UAC_STRICT = 1
    UAC_STANDARD = 2
    UAC_WEAK = 3
    UAC_DISABLED = 4

    def __init__(self):
        self.time_mode = 'auto'
        self.time_offset = 0.0
        self.debug_mode = False
        self.smart_memory = False
        self.auto_backup = 'at_start'
        self.lang = 'ru'
        self.uac_level = self.UAC_STANDARD
        self.x3_speed = 'normal'

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

    def get_uac_name(self):
        names = {
            1: "1 (Строгий - Пароль)",
            2: "2 (Стандартный - Подтверждение)",
            3: "3 (Слабый - Авто User)",
            4: "4 (Отключено - Без запросов)"
        }
        return names.get(self.uac_level, "Неизвестно")

    def to_dict(self):
        return {'time_mode': self.time_mode, 'time_offset': self.time_offset,
                'debug_mode': self.debug_mode, 'smart_memory': self.smart_memory,
                'auto_backup': self.auto_backup, 'lang': self.lang,
                'uac_level': self.uac_level, 'x3_speed': self.x3_speed}

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        self.time_mode = data.get('time_mode', 'auto')
        self.time_offset = data.get('time_offset', 0.0)
        self.debug_mode = data.get('debug_mode', False)
        self.smart_memory = data.get('smart_memory', False)
        self.auto_backup = data.get('auto_backup', 'at_start')
        if self.auto_backup not in self.VALID_AUTOBACKUP:
            self.auto_backup = 'at_start'
        self.lang = data.get('lang', 'ru')
        self.uac_level = data.get('uac_level', self.UAC_STANDARD)
        self.x3_speed = data.get('x3_speed', 'normal').lower()


class DebugLogger:
    def __init__(self, fs):
        self.fs = fs
        self.errors = []
        self._next_id = 1
        self._lock = threading.Lock()

    def log(self, etype, msg, trace='', source='system', line=''):
        with self._lock:
            e = {'id': self._next_id, 'type': etype,
                 'message': str(msg)[:500], 'traceback': str(trace)[:2000],
                 'source': source, 'line': str(line)[:200],
                 'time': datetime.datetime.now().isoformat()}
            self._next_id += 1
            self.errors.append(e)
            if len(self.errors) > 200:
                self.errors = self.errors[-200:]
        self.save()
        return e

    def save(self):
        try:
            with perm_root():
                self.fs.write_file('/sysdata/errors.json',
                                   json.dumps(self.errors, indent=2, ensure_ascii=False))
            return True
        except (OSError, PermissionError):
            return False

    def load(self):
        try:
            with perm_root():
                c = self.fs.read_file('/sysdata/errors.json')
            if c:
                self.errors = json.loads(c)
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


# ═══════════════════════════════════════════════════════════════
#  X4 PARSER / RUNTIME
# ═══════════════════════════════════════════════════════════════
SAFE_BUILTINS = {
    'print': print, 'input': input, 'len': len, 'str': str, 'int': int,
    'float': float, 'bool': bool, 'list': list, 'dict': dict,
    'tuple': tuple, 'set': set, 'range': range, 'enumerate': enumerate,
    'zip': zip, 'sorted': sorted, 'reversed': reversed, 'sum': sum,
    'min': min, 'max': max, 'abs': abs, 'round': round, 'pow': pow,
    'divmod': divmod, 'isinstance': isinstance, 'type': type, 'repr': repr,
    'Exception': Exception, 'ValueError': ValueError, 'TypeError': TypeError,
    'KeyError': KeyError, 'IndexError': IndexError,
    'ZeroDivisionError': ZeroDivisionError,
    'True': True, 'False': False, 'None': None,
}


class X4Runtime:
    def __init__(self, shell, app_name='unknown'):
        self.shell = shell
        self.app_name = app_name
        self._user_granted = False
        self._last_debug_time = 0.0
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

    def _debug_error(self, message):
        now = time.time()
        if now - self._last_debug_time < 1.0:
            return False
        self._last_debug_time = now
        if self.shell.kernel.settings.debug_mode and self.shell.kernel.debug:
            self.shell.kernel.debug.log('x4_app_error', str(message),
                                        source=self.app_name)
            return True
        return False

    def _request_user(self, reason=''):
        if PermissionContext.get() == Perm.USER:
            return True
        if self._user_granted:
            return True
            
        uac = self.shell.kernel.settings.uac_level
        
        if uac == SettingsManager.UAC_DISABLED:
            print(C.c(f"  [UAC Auto] Выданы USER права приложению '{self.app_name}'", C.Y))
            self._user_granted = True
            PermissionContext.set(Perm.USER, user=self.shell.user, app=self.app_name)
            return True

        if uac == SettingsManager.UAC_WEAK:
            print(C.c(f"  [UAC Info] Выданы USER права приложению '{self.app_name}'", C.Y))
            self._user_granted = True
            PermissionContext.set(Perm.USER, user=self.shell.user, app=self.app_name)
            return True

        print()
        print(C.c("  ╔═══ [UAC] Запрос привилегий USER ═══", C.Y + C.B))
        print(C.c(f"  ║ Приложение: {self.app_name}", C.Y))
        if reason:
            print(C.c(f"  ║ Причина:    {reason[:60]}", C.Y))
        print(C.c("  ╚═════════════════════════════════════", C.Y + C.B))
        
        if uac == SettingsManager.UAC_STRICT:
            if not self.shell.kernel.um.has_password(self.shell.user):
                print(C.c("  [UAC] Требуется пароль, но у пользователя нет пароля!", C.R))
                return False
            try:
                pw = input(C.c("  Введите ваш пароль для подтверждения: ", C.W))
            except (EOFError, KeyboardInterrupt):
                pw = ""
            if self.shell.kernel.um.auth(self.shell.user, pw):
                self._user_granted = True
                PermissionContext.set(Perm.USER, user=self.shell.user, app=self.app_name)
                print(C.c("  [UAC: Права USER предоставлены]", C.G))
                return True
            print(C.c("  [UAC: Неверный пароль. Отказано]", C.R))
            return False

        try:
            ans = input(C.c(
                "  Дать этому приложению USER права на текущую сессию? (y/n): ",
                C.W)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = 'n'
        if ans in ('y', 'yes', 'да', 'д'):
            self._user_granted = True
            PermissionContext.set(Perm.USER, user=self.shell.user, app=self.app_name)
            print(C.c("  [UAC: Права USER предоставлены]", C.G))
            return True
        print(C.c("  [UAC: Отказано]", C.R))
        return False

    def execute(self, code):
        clean_code = textwrap.dedent(code).strip()

        validator = X4ASTValidator()
        ok, errs = validator.validate(clean_code)
        if not ok:
            print()
            print(C.c(f"  [SECURITY] X4-код '{self.app_name}' отклонён.", C.R + C.B))
            for e in errs[:10]:
                print(C.c(f"    • {e}", C.R))
            if len(errs) > 10:
                print(C.c(f"    ... и ещё {len(errs)-10}", C.R))
            self.shell.kernel.notifications.send(
                source=self.app_name, title=f"Security: {self.app_name}",
                message="X4-код отклонён AST-валидатором",
                icon='err', priority='high')
            if self.shell.kernel.settings.debug_mode and self.shell.kernel.debug:
                self.shell.kernel.debug.log('x4_security',
                                            'AST validation failed',
                                            '\n'.join(errs),
                                            source=self.app_name)
            return

        notify = lambda t, m: self.shell.kernel.notifications.send(
            source=self.app_name, title=str(t), message=str(m),
            icon='app', priority='normal')
        notify_high = lambda t, m: self.shell.kernel.notifications.send(
            source=self.app_name, title=str(t), message=str(m),
            icon='app', priority='high')

        env = {
            '__builtins__': dict(SAFE_BUILTINS),
            'math': math, 'random': random, 'time': time,
            'json': json, 're': re, 'datetime': datetime,
            'clear': clear, 'C': C,
            'color': self._color_print, 'print_color': self._color_print,
            'notify': notify, 'notify_high': notify_high,
            'request_user': self._request_user,
            'debug_error': self._debug_error,
            'eval': safe_eval,
            'spawn_thread': _spawn_thread_helper,
            'cache_write': lambda k, v: self._w(f'/cache/{self.app_name}_{str(k).strip("/")}', str(v)),
            'cache_read': lambda k: self._r(f'/cache/{self.app_name}_{str(k).strip("/")}') or '',
            'cache_has': lambda k: self._e(f'/cache/{self.app_name}_{str(k).strip("/")}'),
            'cache_del': lambda k: self._d(f'/cache/{self.app_name}_{str(k).strip("/")}'),
            'fwrite': lambda p, c: self._w(str(p), str(c)),
            'fappend': lambda p, c: self._w(str(p), str(c), append=True),
            'fread': lambda p: self._r(str(p)) or '',
            'fexists': lambda p: self._e(str(p)),
            'fdelete': lambda p: self._d(str(p)),
            'fmkdir': lambda p: self._m(str(p)),
            'flist': lambda p: [i['name'] for i in (
                self.shell.kernel.fs.list_dir(str(p), self.shell.cwd) or [])],
            'sleep': time.sleep,
            'sysinfo': lambda: print(
                f"  OS: {self.vars['__OS__']} | User: {self.shell.user} | App: {self.app_name}"),
            'background': lambda: self.shell.kernel.app_bg.register(self.app_name),
        }
        env.update(self.vars)
        old_state = PermissionContext._state()
        PermissionContext.set(Perm.PROGRAM, user=self.shell.user, app=self.app_name)
        try:
            exec(clean_code, env)
        except KeyboardInterrupt:
            print("\n  [Прервано]")
        except Exception as e:
            self._handle_crash(e, tb_module.format_exc())
        finally:
            PermissionContext.set(*old_state)

    def _w(self, p, c, append=False):
        try:
            return self.shell.kernel.fs.write_file(p, c, self.shell.cwd, append=append)
        except Exception:
            return False

    def _r(self, p):
        try:
            return self.shell.kernel.fs.read_file(p, self.shell.cwd)
        except Exception:
            return None

    def _e(self, p):
        try:
            return self.shell.kernel.fs.exists(p, self.shell.cwd)
        except Exception:
            return False

    def _d(self, p):
        try:
            return self.shell.kernel.fs.delete(p, self.shell.cwd, recursive=True)
        except Exception:
            return False

    def _m(self, p):
        try:
            return self.shell.kernel.fs.mkdir(p, self.shell.cwd)
        except Exception:
            return False

    def _handle_crash(self, error, trace_str):
        print(C.c(f"\n  [Ошибка приложения] {error}", C.R))
        dbg = self.shell.kernel.debug if (
            self.shell.kernel.settings.debug_mode and self.shell.kernel.debug) else None
        cr = CrashLogger(self.shell.kernel.fs, dbg)
        p, _ = cr.log_crash(self.app_name, error, trace_str, "X4 Native Exec")
        print(C.c(f"  [Лог: {p}]", C.Y))
        self.shell.kernel.notifications.send(
            source=self.app_name, title=f"Crash: {self.app_name}",
            message=str(error)[:50], icon='err', priority='high')


class X4Parser:
    @staticmethod
    def parse(content):
        r = {'info': {}, 'code': '', 'data': {}, 'other': ''}
        m = re.search(r'\[INFO\](.*?)(?=\[CODE\]|\[DATA\]|\[OTHER\]|\[END\])',
                      content, re.DOTALL | re.IGNORECASE)
        if m:
            for ln in m.group(1).strip().split('\n'):
                ln = ln.strip()
                if ':' in ln and not ln.startswith('#'):
                    k, v = ln.split(':', 1)
                    r['info'][k.strip().lower()] = v.strip()
        m = re.search(r'\[CODE\](.*?)\[/CODE\]', content, re.DOTALL | re.IGNORECASE)
        if m:
            r['code'] = m.group(1)
        m = re.search(r'\[DATA\](.*?)\[/DATA\]', content, re.DOTALL | re.IGNORECASE)
        if m:
            for ln in m.group(1).strip().split('\n'):
                ln = ln.strip()
                if ':' in ln and not ln.startswith('#'):
                    k, v = ln.split(':', 1)
                    r['data'][k.strip().lower()] = v.strip()
        m = re.search(r'\[OTHER\](.*?)(?=\[END\]|\Z)', content, re.DOTALL | re.IGNORECASE)
        if m:
            r['other'] = m.group(1).strip()
        return r

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


# ═══════════════════════════════════════════════════════════════
#  APP MANAGER
# ═══════════════════════════════════════════════════════════════
class AppManager:
    def __init__(self, fs, guardian, notifications=None, app_bg=None):
        self.fs = fs
        self.apps = {}
        self.guardian = guardian
        self.notifications = notifications
        self.app_bg = app_bg

    def load_installed(self):
        with perm_root():
            items = self.fs.list_dir('/apps/installed')
        if not items:
            return
        for it in items:
            n = it['name']
            if it['is_dir']:
                continue
            if n.endswith('.x4') and not n.lower().endswith('.x4s'):
                with perm_root():
                    c = self.fs.read_file('/apps/installed/' + n)
                if c:
                    p = X4Parser.parse(c)
                    p['format'] = 'x4'
                    key = p['info'].get('name', n[:-3])
                    self.apps[key] = p
            elif n.lower().endswith('.x4s'):
                with perm_root():
                    raw = self.fs.read_bytes('/apps/installed/' + n)
                if raw:
                    try:
                        if raw.startswith(b'X4S\x01'):
                            d = lzma.decompress(raw[4:]).decode('utf-8', errors='replace')
                        else:
                            d = lzma.decompress(raw).decode('utf-8', errors='replace')
                        p = X4Parser.parse(d)
                        p['format'] = 'x4s'
                        key = p['info'].get('name', n[:-4])
                        self.apps[key] = p
                    except (lzma.LZMAError, UnicodeDecodeError):
                        pass

    def install_builtins(self):
        for name, content in self._builtins().items():
            with perm_root():
                self.fs.write_file(f'/apps/installed/{name}.x4', content)
            p = X4Parser.parse(content)
            p['format'] = 'x4'
            an = p['info'].get('name', name)
            self.apps[an] = p
            with perm_root():
                self.fs.mkdir(p['data'].get('folder', f'/apps/data/{an}'))

    def install(self, filename, cwd='/', home_dir=None):
        content = None
        is_x4s = False
        with perm_root():
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
            return False, f"'{filename}' не найден"
        p = X4Parser.parse(content)
        name = p['info'].get('name', '')
        if not name:
            return False, "Нет name в [INFO]"
        if not p['code']:
            return False, "Нет [CODE]"
        with perm_root():
            if is_x4s:
                ro = self.fs.read_bytes(filename, cwd)
                self.fs.write_bytes(f'/apps/installed/{name}.x4s', ro)
                p['format'] = 'x4s'
            else:
                self.fs.write_file(f'/apps/installed/{name}.x4', content)
                p['format'] = 'x4'
            self.fs.mkdir(p['data'].get('folder', f'/apps/data/{name}'))
        self.apps[name] = p
        if self.notifications:
            self.notifications.send(
                source='system', title=f"Установлено: {name}",
                message=f"v{p['info'].get('version','?')}",
                icon='ok', priority='normal')
        return True, f"'{name}' v{p['info'].get('version','?')} установлено!"

    def run(self, name, shell):
        if name not in self.apps:
            return False, f"'{name}' не найдено"
        app = self.apps[name]
        info = app['info']
        fmt = app.get('format', 'x4').upper()
        if fmt == 'X4S':
            print(C.c(f"  [X4 SUPER: распаковка '{name}' в RAM...]", C.CY + C.DIM))
            time.sleep(0.05)
        print(C.c(f"  [{info.get('name', name)} v{info.get('version','?')} ({fmt}) "
                  f"— Тег: {info.get('tag','None')}]", C.DIM))
        if info.get('background', '').lower() == 'true' and self.app_bg:
            self.app_bg.register(name, info)
        X4Runtime(shell, app_name=name).execute(app['code'])
        deleted = self.guardian.cleanup_app_folder(self.fs, name)
        if deleted:
            print(C.c(f"  [Guardian] Данные '{name}' оптимизированы:", C.Y))
            for fn, fsz in deleted:
                print(C.c(f"    Удалено: {fn} ({self.guardian.fmt_size(fsz)})", C.Y))
        print()
        print(C.c("  Приложение завершило работу.", C.DIM))
        try:
            input(C.c("  Нажмите Enter...", C.DIM))
        except (EOFError, KeyboardInterrupt):
            pass
        return True, ""

    def remove(self, name, backup_data_to_cache=True):
        if name not in self.apps:
            return False, "Не найдено"
        dp = f'/apps/data/{name}'
        with perm_root():
            hd = self.fs.exists(dp) and bool(self.fs.list_dir(dp))
        ci = ""
        if backup_data_to_cache and hd:
            with perm_root():
                self.fs.mkdir('/cache/deleted_apps')
                ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                bcf = f"/cache/deleted_apps/{name}_data_{ts}.tar.xz"
                rd, _ = self.fs.to_real_path(dp)
                rc, _ = self.fs.to_real_path(bcf)
            try:
                with lzma.open(rc, 'wb') as xz_out:
                    with tarfile.open(fileobj=xz_out, mode='w') as tar:
                        tar.add(rd, arcname='data')
                ci = f" (Данные в {bcf})"
            except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError):
                pass
        del self.apps[name]
        with perm_root():
            self.fs.delete(f'/apps/installed/{name}.x4')
            self.fs.delete(f'/apps/installed/{name}.x4s')
            self.fs.delete(f'/apps/installed/{name}.X4S')
            self.fs.delete(dp, recursive=True)
        if self.app_bg:
            self.app_bg.unregister(name)
        if self.notifications:
            self.notifications.delete_by_source(name)
        return True, f"'{name}' удалено{ci}."

    def update_app(self, name, new_file_path, cwd='/'):
        if name not in self.apps:
            return False, f"'{name}' не установлено"
        with perm_root():
            c = self.fs.read_file(new_file_path, cwd)
        if not c:
            return False, f"'{new_file_path}' не найден"
        p = X4Parser.parse(c)
        if not p['code']:
            return False, "Нет [CODE]"
        with perm_root():
            self.fs.write_file(f'/apps/installed/{name}.x4', c)
        p['format'] = 'x4'
        self.apps[name] = p
        return True, f"'{name}' обновлено до v{p['info'].get('version','новой')}!"

    def disable(self, name):
        if name not in self.apps:
            return False, f"'{name}' не найдено"
        orig = None
        with perm_root():
            for ext in ('.x4', '.x4s', '.X4S'):
                cand = f'/apps/installed/{name}{ext}'
                if self.fs.exists(cand):
                    orig = cand
                    break
        if not orig:
            return False, "Файл не найден"
        avp = f'/apps/installed/{name}.disabled'
        with perm_root():
            ra, _ = self.fs.to_real_path(avp)
            rf, _ = self.fs.to_real_path(orig)
            rd, _ = self.fs.to_real_path(f'/apps/data/{name}')
        meta = {'name': name, 'orig_file_name': Path(orig).name,
                'disabled_at': datetime.datetime.now().isoformat(),
                'info': self.apps[name]['info']}
        try:
            with lzma.open(ra, 'wb', preset=9 | lzma.PRESET_EXTREME) as xz_out:
                with tarfile.open(fileobj=xz_out, mode='w') as tar:
                    tar.add(rf, arcname='app_binary')
                    if rd.exists():
                        tar.add(rd, arcname='data')
                    mb = json.dumps(meta, indent=2, ensure_ascii=False).encode('utf-8')
                    ti = tarfile.TarInfo(name='disabled_meta.json')
                    ti.size = len(mb); ti.mtime = int(time.time())
                    tar.addfile(ti, io.BytesIO(mb))
            with perm_root():
                self.fs.delete(orig)
                self.fs.delete(f'/apps/data/{name}', recursive=True)
            del self.apps[name]
            if self.app_bg:
                self.app_bg.unregister(name)
            sz = self.guardian.fmt_size(ra.stat().st_size)
            return True, f"'{name}' отключено → {avp} ({sz})"
        except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError) as e:
            if ra.exists():
                try:
                    ra.unlink()
                except OSError:
                    pass
            return False, f"Ошибка: {e}"

    def enable(self, name):
        avp = f'/apps/installed/{name}.disabled'
        with perm_root():
            if not self.fs.exists(avp):
                return False, f"'{name}' не найдено среди отключённых"
            ra, _ = self.fs.to_real_path(avp)
        try:
            with lzma.open(ra, 'rb') as xz_in:
                with tarfile.open(fileobj=xz_in, mode='r') as tar:
                    mm = tar.extractfile('disabled_meta.json')
                    meta = json.loads(mm.read().decode('utf-8')) if mm else {}
                    orig = meta.get('orig_file_name', f"{name}.x4")
                    ab = tar.extractfile('app_binary')
                    if ab:
                        with perm_root():
                            self.fs.write_bytes(f'/apps/installed/{orig}', ab.read())
                    for m in tar.getmembers():
                        if m.name.startswith('data/'):
                            rel = m.name[5:]
                            if not rel:
                                continue
                            op = f'/apps/data/{name}/{rel}'
                            with perm_root():
                                if m.isdir():
                                    self.fs.mkdir(op)
                                elif m.isfile():
                                    ef = tar.extractfile(m)
                                    if ef:
                                        self.fs.write_bytes(op, ef.read())
            with perm_root():
                self.fs.delete(avp)
            self.load_installed()
            return True, f"'{name}' включено!"
        except (OSError, PermissionError, tarfile.TarError, lzma.LZMAError,
                json.JSONDecodeError) as e:
            return False, f"Ошибка: {e}"

    def list_disabled(self):
        with perm_root():
            items = self.fs.list_dir('/apps/installed') or []
        return [i['name'][:-9] for i in items if i['name'].endswith('.disabled')]

    def get_info(self, name):
        return self.apps.get(name, {}).get('info', {})

    def _builtins(self):
        return {
'calc': """[INFO]
name: calc
description: Удобный калькулятор
version: 1.3.0
author: Kostyl Studios
tag: Technical
background: false

[CODE]
print("=== Калькулятор (Technical) ===")
color("Введите выражение или 'exit'", "cyan")
while True:
    expr = input("calc> ").strip()
    if expr.lower() in ('exit','quit','q'): break
    if not expr: continue
    try:
        res = eval(expr, {"math": math})
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
color("Я загадал число от 1 до 100.", "yellow")
while True:
    val = input("Догадка (или 'exit'): ").strip()
    if val.lower() in ('exit','q'):
        color("Прервано. Было: " + str(target), "magenta")
        break
    if not val.isdigit():
        color("Введите целое!", "red"); continue
    num = int(val); attempts += 1
    if num < target: color("Больше!", "cyan")
    elif num > target: color("Меньше!", "cyan")
    else:
        color("ПОЗДРАВЛЯЕМ! За " + str(attempts) + " попыток!", "green")
        notify("Game: Guess", "Победа за " + str(attempts))
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
version: 4.4.0
author: Kostyl Studios
tag: Technical
background: false

[CODE]
print("=== Заметки (Technical) ===")
notes_dir = "/apps/data/notes"
fmkdir(notes_dir)
while True:
    print("")
    color("-- Меню --", "cyan")
    print("1. Создать  2. Прочитать  3. Список  4. Удалить  5. Выход")
    choice = input("Выберите (1-5): ").strip()
    if choice == "1":
        name = input("Имя: ").strip()
        if name:
            text = input("Текст: ")
            fwrite(notes_dir + "/" + name + ".txt", text)
            color("Сохранено!", "green")
    elif choice == "2":
        name = input("Имя: ").strip()
        data = fread(notes_dir + "/" + name + ".txt")
        if data:
            color("-- " + name + " --", "yellow"); print(data)
        else: color("Не найдено.", "red")
    elif choice == "3":
        for f in flist(notes_dir): print("  * " + str(f))
    elif choice == "4":
        name = input("Имя: ").strip()
        fdelete(notes_dir + "/" + name + ".txt")
        color("Удалено.", "yellow")
    elif choice in ("5","exit","q"):
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
version: 3.2.0
author: Kostyl Studios
tag: Demo
background: false

[CODE]
color("=== Привет, " + __USER__ + "! ===", "green")
print("Добро пожаловать в " + __OS__)
print("Дата: " + __DATE__ + " " + __TIME__)
cache_write("last_user.txt", __USER__)
color("Приложение работает в PROGRAM-песочнице.", "cyan")
notify("Hello App", "Запущено " + __USER__)
[/CODE]

[DATA]
folder: /apps/data/hello
[/DATA]

[OTHER]
Free License -- Kostyl Studios
[/OTHER]
[END]"""
        }


# ═══════════════════════════════════════════════════════════════
#  HISTORY
# ═══════════════════════════════════════════════════════════════
class HistoryManager:
    def __init__(self, fs, max_size=500):
        self.fs = fs
        self.entries = []
        self.max_size = max_size
        self._save_lock = threading.Lock()

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
        def _do():
            with self._save_lock:
                try:
                    with perm_root():
                        self.fs.write_file(
                            '/sysdata/history.json',
                            json.dumps(self.entries, indent=2, ensure_ascii=False))
                except (OSError, PermissionError):
                    pass
        threading.Thread(target=_do, daemon=True).start()

    def load(self):
        try:
            with perm_root():
                c = self.fs.read_file('/sysdata/history.json')
            if c:
                self.entries = json.loads(c)[-self.max_size:]
                return True
        except (json.JSONDecodeError, OSError):
            pass
        self.entries = []
        return False


# ═══════════════════════════════════════════════════════════════
#  ЯДРО
# ═══════════════════════════════════════════════════════════════
class Kernel:
    VERSION = '19.1'
    BUILD = '18.10.2026'
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
        meta = _load_pyos_meta(get_script_path())
        if 'hostname' in meta:
            self.hostname = meta['hostname']
            return True
        return False

    def _save_hostname(self):
        _save_pyos_meta(get_script_path(), {'hostname': self.hostname})

    def trigger_bsod(self, code, msg, details=''):
        with self._bsod_lock:
            if self._bsod_pending:
                return
            self._bsod_pending = True
            self._bsod_error_code = code
            self._bsod_message = msg
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

    def run_smart_memory_cleanup(self):
        if not self.settings.smart_memory or not self.fs:
            return 0, 0
        dd = df = 0
        for td in ['/apps/store', '/apps/logs']:
            with perm_root():
                if self.fs.exists(td) and self.fs.is_dir(td):
                    items = self.fs.list_dir(td)
                    if items is not None and len(items) == 0:
                        if self.fs.delete(td):
                            dd += 1
        with perm_root():
            if self.fs.exists('/apps/logs') and self.fs.is_dir('/apps/logs'):
                items = self.fs.list_dir('/apps/logs')
                if items:
                    for it in items:
                        if not it['is_dir'] and it['size'] == 0:
                            if self.fs.delete(f"/apps/logs/{it['name']}"):
                                df += 1
        return dd, df

    def _start_hourly_autobackup_worker(self):
        def worker():
            while self.running:
                time.sleep(60)
                if not self.running:
                    break
                if self.settings.auto_backup == 'hourly':
                    with perm_root():
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
            with perm_root():
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
        logo = [f"  PyOS v{self.VERSION}", f"  build {self.BUILD}",
                f"  {self.COMPANY} [Argon2id+Nexus+AST]"]
        print(SimpleBox.box('\n'.join(logo), 46, '='))
        print()
        stages = ["Kernel", "Argon2id", "Permissions", "AST Validator",
                  "Filesystem", "Trash", "Guardian", "Integrity",
                  "SmartMemory", "Notifications", "AutoBackup",
                  "Cache", "App Manager"]
        total = len(stages)
        bw = 24
        for i, s in enumerate(stages, 1):
            r = i / total
            f = int(bw * r)
            bar = '#' * f + '.' * (bw - f)
            pct = int(r * 100)
            print(f"\r  {C.c(f'[{bar}] {pct:3d}% {s}...', C.G)}          ",
                  end='', flush=True)
            time.sleep(0.02)
        print(f"\r  {C.c('[' + '#' * bw + '] 100%', C.G)} "
              f"{C.c('Готово!', C.G + C.B)}          \n")

    def setup(self):
        print(SimpleBox.header(f"PyOS {self.VERSION} build {self.BUILD}", 46))
        print(f"  {self.t('Первоначальная настройка', 'First Time Setup')}")
        print("=" * 46)
        print()
        a = input(f"  {self.t('Автонастройка? (yes/no): ', 'Auto setup? (yes/no): ')}").strip().lower()
        if a in ('yes', 'y', 'да', 'д'):
            self._auto_setup()
            return
        self._manual_setup()

    def _auto_setup(self):
        print(C.c(f"\n  [Auto Setup]", C.CY))
        self.hostname = 'Computer'
        self._save_hostname()
        self.fs = RealFS(self.base_path)
        self.fs.init_structure(self.hostname)
        self.trash = TrashManager(self.fs, self.guardian)
        self.debug = DebugLogger(self.fs)
        un = 'User'
        self.um.create(un, None, '')
        with perm_root():
            for d in [f'/home/{un}', f'/home/{un}/Desktop', f'/home/{un}/Documents']:
                self.fs.mkdir(d)
        self.guardian.set_app_folder_limit(1024 * 1024)
        self.apps = AppManager(self.fs, self.guardian, self.notifications, self.app_bg)
        self.apps.install_builtins()
        self.history = HistoryManager(self.fs)
        self._fs_checker = FSHealthChecker(self.fs, self)
        self._fs_checker.start()
        self._start_hourly_autobackup_worker()
        save_code_hash(get_script_path())
        BackupManager.create_backup("initial_setup", self)
        print(C.c(f"\n  Готово!", C.G))
        self.save_state()

    def _manual_setup(self):
        self.hostname = input("  Имя компьютера [pyos]: ").strip() or 'pyos'
        self._save_hostname()
        self.fs = RealFS(self.base_path)
        self.fs.init_structure(self.hostname)
        self.trash = TrashManager(self.fs, self.guardian)
        self.debug = DebugLogger(self.fs)
        while True:
            un = input("  Имя пользователя: ").strip()
            if un and un.isalnum():
                break
            print(C.c("  Только буквы и цифры!", C.R))
        if input("  Установить пароль? (y/n): ").strip().lower() in ('y', 'yes', 'да'):
            while True:
                up = input("  Пароль: ").strip()
                if len(up) < 2:
                    print(C.c("  Слишком короткий", C.R))
                    continue
                if input("  Подтвердите: ").strip() != up:
                    print(C.c("  Не совпадают", C.R))
                    continue
                break
            uh = input("  Подсказка (Enter = нет): ").strip()
            self.um.create(un, up, uh)
        else:
            self.um.create(un, None, '')
        with perm_root():
            for d in [f'/home/{un}', f'/home/{un}/Desktop', f'/home/{un}/Documents']:
                self.fs.mkdir(d)
        self.apps = AppManager(self.fs, self.guardian, self.notifications, self.app_bg)
        self.apps.install_builtins()
        self.history = HistoryManager(self.fs)
        self._fs_checker = FSHealthChecker(self.fs, self)
        self._fs_checker.start()
        self._start_hourly_autobackup_worker()
        save_code_hash(get_script_path())
        BackupManager.create_backup("initial_setup", self)
        print(C.c(f"\n  Готово!\n", C.G))
        self.save_state()

    def save_state(self):
        try:
            with perm_root():
                self.run_smart_memory_cleanup()
                st = {'hostname': self.hostname, 'base_path': self.base_path,
                      'version': self.VERSION, 'build': self.BUILD,
                      'company': self.COMPANY, 'hash_algo': 'Argon2id+salt',
                      'users': {'users': self.um.users},
                      'guardian': {'daily_limit': self.guardian.daily_limit,
                                   'app_folder_limit': self.guardian.app_folder_limit,
                                   'suggest_commands': self.guardian.suggest_commands},
                      'settings': self.settings.to_dict(),
                      'notifications': self.notifications.to_dict(),
                      'timers': self.timer_service.to_dict(),
                      'background_apps': self.app_bg.to_dict()}
                sp = self.get_save_path()
                sp.parent.mkdir(parents=True, exist_ok=True)
                with open(sp, 'w', encoding='utf-8') as f:
                    json.dump(st, f, indent=2, ensure_ascii=False)
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
        if not isinstance(st, dict):
            return
        self.hostname = st.get('hostname', 'pyos')
        self.base_path = st.get('base_path', self.base_path)
        users = st.get('users', {})
        if isinstance(users, dict):
            uu = users.get('users', {})
            if isinstance(uu, dict):
                self.um.users = uu
        gd = st.get('guardian', {})
        if isinstance(gd, dict):
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
            print(C.c("  [AutoBackup] Создание копии...", C.CY))
            BackupManager.create_backup("auto_shutdown", self)
        if self._fs_checker:
            self._fs_checker.stop()
        self.timer_service.stop()
        self.run_smart_memory_cleanup()
        self.save_state()
        print(C.c(f"  {self.COMPANY} -- PyOS {self.VERSION}", C.DIM))
        print(C.c(f"  {self.t('До свидания!', 'Goodbye!')}", C.G))
        print()
        self.running = False

    def check_fs_health(self):
        if self.fs and self.fs.hostname_dir:
            if not self.fs.hostname_dir.exists():
                self.trigger_bsod('CRITICAL_DATA_DESTROYED',
                                  'System data folder deleted.',
                                  f'Missing: {self.fs.hostname_dir}')
                return False
        return True


# ═══════════════════════════════════════════════════════════════
#  SHELL
# ═══════════════════════════════════════════════════════════════
class Shell:
    MAN_PAGES = {
        'ls': {'desc': 'Содержимое каталога.', 'synopsis': 'ls [-a] [-l] [путь]',
               'details': 'Цветовая индикация типов.',
               'options': [('-a', 'Скрытые.'), ('-l', 'Подробно.')],
               'examples': ['ls', 'ls -la']},
        'cd': {'desc': 'Смена каталога.', 'synopsis': 'cd [путь | ~ | - | ДИСК:путь]',
               'details': 'Перемещение по FS.',
               'options': [('~', 'Домой.'), ('-', 'Назад.'), ('D:', 'Диск.')],
               'examples': ['cd /apps', 'cd D:/data']},
        'pwd': {'desc': 'Текущий путь.', 'synopsis': 'pwd',
                'details': 'Диск и каталог.', 'options': [], 'examples': ['pwd']},
        'trash': {'desc': 'Корзина.', 'synopsis': 'trash [list | empty | rm <id> | restore <id>]',
                  'details': 'Сжатие в tar.xz, восстановление.',
                  'options': [('list', 'Список.'), ('empty', 'Очистить.'),
                              ('restore <id>', 'Восстановить.'), ('rm <id>', 'Удалить.')],
                  'examples': ['trash', 'trash restore 1', 'trash empty']},
        'app': {'desc': 'Менеджер приложений.',
                'synopsis': 'app <store | tags | manager | list | run | install | remove | disable | enable>',
                'details': 'X4-приложения (.x4 / .x4s) в PROGRAM-песочнице + Центр Приложений GitHub.',
                'options': [('store', 'Центр Приложений.'), ('tags', 'По тегам.'), ('manager', 'Интерактив.'),
                            ('run <n>', 'Запуск.'), ('install <f>', 'Установка.'),
                            ('disable', 'Сжать.'), ('enable', 'Разжать.')],
                'examples': ['app store', 'app tags', 'app run calc']},
        'x3': {'desc': 'Выполнение скриптов автоматизации.', 'synopsis': 'x3 [--fast] <файл.x3> [arg1 arg2 ...]',
               'details': 'Выполняет цепочку команд в терминале от имени USER с поддержкой аргументов ($1, $2) и рекурсии.',
               'options': [('--fast', 'Быстрое выполнение без пауз.')], 'examples': ['x3 script.x3 hello 123', 'x3 --fast auto']},
        'newx3': {'desc': 'Создать шаблон x3.', 'synopsis': 'newx3 <имя>',
                  'details': 'Создает файл автоматизации в папке Documents.',
                  'options': [], 'examples': ['newx3 setup']},
        'guardian': {'desc': 'Центр безопасности.',
                     'synopsis': 'guardian [update | uninstall | github]',
                     'details': 'Целостность, патчи, автообновления с GitHub, удаление.',
                     'options': [('update', 'Обновления.'), ('github', 'Скачать с GitHub.'), ('uninstall', 'Удаление.')],
                     'examples': ['guardian', 'guardian github']},
        'backup': {'desc': 'Резервные копии.',
                   'synopsis': 'backup [list | create [n] | restore <n> | rm <n>]',
                   'details': 'LZMA Extreme + Argon2id+salt.',
                   'options': [], 'examples': ['backup', 'backup create snap']},
        'settings': {'desc': 'Настройки.',
                     'synopsis': 'settings [lang|autobackup|debug|smartmem|uac|x3_speed]',
                     'details': 'Язык, бэкапы, отладка, UAC, скорость X3.',
                     'options': [('uac 1-4', 'Уровень UAC.'), ('x3_speed fast|normal', 'Скорость X3.')], 'examples': ['settings uac 2']},
        'uac': {'desc': 'Управление UAC.', 'synopsis': 'uac [1|2|3|4]',
                'details': '1: Строгий (Пароль)\n2: Стандартный (y/n)\n3: Слабый (Авто User)\n4: Отключено',
                'options': [], 'examples': ['uac 1', 'uac 3']},
        'perms': {'desc': 'Права Nexus.', 'synopsis': 'perms',
                  'details': 'ROOT/USER/PROGRAM, правила AST-валидатора, уровни x3_speed.',
                  'options': [], 'examples': ['perms']},
        'man': {'desc': 'Справка.', 'synopsis': 'man [команда]',
                'details': 'Manual pages.', 'options': [],
                'examples': ['man app', 'man x3']},
    }

    def __init__(self, kernel):
        self.kernel = kernel
        self.cwd = '/'
        self.user = None
        self.env = {'HOME': '/', 'CACHE': '/cache', 'USER': ''}
        self.aliases = {'ll': 'ls -l', 'la': 'ls -a', 'cls': 'clear',
                        '..': 'cd ..', 'q': 'exit', 'recycle': 'trash', 'bin': 'trash'}
        self._oldpwd = {'path': self.cwd, 'disk': 'C'}

    def _docs(self):
        return f'/home/{self.user}/Documents'

    def desktop(self):
        clear()
        if not self.kernel.check_fs_health():
            return
        now = self.kernel.get_now()
        g = self.kernel.guardian
        dk = self.kernel.fs.current_disk
        disks = self.kernel.fs.get_disks()
        usage = self.kernel.fs.disk_usage(dk)
        lim = f"{g.daily_limit} мин" if g.daily_limit else self.kernel.t("Без лимита", "No limit")
        has_pw = self.kernel.t("Да", "Yes") if self.kernel.um.has_password(self.user) else "Нет"
        nb = self.kernel.notifications.format_badge()
        at = len(self.kernel.timer_service.get_active())
        bg = len(self.kernel.app_bg.get_all())
        sm = self.kernel.settings.smart_memory
        ab = self.kernel.settings.auto_backup
        lang = self.kernel.settings.lang.upper()
        uac_str = self.kernel.settings.get_uac_name()
        with perm_root():
            dc = len(self.kernel.apps.list_disabled()) if self.kernel.apps else 0
            tc = len(self.kernel.trash.list_items()) if self.kernel.trash else 0
        ac = len(self.kernel.apps.apps) if self.kernel.apps else 0

        print("=" * 56)
        print(f"  PyOS v{Kernel.VERSION} build {Kernel.BUILD} -- {self.kernel.hostname}")
        print(f"  {C.c('Nexus v19.1', C.Y + C.B)} | Argon2id+salt | UAC ({uac_str})")
        print("=" * 56)
        print(f"  Пользователь:       {C.c(self.user, C.G)} [USER]")
        print(f"  Пароль:             {has_pw} (Argon2id)")
        print(f"  Язык:               {lang}")
        print(f"  Время:              {now.strftime('%H:%M:%S')}")
        print(f"  Сессия:             {g.session_str()} (лимит: {lim})")
        print("-" * 56)
        print(f"  Диски:              {' '.join(d + ':' for d in disks)} (Current: {dk}:)")
        print(f"  Занято:             {g.fmt_size(usage)}")
        
        if ac == 0 and dc == 0:
            print(f"  Приложения:         {C.c('Тут пока пусто, но вы можете найти приложения в Центре приложений!', C.Y)}")
        elif ac == 0 and dc > 0:
            print(f"  Приложения:         {C.c(f'Активных: 0 (Отключено: {dc}) — Включите их через app manager', C.Y)}")
        else:
            print(f"  Приложения:         {ac} (Откл: {dc})")
            
        print(f"  Корзина:            {tc} элементов")
        print(f"  Автобэкап:          {C.c(ab, C.CY)}")
        print(f"  UAC Контроль:       {C.c(uac_str, C.CY)}")
        print(f"  Smart Memory:       {C.c('ON', C.G) if sm else C.c('OFF', C.DIM)}")
        if self.kernel.settings.debug_mode:
            ec = self.kernel.debug.count() if self.kernel.debug else 0
            print(f"  Debug:              {C.c('ON', C.Y)} ({ec} errors)")
        print("-" * 56)
        sp = [f"Notif: {nb}"]
        if at > 0:
            sp.append(C.c(f"Timers: {at}", C.CY))
        if bg > 0:
            sp.append(C.c(f"Bg: {bg}", C.M))
        print('  ' + ' | '.join(sp))
        print("-" * 56)
        print("  man | app store | guardian | uac | trash | app tags / manager | x3")
        print("=" * 56)
        print()
        panel = self.kernel.notifications.format_panel(max_show=4)
        if panel:
            print(panel)
            print()

    def login(self):
        if not self.kernel.um.users:
            self.kernel.um.create('User', None, '')
            with perm_root():
                self.kernel.fs.mkdir('/home/User')
            self.kernel.save_state()
        users = self.kernel.um.list_users()
        print("=" * 44)
        print(f"  {self.kernel.t('Выберите пользователя', 'Select User')}")
        print("=" * 44)
        for u in users:
            info = self.kernel.um.get_public_info(u) or {}
            hp = "[Argon2id]" if info.get('has_password', True) else "[open]"
            print(f"  {hp} {u:<16} disk={info.get('disk','C')}:")
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
            print(C.c("  Неверный пароль.", C.R))
            if fail.get(un, 0) >= 3:
                h = self.kernel.um.get_hint(un)
                if h:
                    print(C.c(f"  Подсказка: {h}", C.CY))
            print()

    def _do_login(self, un):
        self.user = un
        info = self.kernel.um.users[un]
        self.kernel.fs.current_disk = info.get('disk', 'C')
        self.env['HOME'] = info['home']
        self.env['USER'] = un
        self.cwd = info['home']
        with perm_root():
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
                print(SimpleBox.box(self.kernel.t(
                    "Лимит времени исчерпан!\nОтдохните.",
                    "Time limit reached!"), 42, '!'))
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
            redir = None
            if '>>' in line:
                idx = self._find_redirect_op(line, '>>')
                if idx >= 0:
                    redir = ('>>', idx)
            if not redir and '>' in line:
                idx = self._find_redirect_op(line, '>')
                if idx >= 0:
                    redir = ('>', idx)
            with perm_user(self.user):
                if redir:
                    op, idx = redir
                    cmd = line[:idx].strip()
                    fp = line[idx + len(op):].strip().strip('"\'')
                    self._redir(cmd, fp, op == '>>')
                    continue
                for k, v in self.env.items():
                    line = re.sub(r'\$' + re.escape(k) + r'\b',
                                  lambda m: str(v), line)
                first = line.split()[0] if line.split() else ''
                if first in self.aliases:
                    line = self.aliases[first] + line[len(first):]
                self._exec(line)

    def _find_redirect_op(self, line, op):
        in_s = in_d = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '\\' and not in_s:
                i += 2
                continue
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            elif not in_s and not in_d and line[i:i + len(op)] == op:
                return i
            i += 1
        return -1

    def _redir(self, cmd, fp, append):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._exec(cmd)
        clean = re.sub(r'\033\[[0-9;]*m', '', buf.getvalue())
        self.kernel.fs.write_file(fp, clean, self.cwd, append)

    def _check_uac_root_action(self, action_description):
        uac = self.kernel.settings.uac_level
        if uac == SettingsManager.UAC_DISABLED:
            print(C.c(f"  [UAC Auto] Выданы ROOT права: {action_description}", C.R))
            return True
        
        print()
        print(C.c("  ╔═══ [UAC] Требуются ROOT права! ═══", C.R + C.B))
        print(C.c(f"  ║ Действие: {action_description}", C.Y))
        print(C.c("  ╚═════════════════════════════════════", C.R + C.B))

        if uac == SettingsManager.UAC_STRICT:
            if not self.kernel.um.has_password(self.user):
                print(C.c("  [UAC] У пользователя нет пароля!", C.R))
                return False
            try:
                pw = input(C.c("  Введите ваш пароль для подтверждения ROOT: ", C.W))
            except (EOFError, KeyboardInterrupt):
                pw = ""
            if self.kernel.um.auth(self.user, pw):
                print(C.c("  [UAC: Права ROOT предоставлены]", C.G))
                return True
            print(C.c("  [UAC: Неверный пароль]", C.R))
            return False

        try:
            ans = input(C.c("  Разрешить выполнение действия? (y/n): ", C.W)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = 'n'
        if ans in ('y', 'yes', 'да', 'д'):
            print(C.c("  [UAC: Права ROOT предоставлены]", C.G))
            return True
        print(C.c("  [UAC: Отказано]", C.R))
        return False

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
            'clear': lambda _a: self._do_desktop(),
            'desktop': lambda _a: self._do_desktop(),
            'whoami': lambda _a: print(f"  {self.user}"),
            'id': self.c_id, 'su': self.c_su,
            'useradd': self.c_useradd, 'userdel': self.c_userdel,
            'passwd': self.c_passwd, 'users': self.c_users,
            'date': lambda _a: print(f"  {self.kernel.get_now().strftime('%Y-%m-%d %H:%M:%S')}"),
            'uptime': lambda _a: print(f"  Session: {self.kernel.guardian.session_str()}"),
            'hostname': lambda _a: print(f"  {self.kernel.hostname}"),
            'neofetch': self.c_neofetch, 'history': self.c_history,
            'alias': self.c_alias, 'export': self.c_export,
            'env': lambda _a: [print(f"  {k}={v}") for k, v in sorted(self.env.items())],
            'edit': self.c_edit, 'nano': self.c_edit,
            'guardian': self.c_guardian, 'uac': self.c_uac,
            'app': self.c_app, 'tags': lambda _a: self.c_app(['tags']),
            'store': lambda _a: self._ui_app_store(),
            'x3': self.c_x3, 'newx3': self.c_newx3,
            'newapp': self.c_newapp, 'disk': self.c_disk,
            'man': self.c_man, 'realpath': self.c_realpath,
            'suggest': self.c_suggest, 'logs': self.c_logs,
            'notif': self.c_notif, 'timer': self.c_timer,
            'settings': self.c_settings, 'debug': self.c_debug,
            'backup': self.c_backup, 'cache': self.c_cache,
            'smartmem': self.c_smartmem, 'perms': self.c_perms,
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
        
        if cmd.lower().endswith('.x3'):
            X3Runner.execute_file(self, cmd, args)
            self._do_desktop()
            return

        cmds = self._get_cmd_map()
        if cmd in cmds:
            try:
                cmds[cmd](args)
            except Exception as e:
                print(C.c(f"  [Ошибка команды] {e}", C.R))
                if self.kernel.settings.debug_mode and self.kernel.debug:
                    self.kernel.debug.log('command_error', str(e),
                                          tb_module.format_exc(), f'cmd:{cmd}', line)
        elif self.kernel.apps and cmd in self.kernel.apps.apps:
            ok, err = self.kernel.apps.run(cmd, self)
            if not ok:
                print(C.c(f"  {err}", C.R))
            self._do_desktop()
        else:
            if self.kernel.fs and self.kernel.fs.is_file(cmd, self.cwd):
                c = self.kernel.fs.read_file(cmd, self.cwd)
                if c:
                    p = X4Parser.parse(c)
                    if p['code']:
                        X4Runtime(self, app_name=p['info'].get(
                            'name', Path(cmd).stem)).execute(p['code'])
                        try:
                            input(C.c("\n  Enter...", C.DIM))
                        except (EOFError, KeyboardInterrupt):
                            pass
                        self._do_desktop()
                        return
            print(C.c(f"  Команда не найдена: {cmd}", C.R))
            known = list(cmds.keys()) + (list(self.kernel.apps.apps.keys())
                                         if self.kernel.apps else [])
            sg = self.kernel.guardian.suggest(cmd, known)
            if sg:
                print(C.c(f"  Возможно: {', '.join(sg)}?", C.Y))

    def _do_desktop(self):
        self.desktop()

    def c_uac(self, args):
        s = self.kernel.settings
        if not args:
            print("=" * 60)
            print("  Контроль учётных записей (UAC) PyOS Nexus")
            print("=" * 60)
            print(f"  Текущий уровень: {C.c(s.get_uac_name(), C.CY)}")
            print("-" * 60)
            print("  Уровни:")
            print("    1 - Строгий:     Требует пароль на USER и ROOT запросы")
            print("    2 - Стандартный: Требует (y/n) подтверждение")
            print("    3 - Слабый:      USER права автоматически, ROOT с подтверждением")
            print("    4 - Отключено:   Все права выдаются автоматически без вопросов")
            print("=" * 60)
            print("  Использование: uac <1|2|3|4>")
            return
        if args[0] in ('1', '2', '3', '4'):
            new_lvl = int(args[0])
            if not self._check_uac_root_action(f"Изменение уровня UAC на {new_lvl}"):
                return
            s.uac_level = new_lvl
            print(C.c(f"  Уровень UAC изменён на: {s.get_uac_name()}", C.G))
            self.kernel.save_state()
        else:
            print(C.c("  Выберите уровень от 1 до 4.", C.R))

    def c_reload(self, _a):
        if self.kernel.apps:
            self.kernel.apps.apps.clear()
            self.kernel.apps.load_installed()
            print(C.c(f"  {len(self.kernel.apps.apps)} приложений", C.G))

    def c_perms(self, _a):
        print("=" * 62)
        print("  Система прав PyOS Nexus v19.1")
        print("=" * 62)
        print(f"  ROOT    — ядро. Недостижим для пользователя.")
        print(f"  USER    — вы [{C.c(self.user, C.G)}]. Запрет: /sysdata,")
        print(f"           write /apps/installed, чужие /home.")
        print(f"  PROGRAM — X4-приложения.")
        print(f"           Доступ только /apps/data/<app> и /cache/<app>_*.")
        print(f"           Расширение — через request_user().")
        print("-" * 62)
        print(f"  UAC Контроль: {self.kernel.settings.get_uac_name()}")
        print(f"  Скорость X3:  {self.kernel.settings.x3_speed}")
        print("-" * 62)
        print(f"  {C.c('AST Validator', C.Y)} отклоняет:")
        print(f"    • import / from / class / async")
        print(f"    • любые dunder-атрибуты (__class__, __globals__ ...)")
        print(f"    • eval*, exec, compile, open, getattr, globals, ...")
        print(f"    • str.format / format_map")
        print("=" * 62)

    def c_trash(self, args):
        t = self.kernel.trash
        if not args or args[0] in ('list', 'ls'):
            items = t.list_items()
            print("=" * 64)
            print("  Корзина PyOS")
            print("=" * 64)
            if not items:
                print(C.c("  Пусто.", C.DIM))
            else:
                for it in items:
                    sz = self.kernel.guardian.fmt_size(it['size']) if not it['is_dir'] else '<DIR>'
                    ts = it['deleted_at'][:19].replace('T', ' ')
                    print(f"  #{it['id']:<3} {it['name']:<22} {sz:>9} | {ts} | {it['disk']}:{it['orig_path']}")
            print("-" * 64)
            print("  trash restore <id> | trash rm <id> | trash empty")
            print("=" * 64)
            return
        sub = args[0].lower()
        if sub in ('empty', 'clear'):
            print(C.c("  Сжатие...", C.CY))
            ok, msg = t.empty(compress=True)
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif sub in ('rm', 'delete', 'del'):
            if len(args) < 2:
                print(C.c("  trash rm <id>", C.R)); return
            ok, msg = t.delete_single(args[1])
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif sub in ('restore', 'undel'):
            if len(args) < 2:
                print(C.c("  trash restore <id>", C.R)); return
            ok, msg = t.restore(args[1])
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif sub == 'put':
            if len(args) < 2:
                print(C.c("  trash put <путь>", C.R)); return
            ok, msg = t.put(args[1], self.cwd)
            print(C.c(f"  {msg}", C.G if ok else C.R))

    def c_rm(self, args):
        perm = '-f' in args or '--perm' in args or '--permanent' in args
        rec = '-r' in args or '-rf' in args or '-fr' in args
        paths = [x for x in args if not x.startswith('-')]
        if not paths:
            print("  rm [-f] [-r] <file|dir>"); return
        for p in paths:
            if perm:
                if self.kernel.fs.delete(p, self.cwd, rec):
                    print(C.c(f"  [Навсегда] {p}", C.Y))
                else:
                    print(C.c(f"  Ошибка: {p}", C.R))
            else:
                ok, msg = self.kernel.trash.put(p, self.cwd)
                print(C.c(f"  [Корзина] {msg}", C.G) if ok else C.c(f"  {msg}", C.R))

    def c_ls(self, args):
        sa = '-a' in args
        lf = '-l' in args or '-la' in args
        paths = [x for x in args if not x.startswith('-')]
        items = self.kernel.fs.list_dir(paths[0] if paths else '.', self.cwd)
        if items is None:
            print(C.c("  Не найдено или запрещено", C.R)); return
        if not sa:
            items = [i for i in items if not i['name'].startswith('.')]
        g = self.kernel.guardian

        def cc(it):
            if it['is_dir']:
                return C.BL + C.B
            n = it['name']
            if n.lower().endswith('.x4s'):
                return C.CY + C.B
            if n.endswith('.x4'):
                return C.M
            if n.lower().endswith('.x3'):
                return C.Y + C.B
            if n.endswith('.backup'):
                return C.G
            if n.endswith('.disabled'):
                return C.DIM
            return C.W

        if lf:
            for it in items:
                tc = 'd' if it['is_dir'] else '-'
                sz = g.fmt_size(it['size']) if not it['is_dir'] else '<DIR>'
                print(f"  {tc} {sz:>10}  {it['modified'][:16]}  "
                      f"{C.c(it['name'] + ('/' if it['is_dir'] else ''), cc(it))}")
        else:
            ln = '  '
            for it in items:
                ln += C.c(it['name'] + ('/' if it['is_dir'] else ''), cc(it)) + '  '
            if ln.strip():
                print(ln)

    def c_cd(self, args):
        if not args:
            self.cwd = self.env.get('HOME', '/')
            return
        p = args[0]
        if p == '-':
            old = self._oldpwd
            self.kernel.fs.current_disk = old['disk']
            p = old['path']
        elif p == '~' or p.startswith('~/'):
            h = self.env.get('HOME', '/')
            p = h if p == '~' else h.rstrip('/') + '/' + p[2:]
        ex, rest = self.kernel.fs.parse_disk_prefix(p)
        if ex:
            self.kernel.fs.current_disk = ex
            p = rest
        r, _ = self.kernel.fs.resolve(p, self.cwd)
        if self.kernel.fs.is_dir(r):
            self._oldpwd = {'path': self.cwd, 'disk': self.kernel.fs.current_disk}
            self.cwd = r
        else:
            print(C.c(f"  Не найдено/запрещено: {args[0]}", C.R))

    def c_pwd(self, _a):
        print(f"  {self.kernel.fs.current_disk}:{self.cwd}")

    def c_mkdir(self, args):
        for p in [x for x in args if not x.startswith('-')]:
            r, _ = self.kernel.fs.resolve(p, self.cwd)
            self.kernel.fs.mkdir(r)

    def c_rmdir(self, args):
        for p in [x for x in args if not x.startswith('-')]:
            ok, msg = self.kernel.trash.put(p, self.cwd)
            print(C.c(f"  [Корзина] {msg}", C.G) if ok else C.c(f"  {msg}", C.R))

    def c_touch(self, args):
        for p in args:
            self.kernel.fs.touch(p, self.cwd)

    def c_cat(self, args):
        for p in args:
            c = self.kernel.fs.read_file(p, self.cwd)
            if c is None:
                print(C.c(f"  Нет доступа/не найден: {p}", C.R)); continue
            print(c)

    def c_echo(self, args):
        s = ' '.join(args)
        s = s.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
        if '\\\\' in s:
            s = s.replace('\\\\', '\\')
        print(s)

    def c_cp(self, args):
        if len(args) < 2:
            print("  cp <src> <dst>"); return
        print(C.c(f"  Скопировано: {args[0]} -> {args[1]}", C.G)
              if self.kernel.fs.copy(args[0], args[1], self.cwd)
              else C.c("  Ошибка", C.R))

    def c_mv(self, args):
        if len(args) < 2:
            print("  mv <src> <dst>"); return
        print(C.c(f"  Перемещено: {args[0]} -> {args[1]}", C.G)
              if self.kernel.fs.move(args[0], args[1], self.cwd)
              else C.c("  Ошибка", C.R))

    def c_rename(self, args):
        if len(args) < 2:
            print("  rename <file> <new>"); return
        print(C.c("  Переименовано", C.G)
              if self.kernel.fs.rename(args[0], args[1], self.cwd)
              else C.c("  Ошибка", C.R))

    def c_find(self, args):
        if not args:
            print("  find [path] <pattern>"); return
        p = args[0] if len(args) > 1 else '.'
        pat = args[1] if len(args) > 1 else args[0]
        for r in self.kernel.fs.find(p, pat, self.cwd):
            print(f"  {r}")

    def c_grep(self, args):
        if len(args) < 2:
            print("  grep <pattern> <file>"); return
        c = self.kernel.fs.read_file(args[1], self.cwd)
        if c is None:
            print(C.c("  Не найден", C.R)); return
        for i, l in enumerate(c.split('\n'), 1):
            if args[0] in l:
                print(f"  {i}: {l.replace(args[0], C.c(args[0], C.R + C.B))}")

    def c_wc(self, args):
        if not args:
            return
        c = self.kernel.fs.read_file(args[0], self.cwd)
        if c is None:
            print(C.c("  Не найден", C.R))
        else:
            lines = c.count('\n') + (1 if c and not c.endswith('\n') else 0)
            print(f"  {lines:>6} строк {len(c.split()):>6} слов {len(c):>6} байт")

    def c_tree(self, args):
        print(self.kernel.fs.tree(args[0] if args else '.', self.cwd))

    def c_du(self, args):
        p = args[0] if args else '.'
        if self.kernel.fs.is_dir(p, self.cwd):
            sz = self.kernel.fs.dir_size_at(p, self.cwd)
        else:
            try:
                rp, _ = self.kernel.fs._resolve_checked(p, self.cwd, write=False)
                sz = rp.stat().st_size if rp.exists() else 0
            except (OSError, PermissionError):
                sz = 0
        print(f"  {self.kernel.guardian.fmt_size(sz)}  {p}")

    def c_df(self, _a):
        g = self.kernel.guardian
        for d in self.kernel.fs.get_disks():
            u = self.kernel.fs.disk_usage(d)
            cur = " <--" if d == self.kernel.fs.current_disk else ""
            print(f"  {d}: {g.fmt_size(u)}{cur}")

    def c_id(self, args):
        u = args[0] if args else self.user
        info = self.kernel.um.get_public_info(u)
        if not info:
            print(C.c(f"  Нет: {u}", C.R)); return
        print(f"  uid={info['uid']}({u}) disk={info.get('disk','C')}: "
              f"pw={'Argon2id' if info.get('has_password',True) else 'no'}")

    def c_su(self, args):
        if not args:
            print("  su <user>"); return
        t = args[0]
        if t not in self.kernel.um.users:
            print(C.c("  Нет", C.R)); return
        if not self.kernel.um.has_password(t):
            self._do_login(t); return
        if self.kernel.um.auth(t, input("  Пароль: ")):
            self._do_login(t)
        else:
            print(C.c("  Неверный", C.R))

    def c_useradd(self, args):
        if not args:
            print("  useradd <name>"); return
        if not self._check_uac_root_action(f"Создание нового пользователя '{args[0]}'"):
            return
        name = args[0]
        pw = None
        hint = ''
        if input(f"  Пароль для {name}? (y/n): ").strip().lower() in ('y', 'yes', 'да'):
            pw = input("  Пароль: ")
            if input("  Подсказка? (y/n): ").strip().lower() in ('y', 'yes', 'да'):
                hint = input("  Подсказка: ")
        ok, err = self.kernel.um.create(name, pw, hint)
        if ok:
            with perm_root():
                for d in [f'/home/{name}', f'/home/{name}/Desktop',
                          f'/home/{name}/Documents']:
                    self.kernel.fs.mkdir(d)
            print(C.c(f"  Создан '{name}'", C.G))
            self.kernel.save_state()
        else:
            print(C.c(f"  {err}", C.R))

    def c_userdel(self, args):
        if not args:
            print("  userdel <name>"); return
        if args[0] == self.user:
            print(C.c("  Нельзя удалить текущего", C.R)); return
        if not self._check_uac_root_action(f"Удаление пользователя '{args[0]}'"):
            return
        if len(self.kernel.um.users) <= 1:
            print(C.c("  Нельзя последнего", C.R)); return
        ud = self.kernel.um.get_disk(args[0])
        if self.kernel.um.delete(args[0]):
            od = self.kernel.fs.current_disk
            with perm_root():
                self.kernel.fs.current_disk = ud
                self.kernel.fs.delete(f'/home/{args[0]}', recursive=True)
                self.kernel.fs.current_disk = od
            print(C.c("  Удалён", C.G))
            self.kernel.save_state()
        else:
            print(C.c("  Ошибка", C.R))

    def c_passwd(self, args):
        t = args[0] if args else self.user
        if t != self.user:
            print(C.c("  Только для себя", C.R)); return
        n = input("  Новый пароль (Enter = убрать): ").strip()
        if n == '':
            self.kernel.um.change_password(t, None)
            self.kernel.um.set_hint(t, '')
            print(C.c("  Пароль удалён", C.Y))
        else:
            if n != input("  Подтвердите: "):
                print(C.c("  Не совпадают", C.R)); return
            self.kernel.um.change_password(t, n)
            print(C.c("  Обновлён (Argon2id)", C.G))
            h = input("  Подсказка (Enter = оставить): ").strip()
            if h:
                self.kernel.um.set_hint(t, h)
        self.kernel.save_state()

    def c_users(self, _a):
        print("=" * 56)
        print("  Пользователи")
        print("=" * 56)
        for u in self.kernel.um.list_users():
            info = self.kernel.um.get_public_info(u) or {}
            cur = " <-- вы" if u == self.user else ""
            hp = "Argon2id" if info.get('has_password', True) else "открыт"
            print(f"  {u:<14} uid={info.get('uid','?')} [{hp}] "
                  f"диск={info.get('disk','C')}: {info.get('created','?')[:10]}{cur}")
        print("-" * 56)
        print(f"  Всего: {len(self.kernel.um.users)}")
        print("=" * 56)

    def c_x3(self, args):
        if not args:
            print("  Использование: x3 [--fast] <файл.x3> [arg1 arg2 ...]")
            return
        fast_mode = False
        if args[0] == '--fast':
            fast_mode = True
            args = args[1:]
        if not args:
            print("  Укажите файл скрипта.")
            return
        X3Runner.execute_file(self, args[0], args[1:], fast_mode=fast_mode)

    def c_newx3(self, args):
        if not args:
            print("  Использование: newx3 <имя>")
            return
        name = args[0]
        if not name.endswith('.x3'):
            name += '.x3'
        docs = self._docs()
        self.kernel.fs.write_file(f'{docs}/{name}', X3Runner.template(name))
        print(C.c(f"  X3 шаблон создан: {docs}/{name}", C.G))

    def c_backup(self, args):
        if not args or args[0] == 'list':
            with perm_root():
                backups = BackupManager.list_backups()
            print("=" * 66)
            print("  Резервные копии (.backup)")
            print("=" * 66)
            if not backups:
                print(C.c("  Нет копий.", C.DIM))
            else:
                for b in backups:
                    sz = self.kernel.guardian.fmt_size(b['size'])
                    ts = b['time'][:19].replace('T', ' ')
                    vb = C.c("[OK]", C.G) if b['valid'] else C.c("[ПОВРЕЖДЕНА!]", C.R + C.B)
                    print(f"  {b['name']:<30} {sz:>9} {vb} {ts}")
            print("-" * 66)
            print("  backup create [n] | backup restore <n> | backup rm <n>")
            print("=" * 66)
            return
        sub = args[0]
        if sub == 'create':
            name = args[1] if len(args) > 1 else None
            print(C.c("  Создание...", C.CY))
            with perm_root():
                ok, res = BackupManager.create_backup(name, self.kernel)
            if ok:
                sz = self.kernel.guardian.fmt_size(res.stat().st_size)
                print(C.c(f"  {res.name} ({sz})", C.G))
            else:
                print(C.c(f"  Ошибка: {res}", C.R))
        elif sub == 'restore':
            if len(args) < 2:
                print(C.c("  backup restore <n>", C.R)); return
            if not self._check_uac_root_action(f"Восстановление бэкапа '{args[1]}'"):
                return
            bdir = BackupManager.get_backup_dir()
            fn = args[1] if args[1].endswith('.backup') else args[1] + '.backup'
            bp = bdir / fn
            if not bp.exists():
                print(C.c(f"  Нет: {fn}", C.R)); return
            with perm_root():
                v, err, _ = BackupManager.verify_backup(bp)
            if not v:
                print(C.c(f"  Повреждена! ({err})", C.R + C.B)); return
            print(C.c("  Восстановление...", C.CY))
            with perm_root():
                ok, msg = BackupManager.restore_backup(bp, self.kernel)
            if ok:
                print(C.c(f"  {msg}! Перезапуск...", C.G))
                time.sleep(1.0)
                sp = get_script_path()
                os.execv(sys.executable, [sys.executable, str(sp)] + sys.argv[1:])
            else:
                print(C.c(f"  Ошибка: {msg}", C.R))
        elif sub in ('rm', 'delete'):
            if len(args) < 2:
                print(C.c("  backup rm <n>", C.R)); return
            bdir = BackupManager.get_backup_dir()
            fn = args[1] if args[1].endswith('.backup') else args[1] + '.backup'
            bp = bdir / fn
            if bp.exists():
                try:
                    bp.unlink()
                    print(C.c(f"  Удалено: {fn}", C.G))
                except (OSError, PermissionError) as e:
                    print(C.c(f"  {e}", C.R))
            else:
                print(C.c(f"  Нет: {fn}", C.R))

    def c_cache(self, args):
        if not args or args[0] == 'list':
            items = self.kernel.fs.list_dir('/cache')
            print("=" * 52)
            print("  /cache")
            print("=" * 52)
            if not items:
                print(C.c("  Пусто.", C.DIM))
            else:
                t = 0
                for it in items:
                    sz = self.kernel.guardian.fmt_size(it['size']) if not it['is_dir'] else '<DIR>'
                    t += it['size']
                    print(f"  {it['name']:<28} {sz:>10}  {it['modified'][:16]}")
                print("-" * 52)
                print(f"  Всего: {self.kernel.guardian.fmt_size(t)}")
            print("-" * 52)
            print("  cache clear | cache cat <f> | cache rm <f>")
            print("=" * 52)
            return
        sub = args[0]
        if sub in ('clear', 'clean'):
            items = self.kernel.fs.list_dir('/cache')
            c = 0
            if items:
                for it in items:
                    self.kernel.fs.delete(f"/cache/{it['name']}", recursive=True)
                    c += 1
            print(C.c(f"  Очищено {c} объектов.", C.G))
        elif sub == 'cat':
            if len(args) < 2:
                print(C.c("  cache cat <f>", C.R)); return
            c = self.kernel.fs.read_file(f"/cache/{args[1]}")
            if c is not None:
                print(c)
            else:
                print(C.c(f"  Нет: {args[1]}", C.R))
        elif sub == 'rm':
            if len(args) < 2:
                print(C.c("  cache rm <f>", C.R)); return
            if self.kernel.fs.delete(f"/cache/{args[1]}", recursive=True):
                print(C.c(f"  Удалено: {args[1]}", C.G))
            else:
                print(C.c(f"  Нет: {args[1]}", C.R))

    def c_smartmem(self, args):
        s = self.kernel.settings
        if not args:
            st = C.c('ON', C.G) if s.smart_memory else C.c('OFF', C.DIM)
            print("=" * 50)
            print("  Smart Memory")
            print("=" * 50)
            print(f"  Статус: {st}")
            print("  smartmem on | off | clean")
            print("=" * 50)
            return
        if args[0] == 'on':
            s.smart_memory = True
            print(C.c("  ON", C.G))
            self.kernel.run_smart_memory_cleanup()
            self.kernel.save_state()
        elif args[0] == 'off':
            s.smart_memory = False
            print(C.c("  OFF", C.Y))
            self.kernel.save_state()
        elif args[0] == 'clean':
            prev = s.smart_memory
            s.smart_memory = True
            d, f = self.kernel.run_smart_memory_cleanup()
            s.smart_memory = prev
            print(C.c(f"  Очищено: {d} папок, {f} файлов.", C.G))

    def c_history(self, args):
        if not self.kernel.history:
            return
        if args and args[0] == 'clear':
            self.kernel.history.clear()
            print(C.c("  Очищено", C.G)); return
        if args and args[0] == 'search':
            pat = ' '.join(args[1:])
            for e in self.kernel.history.search(pat):
                print(f"  {C.c(e['time'][:19], C.DIM)}  {e['cmd']}")
            return
        for i, e in enumerate(self.kernel.history.get_all(), 1):
            print(f"  {i:>4}  {C.c(e['time'][:19], C.DIM)}  {e['cmd']}")

    def c_logs(self, args):
        with perm_root():
            items = self.kernel.fs.list_dir('/apps/logs')
        if not args:
            logs = [i for i in (items or []) if i['name'].endswith('.json')]
            if not logs:
                print(C.c("  Логов нет.", C.G)); return
            for it in logs:
                print(f"  {it['name']:<35} {self.kernel.guardian.fmt_size(it['size']):>8}")
            return
        if args[0] == 'clear':
            c = 0
            with perm_root():
                for it in (items or []):
                    if it['name'].endswith('.json'):
                        self.kernel.fs.delete(f"/apps/logs/{it['name']}")
                        c += 1
            print(C.c(f"  Удалено: {c}", C.G))
            return
        fn = args[0] if args[0].endswith('.json') else args[0] + '.json'
        with perm_root():
            c = self.kernel.fs.read_file(f'/apps/logs/{fn}')
        if c:
            print(c)
        else:
            print(C.c(f"  Нет: {fn}", C.R))

    def c_neofetch(self, _a):
        k = self.kernel
        g = k.guardian
        data = {'OS': f'PyOS v{Kernel.VERSION}', 'Build': Kernel.BUILD,
                'Company': Kernel.COMPANY,
                'Security': 'Argon2id + Nexus + AST',
                'Permissions': 'Root/User/Program',
                'UAC Control': k.settings.get_uac_name(),
                'Computer': k.hostname, 'User': self.user,
                'Language': k.settings.lang.upper(),
                'AutoBackup': k.settings.auto_backup,
                'Session': g.session_str(),
                'Time': k.get_now().strftime('%H:%M:%S'),
                'Disks': ' '.join(d + ':' for d in k.fs.get_disks()),
                'Apps': str(len(k.apps.apps)) if k.apps else '0',
                'SmartMem': 'ON' if k.settings.smart_memory else 'OFF',
                'Python': sys.version.split()[0]}
        print("=" * 48)
        print("  Информация о системе")
        print("=" * 48)
        for key, val in data.items():
            print(f"  {key:<14}: {val}")
        print("=" * 48)

    def c_suggest(self, args):
        g = self.kernel.guardian
        if not args:
            print(f"  Подсказки: {'ON' if g.suggest_commands else 'OFF'}")
            return
        if args[0] == 'on':
            g.suggest_commands = True
            print(C.c("  Включены", C.G))
        elif args[0] == 'off':
            g.suggest_commands = False
            print(C.c("  Отключены", C.Y))
        self.kernel.save_state()

    def c_guardian(self, args):
        if args and args[0] in ('update', 'updates'):
            self._ui_update_center(); return
        if args and args[0] in ('github', 'git'):
            self._ui_github_update(); return
        if args and args[0] in ('uninstall', 'destroy'):
            self._ui_uninstall_center(); return
        self._guardian_screen()

    def _guardian_screen(self):
        while True:
            clear()
            g = self.kernel.guardian
            report = g.disk_report(self.kernel.fs)
            lim = f"{g.daily_limit} мин" if g.daily_limit else "Без лимита"
            ac = g.check_all_apps(self.kernel.fs)
            print("=" * 56)
            print("  Guardian — Безопасность & Оптимизация")
            print("=" * 56)
            print(f"  Сессия:          {g.session_str()} (лимит: {lim})")
            print(f"  Диск занято:     {g.fmt_size(report['total'])}")
            print(f"  Автобэкап:       {C.c(self.kernel.settings.auto_backup, C.CY)}")
            print(f"  UAC Контроль:    {C.c(self.kernel.settings.get_uac_name(), C.CY)}")
            print(f"  Лимит на app:    {g.fmt_size(g.app_folder_limit)}")
            if ac:
                print("-" * 56)
                for a in ac:
                    st = C.c("ПЕРЕПОЛНЕНИЕ!", C.R) if a['over'] else C.c("OK", C.G)
                    print(f"    {a['name']:<16} {g.fmt_size(a['size']):>8} {st}")
            print("-" * 56)
            print("  1. Проверить обновления на GitHub")
            print("  2. Центр обновлений PyOS (Локально/Патчи)")
            print("  3. Оптимизация памяти приложений")
            print("  4. Деинсталляция PyOS")
            print("  0. Назад")
            print("=" * 56)
            try:
                ch = input(C.c("  Выберите (0-4): ", C.W)).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if ch in ('0', 'q', 'exit', ''):
                break
            elif ch == '1':
                self._ui_github_update()
            elif ch == '2':
                self._ui_update_center()
            elif ch == '3':
                print()
                any_c = False
                for it in self.kernel.fs.list_dir('/apps/data') or []:
                    if it['is_dir']:
                        d = g.cleanup_app_folder(self.kernel.fs, it['name'])
                        if d:
                            any_c = True
                            print(C.c(f"  Очищено в {it['name']}: {len(d)}", C.G))
                if not any_c:
                    print(C.c("  Все в норме.", C.G))
                input(C.c("\n  Enter...", C.DIM))
            elif ch == '4':
                if self._ui_uninstall_center():
                    return
        self._do_desktop()

    def _ui_github_update(self):
        clear()
        print("=" * 64)
        print("  Guardian: Поиск обновлений на GitHub")
        print("=" * 64)
        print(f"  Текущая версия: v{Kernel.VERSION} (build {Kernel.BUILD})")
        print("  Репозиторий:    https://github.com/bogdangotj/PYOS")
        print("-" * 64)
        
        done_event = threading.Event()
        res_data = [False, "", ""]

        def _on_check(ok, ver, bld):
            res_data[0] = ok
            res_data[1] = ver
            res_data[2] = bld
            done_event.set()

        self.kernel.guardian.check_github_update_async(Kernel.VERSION, _on_check)

        print("  [Подключение к GitHub...]", end="", flush=True)
        ticks = 0
        while not done_event.is_set():
            time.sleep(0.2)
            print(".", end="", flush=True)
            ticks += 1
            if ticks > 35:  # Ограничение точек прогресса (защита от бесконечного зависания)
                print("\n  [Предупреждение: ответ от GitHub задерживается...]")
                break
        print("\n")

        ok, ver, bld = res_data
        if not ok:
            print(C.c(f"  Ошибка проверки: {ver}", C.R))
            input(C.c("\n  Enter...", C.DIM))
            return
            
        if ver == Kernel.VERSION and bld == Kernel.BUILD:
            print(C.c("  У вас установлена самая свежая версия!", C.G + C.B))
            input(C.c("\n  Enter...", C.DIM))
            return

        print(C.c(f"  Найдена новая версия: v{ver} (build {bld})!", C.G + C.B))
        print("  1. Загрузить и установить прямо сейчас")
        print("  0. Отмена")
        try:
            c = input(C.c("  > ", C.W)).strip()
        except (EOFError, KeyboardInterrupt):
            return
        if c == '1':
            if not self._check_uac_root_action("Установка обновления ядра с GitHub"):
                return
            print(C.c("  Загрузка исходного кода с GitHub...", C.CY))
            try:
                code = self.kernel.guardian.download_github_code()
                ok_u, msg = self.kernel.guardian.apply_full_code_update(code, self.kernel)
                if ok_u:
                    print(C.c(f"  {msg}", C.G))
                    print(C.c("  Перезапуск PyOS...", C.CY))
                    time.sleep(1.2)
                    sp = get_script_path()
                    os.execv(sys.executable, [sys.executable, str(sp)] + sys.argv[1:])
                else:
                    print(C.c(f"  Ошибка установки: {msg}", C.R))
            except Exception as e:
                print(C.c(f"  Ошибка: {e}", C.R))
            input(C.c("\n  Enter...", C.DIM))

    def _ui_update_center(self):
        clear()
        sp = get_script_path()
        ch = compute_file_hash(sp)
        print("=" * 64)
        print("  Guardian: Локальный центр обновлений")
        print("=" * 64)
        print(f"  Версия: v{Kernel.VERSION} (build {Kernel.BUILD})")
        print(f"  Argon2id+salt: {C.c(ch, C.CY)}")
        print("-" * 64)
        print("  1. Применить патч (.patch PyOS/Git Diff)")
        print("  2. Вставить патч вручную")
        print("  3. Установить новый файл кода (.py)")
        print("  0. Отмена")
        print("=" * 64)
        try:
            c = input(C.c("  (0-3): ", C.W)).strip()
        except (EOFError, KeyboardInterrupt):
            return
        if c in ('0', 'q', 'exit', ''):
            return
        if not self._check_uac_root_action("Применение системных обновлений"):
            return
        if c == '1':
            pp = input("  Путь: ").strip()
            if not pp:
                return
            ct = self.kernel.fs.read_file(pp, self.cwd)
            if not ct:
                pr = Path(pp)
                if pr.is_file():
                    ct = pr.read_text(encoding='utf-8', errors='replace')
            if not ct:
                print(C.c("  Не найден!", C.R)); time.sleep(1.5); return
            self._execute_patch(ct)
        elif c == '2':
            print(C.c("\n  Вставьте ([BEGIN PYOS PATCH]...[END PYOS PATCH])", C.Y))
            print(C.c("  Строка 'EOF' для завершения:", C.DIM))
            lines = []
            while True:
                try:
                    l = input()
                    if l.strip() == 'EOF':
                        break
                    lines.append(l)
                except (EOFError, KeyboardInterrupt):
                    break
            raw = "\n".join(lines).strip()
            if raw:
                self._execute_patch(raw)
        elif c == '3':
            cf = input("  Путь (.py): ").strip()
            if not cf:
                return
            ct = self.kernel.fs.read_file(cf, self.cwd)
            if not ct:
                pr = Path(cf)
                if pr.is_file():
                    ct = pr.read_text(encoding='utf-8', errors='replace')
            if not ct:
                print(C.c("  Не найден!", C.R)); time.sleep(1.5); return
            print(C.c("  Верификация...", C.CY))
            ok, msg = self.kernel.guardian.apply_full_code_update(ct, self.kernel)
            if ok:
                print(C.c(f"  {msg}", C.G))
                print(C.c("  Перезапуск...", C.CY))
                time.sleep(1.2)
                sp = get_script_path()
                os.execv(sys.executable, [sys.executable, str(sp)] + sys.argv[1:])
            else:
                print(C.c(f"  Ошибка: {msg}", C.R))
                input(C.c("\n  Enter...", C.DIM))

    def _execute_patch(self, patch_str):
        print(C.c("\n  Проверка и наложение диффа...", C.CY))
        ok, msg = self.kernel.guardian.apply_patch_update(patch_str, self.kernel)
        if ok:
            print(C.c(f"  {msg}", C.G))
            print(C.c("  Перезапуск...", C.CY))
            time.sleep(1.2)
            sp = get_script_path()
            os.execv(sys.executable, [sys.executable, str(sp)] + sys.argv[1:])
        else:
            print(C.c(f"  Ошибка:\n{msg}", C.R))
            input(C.c("\n  Enter...", C.DIM))

    def _ui_uninstall_center(self):
        clear()
        print("=" * 64)
        print(C.c("  МАСТЕР УДАЛЕНИЯ PYOS", C.R + C.B))
        print("=" * 64)
        print("  1. Полное удаление")
        print("  2. Удаление с бэкапом")
        print("  0. Отмена")
        print("=" * 64)
        try:
            c = input(C.c("  (0-2): ", C.W)).strip()
        except (EOFError, KeyboardInterrupt):
            return False
        if c not in ('1', '2'):
            return False
        
        print(C.c("\n  [ВНИМАНИЕ] Вы собираетесь полностью удалить PyOS!", C.R + C.B))
        print(C.c(f"  Для подтверждения введите ваше имя пользователя ('{self.user}'): ", C.Y), end="")
        try:
            confirm_user = input().strip()
        except (EOFError, KeyboardInterrupt):
            return False
        
        if confirm_user != self.user:
            print(C.c("  Имя пользователя не совпадает. Операция отменена.", C.R))
            time.sleep(1.5)
            return False

        confirm_phrase = f"DELETE {self.user}"
        print(C.c(f"  Введите '{confirm_phrase}' для окончательного подтверждения: ", C.R), end="")
        try:
            confirm_p = input().strip()
        except (EOFError, KeyboardInterrupt):
            return False

        if confirm_p.strip() != confirm_phrase:
            print(C.c("  Подтверждающая фраза не совпала. Удаление отменено.", C.R))
            time.sleep(1.5)
            return False

        mode = 'full' if c == '1' else 'backup'
        print(C.c("\n  Выполняется деинсталляция...", C.Y))
        ok, bp = self.kernel.guardian.uninstall_pyos(mode, self.kernel)
        if ok:
            clear()
            print("=" * 60)
            print(C.c("  PyOS деинсталлирована.", C.G + C.B))
            if bp:
                print(f"  Бэкап сохранён: {bp}")
            print("=" * 60)
            sys.exit(0)
        return False

    def _ui_app_store(self):
        while True:
            clear()
            print("=" * 66)
            print("  🛒 Центр Приложений PyOS (GitHub AppStore)")
            print("=" * 66)
            print("  [Подключение к репозиторию GitHub...]")
            
            ok, apps = self.kernel.guardian.fetch_store_apps()
            if not ok:
                print(C.c(f"  Ошибка загрузки списка приложений: {apps}", C.R))
                input(C.c("\n  Enter...", C.DIM))
                break

            print("-" * 66)
            if not apps:
                print(C.c("  В репозитории GitHub пока нет приложений.", C.Y))
            else:
                for idx, app_name in enumerate(apps, 1):
                    installed = " [Установлено]" if app_name in self.kernel.apps.apps else ""
                    print(f"  {idx:>2}. {app_name:<25}{C.c(installed, C.G)}")

            print("-" * 66)
            print("  S. Поиск приложений")
            print("  R. Обновить список (сбросить кэш)")
            print("  0. Назад")
            print("=" * 66)
            
            try:
                choice = input(C.c("  Выберите действие или номер приложения: ", C.W)).strip()
            except (EOFError, KeyboardInterrupt):
                break

            if choice in ('0', 'q', 'exit'):
                break

            if choice.lower() == 'r':
                print(C.c("  Обновление кэша...", C.CY))
                self.kernel.guardian.fetch_store_apps(force_refresh=True)
                continue

            if choice.lower() == 's':
                query = input("  Поиск: ").strip().lower()
                matched = [a for a in apps if query in a.lower()]
                print()
                if not matched:
                    print(C.c("  Ничего не найдено.", C.R))
                else:
                    print(C.c("  Результаты поиска:", C.CY))
                    for m in matched:
                        print(f"    • {m}")
                input(C.c("\n  Enter...", C.DIM))
                continue

            if choice.isdigit() and 1 <= int(choice) <= len(apps):
                selected_app = apps[int(choice) - 1]
                self._ui_app_store_download(selected_app)

    def _ui_app_store_download(self, app_name):
        clear()
        print("=" * 60)
        print(f"  Приложение: {C.c(app_name, C.G + C.B)}")
        print("=" * 60)
        print("  Получение доступных версий...")
        
        ok, versions = self.kernel.guardian.fetch_app_versions(app_name)
        print("-" * 60)
        print("  Доступные версии:")
        for idx, ver in enumerate(versions, 1):
            print(f"    {idx}. {ver}")
        print("-" * 60)
        print("  0. Отмена")
        
        try:
            v_choice = input(C.c("  Выберите версию для скачивания (по умолч. 1): ", C.W)).strip()
        except (EOFError, KeyboardInterrupt):
            return

        if v_choice in ('0', 'q'):
            return

        target_ver = versions[0]
        if v_choice.isdigit() and 1 <= int(v_choice) <= len(versions):
            target_ver = versions[int(v_choice) - 1]

        # Исправлено: если версия одна и является fallback-файлом .x4, качаем напрямую без подпапки
        if len(versions) == 1 and '/' not in target_ver:
            app_rel_path = target_ver
        else:
            app_rel_path = f"{app_name}/{target_ver}"
            if not app_rel_path.startswith(app_name):
                app_rel_path = f"{app_name}/{target_ver}"

        print(C.c(f"\n  Загрузка {app_rel_path}...", C.CY))
        try:
            data = self.kernel.guardian.download_app_file(app_rel_path)
            target_filename = Path(target_ver).name
            
            with perm_root():
                self.kernel.fs.mkdir('/apps/store')
                if isinstance(data, bytes):
                    self.kernel.fs.write_bytes(f'/apps/store/{target_filename}', data)
                else:
                    self.kernel.fs.write_file(f'/apps/store/{target_filename}', str(data))

            ok_i, msg = self.kernel.apps.install(target_filename, home_dir=self.env['HOME'])
            if ok_i:
                print(C.c(f"  {msg}", C.G + C.B))
            else:
                print(C.c(f"  Ошибка установки: {msg}", C.R))
        except Exception as e:
            print(C.c(f"  Ошибка скачивания: {e}", C.R))

        input(C.c("\n  Enter...", C.DIM))

    def _ui_app_tags(self):
        apps = self.kernel.apps.apps
        if not apps:
            print(C.c("  Тут пока пусто, но вы можете найти приложения в Центре приложений!", C.Y))
            input(C.c("\n  Enter...", C.DIM))
            return
        tm = {}
        for an, ad in apps.items():
            t = ad.get('info', {}).get('tag', 'Other').strip() or 'Other'
            tm.setdefault(t.capitalize(), []).append(an)
        st = sorted(tm.keys(), key=lambda x: len(tm[x]), reverse=True)
        print()
        print("=" * 50)
        print("  Теги приложений")
        print("=" * 50)
        for i, t in enumerate(st, 1):
            print(f"  {i}. {t} ({len(tm[t])}) [Установлено]")
        print("=" * 50)
        print("  0. Отмена")
        print()
        try:
            c = input(C.c("  Тег: ", C.W)).strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not c or c in ('0', 'q', 'exit'):
            return
        if not c.isdigit() or not (1 <= int(c) <= len(st)):
            print(C.c("  Неверно.", C.R)); return
        ch = st[int(c) - 1]
        ai = sorted(tm[ch])
        print()
        print("=" * 50)
        print(f"  Приложения [{ch}]")
        print("=" * 50)
        for i, an in enumerate(ai, 1):
            info = self.kernel.apps.get_info(an)
            print(f"  {i}. {an:<14} v{info.get('version','1.0'):<5} - "
                  f"{info.get('description','')[:30]}")
        print("=" * 50)
        print("  0. Назад")
        print()
        try:
            ac = input(C.c("  Выбор: ", C.G)).strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not ac or ac in ('0', 'q', 'exit'):
            return
        if not ac.isdigit() or not (1 <= int(ac) <= len(ai)):
            print(C.c("  Неверно.", C.R)); return
        sel = ai[int(ac) - 1]
        clear()
        self.kernel.apps.run(sel, self)
        self._do_desktop()

    def _ui_app_manager(self):
        while True:
            clear()
            apps = self.kernel.apps.apps
            dis = self.kernel.apps.list_disabled()
            print("=" * 56)
            print("  Менеджер Программ")
            print("=" * 56)
            print(f"  Активных: {len(apps)} | Отключенных: {len(dis)}")
            print("-" * 56)
            print("  1. Центр приложений (GitHub App Store)")
            print("  2. Удалить приложение (данные → cache)")
            print("  3. Обновить приложение")
            print("  4. Отключить (сжать)")
            print("  5. Включить (распаковать)")
            print("  6. Список приложений")
            print("  0. Назад")
            print("=" * 56)
            try:
                c = input(C.c("  (0-6): ", C.W)).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if c in ('0', 'q', 'exit', ''):
                break
            if c == '1':
                self._ui_app_store()
            elif c == '2':
                al = sorted(apps.keys())
                if not al:
                    print(C.c("  Нет.", C.Y)); time.sleep(1.2); continue
                for i, an in enumerate(al, 1):
                    print(f"  {i}. {an}")
                print("  0. Отмена")
                s = input("  Номер: ").strip()
                if s.isdigit() and 1 <= int(s) <= len(al):
                    d = al[int(s) - 1]
                    if input(C.c(f"  Удалить '{d}'? (y/n): ", C.Y)).lower() in ('y', 'yes', 'да'):
                        ok, msg = self.kernel.apps.remove(d, backup_data_to_cache=True)
                        print(C.c(f"  {msg}", C.G if ok else C.R))
                input(C.c("\n  Enter...", C.DIM))
            elif c == '3':
                al = sorted(apps.keys())
                if not al:
                    print(C.c("  Нет.", C.Y)); time.sleep(1.2); continue
                for i, an in enumerate(al, 1):
                    v = self.kernel.apps.get_info(an).get('version', '?')
                    print(f"  {i}. {an} (v{v})")
                print("  0. Отмена")
                s = input("  Номер: ").strip()
                if s.isdigit() and 1 <= int(s) <= len(al):
                    ua = al[int(s) - 1]
                    np = input("  Путь к новому .x4: ").strip()
                    if np:
                        ok, msg = self.kernel.apps.update_app(ua, np, self.cwd)
                        print(C.c(f"  {msg}", C.G if ok else C.R))
                input(C.c("\n  Enter...", C.DIM))
            elif c == '4':
                al = sorted(apps.keys())
                if not al:
                    print(C.c("  Нет.", C.Y)); time.sleep(1.2); continue
                for i, an in enumerate(al, 1):
                    print(f"  {i}. {an}")
                print("  0. Отмена")
                s = input("  Номер: ").strip()
                if s.isdigit() and 1 <= int(s) <= len(al):
                    fa = al[int(s) - 1]
                    print(C.c(f"  Сжатие '{fa}'...", C.CY))
                    ok, msg = self.kernel.apps.disable(fa)
                    print(C.c(f"  {msg}", C.G if ok else C.R))
                input(C.c("\n  Enter...", C.DIM))
            elif c == '5':
                dl = sorted(dis)
                if not dl:
                    print(C.c("  Нет отключенных.", C.DIM)); time.sleep(1.2); continue
                for i, an in enumerate(dl, 1):
                    print(f"  {i}. {an} [отключено]")
                print("  0. Отмена")
                s = input("  Номер: ").strip()
                if s.isdigit() and 1 <= int(s) <= len(dl):
                    uf = dl[int(s) - 1]
                    print(C.c(f"  Восстановление '{uf}'...", C.CY))
                    ok, msg = self.kernel.apps.enable(uf)
                    print(C.c(f"  {msg}", C.G if ok else C.R))
                input(C.c("\n  Enter...", C.DIM))
            elif c == '6':
                self.c_app(['list'])
                input(C.c("\n  Enter...", C.DIM))
        self._do_desktop()

    def c_app(self, args):
        if not self.kernel.apps:
            print(C.c("  Приложения недоступны", C.R)); return
        if not args:
            print("  app store | app tags | app manager")
            print("  app <run|list|info|install|remove|disable|enable> [name]")
            return
        act = args[0].lower()
        if act == 'store':
            self._ui_app_store()
        elif act == 'tags':
            self._ui_app_tags()
        elif act in ('manager', 'manage'):
            self._ui_app_manager()
        elif act == 'run':
            if len(args) < 2:
                print("  app run <name>"); return
            ok, err = self.kernel.apps.run(args[1], self)
            if not ok:
                print(C.c(f"  {err}", C.R))
            self._do_desktop()
        elif act == 'list':
            apps = self.kernel.apps.apps
            g = self.kernel.guardian
            print("=" * 66)
            print("  Установленные приложения")
            print("=" * 66)
            if not apps:
                dis = self.kernel.apps.list_disabled()
                if dis:
                    print(C.c(f"  Активных приложений нет, но есть отключенные: {', '.join(dis)}", C.Y))
                else:
                    print(C.c("  Тут пока пусто, но вы можете найти приложения в Центре приложений!", C.Y))
            else:
                for name, data in apps.items():
                    info = data.get('info', {})
                    fmt = data.get('format', 'x4').upper()
                    fb = C.c("[X4S]", C.CY + C.B) if fmt == 'X4S' else C.c("[x4]", C.M)
                    tag = f"[{info.get('tag','Other')}]"
                    cur, _, _ = g.check_app_folder(self.kernel.fs, name)
                    print(f"  {name:<12} {fb} v{info.get('version','?'):<5} "
                          f"{g.fmt_size(cur):>6} {tag:<12} "
                          f"{info.get('description','')[:16]}")
            dis = self.kernel.apps.list_disabled()
            if dis:
                print("-" * 66)
                print(C.c(f"  Отключенные: {', '.join(dis)}", C.DIM))
            print("-" * 66)
            print(f"  Активно: {len(apps)} | Отключено: {len(dis)}")
            print("=" * 66)
        elif act == 'info':
            if len(args) < 2:
                return
            info = self.kernel.apps.get_info(args[1])
            if info:
                print("=" * 44)
                print(f"  Информация: {args[1]}")
                print("=" * 44)
                for k, v in info.items():
                    print(f"  {k}: {v}")
                print("=" * 44)
            else:
                print(C.c("  Нет", C.R))
        elif act == 'install':
            if len(args) < 2:
                print("  app install <file.x4|.x4s>"); return
            ok, msg = self.kernel.apps.install(args[1], self.cwd, home_dir=self.env['HOME'])
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif act == 'remove':
            if len(args) < 2:
                return
            ok, msg = self.kernel.apps.remove(args[1], backup_data_to_cache=True)
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif act == 'disable':
            if len(args) < 2:
                return
            ok, msg = self.kernel.apps.disable(args[1])
            print(C.c(f"  {msg}", C.G if ok else C.R))
        elif act == 'enable':
            if len(args) < 2:
                return
            ok, msg = self.kernel.apps.enable(args[1])
            print(C.c(f"  {msg}", C.G if ok else C.R))

    def c_newapp(self, args):
        if not args:
            print("  newapp <name> [tag]"); return
        name = args[0]
        tag = args[1] if len(args) > 1 else "Technical"
        docs = self._docs()
        self.kernel.fs.write_file(f'{docs}/{name}.x4',
                                  X4Parser.template(name, self.user, tag=tag))
        print(C.c(f"  Шаблон: {docs}/{name}.x4 (Тег: {tag})", C.G))

    def c_disk(self, args):
        g = self.kernel.guardian
        if not args:
            for d in self.kernel.fs.get_disks():
                u = self.kernel.fs.disk_usage(d)
                cur = " <--" if d == self.kernel.fs.current_disk else ""
                print(f"  {d}: {g.fmt_size(u)}{cur}")
            return
        if args[0] == 'add':
            if len(args) < 2:
                print("  disk add <буква>"); return
            if not self._check_uac_root_action(f"Создание виртуального диска {args[1]}:"):
                return
            l = args[1].upper()
            if len(l) != 1 or not l.isalpha():
                print(C.c("  A-Z", C.R)); return
            if l in self.kernel.fs.get_disks():
                print(C.c(f"  {l}: уже есть", C.R)); return
            with perm_root():
                self.kernel.fs.create_disk(l)
            print(C.c(f"  Диск {l}: создан", C.G))
            self.kernel.save_state()

    def c_edit(self, args):
        if not args:
            print("  edit <file>"); return
        p = args[0]
        docs = self._docs()
        fp = f"{docs}/{p}" if '/' not in p and not p.startswith('/') and ':' not in p else p
        c = self.kernel.fs.read_file(fp, self.cwd)
        if c is not None and '\0' in c:
            print(C.c("  Бинарный не поддерживается.", C.R)); return
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
                self._do_desktop(); return
            if inp == ':wq':
                self.kernel.fs.write_file(fp, '\n'.join(new), self.cwd)
                print(f"  Сохранено: {fp}")
                self._do_desktop(); return
            if inp in (':w', ':s'):
                self.kernel.fs.write_file(fp, '\n'.join(new), self.cwd)
                print("  Сохранено"); continue
            if inp == ':p':
                for i, l in enumerate(new):
                    print(f"  {C.c(str(i+1).rjust(3), C.DIM)} | {l}")
                continue
            new.append(inp)
            print(f"  {C.c(str(len(new)).rjust(3), C.DIM)} | {inp}")

    def c_settings(self, args):
        s = self.kernel.settings
        now = self.kernel.get_now()
        if not args:
            print("=" * 52)
            print(f"  Настройки — PyOS {Kernel.VERSION}")
            print("=" * 52)
            print(f"  Язык:         {s.lang.upper()}")
            print(f"  AutoBackup:   {C.c(s.auto_backup, C.CY)}")
            print(f"  UAC Контроль: {C.c(s.get_uac_name(), C.CY)}")
            print(f"  X3 Скорость:  {C.c(s.x3_speed, C.CY)}")
            print(f"  Время:        {now.strftime('%H:%M:%S')}")
            print(f"  Дата:         {now.strftime('%Y-%m-%d')}")
            print(f"  Debug:        {C.c('ON',C.Y) if s.debug_mode else C.c('OFF',C.DIM)}")
            print(f"  Smart Memory: {C.c('ON',C.G) if s.smart_memory else C.c('OFF',C.DIM)}")
            print("-" * 52)
            print("  settings lang ru|en")
            print("  settings uac 1|2|3|4")
            print("  settings x3_speed fast|normal")
            print("  settings autobackup off|at_start|at_shutdown|hourly")
            print("  settings debug on|off")
            print("  settings smartmem on|off|clean")
            print("=" * 52)
            return
        sub = args[0]
        if sub == 'uac' and len(args) > 1:
            self.c_uac(args[1:])
        elif sub == 'x3_speed' and len(args) > 1:
            val = args[1].lower()
            if val in ('fast', 'normal'):
                s.x3_speed = val
                print(C.c(f"  Скорость X3 → {s.x3_speed}", C.G))
                self.kernel.save_state()
            else:
                print(C.c("  x3_speed fast|normal", C.R))
        elif sub == 'lang':
            if len(args) > 1 and args[1].lower() in ('ru', 'en'):
                s.lang = args[1].lower()
                print(C.c(f"  Язык → {s.lang.upper()}", C.G))
                self.kernel.save_state()
            else:
                print(C.c("  settings lang ru|en", C.R))
        elif sub == 'autobackup':
            if len(args) > 1 and args[1].lower() in SettingsManager.VALID_AUTOBACKUP:
                s.auto_backup = args[1].lower()
                print(C.c(f"  AutoBackup → {s.auto_backup}", C.G))
                self.kernel.save_state()
            else:
                print(C.c("  off|at_start|at_shutdown|hourly", C.R))
        elif sub == 'smartmem':
            self.c_smartmem(args[1:])
        elif sub == 'debug':
            if len(args) < 2:
                return
            if args[1] == 'on':
                s.debug_mode = True
                print(C.c("  Debug ON", C.Y))
                self.kernel.save_state()
            elif args[1] == 'off':
                s.debug_mode = False
                print(C.c("  Debug OFF", C.G))
                self.kernel.save_state()

    def c_alias(self, args):
        if not args:
            for k, v in self.aliases.items():
                print(f"  {k}='{v}'")
            return
        s = ' '.join(args)
        if '=' in s:
            n, v = s.split('=', 1)
            self.aliases[n.strip()] = v.strip("'\"")

    def c_export(self, args):
        if not args:
            for k, v in sorted(self.env.items()):
                print(f"  {k}={v}")
            return
        for x in args:
            if '=' in x:
                k, v = x.split('=', 1)
                self.env[k] = v

    def c_realpath(self, args):
        p = args[0] if args else '.'
        try:
            rp, dk = self.kernel.fs._resolve_checked(p, self.cwd, write=False)
            vp, _ = self.kernel.fs.resolve(p, self.cwd)
            print(f"  {dk}:{vp} -> {rp}")
        except PermissionError:
            print(C.c("  Доступ запрещён.", C.R))

    def c_debug(self, args):
        if not self.kernel.settings.debug_mode:
            print(C.c("  Debug выключен. 'settings debug on'", C.Y)); return
        if not self.kernel.debug:
            print(C.c("  Не инициализирован", C.R)); return
        if not args:
            errs = self.kernel.debug.get_recent(15)
            if not errs:
                print(C.c("  Ошибок нет", C.DIM)); return
            for e in errs:
                t = e.get('time', '')[11:19]
                print(f"  #{e.get('id','?'):<3} [{e.get('source','?')[:10]}] "
                      f"{e.get('message','')[:35]} {C.c(t, C.DIM)}")
            return
        if args[0] == 'clear':
            self.kernel.debug.clear()
            print(C.c("  Очищено", C.G))

    def c_notif(self, args):
        nc = self.kernel.notifications
        if not args:
            all_n = nc.get_all()
            if not all_n:
                print(C.c("  Нет уведомлений", C.DIM)); return
            for n in all_n[-15:]:
                rm = C.c('+', C.G) if n['read'] else C.c('*', C.Y)
                print(f"  {rm} #{n['id']:<3} [{n['source'][:10]}] "
                      f"{n['title'][:25]} {C.c(n['time'][11:16], C.DIM)}")
            return
        if args[0] == 'read':
            nc.mark_read(int(args[1]) if len(args) > 1 and args[1].isdigit() else None)
            print(C.c("  Отмечено", C.G))
        elif args[0] == 'clear':
            nc.delete()
            print(C.c("  Очищено", C.G))

    def c_timer(self, args):
        ts = self.kernel.timer_service
        if not args:
            all_t = ts.get_all()
            now = datetime.datetime.now()
            if not all_t:
                print(C.c("  Таймеров нет", C.DIM)); return
            for t in all_t:
                if t['fired']:
                    print(f"  + #{t['id']:<3} {t['label'][:20]} ЗАВЕРШЕН")
                else:
                    rem = max(0, int((t['end_time'] - now).total_seconds()))
                    m2, s = divmod(rem, 60)
                    h, m2 = divmod(m2, 60)
                    print(f"  @ #{t['id']:<3} {t['label'][:20]} {h}:{m2:02d}:{s:02d}")
            return
        if args[0] in ('add', 'set'):
            if len(args) < 2:
                print("  timer add <сек> [метка]"); return
            try:
                secs = int(args[1])
                label = ' '.join(args[2:]) if len(args) > 2 else 'Таймер'
                tid = ts.add_timer(secs, label)
                print(C.c(f"  Таймер #{tid}: {label} ({secs}с)", C.G) if tid
                      else C.c("  Ошибка", C.R))
            except ValueError:
                print(C.c("  Неверное число", C.R))
        elif args[0] in ('cancel', 'rm'):
            if len(args) > 1 and args[1].isdigit():
                print(C.c("  Отменен", C.G) if ts.cancel_timer(int(args[1]))
                      else C.c("  Не найден", C.R))
        elif args[0] == 'clear':
            ts.cleanup()
            print(C.c("  Очищено", C.G))

    def c_man(self, args):
        if not args:
            print("=" * 72)
            print("  MANUAL PAGES PYOS")
            print("=" * 72)
            print("  man <имя_команды>")
            print("-" * 72)
            names = sorted(self.MAN_PAGES.keys())
            cols = 4
            for i in range(0, len(names), cols):
                chunk = names[i:i + cols]
                print("".join(f"  {c:<16}" for c in chunk))
            print("-" * 72)
            print("=" * 72)
            return
        cmd = args[0].lower()
        if cmd not in self.MAN_PAGES:
            print(C.c(f"  '{cmd}' не найден.", C.R))
            m = difflib.get_close_matches(cmd, list(self.MAN_PAGES.keys()), n=3, cutoff=0.5)
            if m:
                print(C.c(f"  Возможно: {', '.join(m)}?", C.Y))
            return
        info = self.MAN_PAGES[cmd]
        print("=" * 72)
        print(f"  РУКОВОДСТВО: {C.c(cmd.upper(), C.G + C.B)}")
        print("=" * 72)
        print(C.c("  НАЗВАНИЕ:", C.Y + C.B))
        print(f"      {cmd} — {info['desc']}")
        print()
        print(C.c("  СИНТАКСИС:", C.Y + C.B))
        for s_line in textwrap.wrap(info['synopsis'], width=66):
            print(f"      {C.c(s_line, C.W + C.B)}")
        print()
        print(C.c("  ОПИСАНИЕ:", C.Y + C.B))
        for line in textwrap.wrap(info['details'], width=66):
            print(f"      {line}")
        print()
        if info['options']:
            print(C.c("  ПАРАМЕТРЫ:", C.Y + C.B))
            for opt, od in info['options']:
                print(f"      {C.c(opt, C.CY):<22} {od}")
            print()
        if info['examples']:
            print(C.c("  ПРИМЕРЫ:", C.Y + C.B))
            for ex in info['examples']:
                print(f"      $ {C.c(ex, C.G)}")
        print("=" * 72)

    def c_help(self, _a):
        cats = [
            ('Файлы', 'ls cd pwd mkdir rmdir touch rm cat cp mv rename find grep wc tree du df'),
            ('Автоматизация x3', 'x3 [--fast] <файл.x3> [args...] | newx3 <имя>'),
            ('Корзина', 'trash (list, empty, rm <id>, restore <id>)'),
            ('Пользователи', 'whoami id su useradd userdel passwd users (Argon2id)'),
            ('Система', 'date uptime hostname neofetch reboot shutdown perms uac'),
            ('Оболочка', 'echo clear desktop history alias export env edit save reload'),
            ('Бэкапы', 'backup (create, list, restore, rm)'),
            ('Кэш', 'cache (list, clear, cat, rm)'),
            ('SmartMem', 'smartmem (on, off, clean)'),
            ('Guardian / GitHub', 'guardian (github, update, uninstall)'),
            ('Программы / Store', 'app (store, tags, manager, list, run, install, remove, disable, enable)'),
            ('Диски', 'disk (add)'),
            ('Уведомления', 'notif | timer'),
            ('Настройки', 'settings (lang, autobackup, uac, x3_speed, debug, smartmem)'),
            ('Справка', 'man <cmd> | help | realpath | exit'),
        ]
        print("=" * 90)
        print(f"  PyOS v{Kernel.VERSION} Справка [Nexus v19.1]")
        print("=" * 90)
        for cat, cl in cats:
            print(f"  {C.c(cat + ':', C.Y)} {cl}")
        print("-" * 90)
        print(C.c(f"  {Kernel.COMPANY} -- PyOS {Kernel.VERSION}", C.DIM))
        print("=" * 90)

    def c_save(self, _a):
        print(C.c("  Сохранено", C.G) if self.kernel.save_state() else C.c("  Ошибка", C.R))

    def c_shutdown(self, _a):
        self.kernel.shutdown()

    def c_reboot(self, _a):
        self.kernel.save_state()
        self.kernel.boot_time = datetime.datetime.now()
        self.kernel.guardian.session_start = datetime.datetime.now()
        if self.kernel.apps:
            self.kernel.apps.apps.clear()
            self.kernel.apps.load_installed()
        clear()
        self.kernel.boot_anim()
        self._do_desktop()

    def c_exit(self, _a):
        self.kernel.shutdown()


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
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
        except (KeyboardInterrupt, EOFError):
            print("\n  [Завершение сеанса]")
        except SystemExit:
            break
        except (RuntimeError, OSError, ValueError, KeyError, TypeError,
                AttributeError) as err:
            print(C.c(f"\n  [Системная ошибка ({type(err).__name__})] {err}", C.R))
            tb_module.print_exc()
            if kernel.settings.debug_mode and kernel.debug:
                kernel.debug.log('panic', str(err), tb_module.format_exc(), 'kernel', '')
            kernel.save_state()
        except Exception as err:
            print(C.c(f"\n  [Критический сбой ({type(err).__name__})] {err}", C.R))
            tb_module.print_exc()
            if kernel.settings.debug_mode and kernel.debug:
                kernel.debug.log('panic', str(err), tb_module.format_exc(), 'kernel', '')
            kernel.save_state()
        if kernel.is_bsod_pending():
            ec, m, d = kernel.get_bsod_info()
            BSOD.crash_and_restart(ec, m, d)
            kernel.restart_after_bsod()
            continue
        break


if __name__ == '__main__':
    main()
