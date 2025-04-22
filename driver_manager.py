import threading
import time
from typing import Dict, Optional, Any
from selenium.webdriver.remote.webdriver import WebDriver
from logger import Logger
from retry_manager import retry_manager

class DriverManager:
    """Менеджер для управления WebDriver с поддержкой потокобезопасности"""
    
    def __init__(self):
        self.logger = Logger("driver_manager")
        self._drivers: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._cleanup_thread = None
        self._stop_cleanup = threading.Event()
        
    def register_driver(self, thread_id: int, driver: WebDriver) -> None:
        """Регистрирует новый драйвер с потокобезопасностью"""
        with self._lock:
            self._drivers[thread_id] = {
                'driver': driver,
                'alive': True,
                'last_active': time.time()
            }
            self.logger.info(f"✅ Драйвер зарегистрирован для потока {thread_id}")
            
            # Запускаем поток очистки если он еще не запущен
            if not self._cleanup_thread or not self._cleanup_thread.is_alive():
                self._start_cleanup_thread()
                
    def get_driver(self, thread_id: int) -> Optional[WebDriver]:
        """Получает драйвер по ID потока с потокобезопасностью"""
        with self._lock:
            driver_info = self._drivers.get(thread_id)
            if driver_info and driver_info['alive']:
                driver_info['last_active'] = time.time()
                return driver_info['driver']
            return None
            
    def get_active_drivers(self) -> Dict[int, Dict[str, Any]]:
        """Получает информацию о всех активных драйверах с потокобезопасностью"""
        with self._lock:
            return {
                thread_id: {
                    'alive': info['alive'],
                    'last_active': info['last_active']
                }
                for thread_id, info in self._drivers.items()
            }
            
    def update_activity(self, thread_id: int) -> None:
        """Обновляет время последней активности драйвера с потокобезопасностью"""
        with self._lock:
            if thread_id in self._drivers:
                self._drivers[thread_id]['last_active'] = time.time()
                
    def mark_driver_dead(self, thread_id: int) -> None:
        """Помечает драйвер как неактивный с потокобезопасностью"""
        with self._lock:
            if thread_id in self._drivers:
                self._drivers[thread_id]['alive'] = False
                self.logger.info(f"❌ Драйвер помечен как неактивный для потока {thread_id}")
                
    def remove_driver(self, thread_id: int) -> None:
        """Удаляет драйвер с потокобезопасностью"""
        with self._lock:
            if thread_id in self._drivers:
                try:
                    driver = self._drivers[thread_id]['driver']
                    driver.quit()
                except Exception as e:
                    self.logger.error(f"❌ Ошибка при закрытии драйвера {thread_id}", exc_info=e)
                finally:
                    del self._drivers[thread_id]
                    self.logger.info(f"✅ Драйвер удален для потока {thread_id}")
                    
    def _start_cleanup_thread(self) -> None:
        """Запускает поток очистки неактивных драйверов"""
        self._stop_cleanup.clear()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop)
        self._cleanup_thread.daemon = True
        self._cleanup_thread.start()
        
    def _cleanup_loop(self) -> None:
        """Цикл очистки неактивных драйверов"""
        while not self._stop_cleanup.is_set():
            try:
                self._cleanup_inactive_drivers()
                time.sleep(60)  # Проверяем каждую минуту
            except Exception as e:
                self.logger.error("❌ Ошибка в цикле очистки драйверов", exc_info=e)
                
    def _cleanup_inactive_drivers(self) -> None:
        """Очищает неактивные драйверы с потокобезопасностью"""
        current_time = time.time()
        with self._lock:
            inactive_threads = [
                thread_id for thread_id, info in self._drivers.items()
                if not info['alive'] or (current_time - info['last_active']) > 300  # 5 минут
            ]
            
            for thread_id in inactive_threads:
                self.logger.warning(f"🧹 Очистка неактивного драйвера {thread_id}")
                self.remove_driver(thread_id)
                
    def cleanup_all(self) -> None:
        """Очищает все драйверы и останавливает поток очистки"""
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
            
        with self._lock:
            thread_ids = list(self._drivers.keys())
            for thread_id in thread_ids:
                self.remove_driver(thread_id)
                
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_all()

# Создаем глобальный экземпляр менеджера
driver_manager = DriverManager() 