# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Aetheris Userbot
# 🌐 https://github.com/coddrago/Aetheris
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import collections
import copy
import json
import logging
import os
import re
import time

try:
    import redis
except ImportError as e:
    if "RAILWAY" in os.environ:
        raise e


import typing

from aetheris_tl.tl.types import Message, User

from . import main, utils
from .pointers import (
    BaseSerializingMiddlewareDict,
    BaseSerializingMiddlewareList,
    NamedTupleMiddlewareDict,
    NamedTupleMiddlewareList,
    PointerDict,
    PointerList,
)
from .tl_cache import CustomTelegramClient
from .types import JSONSerializable

__all__ = [
    "Database",
    "PointerList",
    "PointerDict",
    "NamedTupleMiddlewareDict",
    "NamedTupleMiddlewareList",
    "BaseSerializingMiddlewareDict",
    "BaseSerializingMiddlewareList",
]

logger = logging.getLogger(__name__)

# --- Shared multi-account database -------------------------------------
# All clients of this process read/write ONE common store, so every account
# has the same modules and the same module configs. Namespaces listed in
# PER_ACCOUNT_NAMESPACES are kept separate per account: inline bot tokens
# must not be shared (two clients polling the same bot = 409 conflict) and
# every account owns its own service channels.
# Per-account data lives in the store under ACCOUNTS_KEY -> "<tg_id>".
_SHARED_STORE: dict | None = None
_STORE_LOADED: bool = False
_DATABASES: list["Database"] = []


def _get_shared_store() -> dict:
    global _SHARED_STORE
    if _SHARED_STORE is None:
        _SHARED_STORE = {}
    return _SHARED_STORE


PER_ACCOUNT_NAMESPACES = frozenset(
    {
        "aetheris.inline",
        "aetheris.inline.token_obtainment",
        "aetheris.forums",
    }
)
ACCOUNTS_KEY = "@accounts"


class NoAssetsChannel(Exception):
    """Raised when trying to read/store asset with no asset channel present"""


class NoContentChannel(Exception):
    """Raised when trying to read/store asset with no content channel present"""


