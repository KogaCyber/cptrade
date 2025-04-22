import time
import logging
from typing import Callable, Any, Optional, Type, Tuple, Union
from functools import wraps
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException
)

class RetryManager:
    """Менеджер для управления повторными попытками и обработки ошибок"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.max_retries = 3
        self.base_delay = 5
        self.max_delay = 60
        
    def exponential_backoff(self, attempt: int) -> float:
        """Вычисляет задержку с экспоненциальным ростом"""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        # Добавляем небольшую случайность для предотвращения thundering herd
        jitter = delay * 0.1
        return delay + (jitter * (0.5 - time.time() % 1))
        
    def retry_on_exception(
        self,
        exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
        max_retries: Optional[int] = None,
        on_retry: Optional[Callable[[Exception, int], None]] = None
    ) -> Callable:
        """Декоратор для повторных попыток выполнения функции при исключениях"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                retries = max_retries or self.max_retries
                last_exception = None
                
                for attempt in range(retries):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < retries - 1:
                            delay = self.exponential_backoff(attempt)
                            self.logger.warning(
                                f"❌ Попытка {attempt + 1}/{retries} не удалась: {str(e)}\n"
                                f"Повторная попытка через {delay:.1f} секунд..."
                            )
                            
                            if on_retry:
                                on_retry(e, attempt)
                                
                            time.sleep(delay)
                        else:
                            self.logger.error(
                                f"❌ Все попытки ({retries}) не удались\n"
                                f"Последняя ошибка: {str(e)}"
                            )
                            
                raise last_exception
                
            return wrapper
        return decorator
        
    def retry_on_condition(
        self,
        condition: Callable[[Any], bool],
        max_retries: Optional[int] = None,
        on_retry: Optional[Callable[[Any, int], None]] = None
    ) -> Callable:
        """Декоратор для повторных попыток выполнения функции до выполнения условия"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                retries = max_retries or self.max_retries
                last_result = None
                
                for attempt in range(retries):
                    result = func(*args, **kwargs)
                    last_result = result
                    
                    if condition(result):
                        return result
                        
                    if attempt < retries - 1:
                        delay = self.exponential_backoff(attempt)
                        self.logger.warning(
                            f"❌ Попытка {attempt + 1}/{retries} не достигла цели\n"
                            f"Повторная попытка через {delay:.1f} секунд..."
                        )
                        
                        if on_retry:
                            on_retry(result, attempt)
                            
                        time.sleep(delay)
                    else:
                        self.logger.error(
                            f"❌ Все попытки ({retries}) не достигли цели\n"
                            f"Последний результат: {last_result}"
                        )
                        
                return last_result
                
            return wrapper
        return decorator
        
    def handle_webdriver_exception(self, e: Exception, context: str) -> None:
        """Обрабатывает исключения WebDriver с подробным логированием"""
        if isinstance(e, TimeoutException):
            self.logger.error(f"❌ Таймаут при {context}: {str(e)}")
        elif isinstance(e, NoSuchElementException):
            self.logger.error(f"❌ Элемент не найден при {context}: {str(e)}")
        elif isinstance(e, StaleElementReferenceException):
            self.logger.error(f"❌ Устаревшая ссылка на элемент при {context}: {str(e)}")
        elif isinstance(e, WebDriverException):
            self.logger.error(f"❌ Ошибка WebDriver при {context}: {str(e)}")
        else:
            self.logger.error(f"❌ Неожиданная ошибка при {context}: {str(e)}")
            
    def is_critical_error(self, e: Exception) -> bool:
        """Проверяет, является ли ошибка критической"""
        critical_exceptions = (
            WebDriverException,
            TimeoutException,
            NoSuchElementException,
            StaleElementReferenceException
        )
        return isinstance(e, critical_exceptions)

# Создаем глобальный экземпляр менеджера
retry_manager = RetryManager() 