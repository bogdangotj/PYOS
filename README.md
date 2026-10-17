# 🛡️ PyOS v18.1 "Sentry"

> Защищенная операционная система-песочница на базе Python с поддержкой Argon2id, AST-валидатора и модульных X4-приложений.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Security](https://img.shields.io/badge/Security-Argon2id%20%2B%20AST-green)
![License](https://img.shields.io/badge/License-Kostyl%20Studios-orange)

## 🚀 Особенности
- **Трёхуровневая система прав** (Root, User, Program).
- **AST-валидатор безопасности** (блокирует опасный код и попытки взлома).
- **Argon2id хэширование** для защиты паролей и целостности кода.
- **Поддержка X4 и X4S приложений** (включая сжатие LZMA).
- **Автономный запуск через .x3 скрипты**.

## 📌 Установка и запуск

1. Установите зависимость для безопасности:
   ```bash
   pip install argon2-cffi
2. Скачайте файл pyos.py и запустите его:
python pyos.py

