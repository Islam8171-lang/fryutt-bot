import logging
import asyncio
from aiohttp import web
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv
import os
import nest_asyncio

# Загружаем переменные из .env файла
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 417731116

# Включаем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния
QUESTION, ORDER = range(2)

# Для хранения вопросов
questions = {}

# Главное меню
def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        ["Узнать цены и товары", "Доставка"],
        ["Наш адрес", "Сделать заказ"],
        ["Задать вопрос?"]
    ], resize_keyboard=True)

# Меню "Назад"
back_menu = ReplyKeyboardMarkup([["Назад"]], resize_keyboard=True)

# Список слов и паттернов для фильтрации спама
BAD_PATTERNS = ["http", "https", "www.", ".net", ".xyz", ".click", ".ru", "free", "claim", "airdrop", "eth"]

# Обработчик сообщений с антиспамом
async def handle_message_with_antispam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.message.text is None:
        return
    
    text_lower = update.message.text.lower()
    if any(pattern in text_lower for pattern in BAD_PATTERNS):
        try:
            await update.message.delete()
            await update.message.reply_text("🚫 Спам-сообщения с ссылками запрещены.")
            logger.info(f"Удалено спам-сообщение от @{update.message.from_user.username}")
        except Exception as e:
            logger.warning(f"Ошибка при удалении спама: {e}")
        return  # Прекращаем дальнейшую обработку этого сообщения

    text = update.message.text
    if text == "Узнать цены и товары":
        await update.message.reply_text(
            "Информацию о товарах и ценах можете ознакомиться в нашей группе: [t.me/fruitstorya](https://t.me/fruitstorya)",
            reply_markup=back_menu
        )
    elif text == "Доставка":
        await update.message.reply_text(
            "Условия доставки:\nДоставляем наши фрукты от 40 до 100 рублей бесплатно\nв пределах 20 км от нашей точки!",
            reply_markup=back_menu
        )
    elif text == "Наш адрес":
        await update.message.reply_text(
            "Наш адрес: Логойская, улица 5А, Валерьяново, Минская область",
            reply_markup=back_menu
        )
    elif text == "Назад":
        await update.message.reply_text("Вы вернулись в главное меню.", reply_markup=main_menu_keyboard())
    elif text == "Задать вопрос?":
        await update.message.reply_text("Напишите ваш вопрос, и мы скоро ответим:")
        return QUESTION
    elif text == "Сделать заказ":
        await update.message.reply_text("Пожалуйста, напишите ваш заказ, имя, телефон, адрес:")
        return ORDER
    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки ниже.", reply_markup=main_menu_keyboard())

# Получение вопроса
async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message.text

    questions[user.id] = {
        "name": user.full_name,
        "question": message
    }

    logger.info(f"Получен вопрос от пользователя {user.full_name} (ID: {user.id}): {message}")

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"❓ Новый вопрос от {user.full_name} (@{user.username or 'без ника'}):\n\n{message}\n\nuser_id: {user.id}"
    )
    
    await update.message.reply_text("Спасибо! Ваш вопрос отправлен. Мы скоро с вами свяжемся.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# Получение заказа
async def handle_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message.text

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🛒 Новый заказ от {user.full_name} (@{user.username or 'без ника'}):\n\n{message}"
    )
    
    await update.message.reply_text("Спасибо за заказ! Мы скоро с вами свяжемся.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# Обработка ответа администратора
async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 2:
        await update.message.reply_text("Используйте команду /answer <user_id> <ответ>")
        return

    user_id = int(context.args[0])
    answer_text = " ".join(context.args[1:])

    if user_id not in questions:
        await update.message.reply_text("Вопрос от этого пользователя не найден.")
        return

    await context.bot.send_message(
        chat_id=user_id,
        text=f"Ответ от оператора: {answer_text}"
    )

    await update.message.reply_text(f"Ответ отправлен пользователю {user_id}.")
    del questions[user_id]

# HTTP сервер для проверки
async def handle(request):
    return web.Response(text="OK")

async def start_http_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("HTTP server запущен на http://0.0.0.0:8080")

def main():
    logger.info("Запуск Telegram-бота...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    question_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^Задать вопрос\?$"), handle_message_with_antispam)],
        states={
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    order_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^Сделать заказ$"), handle_message_with_antispam)],
        states={
            ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(question_conv)
    app.add_handler(order_conv)

    # Один обработчик сообщений с антиспамом и основным меню
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_with_antispam))

    app.add_handler(CommandHandler("answer", answer))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(start_http_server())

    logger.info("Бот успешно запущен и слушает polling...")
    app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()
    main()
