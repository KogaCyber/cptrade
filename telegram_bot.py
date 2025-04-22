import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from main import driver_manager, take_screenshot, send_to_telegram

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот для мониторинга Binance.\n"
        "Доступные команды:\n"
        "/screenshot - Сделать скриншот текущего состояния\n"
        "/status - Проверить статус мониторинга"
    )

async def take_screenshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /screenshot"""
    try:
        # Получаем активные драйверы
        active_drivers = driver_manager.get_active_drivers()
        
        if not active_drivers:
            await update.message.reply_text("❌ Нет активных потоков мониторинга")
            return
            
        # Отправляем сообщение о начале процесса
        await update.message.reply_text("📸 Создание скриншотов...")
        
        # Создаем скриншоты для каждого активного драйвера
        for thread_id, driver_info in active_drivers.items():
            try:
                # Получаем драйвер
                driver = driver_manager.get_driver(thread_id)
                if not driver:
                    await update.message.reply_text(f"❌ Драйвер не найден для потока {thread_id}")
                    continue
                    
                # Создаем скриншот
                screenshot = take_screenshot(driver, thread_id)
                if screenshot:
                    # Отправляем скриншот
                    await update.message.reply_photo(
                        photo=screenshot,
                        caption=f"📊 Скриншот потока {thread_id}"
                    )
                else:
                    await update.message.reply_text(f"❌ Не удалось создать скриншот для потока {thread_id}")
                    
            except Exception as e:
                logger.error(f"Ошибка при создании скриншота для потока {thread_id}", exc_info=e)
                await update.message.reply_text(f"❌ Ошибка при создании скриншота для потока {thread_id}")
                
    except Exception as e:
        logger.error("Ошибка при обработке команды /screenshot", exc_info=e)
        await update.message.reply_text("❌ Произошла ошибка при создании скриншотов")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    try:
        # Получаем активные драйверы
        active_drivers = driver_manager.get_active_drivers()
        
        if not active_drivers:
            await update.message.reply_text("❌ Нет активных потоков мониторинга")
            return
            
        # Формируем сообщение о статусе
        status_message = "📊 Статус мониторинга:\n\n"
        for thread_id, driver_info in active_drivers.items():
            status_message += f"Поток {thread_id}:\n"
            status_message += f"Статус: {'Активен' if driver_info['alive'] else 'Неактивен'}\n"
            status_message += f"Последняя активность: {driver_info['last_active']}\n\n"
            
        await update.message.reply_text(status_message)
        
    except Exception as e:
        logger.error("Ошибка при обработке команды /status", exc_info=e)
        await update.message.reply_text("❌ Произошла ошибка при получении статуса")

def main():
    """Запуск бота"""
    try:
        # Получаем токен бота из переменных окружения
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.error("❌ Не указан токен бота в переменных окружения")
            return
            
        # Создаем приложение
        application = Application.builder().token(bot_token).build()
        
        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("screenshot", take_screenshot_command))
        application.add_handler(CommandHandler("status", status_command))
        
        # Запускаем бота
        logger.info("🚀 Запуск Telegram бота")
        application.run_polling()
        
    except Exception as e:
        logger.critical("❌ Критическая ошибка при запуске бота", exc_info=e)

if __name__ == "__main__":
    main() 