import os
import re
import asyncio
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

# ===================== CONFIG =====================
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
ADMIN_IDS_RAW = (os.getenv("ADMIN_IDS") or "").strip()  # "123,456"
ADMIN_IDS = {int(x) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()}
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@BRILIANTEX").strip()  # visible in UI
DB_PATH = "bot.db"

# ===================== LOGGING =====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smm_bot")

# ===================== i18n =====================

I18N = {
    "ru": {
        "lang_name": "🇷🇺 Русский",
        "choose_lang_title": "🌐 Выберите язык / Тілді таңдаңыз:",
        "welcome_title": "🚀 Привет! Я помогу прокачать твой аккаунт.",
        "welcome_body": (
            "🔥 Быстрый рост и доверие к странице\n"
            "📈 Подписчики, лайки и просмотры\n"
            "💎 Для бизнеса, блогеров и личных аккаунтов\n\n"
            "👇 Выбери платформу ниже и начни продвижение уже сегодня"
        ),

        "main_menu_title": "🏠 Главное меню:",
        "menu_prices": "💰 Цены / Услуги",
        "menu_orders": "🧾 Мои заказы",
        "menu_faq": "❓ FAQ",
        "menu_lang": "🌐 Сменить язык",

        "back": "⬅️ Назад",
        "home": "🏠 Главное меню",

        "choose_platform": "📱 Выберите платформу:",
        "choose_service": "🧩 Выберите услугу:",
        "choose_pack": "📦 Выберите пакет:",

        "tiktok": "TikTok",
        "instagram": "Instagram",
        "youtube": "YouTube",
        "telegram": "Telegram",

        "srv_tiktok_likes": "👍 Лайки",
        "srv_tiktok_followers": "➕ Подписчики",
        "srv_tiktok_views": "👁 Просмотры",

        "srv_inst_likes": "👍 Лайки",
        "srv_inst_followers": "➕ Подписчики",
        "srv_inst_comments": "💬 Комментарии",
        "srv_inst_views": "👁 Просмотры",

        "srv_yt_views": "👁 Просмотры",
        "srv_yt_followers": "➕ Подписчики",
        "srv_yt_likes": "👍 Лайки",

        "srv_tg_members": "➕ Подписчики/участники",
        "srv_tg_postviews": "👁 Просмотры поста",
        "srv_tg_reacts": "👍 Реакции",

        "pack_line": "• {qty} — {price}₸",
        "selected_final": (
            "✅ Вы выбрали: <b>{platform}</b>\n"
            "🧩 Услуга: <b>{service}</b>\n"
            "📦 Пакет: <b>{qty}</b>\n"
            "💰 Цена: <b>{price}₸</b>\n\n"
            "Чтобы купить — напишите администратору: {admin}"
        ),
        "btn_write_admin": "✉️ Написать админу",

        "send_check_hint": (
            "📎 Отправьте сюда <b>скриншот</b> или <b>файл</b> (чек/квитанцию).\n"
            "Я перешлю администратору, а заказ сохраню со статусом <b>pending</b>."
        ),
        "check_received": "✅ Принято! Я отправил чек администратору. Ваш заказ в статусе <b>pending</b>.",
        "need_check_first": "⚠️ Сначала выберите пакет, затем отправляйте чек/скрин.",
        "my_orders_empty": "🧾 У вас пока нет заказов.",
        "my_orders_title": "🧾 Ваши заказы:",
        "order_row": "🆔 #{id} • {platform} / {service} / {qty} • <b>{status}</b>",

        "faq_text": (
            "❓ <b>FAQ</b>\n\n"
            "• <b>Как заказать?</b> Выберите платформу → услугу → пакет → напишите админу.\n"
            "• <b>Как подтвердить оплату?</b> Нажмите «Отправить чек/скриншот» и отправьте файл/фото.\n"
            "• <b>Сколько ждать?</b> Обычно от нескольких минут до нескольких часов (зависит от нагрузки).\n"
            "• <b>Если что-то не так?</b> Напишите администратору: {admin}\n"
        ),

        "profile_text": (
            "👤 <b>Профиль</b>\n"
            "• ID: <code>{user_id}</code>\n"
            "• Язык: <b>{lang}</b>\n"
            "• Заказов: <b>{orders_count}</b>\n"
        ),

        "admin_only": "⛔️ Доступ только для администратора.",
        "admin_menu_title": "🛠 <b>Admin panel</b>",
        "admin_btn_pending": "📦 Заказы (pending)",
        "admin_btn_done": "✅ Сделать Done",
        "admin_btn_cancel": "❌ Сделать Cancel",
        "admin_btn_prices": "💸 Редактировать цены",

        "admin_pending_empty": "📦 Pending-заказов нет.",
        "admin_pending_title": "📦 Pending заказы:\n\n{rows}",
        "admin_pending_row": "🆔 #{id} | {user_id} | {platform}/{service}/{qty} | {price}₸ | {status}",

        "admin_ask_order_id_done": "Введите ID заказа, который нужно отметить как ✅ done (пример: 12)",
        "admin_ask_order_id_cancel": "Введите ID заказа, который нужно отметить как ❌ cancel (пример: 12)",
        "admin_done_ok": "✅ Готово. Заказ #{id} отмечен как done.",
        "admin_cancel_ok": "❌ Готово. Заказ #{id} отмечен как cancel.",
        "admin_bad_id": "⚠️ Неверный ID. Попробуйте ещё раз.",

        "admin_prices_help": (
            "💸 <b>Редактирование цен</b>\n\n"
            "Отправьте команду в формате:\n"
            "<code>setprice platform service qty price</code>\n\n"
            "Пример:\n"
            "<code>setprice tiktok tiktok_followers 100 250</code>\n\n"
            "platform: tiktok/instagram/youtube/telegram\n"
            "service: как в списке услуг (например tiktok_followers)\n"
            "qty: 100/500/1000 ...\n"
            "price: число\n"
        ),
        "admin_setprice_ok": "✅ Цена обновлена: {platform} / {service} / {qty} = {price}₸",
        "admin_setprice_bad": "⚠️ Формат неверный. Пример: setprice tiktok tiktok_followers 100 250",
        "unknown_callback": "⚠️ Что-то пошло не так. Возвращаю в меню.",
    },
    "kz": {
        "lang_name": "🇰🇿 Қазақша",
        "choose_lang_title": "🌐 Тілді таңдаңыз / Выберите язык:",
        "welcome_title": "🚀 Сәлем! Мен аккаунтыңды күшейтуге көмектесемін.",
        "welcome_body": (
            "🔥 Парақшаңа сенім мен белсенділік қосамыз\n"
            "📈 Подписчик, лайк және қаралым арқылы өсім\n"
            "💎 Бизнеске, блогерлерге және жеке аккаунттарға арналған\n\n"
            "👇 Төмендегі батырманы басып, қазірден бастап дамытуды баста"
        ),

        "main_menu_title": "🏠 Басты мәзір:",
        "menu_prices": "💰 Бағалар / Қызметтер",
        "menu_orders": "🧾 Менің тапсырыстарым",
        "menu_faq": "❓ FAQ",
        "menu_lang": "🌐 Тілді ауыстыру",

        "back": "⬅️ Артқа",
        "home": "🏠 Басты мәзір",

        "choose_platform": "📱 Платформаны таңдаңыз:",
        "choose_service": "🧩 Қызметті таңдаңыз:",
        "choose_pack": "📦 Пакетті таңдаңыз:",

        "tiktok": "TikTok",
        "instagram": "Instagram",
        "youtube": "YouTube",
        "telegram": "Telegram",

        "srv_tiktok_likes": "👍 Лайк",
        "srv_tiktok_followers": "➕ Подписчик",
        "srv_tiktok_views": "👁 Қаралым",

        "srv_inst_likes": "👍 Лайк",
        "srv_inst_followers": "➕ Подписчик",
        "srv_inst_comments": "💬 Комментарий",
        "srv_inst_views": "👁 Қаралым",

        "srv_yt_views": "👁 Қаралым",
        "srv_yt_followers": "➕ Подписчик",
        "srv_yt_likes": "👍 Лайк",

        "srv_tg_members": "➕ Қатысушы/подписчик",
        "srv_tg_postviews": "👁 Пост қаралымы",
        "srv_tg_reacts": "👍 Реакция",

        "pack_line": "• {qty} — {price}₸",
        "selected_final": (
            "✅ Таңдауыңыз:\n"
            "📌 Платформа: <b>{platform}</b>\n"
            "🧩 Қызмет: <b>{service}</b>\n"
            "📦 Пакет: <b>{qty}</b>\n"
            "💰 Баға: <b>{price}₸</b>\n\n"
            "Сатып алу үшін админге жазыңыз: {admin}"
        ),
        "btn_write_admin": "✉️ Админге жазу",

        "send_check_hint": (
            "📎 Осы жерге <b>скриншот</b> немесе <b>файл</b> (чек) жіберіңіз.\n"
            "Мен админге жіберемін, тапсырыс <b>pending</b> болып сақталады."
        ),
        "check_received": "✅ Қабылданды! Чек админге жіберілді. Тапсырысыңыз <b>pending</b> статусында.",
        "need_check_first": "⚠️ Алдымен пакет таңдаңыз, содан кейін чек/скрин жіберіңіз.",
        "my_orders_empty": "🧾 Сізде әзірге тапсырыс жоқ.",
        "my_orders_title": "🧾 Сіздің тапсырыстарыңыз:",
        "order_row": "🆔 #{id} • {platform} / {service} / {qty} • <b>{status}</b>",

        "faq_text": (
            "❓ <b>FAQ</b>\n\n"
            "• <b>Қалай тапсырыс беремін?</b> Платформа → қызмет → пакет таңдаңыз.\n"
            "• <b>Төлемді қалай жасаймын?</b> Админге жазу арқылы.\n"
            "• <b>Қанша күтемін?</b> Әдетте бірнеше минуттан бірнеше сағатқа дейін.\n"
            "• <b>Бірдеңе қате болса</b> Админге жазыңыз: {admin}\n"
        ),

        "profile_text": (
            "👤 <b>Профиль</b>\n"
            "• ID: <code>{user_id}</code>\n"
            "• Тіл: <b>{lang}</b>\n"
            "• Тапсырыс саны: <b>{orders_count}</b>\n"
        ),

        "admin_only": "⛔️ Тек админ үшін.",
        "admin_menu_title": "🛠 <b>Admin panel</b>",
        "admin_btn_pending": "📦 Тапсырыстар (pending)",
        "admin_btn_done": "✅ Done жасау",
        "admin_btn_cancel": "❌ Cancel жасау",
        "admin_btn_prices": "💸 Бағаны өзгерту",

        "admin_pending_empty": "📦 Pending тапсырыс жоқ.",
        "admin_pending_title": "📦 Pending тапсырыстар:\n\n{rows}",
        "admin_pending_row": "🆔 #{id} | {user_id} | {platform}/{service}/{qty} | {price}₸ | {status}",

        "admin_ask_order_id_done": "✅ done ету үшін тапсырыс ID жіберіңіз (мысалы: 12)",
        "admin_ask_order_id_cancel": "❌ cancel ету үшін тапсырыс ID жіберіңіз (мысалы: 12)",
        "admin_done_ok": "✅ Дайын. #{id} тапсырыс done болды.",
        "admin_cancel_ok": "❌ Дайын. #{id} тапсырыс cancel болды.",
        "admin_bad_id": "⚠️ ID қате. Қайта көріңіз.",

        "admin_prices_help": (
            "💸 <b>Бағаны өзгерту</b>\n\n"
            "Формат:\n"
            "<code>setprice platform service qty price</code>\n\n"
            "Мысал:\n"
            "<code>setprice tiktok tiktok_followers 100 250</code>\n"
        ),
        "admin_setprice_ok": "✅ Баға жаңартылды: {platform} / {service} / {qty} = {price}₸",
        "admin_setprice_bad": "⚠️ Формат қате. Мысал: setprice tiktok tiktok_followers 100 250",
        "unknown_callback": "⚠️ Қате болды. Мәзірге қайтарамын.",
    }
}

