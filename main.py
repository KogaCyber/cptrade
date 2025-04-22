import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
import time
import sys
import os
import traceback
import requests
import json
import random
import threading
from queue import Queue
from auth_manager import AuthManager
from page_manager import PageManager
from order_manager import OrderManager
from driver_manager import DriverManager
from screenshot_manager import ScreenshotManager
from telegram_manager import telegram_manager
from vpn_checker import VPNChecker
from env_manager import EnvManager
import base64
from io import BytesIO
from PIL import Image
from logger import Logger
from credentials_manager import CredentialsManager
from typing import Dict

# Инициализация менеджера переменных окружения
env = EnvManager()

# Инициализация логгера
logger = Logger("binance_bot")

# Инициализация менеджера драйверов
driver_manager = DriverManager()

# Инициализация драйвера
options = uc.ChromeOptions()
options.add_argument('--start-maximized')
driver = uc.Chrome(options=options)

# Регистрируем драйвер в менеджере
driver_manager.register_driver(1, driver)

# Проверка VPN перед запуском
vpn_checker = VPNChecker(driver)
success, message = vpn_checker.check_vpn()

if not success:
    logger.error(f"❌ {message}")
    if not vpn_checker.wait_for_vpn(timeout=env.get_int("VPN_CHECK_TIMEOUT", 300)):
        logger.critical("❌ Превышено время ожидания VPN. Завершение работы.")
        driver.quit()
        sys.exit(1)

# Загрузка URL из конфигурационного файла
def load_urls():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            return config.get('urls', [])
    except FileNotFoundError:
        logger.warning("Файл конфигурации не найден")
        return []
    except json.JSONDecodeError as e:
        logger.error("Ошибка при чтении файла конфигурации", exc_info=e)
        return []

def take_screenshot(driver, thread_id):
    """Создание скриншота текущего окна браузера"""
    try:
        screenshot_manager = ScreenshotManager(driver)
        return screenshot_manager.take_screenshot(thread_id)
    except Exception as e:
        logger.error(f"❌ Ошибка при создании скриншота (Поток {thread_id})", exc_info=e)
        return None

def check_table_data(driver, thread_id):
    """
    Проверяет данные в таблице и отправляет их через Telegram
    
    Args:
        driver: WebDriver
        thread_id: ID потока
    """
    logger = Logger("main")
    
    try:
        # Ждем загрузки таблицы
        logger.info(f"⏳ Ожидание загрузки таблицы (Поток {thread_id})...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-row-key]"))
        )
        
        # Находим все строки таблицы
        rows = driver.find_elements(By.CSS_SELECTOR, "tr[data-row-key]")
        
        if not rows:
            logger.warning(f"⚠️ Таблица пуста (Поток {thread_id})")
            return
            
        # Собираем данные из первой строки
        row = rows[0]
        
        # Извлекаем данные из ячеек
        symbol = row.find_element(By.CSS_SELECTOR, ".name").text
        leverage = row.find_element(By.CSS_SELECTOR, "td[aria-colindex='2']").text
        entry_price = row.find_element(By.CSS_SELECTOR, "td[aria-colindex='3']").text
        mark_price = row.find_element(By.CSS_SELECTOR, "td[aria-colindex='4']").text
        time_element = row.find_element(By.CSS_SELECTOR, "td[aria-colindex='5']").text
        
        # Извлекаем PNL и процент
        pnl_cell = row.find_element(By.CSS_SELECTOR, "td[aria-colindex='6']")
        pnl_elements = pnl_cell.find_elements(By.CSS_SELECTOR, ".Number")
        pnl = pnl_elements[0].text if len(pnl_elements) > 0 else "N/A"
        pnl_percent = pnl_elements[1].text if len(pnl_elements) > 1 else "N/A"
        
        # Формируем сообщение
        message = (
            f"📊 Данные позиции (Поток {thread_id}):\n\n"
            f"Символ: {symbol}\n"
            f"Плечо: {leverage}x\n"
            f"Цена входа: {entry_price}\n"
            f"Текущая цена: {mark_price}\n"
            f"Время: {time_element}\n"
            f"PNL: {pnl}\n"
            f"PNL %: {pnl_percent}"
        )
        
        # Отправляем сообщение в Telegram
        telegram_manager.send_message(message)
        logger.info(f"✅ Данные отправлены в Telegram (Поток {thread_id})")
        
    except TimeoutException:
        logger.error(f"❌ Таймаут при ожидании таблицы (Поток {thread_id})")
    except NoSuchElementException as e:
        logger.error(f"❌ Элемент не найден (Поток {thread_id}): {str(e)}")
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке данных таблицы (Поток {thread_id})", exc_info=e)

