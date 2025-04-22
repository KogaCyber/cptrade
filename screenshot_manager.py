import os
import time
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from logger import Logger
from env_manager import EnvManager

class ScreenshotManager:
    """Менеджер для создания и сохранения скриншотов"""
    
    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.logger = Logger("screenshot_manager")
        self.env = EnvManager()
        self.screenshots_dir = "screenshots"
        self._ensure_screenshots_dir()
        
    def _ensure_screenshots_dir(self) -> None:
        """Создает директорию для скриншотов если она не существует"""
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir)
            self.logger.info(f"✅ Создана директория {self.screenshots_dir}")
            
    def take_screenshot(self, thread_id: int) -> Optional[str]:
        """
        Создает скриншот текущего окна браузера
        
        Args:
            thread_id: ID потока для именования файла
            
        Returns:
            Optional[str]: Путь к сохраненному скриншоту или None в случае ошибки
        """
        try:
            # Устанавливаем размер окна
            self.driver.set_window_size(1920, 1080)
            
            # Ждем загрузки страницы
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Создаем имя файла с временной меткой
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_thread_{thread_id}_{timestamp}.png"
            filepath = os.path.join(self.screenshots_dir, filename)
            
            # Делаем скриншот
            self.driver.save_screenshot(filepath)
            self.logger.info(f"✅ Скриншот сохранен: {filepath}")
            
            return filepath
            
        except TimeoutException:
            self.logger.error("❌ Таймаут при ожидании загрузки страницы")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при создании скриншота: {str(e)}")
            return None
            
    def take_element_screenshot(self, element_selector: str, thread_id: int) -> Optional[str]:
        """
        Создает скриншот конкретного элемента
        
        Args:
            element_selector: CSS селектор элемента
            thread_id: ID потока для именования файла
            
        Returns:
            Optional[str]: Путь к сохраненному скриншоту или None в случае ошибки
        """
        try:
            # Ждем появления элемента
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, element_selector))
            )
            
            # Создаем имя файла с временной меткой
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"element_screenshot_thread_{thread_id}_{timestamp}.png"
            filepath = os.path.join(self.screenshots_dir, filename)
            
            # Делаем скриншот элемента
            element.screenshot(filepath)
            self.logger.info(f"✅ Скриншот элемента сохранен: {filepath}")
            
            return filepath
            
        except TimeoutException:
            self.logger.error(f"❌ Таймаут при ожидании элемента: {element_selector}")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при создании скриншота элемента: {str(e)}")
            return None 