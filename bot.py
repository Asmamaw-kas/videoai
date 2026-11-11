"""
Main bot — ሙሉ በሙሉ በአማርኛ ቋንቋ።

ፍሰት፦
  Welcome screen (Start button)
    → step 1: የኢሜይል ብዛት ምረጥ
    → step 2: ኢሜይሎችን አስገባ
    → step 3: ማጠቃለያ / ማረጋገጫ
    → step 4: የክፍያ ዘዴ ምረጥ
    → step 5: ስክሪንሾት ላክ
    → ማረጋገጫ ጠብቅ
"""

import logging
import re
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import config
import database as db
from admin import register_admin_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conversation states
# ---------------------------------------------------------------------------
(
    STATE_WELCOME,
    STATE_CHOOSE_EMAIL_COUNT,
    STATE_ENTER_EMAILS,
    STATE_CONFIRM,
    STATE_CHOOSE_PAYMENT,
    STATE_SEND_SCREENSHOT,
) = range(6)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ---------------------------------------------------------------------------
# Shared keyboards
# ---------------------------------------------------------------------------

def welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 ምዝገባ ጀምር", callback_data="welcome:start")]
    ])


def email_count_keyboard() -> InlineKeyboardMarkup:
    """1 … MAX_EMAILS inline buttons, 2 per row."""
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for n in range(1, config.MAX_EMAILS + 1):
        price = config.calculate_price(n)
        row.append(InlineKeyboardButton(
            f"{n} ኢሜይል – {price} ብር",
            callback_data=f"emails:{n}",
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("❌ ሰርዝ", callback_data="nav:cancel")])
    return InlineKeyboardMarkup(buttons)


def payment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏦 CBE ባንክ",  callback_data="pay:CBE"),
            InlineKeyboardButton("📱 Telebirr", callback_data="pay:Telebirr"),
        ],
        [InlineKeyboardButton("◀️ ተመለስ", callback_data="nav:back_to_confirm")],
    ])


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ክፍያ ወደ መምረጥ", callback_data="confirm:proceed")],
        [InlineKeyboardButton("✏️ ኢሜይሎችን edit",        callback_data="confirm:edit")],
        [InlineKeyboardButton("❌ ሰርዝ",                 callback_data="nav:cancel")],
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ ሰርዝ", callback_data="nav:cancel")]
    ])


# ---------------------------------------------------------------------------
# Step text helpers
# ---------------------------------------------------------------------------

def step_header(current: int, total: int = 5) -> str:
    filled   = "●" * current
    unfilled = "○" * (total - current)
    return f"step {current}/{total}  {filled}{unfilled}\n"


# ===========================================================================
# WELCOME SCREEN
# ===========================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()

    # Works for both /start command and "restart" callback
    text = (
        "╔══════════════════════╗\n"
        "       🌟 እንኳን ደህና መጡ! 🌟\n"
        "╚══════════════════════╝\n\n"
        "🎯 *videoai* አገልግሎት ምዝገባ ቦት\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📧 *የዋጋ ዝርዝር*\n"
        f"  • 1 ኢሜይል    →  *{config.BASE_PRICE} ብር*\n"
        f"  • 2 ኢሜይሎች  →  *{config.calculate_price(2)} ብር*\n"
        f"  • 3 ኢሜይሎች  →  *{config.calculate_price(3)} ብር*\n"
        f"  _(ተጨማሪ ኢሜይል +{config.PRICE_PER_EXTRA_EMAIL} ብር)_\n\n"
        "💳 *የክፍያ ዘዴዎች*\n"
        "  • 🏦 CBE ባንክ\n"
        "  • 📱 Telebirr\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 ለመጀመር ከታች ያለውን ቁልፍ ይጫኑ"
    )

    if update.message:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=welcome_keyboard(),
        )
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=welcome_keyboard(),
        )
    return STATE_WELCOME


async def cb_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "status":
        return await _show_status(update, context, via_query=True)

    # action == "start"
    await query.edit_message_text(
        f"{step_header(1)}\n"
        "📧 *ስንት ኢሜይል ማስመዝገብ ይፈልጋሉ?*\n\n"
        "ከዚህ በታች ካለው ዝርዝር ይምረጡ፦\n"
        "_(ቁጥሩ ሲጨምር ዋጋውም ይጨምራል)_",
        parse_mode="Markdown",
        reply_markup=email_count_keyboard(),
    )
    return STATE_CHOOSE_EMAIL_COUNT


# ===========================================================================
# STEP 1 — የኢሜይል ብዛት ምረጥ
# ===========================================================================

