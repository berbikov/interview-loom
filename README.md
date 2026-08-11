# Interview Loom

Interview Loom — локальное приложение для записи и AI-анализа тренировочных собеседований. Оно помогает разобрать ответ после записи, а не получать скрытые подсказки во время настоящего интервью.

Версия 1.1 объединяет FastAPI/web-интерфейс и устанавливаемое desktop-приложение для macOS и Windows. Видео и SQLite остаются на устройстве пользователя. `faster-whisper` создаёт расшифровку локально, Gemini возвращает строго проверенный Pydantic-разбор, а AI Chat отвечает на уточняющие вопросы по конкретной записи. При отсутствии Gemini key приложение сохраняет и показывает транскрипцию без AI-оценки.

## 1. Описание продукта

Пользователь задаёт должность и вопрос, записывает камеру, микрофон и при необходимости экран либо загружает готовое видео. После обработки он видит видео, транскрипцию, оценки структуры, ясности и конкретики, сильные и слабые стороны, слова-паразиты, рекомендации, улучшенную версию ответа и следующий вопрос интервьюера.

## 2. Возможности MVP

- запись камеры и микрофона, экрана и микрофона или комбинированного режима;
- Start, Pause, Resume, Stop, таймер и предварительный просмотр;
- загрузка готового WebM, MP4 или MOV через выбор файла или drag-and-drop;
- серверная проверка MIME-типа, сигнатуры контейнера, размера и пустого файла;
- безопасное UUID-имя файла и публичный UUID записи;
- локальная транскрибация через `faster-whisper`;
- фоновые статусы `uploaded`, `transcribing`, `analyzing`, `completed`, `failed`;
- polling, skeleton loading, progress bar и повторный запуск обработки;
- строгий JSON-анализ Gemini через Pydantic;
- AI Chat по расшифровке и результатам анализа с историей в SQLite;
- персональный Gemini key в системном keyring desktop-версии;
- SQLite, Alembic-миграции, логирование и безопасные сообщения об ошибках;
- адаптивный русскоязычный интерфейс;
- health-check `GET /health` и OpenAPI `/docs`;
- статический публичный лендинг и автоматические GitHub Releases;
- desktop-сборки без ручного запуска Terminal.

## 3. Архитектура

```text
Публичный GitHub Pages landing ──► GitHub Releases ──► macOS / Windows installer

Browser или native desktop window
        │ Jinja2 + небольшой vanilla JavaScript
        ▼
FastAPI routers ─┬─ Storage service ────────────────► локальные uploads
                 ├─ SQLAlchemy 2 + Alembic ────────► локальная SQLite
                 └─ BackgroundTasks
                         │
                         ▼
                 RecordingProcessor / AI Chat
                   ├─ faster-whisper/PyAV ─────────► transcript
                   └─ Google Gen AI SDK ───────────► Pydantic AIAnalysis + chat
```

Основные части:

- `app/main.py` — фабрика FastAPI, lifecycle и middleware;
- `app/routers/` — HTML-страницы и JSON API;
- `app/services/storage.py` — безопасное сохранение медиа;
- `app/services/transcription.py` — ленивая переиспользуемая Whisper-модель;
- `app/services/gemini.py` — Gemini prompt, retry и проверка ответа;
- `app/services/secret_store.py` — окружение в web-режиме и системный keyring в desktop;
- `desktop/`, `interview_loom.spec` — общий Python runtime для двух ОС;
- `landing/` — независимый публичный сайт;
- `.github/workflows/` — CI, Pages и release-сборки;
- `tests/` — изолированные тесты без реальных запросов к Gemini.

## 4. Требования

Для разработки нужны Python 3.12, Git и современный браузер. Системный FFmpeg необязателен: `faster-whisper` декодирует медиа через PyAV. Интернет нужен для первого скачивания Whisper-модели и AI-анализа Gemini.

Для пользователя готовой desktop-сборки Python и Terminal не нужны. macOS-сборка рассчитана на Apple Silicon и macOS 12+, Windows-сборка — на Windows 10/11 x64.

## 5. Установка Python

