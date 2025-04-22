import os
import requests
import time
from typing import Tuple
from logger import Logger
from telegram_manager import telegram_manager
from env_manager import EnvManager
from vpn_extension_manager import VPNExtensionManager

class VPNChecker:
    """Класс для проверки состояния VPN"""
    
    def __init__(self, driver=None):
        self.logger = Logger("vpn_checker")
        self.env = EnvManager()
        self.env_type = self.env.get("ENV_TYPE", "local")
        self.check_url = "https://www.binance.com"
        self.max_retries = self.env.get_int("VPN_CHECK_RETRIES", 3)
        self.retry_delay = self.env.get_int("VPN_CHECK_DELAY", 5)
        self.extension_manager = VPNExtensionManager(driver) if driver else None
        
    def check_vpn(self) -> Tuple[bool, str]:
        """
        Проверяет статус VPN
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        # Всегда возвращаем True, так как проверка будет ручной
        return True, "VPN проверяется вручную"
        
    def wait_for_vpn(self, timeout: int = 300) -> bool:
        """
        Ожидание активации VPN с таймаутом
        
        Args:
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            bool: True если пользователь подтвердил активацию VPN
        """
        logger = Logger("vpn_checker")
        
        logger.info("⏳ Ожидание активации VPN...")
        logger.info("После включения VPN нажмите Enter в консоли")
        
        # Ожидаем нажатия Enter
        input()
        
        # Если пользователь нажал Enter, считаем что VPN работает
        logger.info("✅ Пользователь подтвердил активацию VPN")
        return True 