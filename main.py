import os
import math
import sqlite3
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ===================== LOGGING =====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===================== CONFIG =====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# PowerShell: $env:ADMIN_IDS="8429326762,111222333"
ADMIN_IDS = set(
    int(x) for x in os.getenv("ADMIN_IDS", "8429326762,8561076526").split(",")
    if x.strip().isdigit()
)

DB_PATH = "bot.db"

# Личка (қайда жазу керек)
TRUST_CONTACT = "@icloud_klk"

PRICES = {
    "KZT": [
        ("АЙФОН 11", "20K"),
        ("АЙФОН 12", "25K"),
        ("АЙФОН 13", "32K"),
        ("АЙФОН 14", "40K"),
        ("АЙФОН 15", "45K"),
        ("АЙФОН 16", "50K"),
        ("АЙФОН 17", "60K"),
        ("Примечание", "(Pro/Max версии считаются отдельно)"),
    ],
    "RUB": [
        ("АЙФОН 11", "3K"),
        ("АЙФОН 12", "3,7K"),
        ("АЙФОН 13", "4,7K"),
        ("АЙФОН 14", "6K"),
        ("АЙФОН 15", "6,7K"),
        ("АЙФОН 16", "7,4K"),
        ("АЙФОН 17", "8,9K"),
        ("Примечание", "(Pro/Max версии считаются отдельно)"),
    ],
}

# ===================== STATES =====================
ASK_CONTACT, ASK_NOTE = range(2)
ADMIN_REVIEW_WAIT_MEDIA = 20

REVIEWS_PER_PAGE = 6  # 1 бет = 6 медиа (альбом)

# ===================== DB =====================
def db_init():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            model TEXT,
            contact TEXT,
            note TEXT,
            currency TEXT,
            status TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_type TEXT NOT NULL,
            file_id TEXT NOT NULL,
            caption TEXT,
            created_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def db_add_review(media_type: str, file_id: str, caption: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reviews (media_type, file_id, caption, created_at) VALUES (?, ?, ?, ?)",
        (media_type, file_id, (caption or "").strip(), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def db_count_reviews() -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM reviews")
    (cnt,) = cur.fetchone()
    conn.close()
    return int(cnt)


def db_get_reviews_page(page: int, per_page: int = REVIEWS_PER_PAGE):
    if page < 1:
        page = 1
    offset = (page - 1) * per_page
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, media_type, file_id, COALESCE(caption, ''), created_at
        FROM reviews
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (per_page, offset),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def db_get_reviews_list(limit: int = 200):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, media_type, COALESCE(caption,''), created_at
        FROM reviews
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def db_del_review(review_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected


# ===================== Keyboards =====================
def kb_main():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💼 Услуги / Цены", callback_data="MENU_PRICES")],
            [InlineKeyboardButton("📝 Заказать", callback_data="MENU_ORDER")],
            [InlineKeyboardButton("🆓 Бесплатная консультация", callback_data="MENU_FREE")],
            [InlineKeyboardButton("⭐ Отзывы", callback_data="MENU_REVIEWS")],
            [InlineKeyboardButton("🔐 Доверие / Гарантия", callback_data="MENU_TRUST")],
            [InlineKeyboardButton("📞 Контакты", callback_data="MENU_CONTACT")],
        ]
    )


def kb_currency():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("KZT 🇰🇿", callback_data="CUR_KZT"),
                InlineKeyboardButton("RUB 🇷🇺", callback_data="CUR_RUB"),
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="BACK_MAIN")],
        ]
    )


def kb_prices_actions(currency: str):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📝 Заказать", callback_data=f"ORDER_{currency}")],
            [InlineKeyboardButton("🆓 Бесплатно", callback_data=f"FREE_{currency}")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="BACK_CURRENCY")],
        ]
    )


def kb_back_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="BACK_MAIN")]])


