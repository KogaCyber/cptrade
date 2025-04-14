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

# Функция для отправки сообщения в Telegram
def send_to_telegram(bot_token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print("✅ Сообщение успешно отправлено в Telegram")
        else:
            print(f"❌ Ошибка отправки сообщения в Telegram: {response.status_code}")
            print(f"Ответ сервера: {response.text}")
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения в Telegram: {str(e)}")
        traceback.print_exc()

# Функция для получения информации о позициях
def get_positions(driver, wait):
    try:
        print("Начинаем поиск позиций...")
        
        # Ждем загрузки таблицы с позициями
        table_selectors = [
            "table.bn-web-table",
            "div.bn-web-table",
            "//table[contains(@class, 'bn-web-table')]",
            "//div[contains(@class, 'bn-web-table')]"
        ]
        
        positions_table = None
        for selector in table_selectors:
            try:
                print(f"Пробуем найти таблицу с селектором: {selector}")
                if selector.startswith("//"):
                    positions_table = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                else:
                    positions_table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                if positions_table:
                    print(f"Таблица с позициями найдена с селектором: {selector}")
                    break
            except (NoSuchElementException, TimeoutException):
                print(f"Селектор {selector} не сработал")
                continue
        
        if not positions_table:
            print("Не удалось найти таблицу с позициями")
            return []
        
        # Ищем строки с позициями
        row_selectors = [
            "tr.bn-web-table-row",
            "//tr[contains(@class, 'bn-web-table-row')]"
        ]
        
        position_rows = []
        for selector in row_selectors:
            try:
                print(f"Пробуем найти строки с селектором: {selector}")
                if selector.startswith("//"):
                    position_rows = driver.find_elements(By.XPATH, selector)
                else:
                    position_rows = driver.find_elements(By.CSS_SELECTOR, selector)
                if position_rows:
                    print(f"Найдено {len(position_rows)} строк с селектором: {selector}")
                    break
            except Exception as e:
                print(f"Ошибка при поиске строк с селектором {selector}: {str(e)}")
                continue
        
        if not position_rows:
            print("Не удалось найти строки с позициями")
            return []
        
        positions_data = []
        
        # Обрабатываем каждую строку
        for i, row in enumerate(position_rows, 1):
            try:
                print(f"Обрабатываем строку {i}...")
                
                # Извлекаем данные из ячеек
                cells = row.find_elements(By.CSS_SELECTOR, "td.bn-web-table-cell")
                
                if len(cells) >= 6:
                    # Извлекаем символ и направление
                    symbol_cell = cells[0]
                    symbol_element = symbol_cell.find_element(By.CSS_SELECTOR, "div.name")
                    symbol = symbol_element.text
                    
                    # Определяем направление (Long/Short) по цвету индикатора
                    direction_element = symbol_cell.find_element(By.CSS_SELECTOR, "div.dir")
                    direction_class = direction_element.get_attribute("class")
                    direction = "Long" if "bg-Buy" in direction_class else "Short"
                    
                    # Извлекаем размер позиции
                    size = cells[1].text
                    
                    # Извлекаем цену входа
                    entry_price = cells[2].text
                    
                    # Извлекаем текущую цену
                    mark_price = cells[3].text
                    
                    # Извлекаем время
                    time_str = cells[4].text
                    
                    # Извлекаем PnL
                    pnl_cell = cells[5]
                    pnl_elements = pnl_cell.find_elements(By.CSS_SELECTOR, "span.Number")
                    pnl_value = pnl_elements[0].text if pnl_elements else "N/A"
                    pnl_percentage = pnl_elements[1].text if len(pnl_elements) > 1 else "N/A"
                    
                    print(f"Данные позиции: Символ={symbol}, Направление={direction}, Размер={size}, Цена входа={entry_price}, Текущая цена={mark_price}, Время={time_str}, PnL={pnl_value} ({pnl_percentage})")
                    
                    positions_data.append({
                        "symbol": symbol,
                        "direction": direction,
                        "size": size,
                        "entry_price": entry_price,
                        "mark_price": mark_price,
                        "time": time_str,
                        "pnl": pnl_value,
                        "pnl_percentage": pnl_percentage
                    })
                else:
                    print(f"Недостаточно ячеек в строке {i}: {len(cells)}")
            except Exception as e:
                print(f"Ошибка при обработке строки {i}: {str(e)}")
                traceback.print_exc()
        
        print(f"Всего обработано позиций: {len(positions_data)}")
        return positions_data
    except Exception as e:
        print(f"Ошибка при получении информации о позициях: {str(e)}")
        print("Полный стек ошибки:")
        traceback.print_exc()
        return []

# Функция для сравнения позиций и отправки только новых
def compare_and_send_new_positions(old_positions, new_positions, bot_token, chat_id):
    print(f"Сравниваем позиции. Старых позиций: {len(old_positions) if old_positions else 0}, новых позиций: {len(new_positions) if new_positions else 0}")
    
    # Если это первый запуск или были проблемы с предыдущими позициями
    if not old_positions:
        # Если есть новые позиции, сохраняем их без отправки уведомления
        print("Первый запуск или восстановление после ошибки. Сохраняем текущие позиции без отправки уведомлений.")
        return new_positions
    
    # Проверяем, не слишком ли резко изменилось количество позиций
    if old_positions and new_positions:
        old_count = len(old_positions)
        new_count = len(new_positions)
        if old_count > 3 and new_count == 0:
            print("Подозрительное изменение количества позиций. Возможно, проблемы с загрузкой.")
            return old_positions
    
    # Создаем множество ключей для быстрого сравнения
    old_keys = set()
    for pos in old_positions:
        key = f"{pos['symbol']}_{pos['size']}_{pos['time']}"
        old_keys.add(key)
        print(f"Добавлен ключ для старой позиции: {key}")
    
    # Находим новые позиции и закрытые позиции
    new_positions_to_send = []
    closed_positions = []
    
    # Создаем множество ключей для новых позиций
    new_keys = set()
    for pos in new_positions:
        key = f"{pos['symbol']}_{pos['size']}_{pos['time']}"
        new_keys.add(key)
        print(f"Добавлен ключ для новой позиции: {key}")
    
    # Проверяем, какие позиции закрыты
    for pos in old_positions:
        key = f"{pos['symbol']}_{pos['size']}_{pos['time']}"
        if key not in new_keys:
            print(f"Найдена закрытая позиция: {key}")
            closed_positions.append(pos)
    
    # Проверяем, какие позиции новые
    for pos in new_positions:
        key = f"{pos['symbol']}_{pos['size']}_{pos['time']}"
        if key not in old_keys:
            print(f"Найдена новая позиция: {key}")
            new_positions_to_send.append(pos)
    
    # Отправляем уведомления о новых позициях
    if new_positions_to_send:
        print(f"Отправляем {len(new_positions_to_send)} новых позиций")
        send_positions_to_telegram(new_positions_to_send, bot_token, chat_id)
    else:
        print("Новых позиций не найдено")
    
    # Отправляем уведомления о закрытых позициях только если это не похоже на проблемы с загрузкой
    if closed_positions and new_positions:  # Проверяем, что есть хотя бы какие-то активные позиции
        print(f"Отправляем {len(closed_positions)} закрытых позиций")
        send_closed_positions_to_telegram(closed_positions, bot_token, chat_id)
    else:
        print("Закрытых позиций не найдено или возможны проблемы с загрузкой")
    
    return new_positions

# Функция для отправки позиций в Telegram
def send_positions_to_telegram(positions, bot_token, chat_id):
    if not positions:
        print("Нет позиций для отправки")
        return
    
    print(f"Подготавливаем сообщение для отправки {len(positions)} позиций")
    
    # Формируем сообщение для Telegram
    message = "<b>Новые позиции:</b>\n\n"
    for i, pos in enumerate(positions, 1):
        try:
            message += f"<b>Позиция {i}:</b>\n"
            message += f"<b>Символ:</b> {pos['symbol']}\n"
            message += f"<b>Направление:</b> {pos['direction']}\n"
            message += f"<b>Размер:</b> {pos['size']}\n"
            message += f"<b>Цена входа:</b> {pos['entry_price']}\n"
            message += f"<b>Текущая цена:</b> {pos['mark_price']}\n"
            message += f"<b>Время:</b> {pos['time']}\n"
            message += f"<b>PNL:</b> {pos['pnl']} ({pos['pnl_percentage']})\n\n"
            print(f"Добавлена позиция {i} в сообщение")
        except Exception as e:
            print(f"Ошибка при форматировании позиции {i}: {str(e)}")
            traceback.print_exc()
    
    # Отправляем сообщение в Telegram
    print("Отправляем сообщение в Telegram")
    send_to_telegram(bot_token, chat_id, message)

# Функция для отправки уведомлений о закрытых позициях в Telegram
def send_closed_positions_to_telegram(positions, bot_token, chat_id):
    if not positions:
        print("Нет закрытых позиций для отправки")
        return
    
    print(f"Подготавливаем сообщение для отправки {len(positions)} закрытых позиций")
    
    # Формируем сообщение для Telegram
    message = "<b>Закрытые позиции:</b>\n\n"
    for i, pos in enumerate(positions, 1):
        try:
            message += f"<b>Позиция {i}:</b>\n"
            message += f"<b>Символ:</b> {pos['symbol']}\n"
            message += f"<b>Направление:</b> {pos['direction']}\n"
            message += f"<b>Размер:</b> {pos['size']}\n"
            message += f"<b>Цена входа:</b> {pos['entry_price']}\n"
            message += f"<b>Текущая цена:</b> {pos['mark_price']}\n"
            message += f"<b>Время:</b> {pos['time']}\n"
            message += f"<b>PNL:</b> {pos['pnl']} ({pos['pnl_percentage']})\n\n"
            print(f"Добавлена закрытая позиция {i} в сообщение")
        except Exception as e:
            print(f"Ошибка при форматировании закрытой позиции {i}: {str(e)}")
            traceback.print_exc()
    
    # Отправляем сообщение в Telegram
    print("Отправляем сообщение о закрытых позициях в Telegram")
    send_to_telegram(bot_token, chat_id, message)

# Функция для получения и отправки информации о позициях
def get_and_send_positions(driver, wait, bot_token, chat_id, old_positions=None):
    try:
        # Получаем все позиции
        positions = driver.find_elements(By.CSS_SELECTOR, "tr.bn-web-table-row")
        if not positions:
            print("ℹ️ Позиции не найдены")
            return None

        print(f"📊 Найдено {len(positions)} позиций")
        
        # Если это первая проверка, просто сохраняем позиции
        if old_positions is None:
            print("ℹ️ Первичная проверка позиций")
            return positions

        # Сравниваем старые и новые позиции
        new_positions = []
        for position in positions:
            try:
                cells = position.find_elements(By.CSS_SELECTOR, "td.bn-web-table-cell")
                if len(cells) >= 6:
                    symbol = cells[0].find_element(By.CSS_SELECTOR, "div.name").text
                    direction = "Long" if "bg-Buy" in cells[0].find_element(By.CSS_SELECTOR, "div.dir").get_attribute("class") else "Short"
                    size = cells[1].text
                    entry_price = cells[2].text
                    mark_price = cells[3].text
                    time_str = cells[4].text
                    pnl_elements = cells[5].find_elements(By.CSS_SELECTOR, "span.Number")
                    pnl_value = pnl_elements[0].text if pnl_elements else "N/A"
                    pnl_percentage = pnl_elements[1].text if len(pnl_elements) > 1 else "N/A"
                    
                    position_info = {
                        'symbol': symbol,
                        'direction': direction,
                        'size': size,
                        'entry_price': entry_price,
                        'mark_price': mark_price,
                        'time': time_str,
                        'pnl_value': pnl_value,
                        'pnl_percentage': pnl_percentage
                    }
                    
                    # Проверяем, является ли это новой позицией
                    is_new = True
                    for old_pos in old_positions:
                        try:
                            old_cells = old_pos.find_elements(By.CSS_SELECTOR, "td.bn-web-table-cell")
                            if len(old_cells) >= 6:
                                old_symbol = old_cells[0].find_element(By.CSS_SELECTOR, "div.name").text
                                old_direction = "Long" if "bg-Buy" in old_cells[0].find_element(By.CSS_SELECTOR, "div.dir").get_attribute("class") else "Short"
                                if old_symbol == symbol and old_direction == direction:
                                    is_new = False
                                    break
                        except:
                            continue
                    
                    if is_new:
                        new_positions.append(position_info)
                        # Формируем и отправляем сообщение
                        message = f"🆕 <b>Новая позиция:</b>\n\n" \
                                 f"📊 <b>Символ:</b> {symbol}\n" \
                                 f"📈 <b>Направление:</b> {direction}\n" \
                                 f"📏 <b>Размер:</b> {size}\n" \
                                 f"💰 <b>Цена входа:</b> {entry_price}\n" \
                                 f"📊 <b>Текущая цена:</b> {mark_price}\n" \
                                 f"⏰ <b>Время:</b> {time_str}\n" \
                                 f"💵 <b>PNL:</b> {pnl_value} ({pnl_percentage})"
                        
                        send_to_telegram(bot_token, chat_id, message)
            except Exception as e:
                print(f"❌ Ошибка при обработке позиции: {str(e)}")
                traceback.print_exc()
                continue
        
        if new_positions:
            print(f"✅ Найдено {len(new_positions)} новых позиций")
        else:
            print("ℹ️ Новых позиций не найдено")
            
        return positions
    except Exception as e:
        print(f"❌ Ошибка при получении позиций: {str(e)}")
        traceback.print_exc()
        return old_positions

# Функция для проверки и обработки процесса входа в систему
def check_and_handle_login(driver, wait):
    try:
        # Проверяем наличие кнопки "Log In" разными способами
        login_selectors = [
            "a.link.cursor-pointer.text-TextLink.no-underline[href='/login']",
            "button.css-1wr4jig",  # Альтернативный селектор
            "//a[contains(text(), 'Log In')]"  # XPath
        ]
        
        login_link = None
        for selector in login_selectors:
            try:
                if selector.startswith("//"):
                    login_link = driver.find_element(By.XPATH, selector)
                else:
                    login_link = driver.find_element(By.CSS_SELECTOR, selector)
                if login_link:
                    break
            except NoSuchElementException:
                continue
        
        if login_link:
            print("Обнаружена кнопка Log In. Нажимаем на нее...")
            login_link.click()
            time.sleep(5)  # Даем время на загрузку страницы входа
            
            # Проверяем наличие кнопки "Continue with Telegram" разными способами
            telegram_selectors = [
                "button[aria-label='Continue with Telegram']",
                "//button[contains(@aria-label, 'Telegram')]",
                "//button[contains(text(), 'Telegram')]"
            ]
            
            telegram_button = None
            for selector in telegram_selectors:
                try:
                    if selector.startswith("//"):
                        telegram_button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    else:
                        telegram_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    if telegram_button:
                        break
                except (NoSuchElementException, TimeoutException):
                    continue
            
            if telegram_button:
                print("Нажимаем на кнопку Continue with Telegram...")
                telegram_button.click()
                time.sleep(5)  # Даем время на обработку нажатия
                
                # Проверяем наличие кнопки "Connect" разными способами
                connect_selectors = [
                    "button.bn-button.bn-button__primary.data-size-large.w-full.mt-6",
                    "//button[contains(text(), 'Connect')]",
                    "button.css-1wr4jig[type='submit']"
                ]
                
                connect_button = None
                for selector in connect_selectors:
                    try:
                        if selector.startswith("//"):
                            connect_button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        else:
                            connect_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                        if connect_button:
                            break
                    except (NoSuchElementException, TimeoutException):
                        continue
                
                if connect_button:
                    print("Нажимаем на кнопку Connect...")
                    connect_button.click()
                    print("Ждем, пока вы войдете в систему...")
                    time.sleep(20)
                    return True
                else:
                    print("Кнопка Connect не найдена")
            else:
                print("Кнопка Continue with Telegram не найдена")
        else:
            print("Кнопка Log In не найдена")
        
        return False
    except Exception as e:
        print(f"Ошибка при попытке входа: {str(e)}")
        return False

def check_all_conditions(driver, wait):
    try:
        print("\n=== Начинаем проверку всех условий ===")
        
        # 1. Проверка никнейма Botir_Nomozov
        try:
            nickname_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#dashboard-userinfo-nickname")))
            nickname_text = nickname_element.text
            print(f"Найден никнейм: {nickname_text}")
            if "Botir_Nomozov" not in nickname_text:
                print("❌ Неверный никнейм! Ожидался Botir_Nomozov")
                return False
            print("✅ Никнейм Botir_Nomozov подтвержден")
        except Exception as e:
            print("❌ Ошибка при проверке никнейма:", str(e))
            return False

        # 2. Проверка кнопки Log In
        try:
            login_buttons = driver.find_elements(By.CSS_SELECTOR, "a.link.cursor-pointer.text-TextLink.no-underline[href='/login']")
            if login_buttons:
                print("❌ Обнаружена кнопка Log In - требуется повторный вход")
                return False
            print("✅ Кнопка Log In не найдена - пользователь в системе")
        except Exception as e:
            print("❌ Ошибка при проверке кнопки Log In:", str(e))
            return False

        # 3. Проверка таблицы с позициями
        try:
            table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.bn-web-table")))
            print("✅ Таблица с позициями найдена")
        except Exception as e:
            print("❌ Ошибка при поиске таблицы с позициями:", str(e))
            return False

        # 4. Проверка строк с позициями
        try:
            positions = driver.find_elements(By.CSS_SELECTOR, "tr.bn-web-table-row")
            print(f"✅ Найдено {len(positions)} позиций")
        except Exception as e:
            print("❌ Ошибка при поиске позиций:", str(e))
            return False

        # 5. Проверка URL
        current_url = driver.current_url
        expected_url = "futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2"
        if expected_url not in current_url:
            print(f"❌ Неверный URL: {current_url}")
            return False
        print("✅ URL подтвержден")

        print("=== Все проверки пройдены успешно ===\n")
        return True
    except Exception as e:
        print("❌ Критическая ошибка при проверке условий:", str(e))
        traceback.print_exc()
        return False

def handle_login_process(driver, wait):
    try:
        print("\n=== Начинаем процесс входа ===")
        
        # 1. Поиск и нажатие кнопки Log In
        login_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.link.cursor-pointer.text-TextLink.no-underline[href='/login']")))
        print("✅ Найдена кнопка Log In")
        login_link.click()
        time.sleep(5)
        
        # 2. Поиск и нажатие кнопки Continue with Telegram
        telegram_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Continue with Telegram']")))
        print("✅ Найдена кнопка Continue with Telegram")
        telegram_button.click()
        time.sleep(5)
        
        # 3. Поиск и нажатие кнопки Connect
        connect_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.bn-button.bn-button__primary.data-size-large.w-full.mt-6")))
        print("✅ Найдена кнопка Connect")
        connect_button.click()
        
        print("⏳ Ожидание входа в систему...")
        time.sleep(20)
        
        # 4. Возврат на страницу лидерборда
        print("Переход на страницу лидерборда...")
        driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
        time.sleep(15)
        
        print("=== Процесс входа завершен ===\n")
        return True
    except Exception as e:
        print("❌ Ошибка при процессе входа:", str(e))
        traceback.print_exc()
        return False

def check_vpn_connection():
    try:
        print("🔍 Проверяем подключение к VPN...")
        # Здесь можно добавить проверку подключения к VPN
        # Например, проверку IP или доступности определенных сервисов
        return True
    except Exception as e:
        print(f"❌ Ошибка при проверке VPN: {str(e)}")
        return False

def login_binance():
    while True:
        try:
            # Настройка опций Chrome
            options = uc.ChromeOptions()
            options.add_argument('--start-maximized')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-features=TranslateUI')
            options.add_argument('--disable-features=IsolateOrigins,site-per-process')
            options.add_argument('--disable-site-isolation-trials')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--ignore-ssl-errors')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--disable-notifications')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-web-security')
            options.add_argument('--allow-running-insecure-content')
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--password-store=basic')
            options.add_argument('--use-mock-keychain')
            options.add_argument('--disable-blink-features')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-extensions-except=')
            options.add_argument('--disable-component-extensions-with-background-pages')
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-breakpad')
            options.add_argument('--disable-component-update')
            options.add_argument('--disable-domain-reliability')
            options.add_argument('--disable-features=AudioServiceOutOfProcess')
            options.add_argument('--disable-hang-monitor')
            options.add_argument('--disable-ipc-flooding-protection')
            options.add_argument('--disable-prompt-on-repost')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-sync')
            options.add_argument('--force-color-profile=srgb')
            options.add_argument('--metrics-recording-only')
            options.add_argument('--no-pings')
            options.add_argument('--no-zygote')
            options.add_argument('--use-gl=swiftshader')
            options.add_argument('--window-size=1920,1080')
            
            # Инициализация драйвера Chrome
            driver = None
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    print("🔄 Инициализация Chrome...")
                    driver = uc.Chrome(options=options, version_main=114)  # Указываем конкретную версию Chrome
                    driver.set_page_load_timeout(60)
                    print("✅ Chrome успешно инициализирован")
                    break
                except Exception as e:
                    print(f"❌ Ошибка при инициализации драйвера (попытка {retry_count + 1}/{max_retries}): {str(e)}")
                    retry_count += 1
                    if retry_count < max_retries:
                        print("⚠️ Пожалуйста, проверьте подключение к VPN и нажмите Enter для продолжения...")
                        input()
                        time.sleep(10)
                    else:
                        print("❌ Превышено максимальное количество попыток, перезапускаем скрипт...")
                        if driver:
                            driver.quit()
                        time.sleep(60)
                        return
            
            # Открытие страницы лидерборда
            max_page_retries = 3
            page_retry_count = 0
            
            while page_retry_count < max_page_retries:
                try:
                    print("🌐 Переходим на страницу профиля...")
                    driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                    break
                except WebDriverException as e:
                    print(f"❌ Ошибка при подключении к Binance (попытка {page_retry_count + 1}/{max_page_retries}): {str(e)}")
                    page_retry_count += 1
                    if page_retry_count < max_page_retries:
                        print("⚠️ Пожалуйста, проверьте подключение к VPN и нажмите Enter для продолжения...")
                        input()
                        time.sleep(10)
                    else:
                        print("❌ Превышено максимальное количество попыток загрузки страницы")
                        if driver:
                            driver.quit()
                        time.sleep(60)
                        return
            
            wait = WebDriverWait(driver, 30)
            positions = None
            last_refresh_time = time.time()
            error_count = 0
            max_errors = 5
            network_error_count = 0
            max_network_errors = 3
            
            while True:
                try:
                    current_time = time.time()
                    if current_time - last_refresh_time >= random.uniform(10, 15):
                        print("\n🔄 Начало цикла обновления")
                        
                        # Очистка памяти
                        if hasattr(driver, 'execute_script'):
                            driver.execute_script("window.gc();")
                        
                        # Обновляем страницу
                        print("🔄 Обновляем страницу...")
                        try:
                            driver.refresh()
                        except WebDriverException as e:
                            print(f"❌ Ошибка при обновлении страницы: {str(e)}")
                            network_error_count += 1
                            if network_error_count >= max_network_errors:
                                print("⚠️ Пожалуйста, проверьте подключение к VPN и нажмите Enter для продолжения...")
                                input()
                                network_error_count = 0
                                continue
                            time.sleep(30)
                            continue
                        
                        last_refresh_time = current_time
                        time.sleep(20)
                        
                        # Проверяем все условия
                        if not check_all_conditions(driver, wait):
                            print("❌ Условия не выполнены, пробуем войти заново...")
                            if handle_login_process(driver, wait):
                                print("✅ Успешный вход")
                                error_count = 0
                                network_error_count = 0
                            else:
                                error_count += 1
                                if error_count >= max_errors:
                                    print("❌ Слишком много ошибок, перезапускаем браузер...")
                                    break
                                continue
                        
                        # Получаем и отправляем информацию о позициях
                        positions = get_and_send_positions(driver, wait, bot_token, chat_id, positions)
                        error_count = 0
                        network_error_count = 0
                    
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Ошибка в цикле обновления: {str(e)}")
                    traceback.print_exc()
                    error_count += 1
                    
                    if error_count >= max_errors:
                        print("❌ Слишком много ошибок, перезапускаем браузер...")
                        break
                    
                    print("🔄 Пробуем перезагрузить страницу...")
                    try:
                        driver.refresh()
                    except:
                        print("⚠️ Пожалуйста, проверьте подключение к VPN и нажмите Enter для продолжения...")
                        input()
                        driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                    time.sleep(30)
            
            # Закрываем браузер перед перезапуском
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            
        except Exception as e:
            print(f"❌ Критическая ошибка: {str(e)}")
            traceback.print_exc()
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            print("🔄 Перезапускаем скрипт через 60 секунд...")
            time.sleep(60)

def run_forever():
    # Бесконечный цикл для перезапуска скрипта в случае критических ошибок
    while True:
        try:
            login_binance()
        except KeyboardInterrupt:
            print("Скрипт остановлен пользователем.")
            break
        except Exception as e:
            print(f"Критическая ошибка: {str(e)}")
            print("Полный стек ошибки:")
            traceback.print_exc()
            print("Перезапускаем скрипт через 10 секунд...")
            time.sleep(10)
            # Продолжаем цикл, чтобы перезапустить скрипт

if __name__ == "__main__":
    # Запускаем функцию, которая будет работать вечно
    run_forever()
