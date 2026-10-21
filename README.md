```markdown
<div align="center">

# 🖥️ PyOS v19.3 «Nexus»

**Полноценная операционная система на Python — с ядром, правами, приложениями и GitHub-магазином**

![Version](https://img.shields.io/badge/version-19.3-00d4ff?style=for-the-badge&logo=python&logoColor=white)
![Build](https://img.shields.io/badge/build-21.10.2026-blueviolet?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-Free-green?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/status-active-brightgreen?style=for-the-badge)

**Kostyl Studios · Argon2id + Salt · ROOT/USER/PROGRAM · UAC · AST-валидатор**

[Возможности](#-возможности) · [Установка](#-установка) · [Быстрый старт](#-быстрый-старт) · [Команды](#-справочник-команд) · [Приложения](#-приложения-x4) · [Безопасность](#-архитектура-безопасности)

</div>

---

## 🎯 Что такое PyOS?

**PyOS** — это настоящая операционная система, написанная целиком на Python. Не эмулятор, не песочница, не учебный проект. Это законченная ОС с:

- 🧠 **Собственным ядром** (Kernel) и менеджером процессов
- 🔐 **Трёхуровневой системой прав** (ROOT / USER / PROGRAM)
- 📁 **Виртуальной файловой системой** с поддержкой нескольких дисков
- 🎨 **GUI-подобным рабочим столом** и терминалом
- 📦 **Центром приложений**, подключённым к GitHub
- 🛡️ **AST-валидатором** для безопасного выполнения кода
- 💾 **Автоматическими бэкапами** с защитой Argon2id

PyOS запускается как обычный Python-скрипт и работает в отдельной папке, **не затрагивая вашу настоящую систему**.

---

## ✨ Возможности

<table>
<tr>
<td width="50%" valign="top">

### 🔐 Безопасность
- **Argon2id + salt** для паролей и целостности
- **AST-валидатор** — блокирует опасный код в приложениях
- **UAC** с 4 уровнями контроля
- **Права ROOT / USER / PROGRAM** через thread-local контексты
- **Проверка целостности** исходного кода при запуске
- **Автоматическое восстановление** из бэкапов при повреждении

### 📦 Приложения
- Формат **`.x4`** — читаемый текст
- Формат **`.x4s`** — сжатый LZMA (X4 Super)
- **Изолированная песочница** `/apps/data/<app>`
- **Центр приложений** из GitHub
- **Установка, обновление, отключение** приложений
- **Автоматическое сжатие** отключённых приложений

</td>
<td width="50%" valign="top">

### 🗂️ Файловая система
- **Виртуальные диски** (C:, D:, E:...)
- **Мультипользовательский режим** с домашними каталогами
- **Корзина** с LZMA-архивацией
- **Умный поиск** по файловому индексу
- **Цветовая индикация** типов файлов
- **Мягкое и жёсткое удаление** (`rm` → trash, `rm --perm`)

### 🛠️ Автоматизация
- **X3-скрипты** — цепочки команд
- **Аргументы** `$1`, `$2`, `$@`
- **Переменные** `$USER`, `$HOME`, `$CACHE`
- **Рекурсия** до 10 уровней
- **Fast Mode** для быстрого выполнения

### 💾 Надёжность
- **Автобэкапы** (при старте, выключении, ежечасно)
- **LZMA Extreme** сжатие
- **BSOD** с восстановлением
- **FSHealthChecker** — следит за целостностью ФС
- **Smart Memory** — очистка мусора

</td>
</tr>
</table>

---

## 📥 Установка

### Требования
- **Python 3.10+**
- **argon2-cffi** (обязательно)
- Интернет (для GitHub AppStore — опционально)

### Один шаг — и всё готово

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/bogdangotj/PYOS.git
cd PYOS

# 2. Установите зависимости
pip install argon2-cffi

# 3. Запустите PyOS
python PYOS.py
```

💡 Первый запуск: PyOS предложит автонастройку (создаст пользователя User без пароля) или ручную настройку (имя компьютера, имя пользователя, пароль, подсказка).

---

🚀 Быстрый старт