def kb_reviews_nav(page: int, total_pages: int):
    total_pages = max(1, total_pages)
    page = max(1, min(page, total_pages))

    left = InlineKeyboardButton("⬅️", callback_data=f"REV_PAGE_{page-1}") if page > 1 else InlineKeyboardButton("⬅️", callback_data="REV_NOP")
    right = InlineKeyboardButton("➡️", callback_data=f"REV_PAGE_{page+1}") if page < total_pages else InlineKeyboardButton("➡️", callback_data="REV_NOP")

    return InlineKeyboardMarkup(
        [
            [
                left,
                InlineKeyboardButton(f"{page}/{total_pages}", callback_data="REV_NOP"),
                right,
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="BACK_MAIN")],
        ]
    )


# ===================== Helpers =====================
def format_prices(currency: str) -> str:
    rows = PRICES.get(currency, [])
    lines, note = [], ""
    for name, price in rows:
        if name == "Примечание":
            note = price
        else:
            lines.append(f"• {name} — {price} {currency}")
    if note:
        lines.append("")
        lines.append(note)
    return "📌 Прайс-лист:\n\n" + "\n".join(lines)


def user_str(user) -> str:
    return f"@{user.username}" if user.username else "(без username)"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except Exception as e:
            logger.warning("notify_admins error to %s: %s", admin_id, e)


async def delete_prev_reviews_pack(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    ids = context.user_data.get("reviews_pack_ids", [])
    if not ids:
        return
    for mid in ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass
    context.user_data["reviews_pack_ids"] = []


def build_media_group(rows):
    """
    Telegram album: подпись только у первого элемента.
    """
    media = []
    for i, (rid, mtype, file_id, caption, _dt) in enumerate(rows):
        cap = ""
        if i == 0:
            cap = "⭐ Отзывы\n\nЛистайте свайпом 👆"
            if caption.strip():
                cap += "\n\n" + caption.strip()[:900]

        if mtype == "video":
            media.append(InputMediaVideo(media=file_id, caption=cap))
        else:
            media.append(InputMediaPhoto(media=file_id, caption=cap))
    return media


async def send_reviews_pack(chat_id: int, context: ContextTypes.DEFAULT_TYPE, page: int):
    total = db_count_reviews()
    if total <= 0:
        await delete_prev_reviews_pack(context, chat_id)
        m = await context.bot.send_message(
            chat_id=chat_id,
            text="⭐ Отзывы\n\nПока отзывов нет.\n\nАдмин добавляет: /addreview",
            reply_markup=kb_back_main(),
        )
        context.user_data["reviews_pack_ids"] = [m.message_id]
        return

    total_pages = max(1, math.ceil(total / REVIEWS_PER_PAGE))
    page = max(1, min(page, total_pages))
    rows = db_get_reviews_page(page, REVIEWS_PER_PAGE)

    await delete_prev_reviews_pack(context, chat_id)

    media_group = build_media_group(rows)

    sent_msgs = await context.bot.send_media_group(chat_id=chat_id, media=media_group)
    msg_ids = [m.message_id for m in sent_msgs]

    nav = await context.bot.send_message(
        chat_id=chat_id,
        text="⬇️ Переключение страниц:",
        reply_markup=kb_reviews_nav(page, total_pages),
    )
    msg_ids.append(nav.message_id)
    context.user_data["reviews_pack_ids"] = msg_ids


# ===================== Handlers =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Привет! 👋\nВыберите интересующий раздел:",
        reply_markup=kb_main(),
    )