async def cb_choose_email_count(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    num   = int(query.data.split(":")[1])
    price = config.calculate_price(num)

    context.user_data["num_emails"]       = num
    context.user_data["price"]            = price
    context.user_data["emails_collected"] = []

    await query.edit_message_text(
        f"{step_header(2)}\n"
        f"✅ *{num} ኢሜይል* ለ *{price} ብር* መርጠዋል።\n\n"
        f"📧 *1ኛ ኢሜይል አድራሻዎን ያስገቡ*\n"
        "_(ምሳሌ፦ abebe@gmail.com)_",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )
    return STATE_ENTER_EMAILS


# ===========================================================================
# STEP 2 — ኢሜይሎችን አንድ በአንድ ሰብስብ
# ===========================================================================

async def msg_enter_email(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text   = update.message.text.strip().lower()
    emails: list = context.user_data["emails_collected"]
    total: int   = context.user_data["num_emails"]

    # Validation
    if not EMAIL_RE.match(text):
        await update.message.reply_text(
            "⚠️ *ትክክለኛ ኢሜይል አድራሻ አይደለም!*\n\n"
            "እባክዎ እንደዚህ ያለ email ይጠቀሙ፦\n"
            "`example@gmail.com`\n\n"
            "እንደገና ያስገቡ፦",
            parse_mode="Markdown",
        )
        return STATE_ENTER_EMAILS

    if text in emails:
        await update.message.reply_text(
            "⚠️ *ይህ ኢሜይል አድራሻ አስቀድሞ ተመዝግቧል!*\n\n"
            "እባክዎ ሌላ ኢሜይል አድራሻ ያስገቡ፦",
            parse_mode="Markdown",
        )
        return STATE_ENTER_EMAILS

    emails.append(text)

    if len(emails) < total:
        remaining = total - len(emails)
        await update.message.reply_text(
            f"{step_header(2)}\n"
            f"✅ ተቀምጧል፦ `{text}`\n\n"
            f"📧 *{len(emails) + 1}ኛ ኢሜይል አድራሻ ያስገቡ*\n"
            f"_(የቀሩ፦ {remaining} ኢሜይሎች)_",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )
        return STATE_ENTER_EMAILS

    # ሁሉም ተሰብስበዋል → ማጠቃለያ
    return await _show_confirm(update, context)


# ===========================================================================
# STEP 3 — ማጠቃለያ / ማረጋገጫ
# ===========================================================================

async def _show_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    emails: list = context.user_data["emails_collected"]
    num:    int  = context.user_data["num_emails"]
    price:  int  = context.user_data["price"]

    email_lines = "\n".join(f"    {i+1}. `{e}`" for i, e in enumerate(emails))
    summary = (
        f"{step_header(3)}\n"
        "📋 *የትዕዛዝ ማጠቃለያ*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📧 ኢሜይሎች ({num}):\n{email_lines}\n\n"
        f"💰 ጠቅላላ መጠን፦  *{price} ብር*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "ትዕዛዙ ትክክል ነው? ለመቀጠል ✅ ይጫኑ፣\n"
        "edit ✏️ ይጫኑ።"
    )

    if update.message:
        await update.message.reply_text(
            summary,
            parse_mode="Markdown",
            reply_markup=confirm_keyboard(),
        )
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            summary,
            parse_mode="Markdown",
            reply_markup=confirm_keyboard(),
        )
    return STATE_CONFIRM


async def cb_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "edit":
        # ኢሜይሎችን ጨርሶ አጥፋ ወደ ኢሜይል ምርጫ ተመለስ
        num   = context.user_data["num_emails"]
        price = context.user_data["price"]
        context.user_data["emails_collected"] = []
        await query.edit_message_text(
            f"{step_header(2)}\n"
            f"✏️ ኢሜይሎቹ ተሰርዘዋል። እንደገና ያስገቡ።\n\n"
            f"📧 *1ኛ ኢሜይል አድራሻዎን ያስገቡ* ({num} ቁጥር ለ {price} ብር)\n"
            "_(ምሳሌ፦ abebe@gmail.com)_",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )
        return STATE_ENTER_EMAILS

    # action == "proceed"
    await query.edit_message_text(
        f"{step_header(4)}\n"
        "💳 *የክፍያ ዘዴ ይምረጡ*\n\n"
        "  🏦 *CBE ባንክ* — የባንክ ቁጥር \n"
        "  📱 *Telebirr* — ስልክ ቁጥር \n\n"
        "👇 ከታች ያለውን ይምረጡ፦",
        parse_mode="Markdown",
        reply_markup=payment_keyboard(),
    )
    return STATE_CHOOSE_PAYMENT


# ===========================================================================
# STEP 4 — የክፍያ ዘዴ ምረጥ
# ===========================================================================

async def cb_choose_payment(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "back_to_confirm":
        return await _show_confirm(update, context)

    method = action   # 'CBE' or 'Telebirr'
    context.user_data["payment_method"] = method

    if method == "CBE":
        details = (
            "🏦 *CBE ባንክ ዝውውር*\n\n"
            f"  🔢 የባንክ ቁጥር፦  `{config.CBE_ACCOUNT}`\n"
            f"  👤 የባለቤት ስም፦  {config.ACCOUNT_NAME}\n"
        )
    else:
        details = (
            "📱 *Telebirr ዝውውር*\n\n"
            f"  📞 ስልክ ቁጥር፦  `{config.TELEBIRR_ACCOUNT}`\n"
            f"  👤 የባለቤት ስም፦  {config.ACCOUNT_NAME}\n"
        )

    # ትዕዛዙን ወደ ዳታቤዝ ያስቀምጡ
    user = query.from_user
    order_id = await db.create_order(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        num_emails=context.user_data["num_emails"],
        price=context.user_data["price"],
        emails=context.user_data["emails_collected"],
    )
    context.user_data["order_id"] = order_id

    await query.edit_message_text(
        f"{step_header(5)}\n"
        f"{details}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 የሚከፍሉት መጠን፦  *{context.user_data['price']} ብር*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ ገንዘቡን ከላኩ በኋላ *የክፍያ ስክሪንሾቱን ፎቶ ይላኩ።*\n\n"
        "_(ፎቶ ብቻ ተቀባይ ነው — screenshot ወይም ደረሰኝ ፎቶ)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ ሰርዝ", callback_data="nav:cancel")]
        ]),
    )
    return STATE_SEND_SCREENSHOT