def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in I18N else "ru"
    text = I18N[lang].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text

# ===================== CATALOG (services & default prices) =====================

PLATFORMS = {
    "tiktok": {"title_key": "tiktok"},
    "instagram": {"title_key": "instagram"},
    "youtube": {"title_key": "youtube"},
    "telegram": {"title_key": "telegram"},
}

SERVICES = {
    "tiktok": {
        "tiktok_likes": {"title_key": "srv_tiktok_likes"},
        "tiktok_followers": {"title_key": "srv_tiktok_followers"},
        "tiktok_views": {"title_key": "srv_tiktok_views"},
    },
    "instagram": {
        "inst_likes": {"title_key": "srv_inst_likes"},
        "inst_followers": {"title_key": "srv_inst_followers"},
        "inst_comments": {"title_key": "srv_inst_comments"},
        "inst_views": {"title_key": "srv_inst_views"},
    },
    "youtube": {
        "yt_views": {"title_key": "srv_yt_views"},
        "yt_followers": {"title_key": "srv_yt_followers"},
        "yt_likes": {"title_key": "srv_yt_likes"},
    },
    "telegram": {
        "tg_members": {"title_key": "srv_tg_members"},
        "tg_postviews": {"title_key": "srv_tg_postviews"},
        "tg_reacts": {"title_key": "srv_tg_reacts"},
    },
}