def open_binance_page(url, thread_id):
    try:
        # Используем существующий драйвер
        driver = driver_manager.get_driver(thread_id)
        if not driver:
            logger.error(f"❌ Драйвер не найден для потока {thread_id}")
            return
        
        # Инициализация менеджеров
        page_manager = PageManager(driver)
        auth_manager = AuthManager(driver)
        
        # Проверяем VPN
        vpn_checker = VPNChecker(driver)
        logger.info("⏳ Ожидание активации VPN...")
        logger.info("После включения VPN нажмите Enter в консоли")
        input()
        logger.info("✅ Пользователь подтвердил активацию VPN")
        
        # Переходим на страницу логина Binance
        logger.info("🌐 Переход на страницу логина Binance...")
        driver.get("https://accounts.binance.com/en/login")
        
        # Ждем загрузки страницы
        if not page_manager.wait_for_page_load():
            logger.error(f"❌ Ошибка загрузки страницы логина (Поток {thread_id})")
            return
            
        logger.info(f"✅ Страница логина Binance успешно открыта (Поток {thread_id})")
        logger.info("⏳ Ожидание ручной авторизации...")
        logger.info("После авторизации нажмите Enter в консоли")
        input()
        
        # Ждем появления элемента с никнеймом пользователя
        logger.info(f"⏳ Ожидание загрузки дашборда (Поток {thread_id})...")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#dashboard-userinfo-nickname"))
            )
            nickname = driver.find_element(By.CSS_SELECTOR, "#dashboard-userinfo-nickname").text
            logger.info(f"✅ Пользователь авторизован: {nickname} (Поток {thread_id})")
            
            # После успешного входа запускаем проверку авторизации
            logger.info("⏳ Запуск проверки авторизации...")
            success, message = auth_manager.check_auth_after_login()
            if not success:
                logger.error(f"❌ Ошибка при проверке авторизации: {message}")
                return
            logger.info("✅ Проверка авторизации успешно завершена")
            
        except TimeoutException:
            logger.error(f"❌ Не удалось найти элемент с никнеймом пользователя (Поток {thread_id})")
            return
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке никнейма пользователя (Поток {thread_id})", exc_info=e)
            return
            
        # Переходим по URL из JSON
        logger.info(f"🌐 Переход по URL: {url} (Поток {thread_id})")
        driver.get(url)
        
        # Ждем загрузки страницы
        if not page_manager.wait_for_page_load():
            logger.error(f"❌ Ошибка загрузки страницы {url} (Поток {thread_id})")
            return
            
        logger.info(f"✅ Страница {url} успешно открыта (Поток {thread_id})")
        
        # Проверяем данные в таблице и отправляем их через Telegram
        check_table_data(driver, thread_id)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при открытии страницы (Поток {thread_id})", exc_info=e)

def start_multiple_pages():
    """Запускает несколько страниц Binance в разных потоках"""
    try:
        # Загружаем URL из JSON файла
        with open('urls.json', 'r') as f:
            urls_data = json.load(f)
            urls = urls_data.get('urls', [])
        
        if not urls:
            logger.error("❌ Нет URL для открытия в файле urls.json")
            return
            
        # Создаем потоки для каждого URL
        threads = []
        for i, url in enumerate(urls, 1):
            thread = threading.Thread(
                target=open_binance_page,
                args=(url, i),
                name=f"BinancePage_{i}"
            )
            threads.append(thread)
            thread.start()
            logger.info(f"✅ Запущен поток {i} для URL: {url}")
            
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()
            
    except Exception as e:
        logger.error("❌ Ошибка при запуске страниц", exc_info=e)
    finally:
        # Очищаем все драйверы при завершении
        driver_manager.cleanup_all()

def main():
    # Инициализация логгера
    logger = Logger("main")
    logger.info("🚀 Запуск бота...")
    
    # Запуск Telegram бота
    telegram_manager.start_polling()
    
    try:
        # Регистрация обработчиков команд
        telegram_manager.register_command("/start", handle_start_command)
        telegram_manager.register_command("/help", handle_help_command)
        telegram_manager.register_command("/url", handle_url_command)
        
        # Запуск основного процесса
        logger.info("🚀 Запуск основного процесса...")
        start_multiple_pages()
        
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал завершения работы")
    except Exception as e:
        logger.error("❌ Критическая ошибка", exc_info=e)
    finally:
        # Остановка Telegram бота
        telegram_manager.stop_polling()
        logger.info("👋 Бот остановлен")

def handle_start_command(message: Dict) -> None:
    """Обработчик команды /start"""
    chat_id = message["chat_id"]
    telegram_manager.send_message(
        "👋 Привет! Я бот для автоматизации торговли.\n\n"
        "Доступные команды:\n"
        "/credentials - Управление учетными данными\n"
        "/help - Помощь",
        chat_id
    )

def handle_help_command(message: Dict) -> None:
    """Обработчик команды /help"""
    chat_id = message["chat_id"]
    telegram_manager.send_message(
        "📚 Помощь по использованию бота:\n\n"
        "1. Используйте /url для управления списком URL:\n"
        "   /url add <url> - Добавить URL\n"
        "   /url list - Показать все URL\n"
        "   /url remove <номер> - Удалить URL\n"
        "   /url clear - Очистить все URL\n\n"
        "2. После добавления URL бот автоматически откроет их\n"
        "3. Все уведомления будут приходить в этот чат",
        chat_id
    )

