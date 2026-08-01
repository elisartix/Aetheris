"""Core health command and lightweight stability watchdog."""

from __future__ import annotations

import asyncio
import logging
import time

from aetheris_tl.tl.types import Message

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class AetherisHealthMod(loader.Module):
    strings = {"name": "AetherisHealth"}

    def __init__(self):
        self._watchdog_task = None
        self._last_health = 0.0

    async def client_ready(self):
        self._watchdog_task = asyncio.create_task(self._watchdog())

    async def on_unload(self):
        if self._watchdog_task:
            self._watchdog_task.cancel()

    async def _watchdog(self):
        while True:
            await asyncio.sleep(60)
            try:
                inline = self.inline
                if inline is None:
                    continue
                if inline.init_complete:
                    await inline._ping_bot()
                elif getattr(inline, "_token", False):
                    # Recreate a dead bot client instead of leaving inline features
                    # permanently disabled after a transient Telegram/network error.
                    await inline._stop()
                    await inline.register_manager(after_break=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Aetheris health watchdog probe failed", exc_info=True)

    @loader.command()
    async def healthcmd(self, message: Message):
        client = self._client
        def s(key: str, fallback: str) -> str:
            try:
                value = self.strings[key]
            except Exception:
                return fallback
            return value or fallback

        inline = getattr(self.inline, "init_complete", False)
        redis_ok = bool(getattr(self._db, "_redis", None))
        forums = bool(self._db.get("aetheris.forums", "channel_id", None))
        api = self.lookup("APILimiter") or self.lookup("APIRatelimiter")
        api_state = "unknown"
        if api:
            api_state = "off" if api.get("disable_protection", False) else "on"
        modules = self.allmodules.health_snapshot()
        log_handler = next(
            (h for h in logging.getLogger().handlers if hasattr(h, "dump")),
            None,
        )
        recent_errors = 0
        if log_handler is not None:
            error_records = [
                record
                for record in log_handler.dump()
                if getattr(record, "levelno", 0) >= logging.ERROR
            ]
            recent_errors = len(error_records)
            last_errors = "\n".join(
                f"- {utils.escape_html(record.name)}: "
                f"{utils.escape_html(record.getMessage()[:140])}"
                for record in error_records[-3:]
            )
        else:
            last_errors = ""
        text = (
            f"<blockquote>{s('title', '<b>Aetheris health</b>')}</blockquote>\n\n"
            f"<blockquote>{s('telegram', 'Telegram session')}: <b>{s('ok', 'OK') if client.is_connected() else s('fail', 'FAIL')}</b></blockquote>\n"
            f"<blockquote>{s('inline', 'Inline bot')}: <b>{s('ok', 'OK') if inline else s('fail', 'FAIL')}</b></blockquote>\n"
            f"<blockquote>{s('redis', 'Redis')}: <b>{s('configured', 'configured') if redis_ok else s('disabled', 'disabled')}</b></blockquote>\n"
            f"<blockquote>{s('forums', 'Log forums')}: <b>{s('ok', 'OK') if forums else s('not_configured', 'not configured')}</b></blockquote>\n"
            f"<blockquote>{s('api', 'API protection')}: <b>{s(api_state, api_state)}</b></blockquote>\n"
            f"<blockquote>{s('errors', 'Recent errors')}: <b>{recent_errors}</b></blockquote>\n"
            f"<blockquote>{s('modules', 'Modules')}: "
            + s(
                'module_stats',
                '<b>{loaded}</b> loaded, <b>{failed}</b> failed, <b>{core_failed}</b> core failed',
            ).format(**modules)
            + "</blockquote>"
            + (f"\n\n{ s('last_errors', '<b>Last errors</b>') }\n{last_errors}" if last_errors else "")
        )
        await utils.answer(message, text)
