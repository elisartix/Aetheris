<div align="center">
  <h1>Aetheris Userbot</h1>
  <p>A stable and secure Telegram userbot with inline UX, forum logs, and Heroku module compatibility</p>

  <p>
    <a href="https://github.com/elisartix/Aetheris"><img src="https://img.shields.io/github/stars/elisartix/Aetheris?style=flat" alt="Stars"></a>
    <a href="https://github.com/elisartix/Aetheris/issues"><img src="https://img.shields.io/github/issues/elisartix/Aetheris" alt="Issues"></a>
    <a href="https://github.com/elisartix/Aetheris/blob/dev/LICENSE"><img src="https://img.shields.io/github/license/elisartix/Aetheris" alt="License"></a>
  </p>
</div>

## What is Aetheris?

Aetheris is an independent fork of Heroku Userbot that preserves user data and module compatibility.

It builds on Heroku's original architecture while providing its own brand, `aetheris-tl`, infrastructure, and additional features:

- isolation of broken user modules;
- inline fallback when the Telegram inline bot fails;
- `.health` for session, inline, Redis, log forums, API protection, and module state;
- watchdog and recent error reporting;
- forum-based logs;
- improved Telegram API protection;
- premium blockquote-style UI;
- migration from Heroku without losing configuration or personal files;
- compatibility with existing Heroku/Hikka modules where possible.

## Installation

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

### Installer

```bash
git clone --branch dev https://github.com/elisartix/Aetheris.git Aetheris
cd Aetheris
bash install.sh --root
```

Aetheris requires Python 3.10+ and API credentials from [Telegram Apps](https://my.telegram.org/apps).

## Migration from Heroku

Aetheris does not require a clean start. Install `aetheris_migration_for_heroku.py` in Heroku and use:

```text
.aetheris scan
.aetheris prepare
.aetheris verify
```

The migration preserves configuration, sessions, installed modules, and other user files. It creates a backup before changing data and converts legacy `heroku.*` namespaces to `aetheris.*`.

## Diagnostics

```text
.health
```

The health report includes the Telegram session, inline bot, Redis, log forums, API protection, loaded modules, and recent errors.

## Security

Do not install untrusted modules. A user module can use the capabilities of a Telegram userbot and may access local files depending on its code and permissions.

Enable API protection and review module source code before installation.

## Origins and credits

Aetheris is a fork of Heroku Userbot. We respect the original project and its authors while maintaining an independent product with its own fixes and features.

- [Heroku Userbot](https://github.com/coddrago/Heroku) - upstream foundation and architectural heritage;
- [Hikka](https://gitlab.com/hikariatama) - ecosystem foundation;
- [Telethon](https://github.com/LonamiWebs/Telethon) - Telegram API foundation;
- [Aetheris](https://github.com/elisartix/Aetheris) - current project.

## License

See `LICENSE` for licensing terms.
