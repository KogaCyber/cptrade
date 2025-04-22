import json
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException
import time
from typing import Optional, Tuple, List, Dict
from logger import Logger
from credentials_manager import CredentialsManager
from timeout_manager import TimeoutManager
from selenium.webdriver.remote.webdriver import WebDriver
from retry_manager import retry_manager
from telegram_manager import TelegramManager

class AuthManager:
    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.logger = Logger("auth_manager")
        self.timeout_manager = TimeoutManager(driver)
        self.credentials_manager = CredentialsManager()
        self.selectors = self._load_selectors()
        self.wait = WebDriverWait(driver, 10)
        
    def _load_selectors(self) -> Dict:
        """Загружает селекторы из файла конфигурации"""
        try:
            with open('selectors.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning("⚠️ Файл селекторов не найден, используются значения по умолчанию")
            return {
                "login": {
                    "email_input": ["input[type='email']"],
                    "password_input": ["input[type='password']"],
                    "submit_button": ["button[type='submit']"],
                    "2fa_input": ["input[type='text']"],
                    "2fa_submit": ["button[type='submit']"]
                },
                "dashboard": {
                    "container": [".dashboard-container"],
                    "logout_button": [".logout-button"],
                    "confirm_logout": [".confirm-logout"]
                }
            }
            
    def _find_element(self, selectors: List[str], timeout: int = 10) -> Optional[Tuple[By, str]]:
        """
        Находит элемент по списку селекторов
        
        Args:
            selectors: Список селекторов для поиска
            timeout: Время ожидания в секундах
            
        Returns:
            (тип локатора, селектор) или None
        """
        for selector in selectors:
            try:
                # Определяем тип селектора
                if selector.startswith('#'):
                    by = By.ID
                    selector = selector[1:]
                elif selector.startswith('.'):
                    by = By.CLASS_NAME
                    selector = selector[1:]
                elif ':contains(' in selector:
                    # Специальная обработка для поиска по тексту
                    text = selector.split(':contains(')[1].rstrip(')')
                    by = By.XPATH
                    selector = f"//*[contains(text(), '{text}')]"
                else:
                    by = By.CSS_SELECTOR
                    
                # Пробуем найти элемент
                success, element = self.timeout_manager.wait_for_element_presence(by, selector, timeout)
                if success:
                    return by, selector
                    
            except Exception:
                continue
                
        return None
        
    def _wait_for_element(self, selectors: List[str], timeout: int = 10) -> Optional[Tuple[By, str]]:
        """
        Ждет появления элемента по списку селекторов
        
        Args:
            selectors: Список селекторов для поиска
            timeout: Время ожидания в секундах
            
        Returns:
            (тип локатора, селектор) или None
        """
        try:
            return self._find_element(selectors, timeout)
        except Exception as e:
            self.logger.error("❌ Ошибка при ожидании элемента", exc_info=e)
            return None
            
    def _click_element(self, selectors: List[str], timeout: int = 10) -> bool:
        """
        Находит и кликает по элементу
        
        Args:
            selectors: Список селекторов для поиска
            timeout: Время ожидания в секундах
            
        Returns:
            bool: Успех операции
        """
        try:
            result = self._find_element(selectors, timeout)
            if not result:
                return False
                
            by, selector = result
            success, element = self.timeout_manager.wait_for_element_clickable(by, selector, timeout)
            if success:
                element.click()
                return True
            return False
            
        except Exception as e:
            self.logger.error("❌ Ошибка при клике по элементу", exc_info=e)
            return False
            
    def login(self) -> Tuple[bool, str]:
        """
        Выполняет вход в аккаунт Binance и проверяет авторизацию
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Переходим на страницу логина
            self.driver.get("https://accounts.binance.com/en/login")
            self.logger.info("🌐 Переход на страницу логина Binance")
            
            # Ждем загрузки страницы
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Выполняем вход через Telegram
            success, message = self.login_via_telegram()
            if not success:
                return False, message
                
            # Ждем завершения авторизации
            success, message = self._wait_for_login_completion()
            if not success:
                return False, message
                
            # Проверяем авторизацию после первого входа
            success, message = self.check_auth_after_login()
            if not success:
                return False, message
                
            return True, "Авторизация успешно завершена и проверена"
            
        except Exception as e:
            self.logger.error("❌ Ошибка при входе в аккаунт", exc_info=e)
            return False, f"Ошибка при входе в аккаунт: {str(e)}"
            
    def wait_for_2fa(self, timeout: int = 300) -> bool:
        """
        Ожидает завершения 2FA
        
        Args:
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            bool: Успех операции
        """
        try:
            return self.timeout_manager.wait_for_url_contains("dashboard", timeout)
        except Exception as e:
            self.logger.error("❌ Ошибка при ожидании 2FA", exc_info=e)
            return False
            
    def is_logged_in(self) -> bool:
        """
        Проверяет, выполнен ли вход
        
        Returns:
            bool: True если выполнен вход
        """
        try:
            # Проверяем наличие элементов дашборда
            result = self._find_element(self.selectors["dashboard"]["container"], timeout=5)
            return result is not None
        except Exception as e:
            self.logger.error("❌ Ошибка при проверке статуса входа", exc_info=e)
            return False
            
    def logout(self) -> bool:
        """
        Выполняет выход из системы
        
        Returns:
            bool: Успех операции
        """
        try:
            # Находим и нажимаем кнопку выхода
            if not self._click_element(self.selectors["dashboard"]["logout_button"]):
                return False
                
            # Ждем и нажимаем кнопку подтверждения
            if not self._click_element(self.selectors["dashboard"]["confirm_logout"]):
                return False
                
            # Ждем выхода
            return self.timeout_manager.wait_for_url_contains("login", timeout=10)
            
        except Exception as e:
            self.logger.error("❌ Ошибка при выходе", exc_info=e)
            return False
            
    def set_credentials(self, email: str, password: str) -> None:
        """Установка учетных данных"""
        self.credentials_manager.set_credentials(email, password)
        self._save_credentials()
        
    def wait_for_2fa(self, timeout: int = 300) -> bool:
        """
        Ожидание завершения 2FA пользователем
        timeout: время ожидания в секундах
        """
        try:
            # Ждем, пока элемент 2FA исчезнет или появится элемент авторизованного состояния
            WebDriverWait(self.driver, timeout).until(
                lambda driver: self.is_logged_in() or 
                not driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
            )
            return self.is_logged_in()
        except TimeoutException:
            return False 

    @retry_manager.retry_on_exception(
        exceptions=(TimeoutException, NoSuchElementException, StaleElementReferenceException),
        max_retries=3
    )
    def login_via_telegram(self) -> Tuple[bool, str]:
        """
        Выполняет вход через Telegram
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Шаг 1: Нажимаем кнопку "Continue with Telegram"
            telegram_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Continue with Telegram']"))
            )
            telegram_button.click()
            self.logger.info("✅ Нажата кнопка 'Continue with Telegram'")
            
            # Шаг 2: Ждем появления кнопки "Connect" и нажимаем её
            connect_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Connect']"))
            )
            connect_button.click()
            self.logger.info("✅ Нажата кнопка 'Connect'")
            
            # Шаг 3: Ждем 30 секунд для получения сообщения в Telegram
            self.logger.info("⏳ Ожидание сообщения в Telegram (30 секунд)...")
            time.sleep(30)
            
            # Шаг 4: Проверяем наличие кнопки "Resend" и нажимаем её если нужно
            try:
                resend_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Resend']"))
                )
                resend_button.click()
                self.logger.info("✅ Нажата кнопка 'Resend'")
                time.sleep(30)  # Ждем еще 30 секунд
            except TimeoutException:
                self.logger.info("ℹ️ Кнопка 'Resend' не найдена, продолжаем...")
            
            # Шаг 5: Ждем появления чекбокса "Don't show this message again"
            try:
                checkbox = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@role='checkbox' and contains(@class, 'stay-signed-in-checkbox')]"))
                )
                checkbox.click()
                self.logger.info("✅ Отмечен чекбокс 'Don't show this message again'")
            except TimeoutException:
                self.logger.warning("⚠️ Чекбокс 'Don't show this message again' не найден")
            
            # Шаг 6: Ждем появления кнопки "Yes" и нажимаем её
            try:
                yes_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Yes']"))
                )
                yes_button.click()
                self.logger.info("✅ Нажата кнопка 'Yes'")
            except TimeoutException:
                self.logger.warning("⚠️ Кнопка 'Yes' не найдена")
            
            # Шаг 7: Ждем завершения аутентификации
            success, message = self._wait_for_login_completion()
            if success:
                self.logger.info("✅ Успешный вход через Telegram")
                return True, "Вход выполнен успешно"
            else:
                self.logger.warning(f"❌ Ошибка входа: {message}")
                return False, message
                
        except Exception as e:
            self.logger.error("❌ Ошибка при входе через Telegram", exc_info=e)
            return False, f"Ошибка при входе: {str(e)}"
            
    def _wait_for_login_completion(self, timeout: int = 300) -> Tuple[bool, str]:
        """
        Ожидает завершения процесса входа
        
        Args:
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Ждем, пока URL изменится на дашборд или появится элемент с никнеймом
            WebDriverWait(self.driver, timeout).until(
                lambda driver: (
                    "dashboard" in driver.current_url or
                    len(driver.find_elements(By.CSS_SELECTOR, "#dashboard-userinfo-nickname")) > 0 or
                    len(driver.find_elements(By.XPATH, "//div[contains(@class, 'dashboard-userinfo-nickname')]")) > 0
                )
            )
            
            # Проверяем наличие элемента с никнеймом
            try:
                nickname_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#dashboard-userinfo-nickname"))
                )
                nickname = nickname_element.text
                self.logger.info(f"✅ Пользователь авторизован: {nickname}")
                return True, f"Пользователь авторизован: {nickname}"
            except TimeoutException:
                # Если не нашли по ID, пробуем найти по классу
                try:
                    nickname_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'dashboard-userinfo-nickname')]"))
                    )
                    nickname = nickname_element.text
                    self.logger.info(f"✅ Пользователь авторизован: {nickname}")
                    return True, f"Пользователь авторизован: {nickname}"
                except TimeoutException:
                    self.logger.error("❌ Не удалось найти элемент с никнеймом пользователя")
                    return False, "Не удалось найти элемент с никнеймом пользователя"
                    
        except TimeoutException:
            self.logger.error("❌ Таймаут ожидания завершения входа")
            return False, "Таймаут ожидания завершения входа"
            
        except Exception as e:
            self.logger.error("❌ Ошибка при ожидании завершения входа", exc_info=e)
            return False, f"Ошибка при ожидании завершения входа: {str(e)}"
            
    def _is_2fa_required(self) -> bool:
        """
        Проверяет, требуется ли 2FA
        
        Returns:
            bool: True если требуется 2FA
        """
        try:
            # Проверяем наличие поля ввода 2FA
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
            )
            return True
        except TimeoutException:
            return False
            
    def _handle_2fa(self) -> Tuple[bool, str]:
        """
        Обрабатывает 2FA
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Ждем ввода 2FA пользователем
            WebDriverWait(self.driver, 300).until(
                lambda driver: not self._is_2fa_required()
            )
            return True, "2FA успешно пройден"
        except TimeoutException:
            return False, "Таймаут ожидания 2FA"
            
    def wait_for_2fa(self, timeout: int = 300) -> bool:
        """
        Ждет завершения 2FA
        
        Args:
            timeout: Время ожидания в секундах
            
        Returns:
            bool: True если 2FA успешно завершен
        """
        try:
            # Ждем исчезновения поля ввода 2FA
            WebDriverWait(self.driver, timeout).until(
                lambda driver: not self._is_2fa_required()
            )
            return True
        except TimeoutException:
            return False 

    def find_and_click_telegram_button(self) -> Tuple[bool, str]:
        """
        Ищет и нажимает кнопку "Continue with Telegram" на странице логина
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Обновляем страницу перед каждой попыткой
                self.driver.refresh()
                self.logger.info(f"🔄 Попытка {attempt + 1}/{max_attempts}: Обновление страницы")
                
                # Ждем появления кнопки Telegram
                telegram_button = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        "//button[@aria-label='Continue with Telegram']"
                    ))
                )
                
                # Проверяем, что кнопка кликабельна
                WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//button[@aria-label='Continue with Telegram']"
                    ))
                )
                
                # Нажимаем на кнопку
                telegram_button.click()
                self.logger.info("✅ Нажата кнопка 'Continue with Telegram'")
                return True, "Кнопка Telegram успешно нажата"
                
            except TimeoutException:
                self.logger.warning(f"⚠️ Попытка {attempt + 1}/{max_attempts}: Кнопка Telegram не найдена")
                if attempt < max_attempts - 1:
                    time.sleep(2)  # Небольшая пауза перед следующей попыткой
                continue
                
            except Exception as e:
                self.logger.error(f"❌ Попытка {attempt + 1}/{max_attempts}: Ошибка при нажатии кнопки Telegram", exc_info=e)
                if attempt < max_attempts - 1:
                    time.sleep(2)
                continue
                
        return False, "Не удалось найти или нажать кнопку Telegram после всех попыток" 

    def find_and_click_connect_button(self) -> Tuple[bool, str]:
        """
        Ищет и нажимает кнопку "Connect" после нажатия кнопки Telegram
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Ждем появления кнопки Connect
            connect_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "//button[@aria-label='Connect' and contains(@class, 'bn-button__primary')]"
                ))
            )
            
            # Проверяем, что кнопка кликабельна
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[@aria-label='Connect' and contains(@class, 'bn-button__primary')]"
                ))
            )
            
            # Нажимаем на кнопку
            connect_button.click()
            self.logger.info("✅ Нажата кнопка 'Connect'")
            return True, "Кнопка Connect успешно нажата"
            
        except TimeoutException:
            self.logger.error("❌ Кнопка Connect не найдена или не кликабельна")
            return False, "Кнопка Connect не найдена или не кликабельна"
            
        except Exception as e:
            self.logger.error("❌ Ошибка при нажатии кнопки Connect", exc_info=e)
            return False, f"Ошибка при нажатии кнопки Connect: {str(e)}"
            
    def wait_for_manual_auth(self, timeout: int = 300) -> Tuple[bool, str]:
        """
        Ожидает ручной авторизации через Telegram и Binance
        
        Args:
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Отправляем уведомление в Telegram
            telegram_manager = TelegramManager()
            if telegram_manager.is_configured():
                telegram_manager.send_message(
                    "⚠️ Требуется ручная авторизация\n"
                    "Пожалуйста, авторизуйтесь через Telegram и Binance\n"
                    "После завершения авторизации нажмите Enter в консоли"
                )
                
            self.logger.info("⏳ Ожидание ручной авторизации...")
            self.logger.info("⚠️ После завершения авторизации нажмите Enter в консоли")
            
            # Ждем нажатия Enter пользователем
            input("Нажмите Enter после завершения авторизации...")
            
            self.logger.info("✅ Пользователь подтвердил завершение авторизации")
            return True, "Авторизация успешно завершена пользователем"
            
        except Exception as e:
            self.logger.error("❌ Ошибка при ожидании авторизации", exc_info=e)
            return False, f"Ошибка при ожидании авторизации: {str(e)}"
            
    def wait_for_username(self, timeout: int = 30) -> Tuple[bool, str]:
        """
        Ожидает появления никнейма пользователя на странице
        
        Args:
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Ждем появления элемента с никнеймом (пробуем разные селекторы)
            selectors = [
                (By.ID, "dashboard-userinfo-nickname"),
                (By.CSS_SELECTOR, ".dashboard-userinfo-nickname"),
                (By.XPATH, "//div[contains(@class, 'dashboard-userinfo-nickname')]"),
                (By.XPATH, "//div[contains(@class, 't-headline5') and contains(@class, 'mb-2')]")
            ]
            
            username_element = None
            for by, selector in selectors:
                try:
                    username_element = WebDriverWait(self.driver, timeout/len(selectors)).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if username_element:
                        break
                except:
                    continue
                    
            if not username_element:
                # Если не нашли по селекторам, попробуем найти по тексту
                try:
                    username_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((
                            By.XPATH,
                            "//div[contains(text(), 'Botir_Nomozov')]"
                        ))
                    )
                except:
                    pass
                    
            if not username_element:
                self.logger.error("❌ Не удалось найти элемент с никнеймом пользователя")
                return False, "Не удалось найти элемент с никнеймом пользователя"
                
            # Получаем никнейм
            username = username_element.text
            self.logger.info(f"✅ Пользователь авторизован: {username}")
            return True, f"Пользователь авторизован: {username}"
            
        except TimeoutException:
            self.logger.error("❌ Таймаут ожидания никнейма пользователя")
            return False, "Таймаут ожидания никнейма пользователя"
            
        except Exception as e:
            self.logger.error("❌ Ошибка при ожидании никнейма пользователя", exc_info=e)
            return False, f"Ошибка при ожидании никнейма пользователя: {str(e)}"
            
    def check_auth_after_login(self) -> Tuple[bool, str]:
        """Проверка авторизации после входа"""
        try:
            # Ждем 30 секунд после первого входа
            self.logger.info("⏳ Ожидание 30 секунд после первого входа...")
            time.sleep(30)
            
            # Переходим на страницу логина
            self.logger.info("🌐 Переход на страницу логина...")
            self.driver.get("https://accounts.binance.com/en/login")
            
            # Ждем загрузки страницы
            if not self.timeout_manager.wait_for_page_load():
                return False, "Ошибка загрузки страницы логина"
                
            # Нажимаем кнопку "Continue with Telegram"
            self.logger.info("🔘 Нажатие кнопки 'Continue with Telegram'...")
            try:
                telegram_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.bn-button.bn-button__icon.bn-button__icon__line.data-size-large.icon-button.mt-4"))
                )
                telegram_button.click()
            except Exception as e:
                self.logger.error(f"❌ Ошибка при нажатии кнопки Telegram: {str(e)}")
                return False, "Ошибка при нажатии кнопки Telegram"
                
            # Нажимаем кнопку "Connect"
            self.logger.info("🔘 Нажатие кнопки 'Connect'...")
            try:
                connect_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.bn-button.bn-button__primary.data-size-large.w-full.mt-6"))
                )
                connect_button.click()
            except Exception as e:
                self.logger.error(f"❌ Ошибка при нажатии кнопки Connect: {str(e)}")
                return False, "Ошибка при нажатии кнопки Connect"
                
            # Ждем 30 секунд для получения сообщения в Telegram
            self.logger.info("⏳ Ожидание сообщения в Telegram...")
            time.sleep(30)
            
            # Бесконечный цикл для нажатия кнопки Resend
            while True:
                try:
                    # Проверяем наличие кнопки "Resend"
                    self.logger.info("🔍 Поиск кнопки 'Resend'...")
                    try:
                        # Пробуем найти кнопку по разным селекторам
                        selectors = [
                            (By.CSS_SELECTOR, "div.bn-mfa-modal button.bn-button.bn-button__primary.data-size-large.bn-mfa-roaming-button"),
                            (By.XPATH, "//div[contains(@class, 'bn-mfa-modal')]//button[@aria-label='Resend']"),
                            (By.CSS_SELECTOR, "div.bn-mfa-modal button[aria-label='Resend']"),
                            (By.CSS_SELECTOR, "div.bn-mfa-modal button.bn-mfa-roaming-button")
                        ]
                        
                        resend_button = None
                        for by, selector in selectors:
                            try:
                                self.logger.info(f"🔍 Пробуем найти кнопку по селектору: {selector}")
                                resend_button = WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_element_located((by, selector))
                                )
                                if resend_button:
                                    self.logger.info(f"✅ Кнопка найдена по селектору: {selector}")
                                    break
                            except TimeoutException:
                                self.logger.info(f"ℹ️ Кнопка не найдена по селектору: {selector}")
                                continue
                                
                        if not resend_button:
                            self.logger.error("❌ Кнопка 'Resend' не найдена ни по одному селектору")
                            # Проверяем, есть ли другие элементы на странице
                            try:
                                elements = self.driver.find_elements(By.TAG_NAME, "button")
                                self.logger.info(f"ℹ️ Найдено {len(elements)} кнопок на странице")
                                for element in elements:
                                    self.logger.info(f"ℹ️ Кнопка: {element.get_attribute('outerHTML')}")
                            except Exception as e:
                                self.logger.error(f"❌ Ошибка при проверке кнопок: {str(e)}")
                            raise TimeoutException("Кнопка 'Resend' не найдена")
                            
                        # Нажимаем кнопку Resend
                        self.logger.info("🔘 Нажатие кнопки 'Resend'...")
                        resend_button.click()
                        
                        # Отправляем сообщение в Telegram
                        telegram_manager = TelegramManager()
                        if telegram_manager.is_configured():
                            telegram_manager.send_message("⚠️ Пожалуйста, подтвердите вход в Binance")
                        
                        # Ждем 30 секунд перед следующей попыткой
                        self.logger.info("⏳ Ожидание 30 секунд перед следующей попыткой...")
                        time.sleep(30)
                        
                    except TimeoutException:
                        # Если кнопка Resend не найдена, проверяем наличие следующих шагов
                        try:
                            # Проверяем наличие чекбокса "Don't show this message again"
                            checkbox = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='checkbox']"))
                            )
                            if checkbox.is_displayed() and checkbox.is_enabled():
                                self.logger.info("✅ Найден чекбокс 'Don't show this message again'")
                                checkbox.click()
                                break
                        except TimeoutException:
                            pass
                            
                        try:
                            # Проверяем наличие кнопки "Yes"
                            yes_button = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-testid='yes-button']"))
                            )
                            if yes_button.is_displayed() and yes_button.is_enabled():
                                self.logger.info("✅ Найдена кнопка 'Yes'")
                                yes_button.click()
                                break
                        except TimeoutException:
                            pass
                            
                        # Если ни один из следующих шагов не найден, продолжаем цикл
                        self.logger.info("ℹ️ Кнопка 'Resend' не найдена, продолжаем поиск...")
                        time.sleep(5)
                        
                except Exception as e:
                    self.logger.error(f"❌ Ошибка при работе с кнопкой Resend: {str(e)}")
                    time.sleep(5)
                    
            # Ждем завершения авторизации
            self.logger.info("⏳ Ожидание завершения авторизации...")
            try:
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#dashboard-userinfo-nickname"))
                )
                self.logger.info("✅ Авторизация успешно завершена")
                return True, "Авторизация успешно завершена"
            except TimeoutException:
                self.logger.error("❌ Таймаут при ожидании завершения авторизации")
                return False, "Таймаут при ожидании завершения авторизации"
            except Exception as e:
                self.logger.error(f"❌ Ошибка при ожидании завершения авторизации: {str(e)}")
                return False, "Ошибка при ожидании завершения авторизации"
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка при проверке авторизации: {str(e)}")
            return False, f"Ошибка при проверке авторизации: {str(e)}" 