DEFAULT_PACKS = [100, 500, 1000]
DEFAULT_PRICES = {
    # service -> qty -> price
    "tiktok_likes": {100: 150, 500: 650, 1000: 1200},
    "tiktok_followers": {100: 250, 500: 1100, 1000: 2000},
    "tiktok_views": {100: 80, 500: 300, 1000: 500},

    "inst_likes": {100: 180, 500: 750, 1000: 1400},
    "inst_followers": {100: 300, 500: 1300, 1000: 2400},
    "inst_comments": {100: 500, 500: 2200, 1000: 4000},
    "inst_views": {100: 90, 500: 350, 1000: 600},

    "yt_views": {100: 120, 500: 550, 1000: 1000},
    "yt_followers": {100: 450, 500: 2100, 1000: 3900},
    "yt_likes": {100: 250, 500: 1150, 1000: 2100},

    "tg_members": {100: 400, 500: 1800, 1000: 3300},
    "tg_postviews": {100: 150, 500: 650, 1000: 1200},
    "tg_reacts": {100: 200, 500: 900, 1000: 1600},
}

# ===================== DB =====================

def db_connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def db_init():
    con = db_connect()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        lang TEXT NOT NULL DEFAULT 'ru',
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS prices (
        platform TEXT NOT NULL,
        service TEXT NOT NULL,
        qty INTEGER NOT NULL,
        price INTEGER NOT NULL,
        PRIMARY KEY (platform, service, qty)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        platform TEXT NOT NULL,
        service TEXT NOT NULL,
        qty INTEGER NOT NULL,
        price INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        proof_file_id TEXT,
        proof_type TEXT
    )
    """)

    # seed prices if empty
    cur.execute("SELECT COUNT(*) AS c FROM prices")
    if cur.fetchone()["c"] == 0:
        for plat, srv_map in SERVICES.items():
            for srv in srv_map.keys():
                packs = DEFAULT_PRICES.get(srv, {})
                for qty in DEFAULT_PACKS:
                    price = int(packs.get(qty, 0))
                    cur.execute(
                        "INSERT OR REPLACE INTO prices(platform, service, qty, price) VALUES(?,?,?,?)",
                        (plat, srv, qty, price)
                    )

    con.commit()
    con.close()

def db_get_lang(user_id: int) -> str:
    con = db_connect()
    cur = con.cursor()
    cur.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row["lang"] if row else "ru"

def db_upsert_user(user_id: int, lang: str):
    con = db_connect()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO users(user_id, lang, created_at)
        VALUES(?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang
    """, (user_id, lang, datetime.utcnow().isoformat()))
    con.commit()
    con.close()

