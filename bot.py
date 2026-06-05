import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─── НАСТРОЙКИ ────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_СЮДА")
DATA_FILE = "data.json"

logging.basicConfig(level=logging.INFO)

# ─── ХРАНИЛИЩЕ ДАННЫХ ─────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tasks": [], "expenses": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── СОСТОЯНИЯ ────────────────────────────────────────────────────────────────
WAIT_TASK, WAIT_EXPENSE_DESC, WAIT_EXPENSE_AMOUNT = range(3)

# ─── ГЛАВНОЕ МЕНЮ ─────────────────────────────────────────────────────────────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Задачи", callback_data="tasks"),
         InlineKeyboardButton("💰 Расходы", callback_data="expenses")],
    ])

def tasks_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")],
        [InlineKeyboardButton("✅ Закрыть задачу", callback_data="close_task")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main")],
    ])

def expenses_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить расход", callback_data="add_expense")],
        [InlineKeyboardButton("🗑 Удалить расход", callback_data="delete_expense")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main")],
    ])

# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Это наш общий трекер задач и расходов.\nВыбери раздел:",
        reply_markup=main_keyboard()
    )

# ─── CALLBACK HANDLER ─────────────────────────────────────────────────────────
async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()

    # ── ГЛАВНОЕ МЕНЮ ──
    if query.data == "main":
        await query.edit_message_text("Выбери раздел:", reply_markup=main_keyboard())
        return ConversationHandler.END

    # ── ЗАДАЧИ: список ──
    if query.data == "tasks":
        tasks = data["tasks"]
        if not tasks:
            text = "📋 *Задачи*\n\nЗадач пока нет."
        else:
            lines = []
            for i, t in enumerate(tasks, 1):
                status = "✅" if t["done"] else "🔲"
                lines.append(f"{status} *{i}.* {t['text']}\n    _{t['author']}  {t['date']}_")
            text = "📋 *Задачи*\n\n" + "\n\n".join(lines)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=tasks_keyboard())
        return ConversationHandler.END

    # ── ЗАДАЧИ: добавить ──
    if query.data == "add_task":
        await query.edit_message_text("✏️ Напиши текст задачи:")
        ctx.user_data["action"] = "add_task"
        ctx.user_data["query_message"] = query.message
        return WAIT_TASK

    # ── ЗАДАЧИ: закрыть ──
    if query.data == "close_task":
        tasks = [t for t in data["tasks"] if not t["done"]]
        if not tasks:
            await query.edit_message_text("Нет открытых задач.", reply_markup=tasks_keyboard())
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton(f"🔲 {t['text'][:40]}", callback_data=f"done_{i}")]
                   for i, t in enumerate(data["tasks"]) if not t["done"]]
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="tasks")])
        await query.edit_message_text("Выбери задачу для закрытия:", reply_markup=InlineKeyboardMarkup(buttons))
        return ConversationHandler.END

    # ── ЗАДАЧИ: отметить выполненной ──
    if query.data.startswith("done_"):
        idx = int(query.data.split("_")[1])
        data["tasks"][idx]["done"] = True
        save_data(data)
        await query.edit_message_text("✅ Задача выполнена!", reply_markup=tasks_keyboard())
        return ConversationHandler.END

    # ── РАСХОДЫ: список ──
    if query.data == "expenses":
        expenses = data["expenses"]
        if not expenses:
            text = "💰 *Расходы*\n\nРасходов пока нет."
        else:
            total = sum(e["amount"] for e in expenses)
            lines = []
            for i, e in enumerate(expenses, 1):
                lines.append(f"*{i}.* {e['desc']} — *{e['amount']}₽*\n    _{e['author']}  {e['date']}_")
            text = "💰 *Расходы*\n\n" + "\n\n".join(lines) + f"\n\n*Итого: {total}₽*"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=expenses_keyboard())
        return ConversationHandler.END

    # ── РАСХОДЫ: добавить ──
    if query.data == "add_expense":
        await query.edit_message_text("✏️ Напиши название расхода (например: такси):")
        ctx.user_data["action"] = "add_expense"
        return WAIT_EXPENSE_DESC

    # ── РАСХОДЫ: удалить ──
    if query.data == "delete_expense":
        expenses = data["expenses"]
        if not expenses:
            await query.edit_message_text("Расходов нет.", reply_markup=expenses_keyboard())
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton(f"🗑 {e['desc']} {e['amount']}₽", callback_data=f"del_{i}")]
                   for i, e in enumerate(expenses)]
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="expenses")])
        await query.edit_message_text("Выбери расход для удаления:", reply_markup=InlineKeyboardMarkup(buttons))
        return ConversationHandler.END

    # ── РАСХОДЫ: подтвердить удаление ──
    if query.data.startswith("del_"):
        idx = int(query.data.split("_")[1])
        data["expenses"].pop(idx)
        save_data(data)
        await query.edit_message_text("🗑 Расход удалён.", reply_markup=expenses_keyboard())
        return ConversationHandler.END

# ─── ПОЛУЧЕНИЕ ТЕКСТА ЗАДАЧИ ──────────────────────────────────────────────────
async def receive_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    name = update.effective_user.first_name or "Кто-то"
    data["tasks"].append({
        "text": update.message.text,
        "done": False,
        "author": name,
        "date": datetime.now().strftime("%d.%m %H:%M")
    })
    save_data(data)
    await update.message.reply_text(
        f"✅ Задача добавлена!\n\n📋 *{update.message.text}*",
        parse_mode="Markdown",
        reply_markup=tasks_keyboard()
    )
    return ConversationHandler.END

# ─── ПОЛУЧЕНИЕ ОПИСАНИЯ РАСХОДА ───────────────────────────────────────────────
async def receive_expense_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["expense_desc"] = update.message.text
    await update.message.reply_text("💵 Теперь напиши сумму (только цифры, например: 1500):")
    return WAIT_EXPENSE_AMOUNT

# ─── ПОЛУЧЕНИЕ СУММЫ РАСХОДА ─────────────────────────────────────────────────
async def receive_expense_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await update.message.reply_text("❌ Введи только число, например: 1500")
        return WAIT_EXPENSE_AMOUNT

    data = load_data()
    name = update.effective_user.first_name or "Кто-то"
    data["expenses"].append({
        "desc": ctx.user_data.get("expense_desc", "?"),
        "amount": amount,
        "author": name,
        "date": datetime.now().strftime("%d.%m %H:%M")
    })
    save_data(data)
    await update.message.reply_text(
        f"✅ Расход добавлен!\n\n💰 *{ctx.user_data['expense_desc']}* — *{amount}₽*",
        parse_mode="Markdown",
        reply_markup=expenses_keyboard()
    )
    return ConversationHandler.END

# ─── ОТМЕНА ───────────────────────────────────────────────────────────────────
async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=main_keyboard())
    return ConversationHandler.END

# ─── ЗАПУСК ───────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button)],
        states={
            WAIT_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_task)],
            WAIT_EXPENSE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_expense_desc)],
            WAIT_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_expense_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(button)],
        per_user=True,
        per_chat=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
