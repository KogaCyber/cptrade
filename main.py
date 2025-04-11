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
        print(f"Пытаемся отправить сообщение в Telegram. Длина сообщения: {len(message)}")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        print(f"Отправляем запрос на URL: {url}")
        print(f"Данные запроса: {data}")
        response = requests.post(url, data=data)
        print(f"Получен ответ от Telegram API. Код ответа: {response.status_code}")
        print(f"Текст ответа: {response.text}")
        if response.status_code == 200:
            print("Сообщение успешно отправлено в Telegram")
        else:
            print(f"Ошибка при отправке сообщения в Telegram: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Ошибка при отправке сообщения в Telegram: {str(e)}")
        print(f"Полный стек ошибки:")
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
    print("Начинаем получение и отправку информации о позициях")
    
    # Проверяем, не произошел ли выход из системы
    if check_and_handle_login(driver, wait):
        print("Произошел автоматический выход из системы. Выполняем вход...")
        # Даем время на полную загрузку страницы после входа
        time.sleep(20)
        # В этом случае пропускаем текущую итерацию, сохраняя старые позиции
        return old_positions
    
    # Ждем загрузки страницы
    print("Ждем загрузки страницы...")
    time.sleep(14)
    
    # Проверяем, что страница действительно загрузилась
    try:
        # Пытаемся найти основные элементы страницы
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.bn-web-table"))
        )
        print("Страница успешно загружена")
    except TimeoutException:
        print("Ошибка загрузки страницы. Возвращаем старые позиции.")
        return old_positions
    
    # Получаем информацию о позициях
    print("Получаем информацию о позициях...")
    positions = get_positions(driver, wait)
    
    # Проверяем, не получили ли мы пустой список позиций из-за проблем с загрузкой
    if not positions and old_positions:
        print("Получен пустой список позиций. Проверяем, не связано ли это с проблемами загрузки...")
        # Проверяем, загружена ли страница корректно
        try:
            # Пытаемся найти основные элементы страницы
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.bn-web-table"))
            )
            print("Страница загружена, но позиции не найдены. Возможно, это временная проблема.")
            # Возвращаем старые позиции, чтобы избежать ложных уведомлений
            return old_positions
        except TimeoutException:
            print("Страница не загружена корректно. Возможно, проблемы с соединением.")
            # Возвращаем старые позиции
            return old_positions
    
    if positions:
        print(f"Получено {len(positions)} позиций")
        # Сравниваем с предыдущими позициями и отправляем только новые
        return compare_and_send_new_positions(old_positions, positions, bot_token, chat_id)
    else:
        print("Не удалось получить информацию о позициях")
        # Возвращаем старые позиции, чтобы избежать ложных уведомлений
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