Скачайте Python 3.12 с [python.org](https://www.python.org/downloads/) или установите через менеджер пакетов.

```bash
# macOS
brew install python@3.12

# проверка
python3.12 --version
```

## 6. Создание виртуального окружения

```bash
# macOS/Linux
python3.12 -m venv .venv
source .venv/bin/activate
```

```powershell
# Windows PowerShell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

## 7. Установка зависимостей

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Для runtime используйте `requirements.txt`, для desktop-разработки — `requirements-desktop.txt`, для сборки установщиков — `requirements-build.txt`.

## 8. Установка FFmpeg

Системный FFmpeg нужен только для дополнительной диагностики через `ffmpeg`/`ffprobe`.

```bash
brew install ffmpeg                 # macOS
sudo apt install ffmpeg             # Ubuntu/Debian
winget install Gyan.FFmpeg          # Windows PowerShell
ffmpeg -version
```

## 9. Настройка GEMINI_API_KEY

Для локального web-режима:

```bash
cp .env.example .env
```

```dotenv
GEMINI_API_KEY=your_local_key
GEMINI_MODEL=gemini-2.5-flash
```

В desktop-приложении откройте страницу «Настройки», перейдите по ссылке Google AI Studio, создайте собственный ключ и вставьте его в форму. Перед сохранением приложение проверит доступ к настроенной модели без генерации текста. Валидный ключ попадёт в Keychain на macOS или Credential Locker на Windows. API возвращает только состояние «настроен/не настроен» и никогда не возвращает сам ключ. Ключ не попадает в HTML, JavaScript, SQLite, логи, установщик или Git.

Если проверка сообщает о региональном ограничении, доступность Gemini API нужно проверять для страны и Google-проекта пользователя. Если квота исчерпана, откройте лимиты проекта в Google AI Studio.

Если ключ отсутствует или Gemini временно недоступен, приложение не падает: транскрипция сохраняется, а AI-анализ можно запустить повторно позднее.

Настройки Whisper находятся в `.env.example`. `WHISPER_LANGUAGE=auto` включает автоматическое определение языка. Первая транскрибация может быть долгой из-за скачивания модели; затем модель переиспользуется.

## 10. Запуск приложения

```bash
uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
```

- приложение: <http://127.0.0.1:8000>;
- health-check: <http://127.0.0.1:8000/health>;
- Swagger: <http://127.0.0.1:8000/docs>.

Каталоги данных создаются автоматически, а Alembic применяет миграции при старте.

## 11. Запуск тестов

```bash
pytest
ruff check app desktop scripts tests
mypy app desktop scripts
python scripts/build_landing.py
python scripts/verify_landing.py public
```

Тесты используют временные SQLite и uploads. Whisper и Gemini заменены stub/mock-объектами: модели не скачиваются и реальный Gemini API не вызывается.

## 12. Ограничения MVP

- `BackgroundTasks` подходит для локального однопользовательского приложения, но не заменяет production-очередь;
- при аварийном завершении прерванная запись помечается `failed` и может быть запущена повторно;
- данные хранятся только локально, синхронизации между устройствами нет;
- нет аккаунтов, командного доступа и автоматической политики удаления;
- прогресс отражает текущий этап, а не процент вычислений модели;
- качество анализа зависит от записи, точности транскрипции и Gemini;
- неподписанные beta-сборки вызывают стандартное предупреждение ОС.

## 13. Возможные улучшения

- очередь задач и изолированный worker для серверного многопользовательского режима;
- Server-Sent Events вместо polling;
- авторизация, шифрованная синхронизация и политика хранения;
- экспорт отчёта в PDF и сравнение нескольких тренировок;
- браузерные end-to-end тесты;
- Intel macOS и Windows ARM64 сборки;
- автоматическое обновление desktop-приложения.

## 14. Почему используется JavaScript

Backend, хранение, транскрибация и AI-логика написаны на Python. Сервер не может напрямую получить доступ к камере, микрофону или окну демонстрации: браузер предоставляет их только через `getUserMedia`, `getDisplayMedia` и `MediaRecorder`. Поэтому небольшой vanilla JavaScript отвечает за разрешения, управление записью, preview, таймер, drag-and-drop и отправку формы. React, Node.js-сервер и frontend-фреймворк не используются.

## 15. Desktop-приложение для macOS и Windows

Локальный beta-архив для Mac создаётся в `release/Interview-Loom-macOS-arm64.zip`. После распаковки перенесите `Interview Loom.app` в «Программы». В публичном релизе пользователь скачивает DMG/ZIP или `Interview-Loom-Setup-x64.exe`, устанавливает приложение и запускает его как обычную программу — Python и Terminal не нужны.

На macOS приложение запрашивает системный доступ к камере и микрофону при первой записи. Если установленная версия WebKit не предоставляет MediaRecorder во встроенном окне, кнопка записи автоматически открывает локальную студию в Safari или Chrome; Interview Loom продолжает работать в фоне, Terminal не требуется.

Desktop-версия запускает FastAPI на случайном loopback-порту и показывает его в нативном WebView. Второй экземпляр блокируется. База, модели, видео и логи находятся в пользовательском каталоге приложения, а ключ — отдельно в системном keyring.

Основная macOS-сборка:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-build.txt
./scripts/build_macos.sh
```

Если на Mac нет Xcode Command Line Tools, автономный тестовый ZIP можно собрать без PyInstaller:

```bash
./scripts/build_macos_portable.sh
```

Windows-сборка выполняется на Windows с установленным Inno Setup. Скрипт добавляет WebView2 bootstrapper в установщик, поэтому отсутствующий runtime устанавливается автоматически:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\scripts\build_windows.ps1
```

Для публичного распространения без предупреждений ОС нужны Apple Developer ID + notarization и Authenticode-сертификат. Секреты подписи передаются только через GitHub Actions Secrets.

## 16. Публичный лендинг и постоянная ссылка

Исходники находятся в `landing/`, собранные файлы — в игнорируемом `public/`.

```bash
GITHUB_REPOSITORY=owner/interview-loom \
SITE_URL=https://owner.github.io/interview-loom \
python scripts/build_landing.py
```

Workflow `.github/workflows/pages.yml` публикует сайт при push в `main`. После создания репозитория выберите **Settings → Pages → Source: GitHub Actions**. Постоянная ссылка будет `https://OWNER.github.io/REPOSITORY/`. Кнопки скачивания ведут на последний GitHub Release.

Для собственного домена добавьте DNS-запись и repository variable `CUSTOM_DOMAIN`; сборка создаст `CNAME`. Файл `landing/_headers` дополнительно используется платформами, которые поддерживают HTTP security headers.

## 17. CI/CD и выпуск версии

- `ci.yml` запускает pytest, Ruff, строгий mypy, compileall, проверку зависимостей и лендинга;
- `pages.yml` публикует статический сайт;
- `release.yml` на теге `v*` собирает macOS ARM64 и Windows x64, выполняет smoke-test исполняемых файлов, создаёт SHA-256, JSON release manifest и GitHub Release.

```bash
git tag v1.0.0
git push origin v1.0.0
```

Для подписи используются GitHub Secrets `MACOS_CERTIFICATE_BASE64`, `MACOS_CERTIFICATE_PASSWORD`, `MACOS_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD`, `WINDOWS_CERTIFICATE_BASE64`, `WINDOWS_CERTIFICATE_PASSWORD`. Если они не заданы, workflow создаёт неподписанные beta-артефакты.

## 18. Миграции данных

Перед изменением существующей SQLite приложение автоматически создаёт резервную копию `app.db.backup-<UTC timestamp>`, затем выполняет `alembic upgrade head`. Для ручного запуска:

```bash
alembic current
alembic upgrade head
```

Новые изменения модели должны оформляться отдельной ревизией. Пользовательская SQLite-база не удаляется при обновлении приложения.

Подробные инструкции: [`docs/RELEASE.md`](docs/RELEASE.md), [`docs/RECOVERY.md`](docs/RECOVERY.md) и [`CHANGELOG.md`](CHANGELOG.md). Каждый release содержит SHA-256 и JSON manifest с версией приложения, commit, размером/хешем артефакта и версиями Python-пакетов.