# ===========================================================================
# STEP 5 — ስክሪንሾት ተቀበል
# ===========================================================================

async def msg_receive_screenshot(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    photo = update.message.photo
    if not photo:
        await update.message.reply_text(
            "⚠️ *ፎቶ ብቻ ይላኩ!*\n\n"
            "እባክዎ የክፍያ ደረሰኝ *ፎቶ (ስክሪንሾት)* ይላኩ።\n"
            "ጽሑፍ ወይም ፋይል አይቀበልም።",
            parse_mode="Markdown",
        )
        return STATE_SEND_SCREENSHOT

    file_id  = photo[-1].file_id
    order_id = context.user_data["order_id"]
    method   = context.user_data["payment_method"]

    await db.update_payment(
        order_id=order_id,
        payment_method=method,
        screenshot_file_id=file_id,
    )

    # አስተዳዳሪዎቹን አሳውቅ
    order = await db.get_order(order_id)
    admin_text = (
        f"🔔 *አዲስ ክፍያ – ትዕዛዝ #{order_id}*\n\n"
        f"👤 ተጠቃሚ: @{order['username'] or 'N/A'} (ID: `{order['user_id']}`)\n"
        f"📧 ኢሜይሎች ({order['num_emails']}):\n"
        + "\n".join(f"  • {e}" for e in order["emails"].split(","))
        + f"\n💰 መጠን: {order['price']} ብር via {method}\n\n"
        "ትዕዛዙን ለማስተዳደር:\n"
        f"`/verify {order_id} <service_link>`\n"
        f"`/reject {order_id}`"
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=admin_text,
                parse_mode="Markdown",
            )
        except Exception as exc:
            logger.warning("Could not notify admin %s: %s", admin_id, exc)

    # የተጠናቀቀ ማሳወቂያ ለተጠቃሚ
    await update.message.reply_text(
        "🎉 *ስክሪንሾት ተቀብለናል!*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 የትዕዛዝ ቁጥርዎ፦  *#{order_id}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ ቡድናችን ክፍያዎን ካረጋገጠ በኋላ\n"
        "   የአገልግሎት ሊንኩን ይልኩልዎታል።\n\n"
        "telegram ላይ በትግስት ይጠብቁን! 🙏",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 የትዕዛዝ ሁኔታ ፈትሽ", callback_data="status:check")],
            [InlineKeyboardButton("🏠 ወደ መነሻ ተመለስ",    callback_data="nav:home")],
        ]),
    )
    return ConversationHandler.END


# ===========================================================================
# Navigation callbacks (cancel / home / status)
# ===========================================================================

async def cb_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "cancel":
        context.user_data.clear()
        await query.edit_message_text(
            "❌ *ትዕዛዙ ተሰርዟል።*\n\n"
            "እንደገና ለመጀመር /start ይጻፉ ወይም ከታች ያለውን ይጫኑ።",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 ወደ መነሻ ተመለስ", callback_data="nav:home")]
            ]),
        )
        return ConversationHandler.END

    if action == "home":
        return await cmd_start(update, context)

    return ConversationHandler.END