```
login: User

========================================================
  PyOS v19.3 build 21.10.2026 -- Kostyl Studios
========================================================
  Пользователь:       User [USER]
  Время:              14:32:07
  Сессия:             00:00:15
--------------------------------------------------------
  Занято:             4.2 KB
  Приложения:         4 (Откл: 0)
--------------------------------------------------------
  Введите 'help' для всех доступных команд.
========================================================

User@Computer:~$ app store
```

Первые шаги

Действие Команда
Список команд help
Справка по команде man app
Открыть магазин приложений app store
Запустить калькулятор app run calc
Создать бэкап backup create my_snapshot
Сменить пользователя su Other
Информация о системе sysinfo

---

📖 Справочник команд

<details>
<summary><b>📁 Файлы и каталоги</b></summary>

Команда Описание
ls [-a] [-l] [путь] Содержимое каталога
cd [путь \| ~ \| - \| D:/path] Смена каталога
pwd Текущий путь с диском
mkdir <путь> Создать каталог
rmdir <путь> Удалить каталог (в корзину)
touch <файл> Создать пустой файл
rm [-r] [--perm] <путь> Удаление (в корзину или навсегда)
cat <файл> Прочитать файл
cp <src> <dst> Копировать
mv <src> <dst> Переместить
rename <файл> <новое> Переименовать
find [путь] <паттерн> Поиск файлов
grep <паттерн> <файл> Поиск по содержимому
wc <файл> Строки / слова / байты
tree [путь] Дерево каталогов
du [путь] Размер каталога
df Использование дисков
edit <файл> Встроенный редактор

</details>

<details>
<summary><b>🗑️ Корзина</b></summary>

Команда Описание
trash Список удалённых файлов
trash restore <id> Восстановить по ID или имени
trash rm <id> Удалить навсегда
trash empty Очистить с LZMA-архивацией

</details>

<details>
<summary><b>👥 Пользователи</b></summary>

Команда Описание
whoami Текущий пользователь
id [user] UID, диск, тип пароля
su <user> Переключиться на пользователя
users Список всех пользователей
useradd <name> Создать (требует ROOT)
userdel <name> Удалить (требует ROOT)
passwd Сменить свой пароль

</details>

<details>
<summary><b>📦 Приложения</b></summary>

Команда Описание
app store Центр приложений (GitHub)
app tags Просмотр по тегам
app manager Интерактивный менеджер
app list Список установленных
app run <name> Запустить
app install <file.x4> Установить из файла
app remove <name> Удалить (данные → cache)
app disable <name> Сжать в .disabled
app enable <name> Распаковать обратно
app info <name> Метаданные

</details>

<details>
<summary><b>⚙️ Автоматизация (X3)</b></summary>

Команда Описание
x3 <file.x3> [args...] Выполнить скрипт
x3 --fast <file.x3> Без паузы
newx3 <name> Создать шаблон

</details>

<details>
<summary><b>🛡️ Guardian / GitHub</b></summary>

Команда Описание
guardian Панель безопасности
guardian github Проверить обновления ядра
guardian uninstall Деинсталляция с бэкапом

</details>

<details>
<summary><b>💾 Бэкапы / Кэш / Настройки</b></summary>

Команда Описание
backup create [name] Создать бэкап
backup list Список всех
backup restore <n> Восстановить
cache list / cache clear Управление кэшем
smartmem on/off/clean Smart Memory
settings lang ru/en Язык интерфейса
settings uac 1-4 Уровень UAC
settings x3_speed fast/normal Скорость X3
settings autobackup off/at_start/at_shutdown/hourly Автобэкапы
debug Журнал ошибок
notif Уведомления
timer add 60 метка Таймер

</details>

---

📦 Приложения (.x4)

Приложения в PyOS — это обычные текстовые файлы с метаданными и Python-кодом.

Структура .x4

```ini
[INFO]
name: calc
description: Удобный калькулятор
version: 1.3.0
author: Kostyl Studios
tag: Technical
background: false

[CODE]
print("=== Калькулятор ===")
while True:
    expr = input("calc> ").strip()
    if expr.lower() in ('exit', 'q'):
        break
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
[END]
```

Доступные API в X4

