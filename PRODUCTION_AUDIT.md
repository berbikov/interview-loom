# Production-аудит Interview Loom

Дата аудита: 9 августа 2026 года.

## Итог

Текущий проект нужно развивать, а не переписывать. FastAPI, SQLAlchemy, Pydantic,
Jinja2, MediaRecorder, faster-whisper и Gemini разделены достаточно хорошо, чтобы
использовать их и в следующих версиях.

Рекомендуемая продуктовая схема:

```text
Публичный HTTPS-лендинг
        │
        ├── описание продукта и документация
        └── GitHub Releases: macOS / Windows
                         │
                         ▼
              Desktop Interview Loom
        pywebview + локальный FastAPI backend
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
          SQLite      uploads     faster-whisper
                                      │
                                      ▼
                           Gemini с ключом пользователя
                         из системного хранилища секретов
```

Это сохраняет Python-бизнес-логику, не требует Terminal у конечного пользователя
и не отправляет видео на публичный сервер. Публичный многопользовательский backend
можно добавить позднее как отдельный продуктовый этап.

## Что уже работает

- FastAPI application factory, lifecycle и health-check;
- запись камеры, микрофона и экрана через browser API;
- preview, пауза, продолжение и отправка записи;
- API загрузки WebM/MP4 с потоковым ограничением размера;
- безопасное UUID-имя файла и публичный `public_id`;
- SQLite-модель записи и статусы обработки;
- локальная транскрибация через faster-whisper;
- Gemini-анализ с Pydantic-валидацией структурированного ответа;
- сохранение транскрипции при отсутствии Gemini key;
- polling страницы результата и повторный запуск анализа;
- адаптивный Jinja2/CSS-лендинг;
- прототип приложения для Apple Silicon на pywebview;
- 38 изолированных pytest-тестов без реальных запросов к Gemini;
- загрузка готового видео, системный keyring и общий desktop runtime;
- Alembic с резервной копией SQLite перед изменением схемы;
- GitHub Pages landing, GitHub Release pipelines и release manifests;
- Ruff, строгий mypy, compile-check и dependency check в CI.

## Что закрыто после аудита

### Публичный сайт — реализовано

- landing полностью отделён от локальной SQLite и видео;
- относительные asset paths поддерживают GitHub Pages project subpath;
- download ведёт на версионированные GitHub Release assets;
- добавлены privacy, terms, support, changelog и автоматические release notes.

### Desktop — реализовано в коде и CI

- PyInstaller формирует автономные macOS arm64 и Windows x64 приложения;
- Inno Setup создаёт Windows installer, macOS job создаёт ZIP и DMG;
- `app/metadata.py` является единым источником версии и identifier;
- реализованы platformdirs, single-instance lock, файловый журнал и startup error;
- build выполняет smoke-test упакованного executable.

### Gemini key пользователя — реализовано

- web/server использует только `GEMINI_API_KEY` из окружения;
- desktop UI сохраняет персональный ключ в Keychain/Credential Locker;
- API никогда не возвращает значение секрета;
- отсутствие или ошибка ключа не мешают сохранению транскрипции.

### Загрузка готового видео — реализовано

- интерфейс поддерживает file picker, drop-zone, preview, длительность и замену;
- backend проверяет MIME, максимальный размер и сигнатуру WebM/MP4/MOV;
- имя хранения всегда создаётся через UUID.

### Надёжность и безопасность — базовая production-часть реализована

- `BackgroundTasks` не является надёжной очередью;
- SQLite и локальные файлы подходят desktop-приложению, но не публичному
  многопользовательскому backend;
- UUID без авторизации не является полноценной моделью доступа для публичного SaaS;
- Alembic, backup перед миграцией, same-origin защита и security headers добавлены;
- test client переведён на `httpx2`, release executable проходит smoke-test;
- lint/type/tests/landing verifier обязательны в CI.

## Целевая архитектура

### Landing

Статическая production-копия дизайна публикуется через GitHub Pages.
После первого deploy появляется постоянный адрес `owner.github.io/repository`;
custom domain подключается через DNS. Кнопки скачивания ведут на assets последнего GitHub Release,
а не на локальную папку приложения.

### Desktop

Один Python launcher используется на macOS и Windows. Он запускает FastAPI на
случайном loopback-порту и открывает pywebview. Бизнес-логика остаётся в `app/`.
Пути данных определяются через `platformdirs`, секреты — через `keyring`.

Сборки создаются PyInstaller на соответствующей ОС. PyInstaller не является
кросс-компилятором, поэтому macOS и Windows собираются отдельными jobs CI.

### Дистрибуция

- Git tag запускает GitHub Actions;
- macOS job создаёт `.app`/`.dmg`, подписывает и нотарифицирует при наличии secrets;
- Windows job создаёт `.exe` и установщик/MSIX, подписывает при наличии secrets;
- checksum и release notes публикуются рядом с файлами;
- лендинг использует стабильную ссылку на последний release.

## Новые зависимости

Runtime desktop:

- `pywebview` — нативное окно;
- `platformdirs` — корректные каталоги данных macOS и Windows;
- `keyring` — macOS Keychain и Windows Credential Locker.

Build-only:

- `pyinstaller` — нативные OS-specific bundles;
- Inno Setup или MSIX tooling — Windows installer;
- Apple codesign/notarytool и DMG tooling — macOS distribution.

Новые зависимости должны быть отделены от web/runtime и dev requirements.

## Внешние ресурсы, которые должен предоставить владелец

Для бесплатной beta-ссылки достаточно GitHub-репозитория с включённым GitHub Pages.
Для собственного адреса нужен купленный домен и доступ к его DNS.

Для production-дистрибуции без системных предупреждений нужны:

- Apple Developer account, Developer ID Application certificate и данные
  notarization;
- Windows publisher identity: Microsoft Store или доверенный signing provider;
- название издателя, support email, privacy policy URL и иконка приложения.

Эти секреты нельзя помещать в репозиторий: они настраиваются только в CI secrets.

До подключения этих ресурсов репозиторий готов к beta-публикации, но нельзя
утверждать, что существует реальный публичный URL или подписанный production installer.
Фактическая Windows-сборка проверяется Windows runner, а notarization — Apple CI job;
их невозможно достоверно заменить локальной проверкой на macOS без аккаунтов владельца.

## Критерии готовности

- пользователь открывает публичный HTTPS-лендинг по постоянному адресу;
- нажимает download и получает проверенный установщик своей ОС;
- приложение устанавливается и запускается без Terminal;
- можно записать новое или выбрать готовое видео;
- Gemini key задаётся в UI и хранится системным хранилищем секретов;
- без ключа работает транскрибация и показывается понятный статус;
- обновление не ломает существующую локальную базу и записи;
- тесты, сборки, checksums и релиз выполняются автоматически;
- ни один API key, сертификат или пользовательское видео не попадает в Git.

## Использованные официальные материалы

- PyInstaller: https://pyinstaller.org/en/stable/
- GitHub Releases: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- Python keyring: https://keyring.readthedocs.io/en/latest/
- Apple notarization: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- Windows code signing: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
