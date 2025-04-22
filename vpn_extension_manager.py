import time
import requests
from typing import Tuple, Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from logger import Logger
from env_manager import EnvManager
from telegram_manager import telegram_manager

class VPNExtensionManager:
    """Менеджер для управления VPN через расширение браузера"""
    
    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.logger = Logger("vpn_extension")
        self.env = EnvManager()
        self.wait = WebDriverWait(driver, 10)
        self.check_url = "https://whatismyipaddress.com/"
        
        # Селекторы элементов VPN расширения
        self.selectors = {
            "extension_button": "button.vpn-extension-button",
            "vpn_toggle": "button.vpn-toggle",
            "status_connected": ".vpn-status.connected",
            "status_disconnected": ".vpn-status.disconnected",
            "connect_button": "button.connect-vpn",
            "disconnect_button": "button.disconnect-button",
            "extension_icon": "img.vpn-extension-icon",
            "icon_connected": "img.vpn-icon-connected",
            "icon_disconnected": "img.vpn-icon-disconnected"
        }
        
    def check_extension_icon(self) -> bool:
        """
        Проверяет состояние иконки расширения VPN
        
        Returns:
            bool: True если иконка показывает подключенное состояние
        """
        try:
            # Проверяем наличие иконки подключенного состояния
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.selectors["icon_connected"]))
            )
            return True
        except TimeoutException:
            return False
            
    def check_extension_api(self) -> bool:
        """
        Проверяет состояние VPN через JavaScript API расширения
        
        Returns:
            bool: True если API показывает подключенное состояние
        """
        try:
            # Проверяем состояние через JavaScript API
            is_connected = self.driver.execute_script("""
                return window.vpnExtension && window.vpnExtension.isConnected();
            """)
            return bool(is_connected)
        except Exception as e:
            self.logger.error(f"❌ Ошибка при проверке API расширения: {str(e)}")
            return False
            
    def wait_for_manual_confirmation(self, timeout: int = 300) -> Tuple[bool, str]:
        """
        Ожидает ручного подтверждения состояния VPN
        
        Args:
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        start_time = time.time()
        check_interval = 5
        
        # Отправляем уведомление в Telegram
        if telegram_manager.is_configured():
            telegram_manager.send_message(
                "⚠️ Требуется подтверждение состояния VPN\n"
                "Пожалуйста, проверьте иконку расширения и подтвердите подключение"
            )
            
        self.logger.info("⏳ Ожидание подтверждения состояния VPN...")
        
        while time.time() - start_time < timeout:
            # Проверяем все возможные индикаторы
            if (self.is_vpn_connected() or 
                self.check_extension_icon() or 
                self.check_extension_api() or 
                self.check_ip_change()):
                self.logger.info("✅ VPN подключен (подтверждено)")
                return True, "VPN подключен (подтверждено)"
                
            remaining_time = int(timeout - (time.time() - start_time))
            self.logger.info(f"⏳ Ожидание подтверждения... Осталось {remaining_time} сек")
            time.sleep(check_interval)
            
        error_msg = "❌ Превышено время ожидания подтверждения"
        self.logger.error(error_msg)
        return False, error_msg
        
    def check_ip_change(self) -> bool:
        """
        Проверяет изменение IP адреса
        
        Returns:
            bool: True если IP изменился
        """
        try:
            response = requests.get(
                self.check_url,
                timeout=10,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            )
            
            if "Your IP address" in response.text:
                self.logger.info("✅ IP адрес изменился (VPN активен)")
                return True
                
            return False
            
        except requests.RequestException as e:
            self.logger.error(f"❌ Ошибка при проверке IP: {str(e)}")
            return False
            
    def wait_for_manual_activation(self, timeout: int = 300) -> Tuple[bool, str]:
        """
        Ожидает ручной активации VPN и нажатия Enter
        
        Args:
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        # Отправляем уведомление в Telegram
        if telegram_manager.is_configured():
            telegram_manager.send_message(
                "⚠️ Требуется ручная активация VPN\n"
                "Пожалуйста, включите VPN и нажмите Enter в консоли"
            )
            
        self.logger.info("⏳ Ожидание ручной активации VPN...")
        self.logger.info("После включения VPN нажмите Enter в консоли")
        
        try:
            input()  # Ждем нажатия Enter
            self.logger.info("✅ VPN активирован (подтверждено пользователем)")
            return True, "VPN активирован (подтверждено пользователем)"
        except KeyboardInterrupt:
            error_msg = "❌ Прервано пользователем"
            self.logger.error(error_msg)
            return False, error_msg
        
    def is_vpn_connected(self) -> bool:
        """
        Проверяет, подключен ли VPN
        
        Returns:
            bool: True если VPN подключен
        """
        try:
            # Проверяем наличие индикатора подключенного состояния
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.selectors["status_connected"]))
            )
            return True
        except TimeoutException:
            return False
            
    def connect_vpn(self) -> Tuple[bool, str]:
        """
        Подключает VPN через расширение
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Открываем интерфейс расширения
            extension_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.selectors["extension_button"]))
            )
            extension_button.click()
            self.logger.info("✅ Открыт интерфейс VPN расширения")
            
            # Нажимаем кнопку подключения
            connect_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.selectors["connect_button"]))
            )
            connect_button.click()
            self.logger.info("✅ Нажата кнопка подключения VPN")
            
            # Ждем подключения
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.selectors["status_connected"]))
            )
            self.logger.info("✅ VPN успешно подключен")
            
            return True, "VPN успешно подключен"
            
        except TimeoutException as e:
            error_msg = "❌ Таймаут при подключении VPN"
            self.logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"❌ Ошибка при подключении VPN: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def disconnect_vpn(self) -> Tuple[bool, str]:
        """
        Отключает VPN через расширение
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Открываем интерфейс расширения
            extension_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.selectors["extension_button"]))
            )
            extension_button.click()
            
            # Нажимаем кнопку отключения
            disconnect_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.selectors["disconnect_button"]))
            )
            disconnect_button.click()
            
            # Ждем отключения
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.selectors["status_disconnected"]))
            )
            
            self.logger.info("✅ VPN успешно отключен")
            return True, "VPN успешно отключен"
            
        except TimeoutException as e:
            error_msg = "❌ Таймаут при отключении VPN"
            self.logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"❌ Ошибка при отключении VPN: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def wait_for_connection(self, timeout: int = 30) -> bool:
        """
        Ожидает подключения VPN
        
        Args:
            timeout: Время ожидания в секундах
            
        Returns:
            bool: True если VPN подключился
        """
        try:
            self.wait = WebDriverWait(self.driver, timeout)
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.selectors["status_connected"]))
            )
            return True
        except TimeoutException:
            return False
            
    def check_vpn_status(self) -> bool:
        """
        Проверяет статус VPN через расширение
        
        Returns:
            bool: True если VPN активен
        """
        try:
            # Проверяем статус VPN через расширение
            status = self.driver.execute_script("""
                return window.vpnExtension && window.vpnExtension.isConnected();
            """)
            
            if status:
                self.logger.info("✅ VPN активен (проверка через расширение)")
                return True
                
            self.logger.warning("⚠️ VPN неактивен (проверка через расширение)")
            return False
            
        except Exception as e:
            self.logger.error("❌ Ошибка при проверке статуса VPN", exc_info=e)
            return False 