Функция Описание
print(...) / color(text, цвет) Вывод с цветом
input(prompt) Ввод пользователя
eval(expr, globals) Безопасное вычисление
fread(p) / fwrite(p, c) / fappend(p, c) Файлы в sandbox
fexists(p) / fdelete(p) / fmkdir(p) / flist(p) Файловые операции
cache_read(k) / cache_write(k, v) Кэш приложения
notify(title, msg) / notify_high(...) Уведомления
sleep(sec) Пауза
request_user(reason) Запрос USER-прав через UAC
spawn_thread(fn, *args) Фоновый поток (с правами)
background() Регистрация как фонового
sysinfo() Информация о системе
__USER__, __DATE__, __TIME__, __CWD__, __APP__ Переменные окружения

Компрессия .x4s

Команда app disable <name> сжимает приложение в .x4s (LZMA + magic X4S\x01):

· Экономия до 80% размера
· Данные приложения сохраняются внутри архива
· Восстанавливается через app enable <name>

Отладочные приложения

Из коробки поставляются:

· 🧮 calc — калькулятор с math
· 🎲 guess — игра «Угадай число»
· 📝 notes — блокнот с файлами
· 👋 hello — демонстрация системы

---

⚡ Автоматизация (.x3)

X3 — это DSL для цепочек команд терминала.

Пример скрипта deploy.x3

```bash
# deploy.x3 — разворачиваем проект
echo "=== Deploy $1 ==="
echo "Пользователь: $USER"
cd /home/$USER/Documents
mkdir project_$1
cd project_$1
touch README.md
fappend README.md "# Project $1"
app list
echo "Готово за $2 секунд!"
```

Запуск

```bash
User@Computer:~$ x3 deploy.x3 myapp 5

  ┌── [X3 Automation] Запуск: deploy.x3 (нормальный)
  $ echo "=== Deploy myapp ==="
  === Deploy myapp ===
  $ echo "Пользователь: User"
  Пользователь: User
  ...
  └── [X3 Automation] Скрипт успешно выполнен.
```

Возможности

· Аргументы: $1, $2, ..., $@ — все аргументы
· Переменные: $USER, $HOME, $CACHE
· Рекурсия: до 10 уровней (защита от бесконечных циклов)
· Fast Mode: x3 --fast script.x3 без задержек
· Остановка: exit, quit, q

---

🛡️ Архитектура безопасности

Права

```
┌─────────────────────────────────────────────────────────┐
│  ROOT (3)                                                │
│  → Ядро, системные команды, создание пользователей      │
│  → Полный доступ к FS                                   │
├─────────────────────────────────────────────────────────┤
│  USER (2)                                                │
│  → Ваши команды в терминале                              │
│  → Запрет: /sysdata, write /apps/installed, чужой home   │
├─────────────────────────────────────────────────────────┤
│  PROGRAM (1)                                             │
│  → X4-приложения                                         │
│  → Доступ: /apps/data/<app>/ и /cache/<app>_*            │
│  → Расширение через request_user() + UAC                 │
├─────────────────────────────────────────────────────────┤
│  NONE (0)                                                │
│  → Доступ запрещён полностью                             │
└─────────────────────────────────────────────────────────┘
```

Каждый поток имеет thread-local контекст прав. Это означает, что X4-приложение физически не может эскалировать права через фоновый поток — дочерние потоки наследуют контекст родителя и сбрасываются в NONE при завершении.

UAC — 4 уровня

Уровень Название Поведение
1 🔒 Строгий Требует пароль на любой запрос
2 🛡️ Стандартный Требует подтверждение y/n
3 ⚠️ Слабый USER авто, ROOT через y/n
4 🔓 Отключён Всё автоматически (для тестов)

AST-валидатор

Перед запуском X4-кода каждая строка проходит проверку AST:

```python
✅ Разрешено:           ❌ Запрещено:
─────────────────       ─────────────────
print, input            import, from
math.sqrt               class, async
random.randint          eval, exec, compile
json, re                open, getattr, globals
float, int, str         __class__, __dict__
fread, fwrite           os.system, subprocess
                        str.format, format_map
```

