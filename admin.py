"""
Admin commands for managing orders.

/pending                  — list all pending orders
/verify <id> <link>       — verify an order and send the service link + instruction image
/reject <id>              — reject an order and notify the user
/orderinfo <id>           — show full details of any order
/setinstruction           — reply with this command to a photo to set the instruction image
/clearinstruction         — remove the saved instruction image
/previewinstruction       — preview the currently saved instruction image
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
import database as db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Guard: only registered admins can use these commands
# ---------------------------------------------------------------------------

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ You are not authorised to use this command.")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ---------------------------------------------------------------------------
# /pending
# ---------------------------------------------------------------------------

@admin_only
async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    orders = await db.get_pending_orders()
    if not orders:
        await update.message.reply_text("✅ No pending orders right now.")
        return

    lines = ["📋 *Pending Orders:*\n"]
    for o in orders:
        lines.append(
            f"🔹 *Order #{o['id']}*\n"
            f"   👤 @{o['username'] or 'N/A'} (ID: `{o['user_id']}`)\n"
            f"   📧 {o['num_emails']} email(s): {o['emails']}\n"
            f"   💰 {o['price']} ETB via {o['payment_method'] or 'not set'}\n"
            f"   🕐 {o['created_at']}\n"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# /orderinfo <id>
# ---------------------------------------------------------------------------

@admin_only
async def cmd_orderinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /orderinfo <order_id>")
        return

    order_id = int(context.args[0])
    order = await db.get_order(order_id)
    if not order:
        await update.message.reply_text(f"❌ Order #{order_id} not found.")
        return

    status_emoji = {"pending": "⏳", "verified": "✅", "rejected": "❌"}.get(
        order["status"], "❓"
    )
    text = (
        f"{status_emoji} *Order #{order['id']}*\n\n"
        f"👤 User: @{order['username'] or 'N/A'} (ID: `{order['user_id']}`)\n"
        f"📛 Name: {order['full_name']}\n"
        f"📧 Emails ({order['num_emails']}):\n"
        + "\n".join(f"   • {e}" for e in order["emails"].split(","))
        + f"\n💰 Price: {order['price']} ETB\n"
        f"💳 Method: {order['payment_method'] or 'N/A'}\n"
        f"📌 Status: {order['status'].upper()}\n"
        f"🕐 Created: {order['created_at']}\n"
    )
    if order["service_link"]:
        text += f"🔗 Link: {order['service_link']}\n"

    # Send screenshot if available
    if order["screenshot_file_id"]:
        await update.message.reply_photo(
            photo=order["screenshot_file_id"],
            caption=text,
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /verify <id> <service_link>
# ---------------------------------------------------------------------------

@admin_only
async def cmd_verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /verify <order_id> <service_link>\n"
            "Example: /verify 5 https://myservice.com/access/abc123"
        )
        return

    order_id = int(context.args[0])
    service_link = context.args[1]

    order = await db.get_order(order_id)
    if not order:
        await update.message.reply_text(f"❌ Order #{order_id} not found.")
        return

    if order["status"] != "pending":
        await update.message.reply_text(
            f"⚠️ Order #{order_id} is already *{order['status'].upper()}*.",
            parse_mode="Markdown",
        )
        return

    await db.verify_order(order_id, service_link)

    # ማረጋገጫ መልዕክት ለተጠቃሚ
    email_list = "\n".join(f"  • {e}" for e in order["emails"].split(","))
    user_message = (
        "🎉 *ክፍያዎ ተረጋግጧል!*\n\n"
        f"አገልግሎቱ ለሚከተሉት ኢሜይሎች ተከፍቷል፦\n{email_list}\n\n"
        f"🔗 *የአገልግሎት ሊንክዎ፦*\n{service_link}\n\n"
        "ስለተመዘገቡ እናመሰግናለን! ጥያቄ ካለዎት ድጋፋችንን ያግኙ።"
    )

    # የመመሪያ ፎቶ ካለ አሳካ
    instruction_file_id = await db.get_setting("instruction_image_file_id")

    try:
        # 1. ማረጋገጫ ጽሑፍ + ሊንክ ላክ
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=user_message,
            parse_mode="Markdown",
        )

        # 2. የመመሪያ ፎቶ ካለ ወዲያው ላክ
        if instruction_file_id:
            await context.bot.send_photo(
                chat_id=order["user_id"],
                photo=instruction_file_id,
                caption=(
                    "📖 *እንዴት መጀመር እንደሚቻል*\n\n"
                    "አገልግሎቱን ለመጠቀም በምስሉ ውስጥ ያሉትን ደረጃዎች ይከተሉ። "
                    "ጥያቄ ካለዎት ድጋፋችንን ያነጋግሩ።"
                ),
                parse_mode="Markdown",
            )

        sent_image_note = " + instruction image" if instruction_file_id else " (no instruction image set)"
        await update.message.reply_text(
            f"✅ Order #{order_id} verified — link{sent_image_note} sent to the user."
        )

    except Exception as exc:
        logger.error("Failed to message user %s: %s", order["user_id"], exc)
        await update.message.reply_text(
            f"✅ Order #{order_id} marked as verified, but I couldn't message the user "
            f"(they may have blocked the bot).\nLink saved: {service_link}"
        )


# ---------------------------------------------------------------------------
# /setinstruction  — reply to a photo, or send this command with a photo attached
# ---------------------------------------------------------------------------

@admin_only
async def cmd_setinstruction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    photo = None

    # Case 1: admin sent the command while attaching a photo in the same message
    if update.message.photo:
        photo = update.message.photo[-1]

    # Case 2: admin replied to a photo message with /setinstruction
    elif update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]

    if not photo:
        await update.message.reply_text(
            "⚠️ Please send a photo with the caption /setinstruction, "
            "or reply to an existing photo with /setinstruction."
        )
        return

    file_id = photo.file_id
    await db.set_setting("instruction_image_file_id", file_id)

    await update.message.reply_text(
        "✅ Instruction image saved!\n\n"
        "It will be automatically sent to users after payment verification.\n"
        "Use /previewinstruction to see it, or /clearinstruction to remove it."
    )


# ---------------------------------------------------------------------------
# /clearinstruction
# ---------------------------------------------------------------------------

@admin_only
async def cmd_clearinstruction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    existing = await db.get_setting("instruction_image_file_id")
    if not existing:
        await update.message.reply_text("ℹ️ No instruction image is currently set.")
        return
    await db.set_setting("instruction_image_file_id", "")
    await update.message.reply_text("🗑 Instruction image cleared. Users will no longer receive it.")


# ---------------------------------------------------------------------------
# /previewinstruction
# ---------------------------------------------------------------------------

@admin_only
async def cmd_previewinstruction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    file_id = await db.get_setting("instruction_image_file_id")
    if not file_id:
        await update.message.reply_text(
            "ℹ️ No instruction image is set yet.\n"
            "Send a photo with the caption /setinstruction to add one."
        )
        return
    await update.message.reply_photo(
        photo=file_id,
        caption="📖 This is the current instruction image sent to users after verification.",
    )


# ---------------------------------------------------------------------------
# /reject <id>
# ---------------------------------------------------------------------------

@admin_only
async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /reject <order_id>")
        return

    order_id = int(context.args[0])
    order = await db.get_order(order_id)
    if not order:
        await update.message.reply_text(f"❌ Order #{order_id} not found.")
        return

    if order["status"] != "pending":
        await update.message.reply_text(
            f"⚠️ Order #{order_id} is already *{order['status'].upper()}*.",
            parse_mode="Markdown",
        )
        return

    await db.reject_order(order_id)

    # ተጠቃሚውን አሳውቅ (rejection)
    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=(
                "❌ *ክፍያዎ ሊረጋገጥ አልቻለም።*\n\n"
                f"ትዕዛዝ #{order_id} ተቀባይነት አላገኘም።\n\n"
                "ይህ ስህተት ነው ብለው ካሰቡ፣ የትዕዛዝ ቁጥርዎን ይዘው ድጋፋችንን ያግኙ። "
                "እንደገና ለመሞከር /start ይጻፉ።"
            ),
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.error("Failed to message user %s: %s", order["user_id"], exc)

    await update.message.reply_text(f"🗑 Order #{order_id} rejected and user notified.")


# ---------------------------------------------------------------------------
# Registration helper (called from bot.py)
# ---------------------------------------------------------------------------

def register_admin_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("pending",            cmd_pending))
    app.add_handler(CommandHandler("orderinfo",          cmd_orderinfo))
    app.add_handler(CommandHandler("verify",             cmd_verify))
    app.add_handler(CommandHandler("reject",             cmd_reject))
    app.add_handler(CommandHandler("setinstruction",     cmd_setinstruction))
    app.add_handler(CommandHandler("clearinstruction",   cmd_clearinstruction))
    app.add_handler(CommandHandler("previewinstruction", cmd_previewinstruction))
