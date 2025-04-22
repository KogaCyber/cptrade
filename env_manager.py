import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from logger import Logger

class EnvManager:
    """Менеджер переменных окружения"""
    
    def __init__(self):
        self.logger = Logger("env_manager")
        self._load_env()
        self._validate_env()
        
    def _load_env(self) -> None:
        """Загружает переменные окружения из .env файла"""
        if not load_dotenv():
            self.logger.warning("⚠️ Файл .env не найден, используются системные переменные окружения")
            
    def _validate_env(self) -> None:
        """Проверяет наличие обязательных переменных окружения"""
        required_vars = [
            "ENV_TYPE",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
                
        if missing_vars:
            error_msg = f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
            
    def get(self, key: str, default: Any = None) -> Any:
        """
        Получает значение переменной окружения
        
        Args:
            key: Имя переменной
            default: Значение по умолчанию
            
        Returns:
            Any: Значение переменной
        """
        return os.getenv(key, default)
        
    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """
        Получает целочисленное значение переменной окружения
        
        Args:
            key: Имя переменной
            default: Значение по умолчанию
            
        Returns:
            Optional[int]: Значение переменной
        """
        value = self.get(key)
        if value is None:
            return default
            
        try:
            return int(value)
        except ValueError:
            self.logger.warning(f"⚠️ Неверный формат переменной {key}: {value}")
            return default
            
    def get_bool(self, key: str, default: Optional[bool] = None) -> Optional[bool]:
        """
        Получает булево значение переменной окружения
        
        Args:
            key: Имя переменной
            default: Значение по умолчанию
            
        Returns:
            Optional[bool]: Значение переменной
        """
        value = self.get(key)
        if value is None:
            return default
            
        return value.lower() in ("true", "1", "yes", "y")
        
    def get_all(self) -> Dict[str, str]:
        """
        Получает все переменные окружения
        
        Returns:
            Dict[str, str]: Словарь переменных окружения
        """
        return dict(os.environ) 