def login_binance():
    # Настройка опций Chrome
    options = uc.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Инициализация драйвера Chrome
    driver = None
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        print(f"Ошибка при инициализации драйвера: {str(e)}")
        print("Пробуем еще раз через 10 секунд...")
        time.sleep(10)
        try:
            driver = uc.Chrome(options=options)
        except Exception as e:
            print(f"Снова ошибка при инициализации драйвера: {str(e)}")
            print("Пробуем еще раз через 30 секунд...")
            time.sleep(30)
            driver = uc.Chrome(options=options)
    
    # Открытие страницы лидерборда
    try:
        print("Переходим на страницу профиля пользователя в лидерборде...")
        driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
        print("Успешно перешли на страницу профиля пользователя в лидерборде!")
    except WebDriverException as e:
        print(f"Ошибка при подключении к Binance: {str(e)}")
        print("Пожалуйста, включите VPN вручную и нажмите Enter, когда будете готовы...")
        input()
        try:
            driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
        except WebDriverException:
            print("Все еще не удается подключиться к Binance. Пожалуйста, проверьте VPN и нажмите Enter...")
            input()
            driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
    
    # Бесконечный цикл для повторных попыток
    while True:
        try:
            wait = WebDriverWait(driver, 20)
            
            # Проверяем, вошли ли мы в систему, ища никнейм "Botir_Nomozov"
            try:
                # Проверяем наличие никнейма
                nickname_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#dashboard-userinfo-nickname")))
                nickname_text = nickname_element.text
                
                if "Botir_Nomozov" in nickname_text:
                    print("Успешно вошли в аккаунт! Обнаружен никнейм: Botir_Nomozov")
                    
                    # Замените на свои данные
                    bot_token = "5859176664:AAEoXNcof-a92yH04l_yhk2WW7tD511kd6Y"
                    chat_id = "-1002599964439"
                    
                    # Получаем и отправляем информацию о позициях
                    positions = get_and_send_positions(driver, wait, bot_token, chat_id)
                    
                    # Запускаем цикл обновления страницы и проверки новых позиций
                    print("Запускаем цикл обновления страницы и проверки новых позиций...")
                    last_refresh_time = time.time()
                    
                    while True:
                        try:
                            current_time = time.time()
                            # Обновляем страницу каждые 7-8 секунд
                            if current_time - last_refresh_time >= random.uniform(7, 8):
                                print("Обновляем страницу...")
                                driver.refresh()
                                last_refresh_time = current_time
                                
                                # Ждем загрузки страницы
                                time.sleep(15)
                                
                                # Проверяем и обрабатываем процесс входа
                                if check_and_handle_login(driver, wait):
                                    print("Процесс входа запущен успешно")
                                else:
                                    print("Кнопка входа не найдена или процесс входа не удался")

                                # Проверяем наличие новых позиций
                                try:
                                    positions = driver.find_elements(By.CSS_SELECTOR, "div.css-1wr4jig")
                                    if positions:
                                        for position in positions:
                                            try:
                                                symbol = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                side = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                size = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                entry_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                mark_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                pnl = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                
                                                message = f"Новая позиция:\nСимвол: {symbol}\nСторона: {side}\nРазмер: {size}\nЦена входа: {entry_price}\nТекущая цена: {mark_price}\nPnL: {pnl}"
                                                send_to_telegram(bot_token, chat_id, message)
                                            except Exception as e:
                                                print(f"Ошибка при обработке позиции: {e}")
                                except Exception as e:
                                    print(f"Ошибка при поиске позиций: {e}")
                                
                                # Получаем и отправляем информацию о новых позициях
                                positions = get_and_send_positions(driver, wait, bot_token, chat_id, positions)
                            
                            # Проверяем, не разлогинились ли мы
                            try:
                                # Проверяем наличие кнопки "Log In" при каждом обновлении
                                try:
                                    login_link = driver.find_element(By.CSS_SELECTOR, "a.link.cursor-pointer.text-TextLink.no-underline[href='/login']")
                                    print("Обнаружена кнопка Log In. Нажимаем на нее...")
                                    login_link.click()
                                    
                                    # Ждем появления кнопки "Continue with Telegram"
                                    telegram_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Continue with Telegram']")))
                                    telegram_button.click()
                                    
                                    # Ждем появления кнопки "Connect" и нажимаем на нее
                                    connect_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.bn-button.bn-button__primary.data-size-large.w-full.mt-6")))
                                    connect_button.click()
                                    
                                    print("Нажали на кнопку Connect. Ждем, пока вы войдете в систему...")
                                    
                                    # Ждем 20 секунд, чтобы дать время на вход в систему
                                    time.sleep(20)
                                    
                                    # Возвращаемся на страницу лидерборда
                                    print("Возвращаемся на страницу профиля пользователя в лидерборде...")
                                    driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                                    print("Успешно вернулись на страницу профиля пользователя в лидерборде!")
                                except (NoSuchElementException, TimeoutException):
                                    # Кнопка "Log In" не найдена, продолжаем проверку никнейма
                                    pass
                                
                                nickname_element = driver.find_element(By.CSS_SELECTOR, "#dashboard-userinfo-nickname")
                                nickname_text = nickname_element.text
                                
                                if "Botir_Nomozov" not in nickname_text:
                                    print(f"Обнаружен никнейм: {nickname_text}, но это не Botir_Nomozov. Перезагружаем страницу...")
                                    driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                                    break
                                
                                # Проверяем наличие новых позиций
                                try:
                                    positions = driver.find_elements(By.CSS_SELECTOR, "div.css-1wr4jig")
                                    if positions:
                                        for position in positions:
                                            try:
                                                symbol = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                side = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                size = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                entry_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                mark_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                pnl = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                
                                                message = f"Новая позиция:\nСимвол: {symbol}\nСторона: {side}\nРазмер: {size}\nЦена входа: {entry_price}\nТекущая цена: {mark_price}\nPnL: {pnl}"
                                                send_to_telegram(bot_token, chat_id, message)
                                            except (NoSuchElementException, WebDriverException) as e:
                                                print(f"Ошибка при обработке позиции: {e}")
                                except (NoSuchElementException, WebDriverException) as e:
                                    print(f"Ошибка при поиске позиций: {e}")
                            except (NoSuchElementException, WebDriverException):
                                print("Сессия истекла или вы не вошли в систему. Перезагружаем страницу...")
                                driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                                break
                            
                            # Небольшая пауза перед следующей проверкой
                            time.sleep(1)
                            
                        except Exception as e:
                            print(f"Ошибка в цикле обновления: {str(e)}")
                            print("Пробуем перезагрузить страницу...")
                            try:
                                driver.refresh()
                            except:
                                driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                            time.sleep(15)
                else:
                    print(f"Обнаружен никнейм: {nickname_text}, но это не Botir_Nomozov. Продолжаем проверку...")
            except (TimeoutException, NoSuchElementException):
                print("Не удалось определить, вошли ли вы в систему. Продолжаем проверку...")
            
            # Держим браузер открытым
            while True:
                try:
                    # Проверяем, не разлогинились ли мы, ища никнейм
                    nickname_element = driver.find_element(By.CSS_SELECTOR, "#dashboard-userinfo-nickname")
                    nickname_text = nickname_element.text
                    
                    if "Botir_Nomozov" in nickname_text:
                        print(f"Вы все еще вошли в систему как: {nickname_text}")
                        
                        # Проверяем, находимся ли мы на странице профиля пользователя в лидерборде
                        current_url = driver.current_url
                        if "futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2" not in current_url:
                            print("Переходим на страницу профиля пользователя в лидерборде...")
                            driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                            print("Успешно перешли на страницу профиля пользователя в лидерборде!")
                            
                            # Замените на свои данные
                            bot_token = "5859176664:AAEoXNcof-a92yH04l_yhk2WW7tD511kd6Y"
                            chat_id = "-1002599964439"
                            
                            # Получаем и отправляем информацию о позициях
                            positions = get_and_send_positions(driver, wait, bot_token, chat_id)
                            
                            # Запускаем цикл обновления страницы и проверки новых позиций
                            print("Запускаем цикл обновления страницы и проверки новых позиций...")
                            last_refresh_time = time.time()
                            
                            while True:
                                try:
                                    current_time = time.time()
                                    # Обновляем страницу каждые 7-8 секунд
                                    if current_time - last_refresh_time >= random.uniform(7, 8):
                                        print("Обновляем страницу...")
                                        driver.refresh()
                                        last_refresh_time = current_time
                                        
                                        # Ждем загрузки страницы
                                        time.sleep(15)
                                        
                                        # Проверяем и обрабатываем процесс входа
                                        if check_and_handle_login(driver, wait):
                                            print("Процесс входа запущен успешно")
                                        else:
                                            print("Кнопка входа не найдена или процесс входа не удался")

                                        # Проверяем наличие новых позиций
                                        try:
                                            positions = driver.find_elements(By.CSS_SELECTOR, "div.css-1wr4jig")
                                            if positions:
                                                for position in positions:
                                                    try:
                                                        symbol = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                        side = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                        size = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                        entry_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                        mark_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                        pnl = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                        
                                                        message = f"Новая позиция:\nСимвол: {symbol}\nСторона: {side}\nРазмер: {size}\nЦена входа: {entry_price}\nТекущая цена: {mark_price}\nPnL: {pnl}"
                                                        send_to_telegram(bot_token, chat_id, message)
                                                    except Exception as e:
                                                        print(f"Ошибка при обработке позиции: {e}")
                                        except Exception as e:
                                            print(f"Ошибка при поиске позиций: {e}")
                                    
                                    # Получаем и отправляем информацию о новых позициях
                                    positions = get_and_send_positions(driver, wait, bot_token, chat_id, positions)
                                    
                                    # Проверяем, не разлогинились ли мы
                                    try:
                                        # Проверяем наличие кнопки "Log In" при каждом обновлении
                                        try:
                                            login_link = driver.find_element(By.CSS_SELECTOR, "a.link.cursor-pointer.text-TextLink.no-underline[href='/login']")
                                            print("Обнаружена кнопка Log In. Нажимаем на нее...")
                                            login_link.click()
                                            
                                            # Ждем появления кнопки "Continue with Telegram"
                                            telegram_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Continue with Telegram']")))
                                            telegram_button.click()
                                            
                                            # Ждем появления кнопки "Connect" и нажимаем на нее
                                            connect_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.bn-button.bn-button__primary.data-size-large.w-full.mt-6")))
                                            connect_button.click()
                                            
                                            print("Нажали на кнопку Connect. Ждем, пока вы войдете в систему...")
                                            
                                            # Ждем 20 секунд, чтобы дать время на вход в систему
                                            time.sleep(20)
                                            
                                            # Возвращаемся на страницу лидерборда
                                            print("Возвращаемся на страницу профиля пользователя в лидерборде...")
                                            driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                                            print("Успешно вернулись на страницу профиля пользователя в лидерборде!")
                                        except (NoSuchElementException, TimeoutException):
                                            # Кнопка "Log In" не найдена, продолжаем проверку никнейма
                                            pass
                                        
                                        nickname_element = driver.find_element(By.CSS_SELECTOR, "#dashboard-userinfo-nickname")
                                        nickname_text = nickname_element.text
                                        
                                        if "Botir_Nomozov" not in nickname_text:
                                            print(f"Обнаружен никнейм: {nickname_text}, но это не Botir_Nomozov. Перезагружаем страницу...")
                                            driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                                            break
                                    except (NoSuchElementException, WebDriverException):
                                        print("Сессия истекла или вы не вошли в систему. Перезагружаем страницу...")
                                        driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                                        break
                                    
                                    # Небольшая пауза перед следующей проверкой
                                    time.sleep(1)
                                    
                                except Exception as e:
                                    print(f"Ошибка в цикле обновления: {str(e)}")
                                    print("Пробуем перезагрузить страницу...")
                                    try:
                                        driver.refresh()
                                    except:
                                        driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                                    time.sleep(15)
                    else:
                        print(f"Обнаружен никнейм: {nickname_text}, но это не Botir_Nomozov")
                    
                    time.sleep(10)  # Проверяем каждые 10 секунд
                except (NoSuchElementException, WebDriverException):
                    print("Сессия истекла или вы не вошли в систему. Обновляем страницу...")
                    try:
                        driver.refresh()  # Обновляем страницу
                        time.sleep(15)  # Ждем загрузки страницы
                        
                        # Проверяем и обрабатываем процесс входа
                        if check_and_handle_login(driver, wait):
                            print("Процесс входа запущен успешно")
                        else:
                            print("Кнопка входа не найдена или процесс входа не удался")
                        
                        # Проверяем наличие новых позиций
                        try:
                            positions = driver.find_elements(By.CSS_SELECTOR, "div.css-1wr4jig")
                            if positions:
                                for position in positions:
                                    try:
                                        symbol = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                        side = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                        size = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                        entry_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                        mark_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                        pnl = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                        
                                        message = f"Новая позиция:\nСимвол: {symbol}\nСторона: {side}\nРазмер: {size}\nЦена входа: {entry_price}\nТекущая цена: {mark_price}\nPnL: {pnl}"
                                        send_to_telegram(bot_token, chat_id, message)
                                    except Exception as e:
                                        print(f"Ошибка при обработке позиции: {e}")
                        except Exception as e:
                            print(f"Ошибка при поиске позиций: {e}")
                    except:
                        print("Не удалось обновить страницу, пробуем загрузить заново...")
                        try:
                            driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                            
                            # Ждем загрузки страницы
                            time.sleep(15)
                            
                            # Проверяем и обрабатываем процесс входа
                            if check_and_handle_login(driver, wait):
                                print("Процесс входа запущен успешно")
                            else:
                                print("Кнопка входа не найдена или процесс входа не удался")
                            
                            # Проверяем наличие новых позиций
                            try:
                                positions = driver.find_elements(By.CSS_SELECTOR, "div.css-1wr4jig")
                                if positions:
                                    for position in positions:
                                        try:
                                            symbol = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                            side = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                            size = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                            entry_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                            mark_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                            pnl = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                            
                                            message = f"Новая позиция:\nСимвол: {symbol}\nСторона: {side}\nРазмер: {size}\nЦена входа: {entry_price}\nТекущая цена: {mark_price}\nPnL: {pnl}"
                                            send_to_telegram(bot_token, chat_id, message)
                                        except Exception as e:
                                            print(f"Ошибка при обработке позиции: {e}")
                            except Exception as e:
                                print(f"Ошибка при поиске позиций: {e}")
                        except:
                            print("Не удалось загрузить страницу. Пожалуйста, проверьте VPN и нажмите Enter...")
                            input()
                            try:
                                driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                                
                                # Ждем загрузки страницы
                                time.sleep(15)
                                
                                # Проверяем и обрабатываем процесс входа
                                if check_and_handle_login(driver, wait):
                                    print("Процесс входа запущен успешно")
                                else:
                                    print("Кнопка входа не найдена или процесс входа не удался")
                                
                                # Проверяем наличие новых позиций
                                try:
                                    positions = driver.find_elements(By.CSS_SELECTOR, "div.css-1wr4jig")
                                    if positions:
                                        for position in positions:
                                            try:
                                                symbol = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                side = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                size = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                entry_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                mark_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                pnl = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                
                                                message = f"Новая позиция:\nСимвол: {symbol}\nСторона: {side}\nРазмер: {size}\nЦена входа: {entry_price}\nТекущая цена: {mark_price}\nPnL: {pnl}"
                                                send_to_telegram(bot_token, chat_id, message)
                                            except Exception as e:
                                                print(f"Ошибка при обработке позиции: {e}")
                                except Exception as e:
                                    print(f"Ошибка при поиске позиций: {e}")
                            except:
                                print("Все еще не удается загрузить страницу. Пожалуйста, проверьте VPN и нажмите Enter...")
                                input()
                                driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                                
                                # Ждем загрузки страницы
                                time.sleep(15)
                                
                                # Проверяем и обрабатываем процесс входа
                                if check_and_handle_login(driver, wait):
                                    print("Процесс входа запущен успешно")
                                else:
                                    print("Кнопка входа не найдена или процесс входа не удался")
                                
                                # Проверяем наличие новых позиций
                                try:
                                    positions = driver.find_elements(By.CSS_SELECTOR, "div.css-1wr4jig")
                                    if positions:
                                        for position in positions:
                                            try:
                                                symbol = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                side = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                size = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                entry_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                mark_price = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                pnl = position.find_element(By.CSS_SELECTOR, "div.css-1wr4jig div.css-1wr4jig").text
                                                
                                                message = f"Новая позиция:\nСимвол: {symbol}\nСторона: {side}\nРазмер: {size}\nЦена входа: {entry_price}\nТекущая цена: {mark_price}\nPnL: {pnl}"
                                                send_to_telegram(bot_token, chat_id, message)
                                            except Exception as e:
                                                print(f"Ошибка при обработке позиции: {e}")
                                except Exception as e:
                                    print(f"Ошибка при поиске позиций: {e}")
                    time.sleep(15)  # Ждем 15 секунд перед следующей проверкой
            
        except (TimeoutException, NoSuchElementException, WebDriverException) as e:
            print(f"Произошла ошибка: {str(e)}")
            print("Обновляем страницу и пробуем снова...")
            try:
                driver.refresh()  # Обновляем страницу
            except:
                print("Не удалось обновить страницу, пробуем загрузить заново...")
                try:
                    driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                except:
                    print("Не удалось загрузить страницу. Пожалуйста, проверьте VPN и нажмите Enter...")
                    input()
                    try:
                        driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                    except:
                        print("Все еще не удается загрузить страницу. Пожалуйста, проверьте VPN и нажмите Enter...")
                        input()
                        driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
            time.sleep(15)  # Ждем 15 секунд перед следующей попыткой
        except Exception as e:
            print(f"Неожиданная ошибка: {str(e)}")
            print("Пробуем перезагрузить страницу...")
            try:
                driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
            except:
                print("Не удалось загрузить страницу. Пожалуйста, проверьте VPN и нажмите Enter...")
                input()
                try:
                    driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
                except:
                    print("Все еще не удается загрузить страницу. Пожалуйста, проверьте VPN и нажмите Enter...")
                    input()
                    driver.get('https://www.binance.com/en/futures-activity/leaderboard/user/um?encryptedUid=BC95584834876A747DCD0AE56B3EA1A2')
            time.sleep(15)  # Ждем 15 секунд перед следующей попыткой

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