def handle_credentials_command(message: Dict) -> None:
    """Обработчик команды /credentials"""
    chat_id = message["chat_id"]
    text = message["text"]
    
    try:
        # Парсинг команды
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            telegram_manager.send_message(
                "❌ Неверный формат команды. Используйте:\n"
                "/credentials set <логин> <пароль>\n"
                "/credentials clear",
                chat_id
            )
            return
            
        action = parts[1].lower()
        
        if action == "set":
            if len(parts) != 3:
                telegram_manager.send_message(
                    "❌ Неверный формат команды. Используйте:\n"
                    "/credentials set <логин> <пароль>",
                    chat_id
                )
                return
                
            credentials = parts[2].split()
            if len(credentials) != 2:
                telegram_manager.send_message(
                    "❌ Неверный формат учетных данных. Используйте:\n"
                    "/credentials set <логин> <пароль>",
                    chat_id
                )
                return
                
            username, password = credentials
            
            # Сохранение учетных данных
            env_manager = EnvManager()
            env_manager.set_credentials(username, password)
            
            telegram_manager.send_message(
                f"✅ Учетные данные успешно сохранены:\n"
                f"Логин: {username}",
                chat_id
            )
            
        elif action == "clear":
            # Очистка учетных данных
            env_manager = EnvManager()
            env_manager.clear_credentials()
            
            telegram_manager.send_message(
                "✅ Учетные данные успешно очищены",
                chat_id
            )
            
        else:
            telegram_manager.send_message(
                "❌ Неизвестное действие. Используйте:\n"
                "/credentials set <логин> <пароль>\n"
                "/credentials clear",
                chat_id
            )
            
    except Exception as e:
        logger = Logger("main")
        logger.error("❌ Ошибка при обработке команды credentials", exc_info=e)
        telegram_manager.send_message(
            "❌ Произошла ошибка при обработке команды",
            chat_id
        )

def handle_url_command(message: Dict) -> None:
    """Обработчик команды /url для управления списком URL"""
    chat_id = message["chat_id"]
    text = message.get("text", "")
    
    try:
        # Показываем инструкцию, если команда без параметров
        if text == "/url":
            telegram_manager.send_message(
                "📝 Управление URL:\n\n"
                "/url add <url> - Добавить URL\n"
                "/url list - Показать все URL\n"
                "/url remove <номер> - Удалить URL по номеру\n"
                "/url clear - Очистить все URL",
                chat_id
            )
            return
            
        # Парсим команду
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            telegram_manager.send_message(
                "❌ Неверный формат команды!\n"
                "Используйте /url для просмотра инструкции",
                chat_id
            )
            return
            
        action = parts[1].lower()
        
        # Загружаем текущий список URL
        try:
            with open('urls.json', 'r') as f:
                urls_data = json.load(f)
                urls = urls_data.get('urls', [])
        except FileNotFoundError:
            urls = []
            
        if action == "add":
            if len(parts) != 3:
                telegram_manager.send_message(
                    "❌ Укажите URL для добавления!\n"
                    "Пример: /url add https://www.binance.com/en/my/wallet/account",
                    chat_id
                )
                return
                
            new_url = parts[2]
            if new_url in urls:
                telegram_manager.send_message(
                    "⚠️ Этот URL уже есть в списке",
                    chat_id
                )
                return
                
            urls.append(new_url)
            telegram_manager.send_message(
                f"✅ URL добавлен:\n{new_url}",
                chat_id
            )
            
        elif action == "list":
            if not urls:
                telegram_manager.send_message(
                    "📝 Список URL пуст",
                    chat_id
                )
                return
                
            message = "📝 Список URL:\n\n"
            for i, url in enumerate(urls, 1):
                message += f"{i}. {url}\n"
            telegram_manager.send_message(message, chat_id)
            
        elif action == "remove":
            if len(parts) != 3:
                telegram_manager.send_message(
                    "❌ Укажите номер URL для удаления!\n"
                    "Пример: /url remove 1",
                    chat_id
                )
                return
                
            try:
                index = int(parts[2]) - 1
                if 0 <= index < len(urls):
                    removed_url = urls.pop(index)
                    telegram_manager.send_message(
                        f"✅ URL удален:\n{removed_url}",
                        chat_id
                    )
                else:
                    telegram_manager.send_message(
                        "❌ Неверный номер URL!",
                        chat_id
                    )
            except ValueError:
                telegram_manager.send_message(
                    "❌ Номер должен быть числом!",
                    chat_id
                )
                return
                
        elif action == "clear":
            urls = []
            telegram_manager.send_message(
                "✅ Список URL очищен",
                chat_id
            )
            
        else:
            telegram_manager.send_message(
                "❌ Неизвестное действие!\n"
                "Используйте /url для просмотра инструкции",
                chat_id
            )
            return
            
        # Сохраняем обновленный список URL
        with open('urls.json', 'w') as f:
            json.dump({"urls": urls}, f, indent=4)
            
    except Exception as e:
        logger = Logger("main")
        logger.error("❌ Ошибка при обработке команды url", exc_info=e)
        telegram_manager.send_message(
            "❌ Произошла ошибка при обработке команды",
            chat_id
        )

if __name__ == "__main__":
    main()