Любой __dunder__ атрибут или запрещённое имя → приложение отклоняется с логом в /sysdata/errors.json.

Argon2id + Salt

Все пароли хранятся как Argon2id(time=2, memory=19456, parallelism=1).

Хеш исходного кода .pyos файла тоже защищён Argon2id:

```
┌─ .pyos ─────────────────────────────────┐
│ {                                       │
│   "salt":       "a4f8b1c2...",          │
│   "hash":       "9e2d7a...",            │
│   "algorithm":  "Argon2id+salt",        │
│   "version":    "19.3",                 │
│   "build":      "21.10.2026",           │
│   "filename":   "PYOS.py",              │
│   "hostname":   "Computer",             │
│   "updated":    "2026-10-21T14:32:07"   │
│ }                                       │
└─────────────────────────────────────────┘
```

При каждом запуске PyOS:

1. Проверяет синтаксис собственного кода
2. Вычисляет Argon2id-хеш
3. Сравнивает с сохранённым
4. При расхождении → предлагает восстановление из бэкапа

---

💾 Файловая система

Структура диска

```
<base_path>/
├── .pyos                       ← Хеш + salt + hostname
├── PYOS.py                     ← Исходный код
├── backups/                    ← LZMA-бэкапы
│   ├── initial_setup.backup
│   ├── auto_boot.backup
│   └── pre_full_update.backup
└── <hostname>/
    └── C/                      ← Диск C:
        ├── home/
        │   └── <user>/
        │       ├── Desktop/
        │       └── Documents/
        ├── sysdata/            ← 🔐 ROOT only
        │   ├── pyos_state.json
        │   ├── history.json
        │   ├── errors.json
        │   ├── trash_index.json
        │   └── trash/
        ├── cache/
        │   ├── deleted_apps/
        │   └── trash_archives/
        └── apps/
            ├── installed/      ← 🔐 write = ROOT
            │   ├── calc.x4
            │   ├── guess.x4
            │   └── notes.x4
            ├── data/           ← sandbox приложений
            │   ├── calc/
            │   └── notes/
            ├── store/          ← скачанные из GitHub
            └── logs/           ← JSON-краши
```

Мультидиск

```bash
# Создать диск D: (ROOT)
User@Computer:~$ disk add D
  Диск D: создан

# Работать с ним
User@Computer:~$ cd D:/projects
User@Computer:D:/projects$ ls
```

---

🔄 Бэкапы и восстановление

Создание

```bash
User@Computer:~$ backup create snapshot_1
  Создание...
  snapshot_1.backup (42.3 KB)
```

Формат:

```
.tar.xz (LZMA Extreme preset=9)
  ├── pyos_source.py       ← Код PyOS
  ├── manifest.json        ← Метаданные + salt + hostname + hash
  └── data/                ← Весь каталог диска
```

Проверка целостности

Каждый бэкап при листинге проверяется:

```bash
User@Computer:~$ backup list
  snapshot_1.backup              42.3 KB [OK] 2026-10-21 14:32
  auto_boot.backup               38.1 KB [OK] 2026-10-21 14:30
  old.backup                      1.2 KB [ПОВРЕЖДЕНА!] 2026-10-20 09:11
```

Автоматические бэкапы

Режим Когда
at_start При загрузке PyOS
at_shutdown При выходе
hourly Каждый час в фоне
off Отключено

Управление: settings autobackup <mode>

Восстановление при краше

Если исходник повреждён, PyOS:

1. Показывает жёлтое предупреждение
2. Предлагает список валидных бэкапов
3. Восстанавливает код и перезапускается автоматически

---

🧠 Smart Memory

Smart Memory автоматически чистит:

· Пустые каталоги в /apps/store и /apps/logs
· Пустые файлы .json в логах
· При завершении сессии

Плюс Guardian мониторит размер /apps/data/<app>:

· Лимит по умолчанию: 1 MB на приложение
· При превышении — удаляются самые большие файлы
· Уведомление выводится в консоль

```bash
User@Computer:~$ smartmem on
  ON
  Очищено: 0 папок, 3 файлов.

User@Computer:~$ settings
  Smart Memory: ON
```

---