async def cb_status_check(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Inline button version of /mystatus."""
    query = update.callback_query
    await query.answer()
    await _show_status(update, context, via_query=True)


# ===========================================================================
# /mystatus — ሁኔታ ማሳያ (shared helper)
# ===========================================================================

async def _show_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    via_query: bool = False,
) -> int:
    user_id = update.effective_user.id
    orders  = await db.get_user_orders(user_id)

    if not orders:
        text = (
            "📭 *እስካሁን ምንም ትዕዛዝ የለዎትም።*\n\n"
            "ለመጀመር ምዝገባ ቁልፍ ይጫኑ።"
        )
    else:
        lines = ["📋 *የትዕዛዞች ሁኔታ*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
        for o in orders:
            emoji = {"pending": "⏳", "verified": "✅", "rejected": "❌"}.get(o["status"], "❓")
            label = {
                "pending":  "በመጠባበቅ ላይ",
                "verified": "ተረጋግጧል ✅",
                "rejected": "ተቀባይነት አላገኘም ❌",
            }.get(o["status"], o["status"])

            lines.append(
                f"{emoji} *ትዕዛዝ #{o['id']}*\n"
                f"   📧 {o['num_emails']} ኢሜይል  •  💰 {o['price']} ብር\n"
                f"   📌 {label}\n"
                f"   🕐 {o['created_at'][:16]}\n"
            )
            if o["status"] == "verified" and o["service_link"]:
                lines.append(f"   🔗 {o['service_link']}\n")
        text = "\n".join(lines)

    back_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 ወደ መነሻ ተመለስ", callback_data="nav:home")]
    ])

    if via_query:
        query = update.callback_query
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=back_btn)

    return ConversationHandler.END


async def cmd_mystatus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _show_status(update, context, via_query=False)


# ===========================================================================
# /cancel command (typed)
# ===========================================================================

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ *ትዕዛዙ ተሰርዟል።*\n\nእንደገና ለመጀመር /start ይጻፉ።",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ===========================================================================
# Fallback — ከሂደቱ ውጭ ለሆኑ መልዕክቶች
# ===========================================================================

async def fallback_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤔 ይህን ትዕዛዝ አልተረዳሁም።\n\n"
        "ምዝገባ ለመጀመር /start\n"
        "ሁኔታ ለማየት /mystatus\n"
        "ለመሰረዝ /cancel",
    )


# ===========================================================================
# Application setup
# ===========================================================================

async def post_init(app: Application) -> None:
    await db.init_db()
    logger.info("Database initialised.")


def main() -> None:
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in your .env file.")

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # ──────────────────────────────────────────────────────────────
    # Conversation handler — covers the full subscription flow
    # ──────────────────────────────────────────────────────────────
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            # Welcome screen
            STATE_WELCOME: [
                CallbackQueryHandler(cb_welcome, pattern=r"^welcome:"),
                CallbackQueryHandler(cb_nav,     pattern=r"^nav:"),
            ],
            # Step 1 – email count
            STATE_CHOOSE_EMAIL_COUNT: [
                CallbackQueryHandler(cb_choose_email_count, pattern=r"^emails:\d+$"),
                CallbackQueryHandler(cb_nav,                pattern=r"^nav:"),
            ],
            # Step 2 – enter emails
            STATE_ENTER_EMAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, msg_enter_email),
                CallbackQueryHandler(cb_nav, pattern=r"^nav:"),
            ],
            # Step 3 – confirm summary
            STATE_CONFIRM: [
                CallbackQueryHandler(cb_confirm, pattern=r"^confirm:"),
                CallbackQueryHandler(cb_nav,     pattern=r"^nav:"),
            ],
            # Step 4 – choose payment
            STATE_CHOOSE_PAYMENT: [
                CallbackQueryHandler(cb_choose_payment, pattern=r"^pay:"),
                CallbackQueryHandler(cb_nav,            pattern=r"^nav:"),
            ],
            # Step 5 – screenshot
            STATE_SEND_SCREENSHOT: [
                MessageHandler(filters.PHOTO,                   msg_receive_screenshot),
                MessageHandler(filters.TEXT & ~filters.COMMAND, msg_receive_screenshot),
                CallbackQueryHandler(cb_nav, pattern=r"^nav:"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("start",  cmd_start),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)

    # Status button outside conversation (after END)
    app.add_handler(CallbackQueryHandler(cb_status_check, pattern=r"^status:check$"))
    app.add_handler(CallbackQueryHandler(cb_nav,          pattern=r"^nav:home$"))

    app.add_handler(CommandHandler("mystatus", cmd_mystatus))

    # Register admin commands
    register_admin_handlers(app)

    # Catch-all fallback for unrecognised messages
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, fallback_msg
    ))

    logger.info("Bot is running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
