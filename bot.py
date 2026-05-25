import logging
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

TOKEN = "8829212128:AAE6G_CCJiafKNoADVADysdf49VbojuBSGI"
DATA_FILE = "tasks.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States
WAITING_TITLE, WAITING_DEADLINE, WAITING_SOURCE = range(3)

def load_tasks():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def get_next_id(tasks):
    if not tasks:
        return 1
    return max(t["id"] for t in tasks) + 1

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Yangi topshiriq", callback_data="new_task")],
        [InlineKeyboardButton("📋 Barcha topshiriqlar", callback_data="list_tasks")],
        [InlineKeyboardButton("⏰ Bugungi & Muddati o'tgan", callback_data="urgent_tasks")],
        [InlineKeyboardButton("📊 Chorak hisobot", callback_data="quarterly_report")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Salom! Men *Ijro Yordamchi Bot*man.\n\n"
        "Topshiriqlarni boshqarish, muddat kuzatish va hisobot chiqarishda yordamlashaman.\n\n"
        "Nima qilmoqchisiz?",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# Menu
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Yangi topshiriq", callback_data="new_task")],
        [InlineKeyboardButton("📋 Barcha topshiriqlar", callback_data="list_tasks")],
        [InlineKeyboardButton("⏰ Bugungi & Muddati o'tgan", callback_data="urgent_tasks")],
        [InlineKeyboardButton("📊 Chorak hisobot", callback_data="quarterly_report")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Asosiy menyu:", reply_markup=reply_markup)

# New task - start
async def new_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📝 *Yangi topshiriq*\n\nTopshiriq sarlavhasini kiriting:",
        parse_mode="Markdown"
    )
    return WAITING_TITLE

async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_title"] = update.message.text
    await update.message.reply_text(
        "📅 Muddatini kiriting (format: *KK.OO.YYYY*, masalan: 30.06.2025)\n"
        "Yoki /skip yozing — muddat yo'q:",
        parse_mode="Markdown"
    )
    return WAITING_DEADLINE

async def receive_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/skip":
        context.user_data["new_deadline"] = None
    else:
        try:
            datetime.strptime(text, "%d.%m.%Y")
            context.user_data["new_deadline"] = text
        except ValueError:
            await update.message.reply_text("❌ Format noto'g'ri. Qaytadan kiriting (KK.OO.YYYY) yoki /skip:")
            return WAITING_DEADLINE

    await update.message.reply_text(
        "🏢 Topshiriq manbaini kiriting:\n(Masalan: Rahbar, Telegram guruh, Hokimlik...)"
    )
    return WAITING_SOURCE

async def receive_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = load_tasks()
    new_task = {
        "id": get_next_id(tasks),
        "title": context.user_data["new_title"],
        "deadline": context.user_data.get("new_deadline"),
        "source": update.message.text,
        "status": "Kutilmoqda",
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "completed_at": None
    }
    tasks.append(new_task)
    save_tasks(tasks)

    deadline_text = new_task["deadline"] if new_task["deadline"] else "Belgilanmagan"
    await update.message.reply_text(
        f"✅ *Topshiriq qo'shildi!*\n\n"
        f"🆔 ID: {new_task['id']}\n"
        f"📝 Sarlavha: {new_task['title']}\n"
        f"📅 Muddat: {deadline_text}\n"
        f"🏢 Manba: {new_task['source']}\n"
        f"🔄 Holat: {new_task['status']}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

# List all tasks
async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = load_tasks()

    if not tasks:
        await query.message.reply_text("📋 Hozircha topshiriqlar yo'q.")
        return

    pending = [t for t in tasks if t["status"] != "Bajarildi"]
    done = [t for t in tasks if t["status"] == "Bajarildi"]

    text = f"📋 *Barcha topshiriqlar* ({len(tasks)} ta)\n\n"

    if pending:
        text += f"🔄 *Bajarilmagan ({len(pending)} ta):*\n"
        for t in pending[-10:]:
            deadline = t["deadline"] if t["deadline"] else "—"
            status_icon = "⚠️" if is_overdue(t["deadline"]) else "🔄"
            text += f"{status_icon} [{t['id']}] {t['title']}\n    📅 {deadline} | 🏢 {t['source']}\n"

    if done:
        text += f"\n✅ *Bajarilgan ({len(done)} ta)*\n"
        for t in done[-5:]:
            text += f"✅ [{t['id']}] {t['title']}\n"

    keyboard = []
    for t in pending[-5:]:
        keyboard.append([InlineKeyboardButton(
            f"✅ [{t['id']}] {t['title'][:30]}...",
            callback_data=f"done_{t['id']}"
        )])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# Mark as done
async def mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[1])
    tasks = load_tasks()

    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "Bajarildi"
            t["completed_at"] = datetime.now().strftime("%d.%m.%Y %H:%M")
            save_tasks(tasks)
            await query.message.reply_text(
                f"✅ *Topshiriq bajarildi!*\n\n"
                f"📝 {t['title']}\n"
                f"⏱ Bajarildi: {t['completed_at']}",
                parse_mode="Markdown"
            )
            return

    await query.message.reply_text("❌ Topshiriq topilmadi.")

# Urgent tasks
def is_overdue(deadline_str):
    if not deadline_str:
        return False
    try:
        deadline = datetime.strptime(deadline_str, "%d.%m.%Y")
        return deadline < datetime.now()
    except:
        return False

def is_today_or_soon(deadline_str, days=3):
    if not deadline_str:
        return False
    try:
        deadline = datetime.strptime(deadline_str, "%d.%m.%Y")
        diff = (deadline - datetime.now()).days
        return -1 <= diff <= days
    except:
        return False

async def urgent_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = load_tasks()
    pending = [t for t in tasks if t["status"] != "Bajarildi"]

    overdue = [t for t in pending if is_overdue(t["deadline"])]
    soon = [t for t in pending if is_today_or_soon(t["deadline"]) and not is_overdue(t["deadline"])]

    text = "⏰ *Shoshilinch topshiriqlar*\n\n"

    if overdue:
        text += f"🔴 *Muddati o'tgan ({len(overdue)} ta):*\n"
        for t in overdue:
            text += f"  ❗ [{t['id']}] {t['title']}\n    📅 {t['deadline']} | 🏢 {t['source']}\n"
    else:
        text += "✅ Muddati o'tgan topshiriqlar yo'q\n"

    text += "\n"

    if soon:
        text += f"🟡 *3 kun ichida muddati tugaydi ({len(soon)} ta):*\n"
        for t in soon:
            text += f"  ⚠️ [{t['id']}] {t['title']}\n    📅 {t['deadline']} | 🏢 {t['source']}\n"
    else:
        text += "✅ Yaqin muddatli topshiriqlar yo'q\n"

    await query.message.reply_text(text, parse_mode="Markdown")

# Quarterly report
async def quarterly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = load_tasks()

    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    quarter_start = datetime(now.year, (quarter - 1) * 3 + 1, 1)
    quarter_end = quarter_start + timedelta(days=92)

    quarter_tasks = []
    for t in tasks:
        try:
            created = datetime.strptime(t["created_at"], "%d.%m.%Y %H:%M")
            if quarter_start <= created <= quarter_end:
                quarter_tasks.append(t)
        except:
            pass

    total = len(quarter_tasks)
    done = len([t for t in quarter_tasks if t["status"] == "Bajarildi"])
    pending = len([t for t in quarter_tasks if t["status"] != "Bajarildi"])
    overdue_count = len([t for t in quarter_tasks if is_overdue(t["deadline"]) and t["status"] != "Bajarildi"])

    percent = round(done / total * 100) if total > 0 else 0

    # Source stats
    sources = {}
    for t in quarter_tasks:
        src = t.get("source", "Noma'lum")
        sources[src] = sources.get(src, 0) + 1

    text = (
        f"📊 *{now.year}-yil {quarter}-chorak hisoboti*\n"
        f"📅 {quarter_start.strftime('%d.%m.%Y')} — {min(quarter_end, now).strftime('%d.%m.%Y')}\n\n"
        f"📌 Jami topshiriqlar: *{total}* ta\n"
        f"✅ Bajarildi: *{done}* ta ({percent}%)\n"
        f"🔄 Jarayonda: *{pending}* ta\n"
        f"❗ Muddati o'tgan: *{overdue_count}* ta\n\n"
    )

    if sources:
        text += "🏢 *Manba bo'yicha:*\n"
        for src, count in sorted(sources.items(), key=lambda x: -x[1]):
            text += f"  • {src}: {count} ta\n"

    bar = "🟩" * (percent // 10) + "⬜" * (10 - percent // 10)
    text += f"\n📈 Bajarish darajasi:\n{bar} {percent}%"

    await query.message.reply_text(text, parse_mode="Markdown")

# Reminder job
async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    tasks = load_tasks()
    pending = [t for t in tasks if t["status"] != "Bajarildi"]
    chat_id = context.job.chat_id

    reminders = []
    for t in pending:
        if is_overdue(t["deadline"]):
            reminders.append(f"🔴 *Muddati o'tgan:* [{t['id']}] {t['title']} (📅 {t['deadline']})")
        elif is_today_or_soon(t["deadline"], days=1):
            reminders.append(f"🟡 *Bugun tugaydi:* [{t['id']}] {t['title']} (📅 {t['deadline']})")

    if reminders:
        text = "⏰ *Kunlik eslatma*\n\n" + "\n".join(reminders)
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.job_queue.run_daily(
        send_reminders,
        time=datetime.strptime("09:00", "%H:%M").time(),
        chat_id=chat_id,
        name=str(chat_id)
    )
    await update.message.reply_text("✅ Har kuni soat 09:00 da eslatma yoqildi!")

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_task_start, pattern="^new_task$")],
        states={
            WAITING_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
            WAITING_DEADLINE: [MessageHandler(filters.TEXT, receive_deadline)],
            WAITING_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_source)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("eslatma", set_reminder))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(list_tasks, pattern="^list_tasks$"))
    app.add_handler(CallbackQueryHandler(urgent_tasks, pattern="^urgent_tasks$"))
    app.add_handler(CallbackQueryHandler(quarterly_report, pattern="^quarterly_report$"))
    app.add_handler(CallbackQueryHandler(mark_done, pattern="^done_\\d+$"))

    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