class Database(dict):
    def __init__(self, client: CustomTelegramClient):
        super().__init__()
        self._client: CustomTelegramClient = client
        self._next_revision_call: int = 0
        self._revisions: list[dict] = []
        self._me: User = None
        self._redis: redis.Redis = None
        self._saving_task: asyncio.Future = None
        _DATABASES.append(self)

    def __repr__(self):
        return object.__repr__(self)

    # --- Shared multi-account routing ---------------------------------
    # The module-level `_SHARED_STORE` dict is the single source of truth.
    # Each Database instance keeps its own dict contents in sync as a merged
    # view (shared data + this account's per-account namespaces), so legacy
    # serialization via `json.dumps(db)` / `orjson.dumps(db)` keeps working.

    @staticmethod
    def _is_per_account(owner: typing.Any) -> bool:
        return isinstance(owner, str) and owner in PER_ACCOUNT_NAMESPACES

    def _tg_key(self) -> str:
        return str(getattr(self._client, "tg_id", ""))

    def _account_area(self, *, create: bool = True) -> dict:
        accounts = _get_shared_store().setdefault(ACCOUNTS_KEY, {})
        if not create:
            return accounts.get(self._tg_key(), {})
        return accounts.setdefault(self._tg_key(), {})

    def _target(self, owner: typing.Any) -> dict:
        if self._is_per_account(owner):
            return self._account_area()
        return _get_shared_store()

    @staticmethod
    def _merged_view_for(tg_key: str) -> dict:
        store = _get_shared_store()
        view = {k: v for k, v in store.items() if k != ACCOUNTS_KEY}
        view.update(store.get(ACCOUNTS_KEY, {}).get(tg_key, {}))
        return view

    def _merged_view(self) -> dict:
        return self._merged_view_for(self._tg_key())

    def _propagate(self) -> None:
        """Refresh the merged dict view of every live Database instance."""
        for db in list(_DATABASES):
            tg_key = str(getattr(db._client, "tg_id", ""))
            if not tg_key:
                continue
            super(Database, db).clear()
            for k, v in self._merged_view_for(tg_key).items():
                super(Database, db).__setitem__(k, v)

    # --- dict protocol (routed to the shared store) --------------------

    def __getitem__(self, owner):
        if self._is_per_account(owner):
            return self._account_area(create=False)[owner]
        store = _get_shared_store()
        if owner != ACCOUNTS_KEY and owner in store:
            return store[owner]
        raise KeyError(owner)

    def __setitem__(self, owner, value):
        if not utils.is_serializable(owner):
            raise RuntimeError(
                "Attempted to write object to "
                f"{owner=} ({type(owner)=}) of database. It is not "
                "JSON-serializable key which will cause errors"
            )

        if not utils.is_serializable(value):
            raise RuntimeError(
                "Attempted to write object of "
                f"{owner=} ({type(value)=}) to database. It is not "
                "JSON-serializable value which will cause errors"
            )

        self._target(owner)[owner] = value
        self._propagate()

    def __delitem__(self, owner):
        deleted = False
        store = _get_shared_store()
        if owner != ACCOUNTS_KEY and owner in store:
            del store[owner]
            deleted = True
        area = self._account_area(create=False)
        if owner in area:
            del area[owner]
            deleted = True
        if not deleted:
            raise KeyError(owner)
        self._propagate()

    def __contains__(self, owner) -> bool:
        if owner == ACCOUNTS_KEY:
            return False
        if self._is_per_account(owner):
            return owner in self._account_area(create=False)
        return owner in _get_shared_store()

    def __iter__(self):
        return iter(self._merged_view())

    def __len__(self) -> int:
        return len(self._merged_view())

    def keys(self):
        return self._merged_view().keys()

    def values(self):
        return self._merged_view().values()

    def items(self):
        return self._merged_view().items()

    def copy(self):
        return self._merged_view()

    def setdefault(self, owner, default=None):
        try:
            return self.__getitem__(owner)
        except KeyError:
            self.__setitem__(owner, default)
            return default

    def pop(self, owner, *args):
        try:
            value = self.__getitem__(owner)
        except KeyError:
            if args:
                return args[0]
            raise
        self.__delitem__(owner)
        return value

    def popitem(self):
        view = self._merged_view()
        if not view:
            raise KeyError("dictionary is empty")
        owner = next(iter(view))
        return owner, self.pop(owner)

    def update(self, *args, **kwargs) -> None:
        items = dict(*args, **kwargs)
        for owner, value in items.items():
            self.__setitem__(owner, value)

    def clear(self) -> None:
        store = _get_shared_store()
        for key in [k for k in store if k != ACCOUNTS_KEY]:
            del store[key]
        self._account_area(create=False).clear()
        self._propagate()

    # --- persistence ----------------------------------------------------

    def _redis_save_sync(self):
        with self._redis.pipeline() as pipe:
            pipe.set(
                str(self._client.tg_id),
                json.dumps(self, ensure_ascii=True),
            )
            pipe.execute()

    async def remote_force_save(self) -> bool:
        """Force save database to remote endpoint without waiting"""
        if not self._redis:
            return False

        await utils.run_sync(self._redis_save_sync)
        logger.debug("Published db to Redis")
        return True

    async def _redis_save(self) -> bool:
        """Save database to redis"""
        if not self._redis:
            return False

        await asyncio.sleep(5)
        await utils.run_sync(self._redis_save_sync)
        logger.debug("Published db to Redis")
        self._saving_task = None
        return True

    async def redis_init(self) -> bool:
        """Init redis database"""
        if REDIS_URI := (
            os.environ.get("REDIS_URL") or main.get_config_key("redis_uri")
        ):
            self._redis = redis.Redis.from_url(REDIS_URI)
        else:
            return False

    async def init(self):
        """Asynchronous initialization unit"""
        if os.environ.get("REDIS_URL") or main.get_config_key("redis_uri"):
            await self.redis_init()

        # Shared multi-account mode: every client reads/writes one common DB
        # file instead of per-account config-<tg_id>.json.
        self._db_file = main.BASE_PATH / "config-shared.json"
        self.read()

    async def ensure_content_channel(self):
        content_channel = None
        existing_channel_id = self.get("aetheris.forums", "channel_id", None)

        if existing_channel_id:
            try:
                content_channel = await self._client.get_entity(existing_channel_id)
                logger.debug(
                    "Found existing content channel with ID %s in database",
                    existing_channel_id,
                )
            except Exception as e:
                logger.warning(
                    f"Saved channel ID {existing_channel_id} not found or inaccessible: {e}"
                )
                content_channel = None
                self.set("aetheris.forums", "forums_cache", {"aetheris-userbot": {}})

        if not content_channel:
            async for dialog in self._client.iter_dialogs():
                if dialog.title and "aetheris-userbot" in dialog.title.lower():
                    content_channel = dialog.entity
                    logger.debug(
                        "Found existing channel '%s' with ID %s",
                        dialog.title,
                        dialog.entity.id,
                    )
                    self.set("aetheris.forums", "channel_id", int(dialog.entity.id))
                    break

        if not content_channel:
            content_channel, _ = await utils.asset_channel(
                client=self._client,
                title="aetheris-userbot",
                description="🪐 Content related to Aetheris will be here",
                silent=True,
                invite_bot=True,
                avatar="https://raw.githubusercontent.com/elisartix/assets/main/aetheris/aetheris.png",
                forum=True,
                hide_general=True,
                _folder="aetheris",
            )
            self.set("aetheris.forums", "channel_id", int(content_channel.id))

        return content_channel

    def read(self):
        """Read database and stores it in self"""
        global _STORE_LOADED

        if self._redis:
            try:
                data = json.loads(
                    self._redis.get(
                        str(self._client.tg_id),
                    ).decode(),
                )
            except Exception:
                logger.exception("Error reading redis database")
                data = {}

            if not _STORE_LOADED:
                _get_shared_store().update(data)
                _STORE_LOADED = True
            self._propagate()
            return

        if not _STORE_LOADED:
            store = _get_shared_store()
            try:
                db = self._db_file.read_text()
                if re.search(r'"(hikka\.)(\S+\":)', db):
                    logging.warning("Converting db after update (hikka → aetheris)")
                    db = re.sub(
                        r"(hikka\.)(\S+\":)", lambda m: "aetheris." + m.group(2), db
                    )
                if re.search(r'"(legacy\.)(\S+\":)', db):
                    logging.warning("Converting db after update (legacy → aetheris)")
                    db = re.sub(
                        r"(legacy\.)(\S+\":)", lambda m: "aetheris." + m.group(2), db
                    )
                if re.search(r'"(heroku\.)(\S+\":)', db):
                    logging.warning("Converting db after update (heroku → aetheris)")
                    db = re.sub(
                        r"(heroku\.)(\S+\":)", lambda m: "aetheris." + m.group(2), db
                    )
                store.update(json.loads(db))
            except json.decoder.JSONDecodeError:
                logger.warning("Database read failed! Creating new one...")
            except FileNotFoundError:
                logger.debug("Database file not found, creating new one...")
            _STORE_LOADED = True

        self._propagate()

    def _update_from_read(self, items: dict) -> None:
        """Update DB from persisted storage without write-protection checks."""
        self.update(items)

    def process_db_autofix(self, db: dict) -> bool:
        if not utils.is_serializable(db):
            return False

        for key, value in db.copy().items():
            if not isinstance(key, (str, int)):
                logger.warning(
                    "DbAutoFix: Dropped key %s, because it is not string or int",
                    key,
                )
                continue

            if not isinstance(value, dict):
                # If value is not a dict (module values), drop it,
                # otherwise it may cause problems
                del db[key]
                logger.warning(
                    "DbAutoFix: Dropped key %s, because it is non-dict, but %s",
                    key,
                    type(value),
                )
                continue

            for subkey in value:
                if not isinstance(subkey, (str, int)):
                    del db[key][subkey]
                    logger.warning(
                        (
                            "DbAutoFix: Dropped subkey %s of db key %s, because it is"
                            " not string or int"
                        ),
                        subkey,
                        key,
                    )
                    continue

        return True

    def save(self) -> bool:
        """Save database"""
        if not self.process_db_autofix(self):
            try:
                rev = self._revisions.pop()
                while not self.process_db_autofix(rev):
                    rev = self._revisions.pop()
            except IndexError:
                raise RuntimeError(
                    "Can't find revision to restore broken database from "
                    "database is most likely broken and will lead to problems, "
                    "so its save is forbidden."
                )

            self.clear()
            self.update(**rev)

            raise RuntimeError(
                "Rewriting database to the last revision because new one destructed it"
            )

        if self._next_revision_call < time.time():
            self._revisions += [dict(self)]
            self._next_revision_call = time.time() + 3

        while len(self._revisions) > 15:
            self._revisions.pop()

        if self._redis:
            if not self._saving_task:
                self._saving_task = asyncio.ensure_future(self._redis_save())
            return True

        try:
            self._db_file.write_text(json.dumps(_get_shared_store(), indent=4))
        except Exception:
            logger.exception("Database save failed!")
            return False

        return True

    async def store_asset(self, message: Message) -> int:
        """
        Save assets
        returns asset_id as integer
        """

        try:
            _assets_topic_id = self.get("aetheris.forums", "forums_cache", {})[
                "aetheris-userbot"
            ]["Assets"]
        except (TypeError, KeyError):
            raise NoAssetsChannel("Tried to save asset to non-existing asset topic.")

        if not (_content_channel_id := self.get("aetheris.forums", "channel_id", None)):
            raise NoContentChannel(
                "Tried to save asset with non-existing content channel."
            )

        return (
            (
                await self._client.send_message(
                    _content_channel_id, message, reply_to=_assets_topic_id
                )
            ).id
            if isinstance(message, Message)
            else (
                await self._client.send_message(
                    _content_channel_id,
                    file=message,
                    force_document=True,
                    message_thread_id=_assets_topic_id,
                )
            ).id
        )

    async def fetch_asset(self, asset_id: int) -> Message | None:
        """Fetch previously saved asset by its asset_id"""

        if not (_content_channel_id := self.get("aetheris.forums", "channel_id", None)):
            raise NoContentChannel(
                "Tried to fetch asset with non-existing content channel."
            )

        try:
            _assets_topic_id = self.get("aetheris.forums", "forums_cache", {})[
                "aetheris-userbot"
            ]["Assets"]
        except (TypeError, KeyError):
            raise NoAssetsChannel("Tried to save asset to non-existing asset topic.")

        asset = await self._client.get_messages(
            _content_channel_id, reply_to=_assets_topic_id, ids=[asset_id]
        )

        return asset[0] if asset else None

    def get(
        self,
        owner: str,
        key: str,
        default: JSONSerializable | None = None,
    ) -> JSONSerializable:
        """Get database key snapshot"""
        return copy.deepcopy(self._get_raw(owner, key, default))

    def _get_raw(
        self,
        owner: str,
        key: str,
        default: JSONSerializable | None = None,
    ) -> JSONSerializable:
        """Get database key"""
        try:
            return self[owner][key]
        except KeyError:
            pass
        # Legacy namespace fallback: modules read `heroku.*` but the DB
        # stores `aetheris.*` (heroku.* keys are converted on load).
        if owner.startswith("heroku."):
            try:
                return self["aetheris." + owner[len("heroku.") :]][key]
            except KeyError:
                pass
        return default

    def set(self, owner: str, key: str, value: JSONSerializable) -> bool:
        """Set database key"""
        if not utils.is_serializable(owner):
            raise RuntimeError(
                "Attempted to write object to "
                f"{owner=} ({type(owner)=}) of database. It is not "
                "JSON-serializable key which will cause errors"
            )

        if not utils.is_serializable(key):
            raise RuntimeError(
                "Attempted to write object to "
                f"{key=} ({type(key)=}) of database. It is not "
                "JSON-serializable key which will cause errors"
            )

        if not utils.is_serializable(value):
            raise RuntimeError(
                "Attempted to write object of "
                f"{key=} ({type(value)=}) to database. It is not "
                "JSON-serializable value which will cause errors"
            )

        # Legacy namespace mapping: writes to `heroku.*` land in `aetheris.*`
        # so both legacy modules and core read the same values.
        if owner.startswith("heroku."):
            owner = "aetheris." + owner[len("heroku.") :]

        self._target(owner).setdefault(owner, {})[key] = value
        self._propagate()
        return self.save()

    def pointer(
        self,
        owner: str,
        key: str,
        default: JSONSerializable | None = None,
        item_type: typing.Any | None = None,
    ) -> JSONSerializable | PointerList | PointerDict:
        """Get a pointer to database key"""
        value = self._get_raw(owner, key, default)
        mapping = {
            list: PointerList,
            dict: PointerDict,
            collections.abc.Hashable: lambda v: v,
        }

        pointer_constructor = next(
            (pointer for type_, pointer in mapping.items() if isinstance(value, type_)),
            None,
        )

        if (current_value := self._get_raw(owner, key, None)) and type(
            current_value
        ) is not type(default):
            raise ValueError(
                f"Can't switch the type of pointer in database (current: {type(current_value)}, requested: {type(default)})"
            )

        if pointer_constructor is None:
            raise ValueError(
                f"Pointer for type {type(value).__name__} is not implemented"
            )

        if item_type is not None:
            if isinstance(value, list):
                for item in self._get_raw(owner, key, default):
                    if not isinstance(item, dict):
                        raise ValueError(
                            "Item type can only be specified for dedicated keys and"
                            " can't be mixed with other ones"
                        )

                return NamedTupleMiddlewareList(
                    pointer_constructor(self, owner, key, default),
                    item_type,
                )
            if isinstance(value, dict):
                for item in self._get_raw(owner, key, default).values():
                    if not isinstance(item, dict):
                        raise ValueError(
                            "Item type can only be specified for dedicated keys and"
                            " can't be mixed with other ones"
                        )

                return NamedTupleMiddlewareDict(
                    pointer_constructor(self, owner, key, default),
                    item_type,
                )

        return pointer_constructor(self, owner, key, default)
