import time
from typing import List, Tuple, Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)
from logger import Logger
from retry_manager import retry_manager

class PageManager:
    """Менеджер для управления страницей и ожидания элементов"""
    
    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.logger = Logger("page_manager")
        self.wait = WebDriverWait(driver, 10)
        
    @retry_manager.retry_on_exception(
        exceptions=(TimeoutException, NoSuchElementException, StaleElementReferenceException),
        max_retries=3
    )
    def refresh_and_wait_for_element(
        self,
        element_selector: str,
        max_retries: int = 3,
        wait_time: int = 6,
        thread_id: int = 1
    ) -> Tuple[bool, str]:
        """
        Обновляет страницу и ждет появления элемента
        
        Args:
            element_selector: CSS селектор элемента
            max_retries: Максимальное количество попыток
            wait_time: Время ожидания в секундах
            thread_id: ID потока
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        for attempt in range(max_retries):
            try:
                # Обновляем страницу
                self.driver.refresh()
                self.logger.log_page_refresh(thread_id, True)
                
                # Ждем загрузки страницы
                if not self.wait_for_page_load():
                    raise TimeoutException("Страница не загрузилась")
                    
                # Проверяем наличие текста "Log In"
                if self.is_login_text_present():
                    self.logger.warning("⚠️ Обнаружен текст 'Log In', требуется повторная попытка")
                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        continue
                    return False, "Обнаружен текст 'Log In' после всех попыток"
                    
                # Ждем появления элемента
                element = WebDriverWait(self.driver, wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, element_selector))
                )
                
                self.logger.log_element_wait(element_selector, True)
                return True, "Элемент успешно найден"
                
            except TimeoutException as e:
                self.logger.log_retry("ожидания элемента", attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                else:
                    return False, f"Таймаут ожидания элемента: {str(e)}"
                    
            except Exception as e:
                self.logger.error(f"❌ Ошибка при обновлении страницы", exc_info=e)
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                else:
                    return False, f"Неожиданная ошибка: {str(e)}"
                    
        return False, "Превышено максимальное количество попыток"
        
    def wait_for_elements(
        self,
        element_selectors: List[str],
        wait_time: int = 6
    ) -> Tuple[bool, List[str]]:
        """
        Ждет появления всех указанных элементов
        
        Args:
            element_selectors: Список CSS селекторов элементов
            wait_time: Время ожидания в секундах
            
        Returns:
            Tuple[bool, List[str]]: (успех, список отсутствующих элементов)
        """
        missing_elements = []
        
        for selector in element_selectors:
            try:
                WebDriverWait(self.driver, wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                self.logger.log_element_wait(selector, True)
            except TimeoutException:
                self.logger.log_element_wait(selector, False)
                missing_elements.append(selector)
                
        return len(missing_elements) == 0, missing_elements
        
    def is_element_present(self, selector: str, timeout: int = 5) -> bool:
        """
        Проверяет наличие элемента на странице
        
        Args:
            selector: CSS селектор элемента
            timeout: Время ожидания в секундах
            
        Returns:
            bool: True если элемент найден
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return True
        except TimeoutException:
            return False
            
    def wait_for_element_clickable(
        self,
        selector: str,
        timeout: int = 10
    ) -> Optional[bool]:
        """
        Ждет пока элемент станет кликабельным
        
        Args:
            selector: CSS селектор элемента
            timeout: Время ожидания в секундах
            
        Returns:
            Optional[bool]: True если элемент кликабелен, None при ошибке
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            return True
        except TimeoutException:
            return False
        except Exception as e:
            self.logger.error(f"❌ Ошибка при ожидании кликабельности элемента {selector}", exc_info=e)
            return None
            
    def wait_for_page_load(self, timeout: int = 10) -> bool:
        """
        Ждет полной загрузки страницы
        
        Args:
            timeout: Время ожидания в секундах
            
        Returns:
            bool: True если страница загружена
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            return True
        except TimeoutException:
            return False
            
    def is_login_text_present(self) -> bool:
        """
        Проверяет наличие текста "Log In" на странице
        
        Returns:
            bool: True если текст найден
        """
        try:
            login_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Log In')]")
            return len(login_elements) > 0
        except Exception:
            return False 