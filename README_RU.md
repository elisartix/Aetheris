<div align="center">
  <h1>Aetheris Userbot</h1>
  <p>Стабильный и безопасный Telegram userbot с inline UX, форумными логами и совместимостью с модулями Heroku</p>

  <p>
    <a href="https://github.com/elisartix/Aetheris"><img src="https://img.shields.io/github/stars/elisartix/Aetheris?style=flat" alt="Stars"></a>
    <a href="https://github.com/elisartix/Aetheris/issues"><img src="https://img.shields.io/github/issues/elisartix/Aetheris" alt="Issues"></a>
    <a href="https://github.com/elisartix/Aetheris/blob/dev/LICENSE"><img src="https://img.shields.io/github/license/elisartix/Aetheris" alt="License"></a>
  </p>
</div>

## Что такое Aetheris

Aetheris - самостоятельный fork Heroku Userbot с сохранением совместимости и данных пользователей.

Проект развивает исходную архитектуру Heroku, но использует собственный бренд, `aetheris-tl`, собственную инфраструктуру и дополнительные функции:

- изоляция падений пользовательских модулей;
- inline fallback при сбоях Telegram inline-бота;
- `.health` с состоянием сессии, inline, Redis, форумов, API protection и модулей;
- watchdog и журнал последних ошибок;
- форумные логи с разделением по событиям;
- улучшенная защита Telegram API;
- premium UI с blockquote-карточками;
- миграция с Heroku без потери конфигурации и пользовательских файлов;
- совместимость с существующими Heroku/Hikka-модулями там, где это возможно.

## Установка

### Ubuntu / Debian

```bash
sudo apt update && sudo apt install git python3 python3-venv -y
 git clone --branch dev https://github.com/elisartix/Aetheris.git Aetheris
cd Aetheris
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m aetheris --root
```

### Быстрый установщик

```bash
git clone --branch dev https://github.com/elisartix/Aetheris.git Aetheris
cd Aetheris
bash install.sh --root
```

Для работы нужны Python 3.10+ и API credentials из [Telegram Apps](https://my.telegram.org/apps).

## Переход с Heroku

Aetheris не требует начинать с нуля. Для подготовки миграции установите модуль `aetheris_migration_for_heroku.py`, затем выполните:

```text
.aetheris scan
.aetheris prepare
.aetheris verify
```

Миграция сохраняет конфигурацию, сессии, установленные модули и остальные пользовательские файлы. Перед изменением создаётся backup. Старые namespace `heroku.*` автоматически переводятся в `aetheris.*`.

## Диагностика

```text
.health
```

Команда показывает состояние Telegram-сессии, inline-бота, Redis, форумов логов, API protection, загруженных модулей и последние ошибки.

## Безопасность

Не устанавливайте непроверенные модули. Пользовательский модуль получает доступ к возможностям Telegram userbot в рамках выданных ему прав и может работать с локальными файлами.

Рекомендуется включить API protection и проверять исходный код модулей перед установкой.

## Источники и благодарности

Aetheris является fork Heroku Userbot. Мы сохраняем уважение к исходному проекту и его авторам, одновременно развивая отдельную ветку с собственными исправлениями и функциями.

- [Heroku Userbot](https://github.com/coddrago/Heroku) - исходная база и архитектурное наследие;
- [Hikka](https://gitlab.com/hikariatama) - фундамент экосистемы;
- [Telethon](https://github.com/LonamiWebs/Telethon) - основа Telegram API;
- [Aetheris](https://github.com/elisartix/Aetheris) - текущий проект.

## Лицензия

Проект распространяется на условиях лицензии, указанной в `LICENSE`.