async def on_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    chat_id = q.message.chat_id

    if data == "REV_NOP":
        return

    if data == "BACK_MAIN":
        await delete_prev_reviews_pack(context, chat_id)
        context.user_data.clear()
        await q.edit_message_text("Выберите интересующий раздел:", reply_markup=kb_main())
        return

    if data == "MENU_PRICES":
        await q.edit_message_text("Выберите валюту:", reply_markup=kb_currency())
        return

    if data == "BACK_CURRENCY":
        await q.edit_message_text("Выберите валюту:", reply_markup=kb_currency())
        return

    if data == "MENU_CONTACT":
        await q.edit_message_text(
            "📞 Контакты\n\n"
            "• Оператор: @your_username\n"
            "• Время работы: 10:00–22:00\n",
            reply_markup=kb_back_main(),
        )
        return

    # ✅ NEW: Trust / Guarantee
    if data == "MENU_TRUST":
        await q.edit_message_text(
            "🔐 Доверие / Гарантия\n\n"
            "✅ У нас есть удостоверение (можем подтвердить).\n"
            "✅ Работаем честно, с гарантией.\n\n"
            "Если хотите убедиться — напишите в личку:\n"
            f"👉 {TRUST_CONTACT}",
            reply_markup=kb_back_main(),
        )
        return

    if data == "MENU_ORDER":
        await delete_prev_reviews_pack(context, chat_id)
        context.user_data.clear()
        context.user_data["flow"] = "order"
        context.user_data["currency"] = "KZT"
        context.user_data["step"] = "model"
        await q.edit_message_text("📱 Укажите модель телефона (пример: iPhone 13):")
        return

    if data == "MENU_FREE":
        await delete_prev_reviews_pack(context, chat_id)
        context.user_data.clear()
        context.user_data["flow"] = "free"
        context.user_data["currency"] = "KZT"
        await q.edit_message_text("🆓 Опишите ваш вопрос одним сообщением:")
        return

    if data == "MENU_REVIEWS":
        await send_reviews_pack(chat_id, context, page=1)
        return

    if data.startswith("REV_PAGE_"):
        try:
            page = int(data.split("_")[-1])
        except ValueError:
            page = 1
        await send_reviews_pack(chat_id, context, page=page)
        return

    if data in ("CUR_KZT", "CUR_RUB"):
        cur = data.split("_")[1]
        context.user_data["currency"] = cur
        await q.edit_message_text(format_prices(cur), reply_markup=kb_prices_actions(cur))
        return

    if data.startswith("ORDER_"):
        cur = data.split("_", 1)[1]
        await delete_prev_reviews_pack(context, chat_id)
        context.user_data.clear()
        context.user_data["flow"] = "order"
        context.user_data["currency"] = cur
        context.user_data["step"] = "model"
        await q.edit_message_text("📱 Укажите модель телефона (пример: iPhone 13):")
        return

    if data.startswith("FREE_"):
        cur = data.split("_", 1)[1]
        await delete_prev_reviews_pack(context, chat_id)
        context.user_data.clear()
        context.user_data["flow"] = "free"
        context.user_data["currency"] = cur
        await q.edit_message_text("🆓 Опишите ваш вопрос одним сообщением:")
        return


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    flow = context.user_data.get("flow")

    if flow not in ("order", "free"):
        await update.message.reply_text("Выберите раздел кнопками 👇", reply_markup=kb_main())
        return ConversationHandler.END

    if flow == "free":
        user = update.effective_user
        username = user_str(user)
        currency = context.user_data.get("currency", "KZT")
        msg = update.message.text.strip()

        await update.message.reply_text("✅ Принято! Мы скоро вам ответим.", reply_markup=kb_main())
        await notify_admins(
            context,
            "🆓 Бесплатная консультация\n\n"
            f"👤 Пользователь: {username} | ID: {user.id}\n"
            f"💱 Валюта: {currency}\n"
            f"📝 Сообщение: {msg}",
        )
        context.user_data.clear()
        return ConversationHandler.END

    step = context.user_data.get("step", "model")

    if step == "model":
        context.user_data["model"] = update.message.text.strip()
        context.user_data["step"] = "contact"
        await update.message.reply_text("📲 Укажите контакт (номер или @username):")
        return ASK_CONTACT

    if step == "contact":
        context.user_data["contact"] = update.message.text.strip()
        context.user_data["step"] = "note"
        await update.message.reply_text("📝 Напишите комментарий (что нужно сделать):")
        return ASK_NOTE

    if step == "note":
        user = update.effective_user
        username = user_str(user)

        currency = context.user_data.get("currency", "KZT")
        model = context.user_data.get("model", "-")
        contact = context.user_data.get("contact", "-")
        note = update.message.text.strip()

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO orders (user_id, username, model, contact, note, currency, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user.id, username, model, contact, note, currency, "Новая", datetime.utcnow().isoformat()),
        )
        order_id = cur.lastrowid
        conn.commit()
        conn.close()

        await update.message.reply_text(
            "✅ Заявка принята!\n\n"
            f"🧾 ID: #{order_id}\n"
            f"📱 Модель: {model}\n"
            f"📲 Контакт: {contact}\n"
            f"💱 Валюта: {currency}\n"
            f"📝 Комментарий: {note}\n\n"
            "Оператор скоро свяжется с вами.",
            reply_markup=kb_main(),
        )

        await notify_admins(
            context,
            "🆕 Новая заявка\n\n"
            f"🧾 ID: #{order_id}\n"
            f"👤 Пользователь: {username} | ID: {user.id}\n"
            f"📱 Модель: {model}\n"
            f"📲 Контакт: {contact}\n"
            f"💱 Валюта: {currency}\n"
            f"📝 Комментарий: {note}",
        )

        context.user_data.clear()
        return ConversationHandler.END

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено.", reply_markup=kb_main())
    return ConversationHandler.END