🛒 GitHub AppStore

PyOS подключается к репозиторию bogdangotj/PYOS и предоставляет:

· 📜 Список приложений из /Apps
· 📥 Скачивание версий через API
· 🔄 Кэширование на 5 минут (защита от rate-limit)
· 🛡️ Обработка 403/404 с понятными ошибками

```bash
User@Computer:~$ app store

==========================================================
  🛒 Центр Приложений PyOS (GitHub AppStore)
==========================================================
  [Подключение к репозиторию GitHub...]
----------------------------------------------------------
   1. Calculator
   2. Snake [Установлено]
   3. Todo
   4. Weather

----------------------------------------------------------
  S. Поиск приложений
  R. Обновить список (сбросить кэш)
  0. Назад
==========================================================
```

Обновление ядра

```bash
User@Computer:~$ guardian github

  Текущая версия: v19.3 (build 21.10.2026)
  Репозиторий:    https://github.com/bogdangotj/PYOS
  [Подключение к GitHub...]
  
  Найдена новая версия: v19.4 (build 22.11.2026)!
  1. Загрузить и установить прямо сейчас
  0. Отмена
```

Установка через apply_full_code_update:

1. Синтаксическая проверка нового кода
2. Автоматический бэкап
3. Замена .pyos-файла
4. Пересчёт Argon2id-хеша
5. Перезапуск

---

🚨 BSOD и восстановление

Если FSHealthChecker обнаружит удаление /home/<hostname>/, PyOS:

```
============================================================
  :(
  Error: CRITICAL_DATA_DESTROYED
  System data folder deleted.
  Missing: /path/to/pyos/Computer
============================================================
  Press Enter to restart...
```

После Enter — полная переинициализация ядра с сохранением кода.

---

🗺️ Roadmap

☑ Argon2id + salt для целостности
☑ AST-валидатор
☑ GitHub AppStore
☑ X3-автоматизация
☑ X4S-компрессия
☑ Мультидиск
☑ UAC 4 уровня
☑ BSOD + восстановление
☐ Псевдографический GUI (TUI)
☐ Сетевые сокеты в X4 (HTTP API)
☐ Пакетный менеджер с зависимостями
☐ Криптография X4 (AES-GCM API)
☐ Плагины ядра (загрузка модулей)

---

🤝 Участие в разработке

Приветствуются:

· 🐛 Баг-репорты — Issues
· 📝 Pull requests — с описанием изменений
· 📦 X4-приложения — публикуйте в /Apps своего форка
· 🌍 Переводы — settings lang поддерживает ru/en

Как создать приложение для PyOS

1. Запустите newapp myapp Technical
2. Отредактируйте /home/User/Documents/myapp.x4
3. Установите: app install myapp.x4
4. Запустите: app run myapp

Тестовый чек-лист

```bash
# 1. Проверка целостности
backup create test && backup list

# 2. Работа с FS
mkdir /home/User/test && cd /home/User/test && touch a.txt

# 3. Проверка прав
rm --perm /sysdata/history.json  # должно быть отказано

# 4. AST-валидатор
echo "[INFO]
name: hacker

[CODE]
import os
os.system('rm -rf /')
[/CODE]

[DATA]
folder: /apps/data/hacker
[/DATA]" > /home/User/Documents/hacker.x4
app install hacker.x4  # должно быть отклонено
```

---

📄 Лицензия

Free License — Kostyl Studios

· ✅ Использование, модификация, распространение
· ✅ Создание собственных приложений
· ✅ Коммерческое использование
· ⚠️ Ссылка на оригинал приветствуется

---

<div align="center">

🌟 PyOS — операционная система будущего на Python

Сделано с ❤️ в Kostyl Studios

«Не просто скрипт. Настоящая ОС.»

```
╔══════════════════════════════════════════════════╗
║   PyOS v19.3 «Nexus»                             ║
║   build 21.10.2026 · Kostyl Studios              ║
║   Argon2id + salt · ROOT/USER/PROGRAM            ║
║   UAC · AST Validator · GitHub AppStore          ║
╚══════════════════════════════════════════════════╝
```

⬆ Наверх

</div>
```

---