def db_get_price(platform: str, service: str, qty: int) -> int:
    con = db_connect()
    cur = con.cursor()
    cur.execute("SELECT price FROM prices WHERE platform=? AND service=? AND qty=?", (platform, service, qty))
    row = cur.fetchone()
    con.close()
    if row:
        return int(row["price"])
    # fallback
    return int(DEFAULT_PRICES.get(service, {}).get(qty, 0))

def db_list_packs(platform: str, service: str):
    con = db_connect()
    cur = con.cursor()
    cur.execute("SELECT qty, price FROM prices WHERE platform=? AND service=? ORDER BY qty ASC", (platform, service))
    rows = cur.fetchall()
    con.close()
    if rows:
        return [(int(r["qty"]), int(r["price"])) for r in rows]
    # fallback
    packs = DEFAULT_PRICES.get(service, {})
    return sorted([(int(q), int(p)) for q, p in packs.items()], key=lambda x: x[0])

def db_create_order(user_id: int, platform: str, service: str, qty: int, price: int, proof_file_id: str, proof_type: str):
    con = db_connect()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO orders(user_id, platform, service, qty, price, status, created_at, proof_file_id, proof_type)
        VALUES(?,?,?,?,?,'pending',?,?,?)
    """, (user_id, platform, service, qty, price, datetime.utcnow().isoformat(), proof_file_id, proof_type))
    con.commit()
    order_id = cur.lastrowid
    con.close()
    return int(order_id)

def db_list_orders_by_user(user_id: int):
    con = db_connect()
    cur = con.cursor()
    cur.execute("""
        SELECT id, platform, service, qty, price, status, created_at
        FROM orders WHERE user_id=?
        ORDER BY id DESC
        LIMIT 50
    """, (user_id,))
    rows = cur.fetchall()
    con.close()
    return rows

def db_count_orders_by_user(user_id: int) -> int:
    con = db_connect()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM orders WHERE user_id=?", (user_id,))
    n = int(cur.fetchone()["c"])
    con.close()
    return n

def db_list_pending_orders(limit: int = 30):
    con = db_connect()
    cur = con.cursor()
    cur.execute("""
        SELECT id, user_id, platform, service, qty, price, status, created_at
        FROM orders WHERE status='pending'
        ORDER BY id ASC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    con.close()
    return rows

def db_update_order_status(order_id: int, status: str) -> bool:
    con = db_connect()
    cur = con.cursor()
    cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    con.commit()
    ok = cur.rowcount > 0
    con.close()
    return ok

