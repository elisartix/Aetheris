# meta developer: @vibecode
"""Инлайн-инвойс для Telegram Stars — набери цену в звёздах и получи кнопку оплаты."""

import re
import logging

from telethon.tl import types
from .. import loader, utils

logger = logging.getLogger(__name__)

THUMB_URL = "https://img.icons8.com/color/344/bank-building.png"


@loader.tds
class StarsInvoiceMod(loader.Module):
    """Инлайн-инвойс для Telegram Stars"""

    strings = {
        "name": "StarsInvoice",
        "inline_hint": "⭐ Stars Invoice",
        "inline_hint_desc": "Напиши: <b>цена</b> или <b>цена | название</b>",
        "invalid_price": "❌ Неверная цена. Укажи целое число звёзд.",
        "zero_price": "❌ Цена не может быть 0.",
        "result_title": "⭐ {price} Stars",
        "result_desc": "{desc}",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "default_description",
                "Оплата Telegram Stars",
                lambda: "Описание по умолчанию для инвойса",
            ),
            loader.ConfigValue(
                "provider_data",
                "{}",
                lambda: "JSON provider_data для инвойса (обычно '{}')",
            ),
        )

    async def client_ready(self, client, db):
        self._client = client

    @loader.inline_handler()
    async def stars_invoice_handler(self, query):
        """
        Инлайн-инвойс Stars.
        Формат: цена [| описание]
        Примеры:  100  |  50 Пицца  |  250 Donation
        """
        raw = query.query.strip()

        # If called without args, show hint
        if not raw:
            await query.answer(
                [
                    await query.builder.article(
                        title=self.strings["inline_hint"],
                        description=self.strings["inline_hint_desc"],
                        text=self.strings["inline_hint_desc"],
                        parse_mode="HTML",
                        thumb=self.inline._web_document(
                            THUMB_URL, width=512, height=512
                        ),
                        id="stars_hint",
                    )
                ],
                cache_time=0,
                private=True,
            )
            return

        # Parse: "price" or "price | description"
        parts = raw.split("|", 1)
        price_str = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else self.config[
            "default_description"
        ]

        # Validate price
        try:
            price = int(price_str)
        except ValueError:
            # Try to extract first number from string
            m = re.search(r"(\d+)", price_str)
            if m:
                price = int(m.group(1))
            else:
                await query.answer(
                    [
                        await query.builder.article(
                            title="❌ Invalid",
                            description=self.strings["invalid_price"],
                            text=self.strings["invalid_price"],
                            parse_mode="HTML",
                            thumb=self.inline._web_document(
                                "https://img.icons8.com/color/344/cancel.png",
                                width=128,
                                height=128,
                            ),
                            id="stars_err_price",
                        )
                    ],
                    cache_time=0,
                    private=True,
                )
                return

        if price <= 0:
            await query.answer(
                [
                    await query.builder.article(
                        title="❌ Invalid",
                        description=self.strings["zero_price"],
                        text=self.strings["zero_price"],
                        parse_mode="HTML",
                        thumb=self.inline._web_document(
                            "https://img.icons8.com/color/344/cancel.png",
                            width=128,
                            height=128,
                        ),
                        id="stars_err_zero",
                    )
                ],
                cache_time=0,
                private=True,
            )
            return

        # Build Stars invoice
        # currency="XTR" — Telegram Stars
        invoice = types.Invoice(
            currency="XTR",
            prices=[
                types.LabeledPrice(
                    label="Stars",
                    amount=price,
                )
            ],
        )

        # Media invoice message — this is what gets sent when user clicks
        send_message = types.InputBotInlineMessageMediaInvoice(
            title=self.strings["result_title"].format(price=price),
            description=description,
            invoice=invoice,
            payload=b"stars_invoice",
            provider="",
            provider_data=types.DataJSON(data=self.config["provider_data"]),
        )

        # The inline result itself
        result = types.InputBotInlineResult(
            id=f"stars_{price}_{utils.rand(8)}",
            type="invoice",
            send_message=send_message,
            title=self.strings["result_title"].format(price=price),
            description=self.strings["result_desc"].format(desc=description),
            thumb=self.inline._web_document(
                THUMB_URL, width=512, height=512
            ),
        )

        await query.answer(
            [result],
            cache_time=0,
            private=True,
        )
