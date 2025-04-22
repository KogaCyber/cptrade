import logging
import os
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler

class Logger:
    """Расширенный класс для логирования с поддержкой ротации файлов и форматирования"""
    
    def __init__(
        self,
        name: str,
        log_dir: str = "logs",
        max_bytes: int = 10_485_760,  # 10MB
        backup_count: int = 5,
        level: int = logging.INFO
    ):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Создаем директорию для логов если её нет
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Форматирование логов
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Хендлер для файла с ротацией
        file_handler = RotatingFileHandler(
            filename=os.path.join(log_dir, f"{name}.log"),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Хендлер для консоли
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
    def _format_message(self, message: str, **kwargs) -> str:
        """Форматирует сообщение с дополнительными параметрами"""
        if kwargs:
            details = " | ".join(f"{k}: {v}" for k, v in kwargs.items())
            return f"{message} | {details}"
        return message
        
    def info(self, message: str, **kwargs) -> None:
        """Логирует информационное сообщение"""
        self.logger.info(self._format_message(message, **kwargs))
        
    def warning(self, message: str, **kwargs) -> None:
        """Логирует предупреждение"""
        self.logger.warning(self._format_message(message, **kwargs))
        
    def error(self, message: str, exc_info: Optional[Exception] = None, **kwargs) -> None:
        """Логирует ошибку с опциональным исключением"""
        if exc_info:
            self.logger.error(
                self._format_message(message, **kwargs),
                exc_info=exc_info
            )
        else:
            self.logger.error(self._format_message(message, **kwargs))
            
    def critical(self, message: str, exc_info: Optional[Exception] = None, **kwargs) -> None:
        """Логирует критическую ошибку"""
        if exc_info:
            self.logger.critical(
                self._format_message(message, **kwargs),
                exc_info=exc_info
            )
        else:
            self.logger.critical(self._format_message(message, **kwargs))
            
    def debug(self, message: str, **kwargs) -> None:
        """Логирует отладочное сообщение"""
        self.logger.debug(self._format_message(message, **kwargs))
        
    def log_login_attempt(self, success: bool, email: str, **kwargs) -> None:
        """Логирует попытку входа"""
        status = "✅ Успешно" if success else "❌ Неудачно"
        self.info(f"Попытка входа {status}", email=email, **kwargs)
        
    def log_retry(self, operation: str, attempt: int, max_retries: int, **kwargs) -> None:
        """Логирует повторную попытку операции"""
        self.warning(
            f"Повторная попытка {operation}",
            attempt=attempt,
            max_retries=max_retries,
            **kwargs
        )
        
    def log_screenshot(self, thread_id: int, success: bool, **kwargs) -> None:
        """Логирует создание скриншота"""
        status = "✅ Успешно" if success else "❌ Неудачно"
        self.info(f"Создание скриншота {status}", thread_id=thread_id, **kwargs)
        
    def log_element_wait(self, element: str, success: bool, **kwargs) -> None:
        """Логирует ожидание элемента"""
        status = "✅ Найден" if success else "❌ Не найден"
        self.info(f"Ожидание элемента {element} {status}", **kwargs)
        
    def log_page_refresh(self, thread_id: int, success: bool, **kwargs) -> None:
        """Логирует обновление страницы"""
        status = "✅ Успешно" if success else "❌ Неудачно"
        self.info(f"Обновление страницы {status}", thread_id=thread_id, **kwargs)
        
    def log_thread_status(self, thread_id: int, status: str, **kwargs) -> None:
        """Логирует статус потока"""
        self.info(f"Статус потока {thread_id}: {status}", **kwargs)
        
    def log_critical_error(self, error: Exception, context: str, **kwargs) -> None:
        """Логирует критическую ошибку с контекстом"""
        self.critical(
            f"Критическая ошибка в {context}",
            exc_info=error,
            **kwargs
        ) 