def db_set_price(platform: str, service: str, qty: int, price: int):
    con = db_connect()
    cur = con.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO prices(platform, service, qty, price)
        VALUES(?,?,?,?)
    """, (platform, service, qty, price))
    con.commit()
    con.close()

# ===================== CALLBACK utils =====================

def cb_kv(prefix: str, value: str) -> str:
    # example: "lang:ru", "menu:prices"
    return f"{prefix}:{value}"

def cb_pack(service: str, qty: int) -> str:
    # "pack:tiktok_followers:100"
    return f"pack:{service}:{qty}"

def parse_cb(data: str):
    """
    Supported:
      lang:ru
      menu:prices/orders/faq/profile/lang
      plat:tiktok
      srv:tiktok_followers
      pack:tiktok_followers:100
      nav:back:...
      admin:pending/done/cancel/prices
    """
    if not data or ":" not in data:
        return None
    parts = data.split(":")
    return parts

# ===================== In-memory state (fallback) =====================

# user_id -> dict with selection context
USER_CTX = {}  # { user_id: { "platform":..., "service":..., "qty":..., "price":... } }

# admin state: waiting for order id input (done/cancel) and waiting for setprice
ADMIN_STATE = {}  # { admin_id: {"mode": "done"/"cancel"/"setprice"} }

# ===================== Keyboards =====================

def kb_lang() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=I18N["ru"]["lang_name"], callback_data=cb_kv("lang", "ru"))],
        [InlineKeyboardButton(text=I18N["kz"]["lang_name"], callback_data=cb_kv("lang", "kz"))],
    ])

def kb_home(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "menu_prices"), callback_data=cb_kv("menu", "prices"))],
        [InlineKeyboardButton(text=t(lang, "menu_orders"), callback_data=cb_kv("menu", "orders"))],
        [InlineKeyboardButton(text=t(lang, "menu_faq"), callback_data=cb_kv("menu", "faq"))],
        [InlineKeyboardButton(text=t(lang, "menu_lang"), callback_data=cb_kv("menu", "lang"))],
    ])

def kb_back_home(lang: str, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "back"), callback_data=back_cb),
            InlineKeyboardButton(text=t(lang, "home"), callback_data=cb_kv("menu", "home")),
        ]
    ])

def kb_platforms(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(lang, "tiktok"), callback_data=cb_kv("plat", "tiktok"))],
        [InlineKeyboardButton(text=t(lang, "instagram"), callback_data=cb_kv("plat", "instagram"))],
        [InlineKeyboardButton(text=t(lang, "youtube"), callback_data=cb_kv("plat", "youtube"))],
        [InlineKeyboardButton(text=t(lang, "telegram"), callback_data=cb_kv("plat", "telegram"))],
        [
            InlineKeyboardButton(text=t(lang, "back"), callback_data=cb_kv("menu", "home")),
            InlineKeyboardButton(text=t(lang, "home"), callback_data=cb_kv("menu", "home")),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_services(lang: str, platform: str) -> InlineKeyboardMarkup:
    srv_map = SERVICES.get(platform, {})
    rows = []
    for srv_key, meta in srv_map.items():
        rows.append([InlineKeyboardButton(text=t(lang, meta["title_key"]), callback_data=cb_kv("srv", srv_key))])
    rows.append([
        InlineKeyboardButton(text=t(lang, "back"), callback_data=cb_kv("menu", "prices")),
        InlineKeyboardButton(text=t(lang, "home"), callback_data=cb_kv("menu", "home")),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_packs(lang: str, platform: str, service: str) -> InlineKeyboardMarkup:
    packs = db_list_packs(platform, service)
    rows = []
    for qty, price in packs:
        txt = f"{qty} — {price}₸"
        rows.append([InlineKeyboardButton(text=txt, callback_data=cb_pack(service, qty))])
    rows.append([
        InlineKeyboardButton(text=t(lang, "back"), callback_data=cb_kv("plat", platform)),
        InlineKeyboardButton(text=t(lang, "home"), callback_data=cb_kv("menu", "home")),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_final(lang: str) -> InlineKeyboardMarkup:
    # admin url without @
    admin_user_clean = ADMIN_USERNAME.lstrip("@")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_write_admin"), url=f"https://t.me/{admin_user_clean}")],
        [
            InlineKeyboardButton(text=t(lang, "back"), callback_data=cb_kv("menu", "prices")),
            InlineKeyboardButton(text=t(lang, "home"), callback_data=cb_kv("menu", "home")),
        ],
    ])

def kb_admin(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "admin_btn_pending"), callback_data="admin:pending")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_done"), callback_data="admin:done")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_cancel"), callback_data="admin:cancel")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_prices"), callback_data="admin:prices")],
        [InlineKeyboardButton(text=t(lang, "home"), callback_data=cb_kv("menu", "home"))],
    ])

# ===================== Render helpers =====================

def platform_title(lang: str, platform: str) -> str:
    meta = PLATFORMS.get(platform)
    return t(lang, meta["title_key"]) if meta else platform

def service_title(lang: str, platform: str, service: str) -> str:
    srv_map = SERVICES.get(platform, {})
    meta = srv_map.get(service)
    if meta:
        return t(lang, meta["title_key"])
    # try find across platforms
    for plat, m in SERVICES.items():
        if service in m:
            return t(lang, m[service]["title_key"])
    return service

# ===================== BOT init =====================

async def safe_answer(cb: CallbackQuery, text: str):
    try:
        await cb.answer(text, show_alert=False)
    except Exception:
        pass

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def send_home(message_or_cb, lang: str):
    text = f"{t(lang, 'main_menu_title')}"
    kb = kb_home(lang)
    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await message_or_cb.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def send_welcome(message: Message, lang: str):
    txt = f"{t(lang,'welcome_title')}\n\n{t(lang,'welcome_body')}"
    await message.answer(txt, reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)

# ===================== Dispatcher handlers =====================

dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not BOT_TOKEN:
        await message.answer("BOT_TOKEN env не задан. Установите BOT_TOKEN и перезапустите.")
        return

    # ensure user exists
    user_id = message.from_user.id
    lang = db_get_lang(user_id)
    if lang not in ("ru", "kz"):
        lang = "ru"
    db_upsert_user(user_id, lang)

    # show language selection always on /start
    await message.answer(t(lang, "choose_lang_title"), reply_markup=kb_lang(), parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(cb: CallbackQuery):
    parts = parse_cb(cb.data)
    if not parts or len(parts) != 2:
        # fallback
        lang = db_get_lang(cb.from_user.id)
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return
    _, lang = parts
    if lang not in ("ru", "kz"):
        lang = "ru"

    db_upsert_user(cb.from_user.id, lang)
    USER_CTX.pop(cb.from_user.id, None)  # reset selection
    await safe_answer(cb, "OK")
    await cb.message.edit_text(t(lang, "welcome_title") + "\n\n" + t(lang, "welcome_body"),
                               reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("menu:"))
async def on_menu(cb: CallbackQuery):
    lang = db_get_lang(cb.from_user.id)
    parts = parse_cb(cb.data)
    if not parts or len(parts) != 2:
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    _, action = parts
    await safe_answer(cb, "✅")

    if action in ("home",):
        await send_home(cb, lang)
        return

    if action == "prices":
        await cb.message.edit_text(t(lang, "choose_platform"), reply_markup=kb_platforms(lang), parse_mode=ParseMode.HTML)
        return

    if action == "orders":
        rows = db_list_orders_by_user(cb.from_user.id)
        if not rows:
            await cb.message.edit_text(t(lang, "my_orders_empty"),
                                       reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
            return
        lines = [t(lang, "my_orders_title")]
        for r in rows:
            plat_t = platform_title(lang, r["platform"])
            srv_t = service_title(lang, r["platform"], r["service"])
            lines.append(t(lang, "order_row",
                           id=r["id"], platform=plat_t, service=srv_t, qty=r["qty"], status=r["status"]))
        await cb.message.edit_text("\n".join(lines),
                                   reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    if action == "faq":
        await cb.message.edit_text(t(lang, "faq_text", admin=ADMIN_USERNAME),
                                   reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    if action == "profile":
        count = db_count_orders_by_user(cb.from_user.id)
        await cb.message.edit_text(
            t(lang, "profile_text",
              user_id=cb.from_user.id,
              lang=t(lang, "lang_name"),
              orders_count=count),
            reply_markup=kb_home(lang),
            parse_mode=ParseMode.HTML
        )
        return

    if action == "lang":
        await cb.message.edit_text(t(lang, "choose_lang_title"),
                                   reply_markup=kb_lang(), parse_mode=ParseMode.HTML)
        return

    if action == "sendcheck":
        # user must have selected a package
        ctx = USER_CTX.get(cb.from_user.id)
        if not ctx or not all(k in ctx for k in ("platform", "service", "qty", "price")):
            await cb.message.edit_text(t(lang, "need_check_first"),
                                       reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
            return

        # mark mode "awaiting_proof"
        ctx["awaiting_proof"] = True
        USER_CTX[cb.from_user.id] = ctx
        await cb.message.edit_text(t(lang, "send_check_hint"),
                                   reply_markup=kb_back_home(lang, cb_kv("menu", "prices")),
                                   parse_mode=ParseMode.HTML)
        return

    # fallback
    await cb.message.edit_text(t(lang, "unknown_callback"),
                               reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("plat:"))
async def on_platform(cb: CallbackQuery):
    lang = db_get_lang(cb.from_user.id)
    parts = parse_cb(cb.data)
    if not parts or len(parts) != 2:
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    _, platform = parts
    if platform not in PLATFORMS:
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    # save ctx
    ctx = USER_CTX.get(cb.from_user.id, {})
    ctx.update({"platform": platform})
    # reset deeper selections
    ctx.pop("service", None)
    ctx.pop("qty", None)
    ctx.pop("price", None)
    ctx.pop("awaiting_proof", None)
    USER_CTX[cb.from_user.id] = ctx

    await safe_answer(cb, "✅")
    await cb.message.edit_text(t(lang, "choose_service"),
                               reply_markup=kb_services(lang, platform),
                               parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("srv:"))
async def on_service(cb: CallbackQuery):
    lang = db_get_lang(cb.from_user.id)
    parts = parse_cb(cb.data)
    if not parts or len(parts) != 2:
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return
    _, service = parts

    ctx = USER_CTX.get(cb.from_user.id)
    if not ctx or "platform" not in ctx:
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    platform = ctx["platform"]
    if service not in SERVICES.get(platform, {}):
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    ctx.update({"service": service})
    ctx.pop("qty", None)
    ctx.pop("price", None)
    ctx.pop("awaiting_proof", None)
    USER_CTX[cb.from_user.id] = ctx

    await safe_answer(cb, "✅")
    await cb.message.edit_text(t(lang, "choose_pack"),
                               reply_markup=kb_packs(lang, platform, service),
                               parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("pack:"))
async def on_pack(cb: CallbackQuery):
    lang = db_get_lang(cb.from_user.id)
    parts = parse_cb(cb.data)
    if not parts or len(parts) != 3:
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    _, service, qty_s = parts
    if not qty_s.isdigit():
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return
    qty = int(qty_s)

    ctx = USER_CTX.get(cb.from_user.id)
    if not ctx or "platform" not in ctx:
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    platform = ctx["platform"]
    if service not in SERVICES.get(platform, {}):
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    price = db_get_price(platform, service, qty)
    ctx.update({"service": service, "qty": qty, "price": price})
    ctx.pop("awaiting_proof", None)
    USER_CTX[cb.from_user.id] = ctx

    plat_t = platform_title(lang, platform)
    srv_t = service_title(lang, platform, service)

    text = t(lang, "selected_final",
             platform=plat_t,
             service=srv_t,
             qty=str(qty),
             price=str(price),
             admin=ADMIN_USERNAME)
    await safe_answer(cb, "✅")
    await cb.message.edit_text(text, reply_markup=kb_final(lang), parse_mode=ParseMode.HTML)

@dp.message(F.photo | F.document)
async def on_proof(message: Message, bot: Bot):
    user_id = message.from_user.id
    lang = db_get_lang(user_id)

    ctx = USER_CTX.get(user_id)
    if not ctx or not ctx.get("awaiting_proof"):
        # ignore or guide
        await message.answer(t(lang, "need_check_first"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    platform = ctx.get("platform")
    service = ctx.get("service")
    qty = ctx.get("qty")
    price = ctx.get("price")

    if not (platform and service and qty and price is not None):
        await message.answer(t(lang, "need_check_first"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    # determine file_id and type
    proof_type = "document"
    proof_file_id = None
    if message.photo:
        proof_type = "photo"
        proof_file_id = message.photo[-1].file_id
    elif message.document:
        proof_type = "document"
        proof_file_id = message.document.file_id

    # save order
    order_id = db_create_order(
        user_id=user_id,
        platform=platform,
        service=service,
        qty=int(qty),
        price=int(price),
        proof_file_id=proof_file_id or "",
        proof_type=proof_type
    )

    # forward to admins
    plat_ru = platform_title("ru", platform)
    srv_ru = service_title("ru", platform, service)
    caption = (
        f"🧾 <b>Новый чек/скрин</b>\n"
        f"🆔 Order: <b>#{order_id}</b>\n"
        f"👤 User: <code>{user_id}</code>\n"
        f"📌 {plat_ru} / {srv_ru} / {qty}\n"
        f"💰 {price}₸\n"
        f"Статус: <b>pending</b>"
    )

    for admin_id in ADMIN_IDS:
        try:
            if proof_type == "photo" and message.photo:
                await bot.send_photo(admin_id, proof_file_id, caption=caption, parse_mode=ParseMode.HTML)
            elif proof_type == "document" and message.document:
                await bot.send_document(admin_id, proof_file_id, caption=caption, parse_mode=ParseMode.HTML)
            else:
                # fallback forward original message
                await message.forward(admin_id)
                await bot.send_message(admin_id, caption, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")

    # clear awaiting mode
    ctx["awaiting_proof"] = False
    USER_CTX[user_id] = ctx

    await message.answer(t(lang, "check_received"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    user_id = message.from_user.id
    lang = db_get_lang(user_id)
    if not is_admin(user_id):
        await message.answer(t(lang, "admin_only"), parse_mode=ParseMode.HTML)
        return
    ADMIN_STATE.pop(user_id, None)
    await message.answer(t(lang, "admin_menu_title"), reply_markup=kb_admin(lang), parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("admin:"))
async def on_admin(cb: CallbackQuery):
    user_id = cb.from_user.id
    lang = db_get_lang(user_id)

    if not is_admin(user_id):
        await safe_answer(cb, "⛔️")
        await cb.message.edit_text(t(lang, "admin_only"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
        return

    parts = parse_cb(cb.data)
    if not parts or len(parts) != 2:
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_admin(lang), parse_mode=ParseMode.HTML)
        return

    _, action = parts
    await safe_answer(cb, "✅")

    if action == "pending":
        rows = db_list_pending_orders(limit=30)
        if not rows:
            await cb.message.edit_text(t(lang, "admin_pending_empty"),
                                       reply_markup=kb_admin(lang), parse_mode=ParseMode.HTML)
            return
        lines = []
        for r in rows:
            lines.append(t(lang, "admin_pending_row",
                           id=r["id"], user_id=r["user_id"],
                           platform=r["platform"], service=r["service"],
                           qty=r["qty"], price=r["price"], status=r["status"]))
        await cb.message.edit_text(t(lang, "admin_pending_title", rows="\n".join(lines)),
                                   reply_markup=kb_admin(lang), parse_mode=ParseMode.HTML)
        return

    if action == "done":
        ADMIN_STATE[user_id] = {"mode": "done"}
        await cb.message.edit_text(t(lang, "admin_ask_order_id_done"),
                                   reply_markup=kb_admin(lang), parse_mode=ParseMode.HTML)
        return

    if action == "cancel":
        ADMIN_STATE[user_id] = {"mode": "cancel"}
        await cb.message.edit_text(t(lang, "admin_ask_order_id_cancel"),
                                   reply_markup=kb_admin(lang), parse_mode=ParseMode.HTML)
        return

    if action == "prices":
        ADMIN_STATE[user_id] = {"mode": "setprice"}
        await cb.message.edit_text(t(lang, "admin_prices_help"),
                                   reply_markup=kb_admin(lang), parse_mode=ParseMode.HTML)
        return

    await cb.message.edit_text(t(lang, "unknown_callback"),
                               reply_markup=kb_admin(lang), parse_mode=ParseMode.HTML)

@dp.message()
async def on_text(message: Message):
    # handle admin numeric input / setprice
    user_id = message.from_user.id
    lang = db_get_lang(user_id)

    if is_admin(user_id) and user_id in ADMIN_STATE:
        mode = ADMIN_STATE[user_id].get("mode")

        if mode in ("done", "cancel"):
            txt = (message.text or "").strip()
            if not txt.isdigit():
                await message.answer(t(lang, "admin_bad_id"), parse_mode=ParseMode.HTML)
                return
            order_id = int(txt)
            new_status = "done" if mode == "done" else "cancel"
            ok = db_update_order_status(order_id, new_status)
            if not ok:
                await message.answer(t(lang, "admin_bad_id"), parse_mode=ParseMode.HTML)
                return
            ADMIN_STATE.pop(user_id, None)
            if new_status == "done":
                await message.answer(t(lang, "admin_done_ok", id=order_id), parse_mode=ParseMode.HTML)
            else:
                await message.answer(t(lang, "admin_cancel_ok", id=order_id), parse_mode=ParseMode.HTML)
            return

        if mode == "setprice":
            txt = (message.text or "").strip()
            # expected: setprice platform service qty price
            m = re.match(r"^setprice\s+(\w+)\s+(\w+)\s+(\d+)\s+(\d+)\s*$", txt, flags=re.IGNORECASE)
            if not m:
                await message.answer(t(lang, "admin_setprice_bad"), parse_mode=ParseMode.HTML)
                return
            platform, service, qty_s, price_s = m.group(1).lower(), m.group(2), m.group(3), m.group(4)
            qty, price = int(qty_s), int(price_s)

            if platform not in PLATFORMS or service not in SERVICES.get(platform, {}):
                await message.answer(t(lang, "admin_setprice_bad"), parse_mode=ParseMode.HTML)
                return

            db_set_price(platform, service, qty, price)
            await message.answer(t(lang, "admin_setprice_ok",
                                   platform=platform, service=service, qty=qty, price=price),
                                 parse_mode=ParseMode.HTML)
            return

    # non-admin: if user types random, show home
    await send_home(message, lang)

@dp.callback_query()
async def on_unknown_callback(cb: CallbackQuery):
    lang = db_get_lang(cb.from_user.id)
    await safe_answer(cb, "⚠️")
    try:
        await cb.message.edit_text(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)
    except Exception:
        # if message can't be edited
        await cb.message.answer(t(lang, "unknown_callback"), reply_markup=kb_home(lang), parse_mode=ParseMode.HTML)

# ===================== MAIN =====================

async def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN env is empty. Set BOT_TOKEN and restart.")
        return

    db_init()
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)

    me = await bot.get_me()
    logger.info(f"Bot started: @{me.username} | admins={list(ADMIN_IDS)} | admin_username={ADMIN_USERNAME}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
