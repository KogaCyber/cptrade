import time
from typing import Callable, Any, Optional, TypeVar, Tuple
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from logger import Logger

T = TypeVar('T')

class TimeoutManager:
    def __init__(self, driver, base_timeout: int = 10, max_retries: int = 3):
        self.driver = driver
        self.base_timeout = base_timeout
        self.max_retries = max_retries
        self.logger = Logger("timeout_manager")
        
    def wait_for(self, 
                 condition: Callable[[Any], T],
                 timeout: Optional[int] = None,
                 retry_count: int = 0,
                 error_message: str = "Таймаут ожидания") -> Tuple[bool, Optional[T]]:
        """
        Ожидает выполнения условия с адаптивным таймаутом
        
        Args:
            condition: Условие для ожидания
            timeout: Базовый таймаут в секундах
            retry_count: Текущий номер попытки
            error_message: Сообщение об ошибке
            
        Returns:
            (успех, результат)
        """
        timeout = timeout or self.base_timeout
        
        try:
            # Увеличиваем таймаут с каждой попыткой
            current_timeout = timeout * (1 + retry_count * 0.5)
            self.logger.debug(f"Попытка {retry_count + 1}/{self.max_retries}, таймаут: {current_timeout}с")
            
            result = WebDriverWait(self.driver, current_timeout).until(condition)
            return True, result
            
        except TimeoutException:
            if retry_count < self.max_retries - 1:
                self.logger.warning(f"⚠️ {error_message}, повторная попытка...")
                return self.wait_for(condition, timeout, retry_count + 1, error_message)
            else:
                self.logger.error(f"❌ {error_message} после {self.max_retries} попыток")
                return False, None
                
        except StaleElementReferenceException:
            if retry_count < self.max_retries - 1:
                self.logger.warning("⚠️ Элемент устарел, повторная попытка...")
                return self.wait_for(condition, timeout, retry_count + 1, error_message)
            else:
                self.logger.error("❌ Элемент устарел после всех попыток")
                return False, None
                
        except Exception as e:
            self.logger.error(f"❌ Неожиданная ошибка: {str(e)}")
            return False, None
            
    def wait_for_page_load(self, timeout: Optional[int] = None) -> bool:
        """
        Ожидает полной загрузки страницы
        
        Args:
            timeout: Таймаут в секундах
            
        Returns:
            bool: Успех операции
        """
        def page_loaded(driver):
            return driver.execute_script("return document.readyState") == "complete"
            
        success, _ = self.wait_for(
            page_loaded,
            timeout,
            error_message="Таймаут загрузки страницы"
        )
        return success
        
    def wait_for_element_presence(self, by, value, timeout: Optional[int] = None) -> Tuple[bool, Any]:
        """
        Ожидает появления элемента
        
        Args:
            by: Тип локатора
            value: Значение локатора
            timeout: Таймаут в секундах
            
        Returns:
            (успех, элемент)
        """
        return self.wait_for(
            EC.presence_of_element_located((by, value)),
            timeout,
            error_message=f"Элемент не найден: {value}"
        )
        
    def wait_for_element_clickable(self, by, value, timeout: Optional[int] = None) -> Tuple[bool, Any]:
        """
        Ожидает кликабельности элемента
        
        Args:
            by: Тип локатора
            value: Значение локатора
            timeout: Таймаут в секундах
            
        Returns:
            (успех, элемент)
        """
        return self.wait_for(
            EC.element_to_be_clickable((by, value)),
            timeout,
            error_message=f"Элемент не кликабелен: {value}"
        )
        
    def wait_for_url_contains(self, url_part: str, timeout: Optional[int] = None) -> bool:
        """
        Ожидает изменения URL
        
        Args:
            url_part: Часть URL для проверки
            timeout: Таймаут в секундах
            
        Returns:
            bool: Успех операции
        """
        def url_changed(driver):
            return url_part in driver.current_url
            
        success, _ = self.wait_for(
            url_changed,
            timeout,
            error_message=f"URL не содержит: {url_part}"
        )
        return success
        
    def wait_for_ajax(self, timeout: Optional[int] = None) -> bool:
        """
        Ожидает завершения AJAX-запросов
        
        Args:
            timeout: Таймаут в секундах
            
        Returns:
            bool: Успех операции
        """
        def ajax_complete(driver):
            return driver.execute_script("return jQuery.active == 0")
            
        success, _ = self.wait_for(
            ajax_complete,
            timeout,
            error_message="Таймаут AJAX-запросов"
        )
        return success 