# ===================== Admin: add review (photo+video) =====================
async def addreview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔️ Доступ только для админа.")
        return ConversationHandler.END

    await update.message.reply_text(
        "⭐ Добавление отзывов\n\n"
        "Отправьте фото или видео (можно альбомом).\n\n"
        "Когда закончите — напишите: DONE\n"
        "Отмена: /cancel"
    )
    return ADMIN_REVIEW_WAIT_MEDIA


async def admin_review_collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔️ Доступ только для админа.")
        return ConversationHandler.END

    if update.message.text:
        t = update.message.text.strip().lower()
        if t == "done":
            await update.message.reply_text("✅ Готово! Отзывы добавлены.\n\nПроверка: ⭐ Отзывы.")
            return ConversationHandler.END

    caption = update.message.caption or ""

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        db_add_review("photo", file_id, caption)
        await update.message.reply_text("✅ Добавлено (фото). Ещё? Отправляйте или DONE.")
        return ADMIN_REVIEW_WAIT_MEDIA

    if update.message.video:
        file_id = update.message.video.file_id
        db_add_review("video", file_id, caption)
        await update.message.reply_text("✅ Добавлено (видео). Ещё? Отправляйте или DONE.")
        return ADMIN_REVIEW_WAIT_MEDIA

    await update.message.reply_text("Отправьте фото/видео отзыв или напишите DONE.")
    return ADMIN_REVIEW_WAIT_MEDIA


async def reviewslist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔️ Доступ только для админа.")
        return

    rows = db_get_reviews_list(limit=200)
    if not rows:
        await update.message.reply_text("Пока отзывов нет. Добавить: /addreview")
        return

    lines = ["⭐ Список отзывов (ID):"]
    for rid, mtype, caption, created_at in rows:
        cap = (caption.strip()[:40] + "…") if caption and len(caption.strip()) > 40 else (caption.strip() or "")
        lines.append(f"• {rid} [{mtype}] — {cap} ({created_at[:19]})")
    lines.append("\nУдалить: /delreview ID")
    await update.message.reply_text("\n".join(lines))


async def delreview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔️ Доступ только для админа.")
        return

    if not context.args:
        await update.message.reply_text("Использование: /delreview ID")
        return

    try:
        rid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Пример: /delreview 12")
        return

    affected = db_del_review(rid)
    if affected:
        await update.message.reply_text(f"✅ Удалено: отзыв #{rid}")
    else:
        await update.message.reply_text("❌ Не найдено. Список: /reviewslist")


# ===================== Init / Build =====================
async def post_init(app: Application):
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning("delete_webhook error: %s", e)


def build_app():
    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN неверный или пустой. Укажите BOT_TOKEN в переменных окружения.")

    db_init()
    logger.info("ADMIN_IDS = %s", ADMIN_IDS)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_click))

    user_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, text_router)],
        states={
            ASK_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_router)],
            ASK_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_router)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(user_conv)

    admin_review_conv = ConversationHandler(
        entry_points=[CommandHandler("addreview", addreview_cmd)],
        states={
            ADMIN_REVIEW_WAIT_MEDIA: [
                MessageHandler(filters.PHOTO, admin_review_collect),
                MessageHandler(filters.VIDEO, admin_review_collect),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_review_collect),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(admin_review_conv)

    app.add_handler(CommandHandler("reviewslist", reviewslist_cmd))
    app.add_handler(CommandHandler("delreview", delreview_cmd))

    return app


if __name__ == "__main__":
    application = build_app()
    application.run_polling(drop_pending_updates=True)
