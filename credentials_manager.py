import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Dict, Optional, Tuple
from logger import Logger

class CredentialsManager:
    def __init__(self, encryption_key: Optional[str] = None):
        self.logger = Logger("credentials_manager")
        self.credentials_file = "credentials.enc"
        self.encryption_key = encryption_key or os.getenv("ENCRYPTION_KEY")
        
        if not self.encryption_key:
            # Генерируем новый ключ, если его нет
            self.encryption_key = self._generate_key()
            self.logger.info("✅ Сгенерирован новый ключ шифрования")
            
        self.fernet = self._create_fernet()
        
    def _generate_key(self) -> str:
        """Генерирует новый ключ шифрования"""
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(os.urandom(32)))
        return key.decode()
        
    def _create_fernet(self) -> Fernet:
        """Создает объект Fernet для шифрования"""
        try:
            return Fernet(self.encryption_key.encode())
        except Exception as e:
            self.logger.error("❌ Ошибка создания объекта Fernet", exc_info=e)
            raise
            
    def save_credentials(self, credentials: Dict[str, str]) -> bool:
        """
        Сохраняет учетные данные в зашифрованном виде
        
        Args:
            credentials: Словарь с учетными данными
            
        Returns:
            bool: Успех операции
        """
        try:
            # Преобразуем в JSON и шифруем
            data = json.dumps(credentials).encode()
            encrypted_data = self.fernet.encrypt(data)
            
            # Сохраняем в файл
            with open(self.credentials_file, "wb") as f:
                f.write(encrypted_data)
                
            self.logger.info("✅ Учетные данные успешно сохранены")
            return True
            
        except Exception as e:
            self.logger.error("❌ Ошибка сохранения учетных данных", exc_info=e)
            return False
            
    def load_credentials(self) -> Optional[Dict[str, str]]:
        """
        Загружает и расшифровывает учетные данные
        
        Returns:
            Dict[str, str]: Словарь с учетными данными или None
        """
        try:
            if not os.path.exists(self.credentials_file):
                self.logger.warning("⚠️ Файл с учетными данными не найден")
                return None
                
            # Читаем и расшифровываем
            with open(self.credentials_file, "rb") as f:
                encrypted_data = f.read()
                
            decrypted_data = self.fernet.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode())
            
            self.logger.info("✅ Учетные данные успешно загружены")
            return credentials
            
        except Exception as e:
            self.logger.error("❌ Ошибка загрузки учетных данных", exc_info=e)
            return None
            
    def update_credentials(self, new_credentials: Dict[str, str]) -> Tuple[bool, str]:
        """
        Обновляет учетные данные
        
        Args:
            new_credentials: Новые учетные данные
            
        Returns:
            (успех, сообщение)
        """
        try:
            # Проверяем обязательные поля
            required_fields = ["email", "password"]
            missing_fields = [field for field in required_fields if field not in new_credentials]
            
            if missing_fields:
                return False, f"Отсутствуют обязательные поля: {', '.join(missing_fields)}"
                
            # Сохраняем новые данные
            if self.save_credentials(new_credentials):
                return True, "✅ Учетные данные успешно обновлены"
            else:
                return False, "❌ Ошибка сохранения учетных данных"
                
        except Exception as e:
            self.logger.error("❌ Ошибка обновления учетных данных", exc_info=e)
            return False, f"❌ Ошибка: {str(e)}"
            
    def get_credentials(self) -> Optional[Dict[str, str]]:
        """
        Получает текущие учетные данные
        
        Returns:
            Dict[str, str]: Словарь с учетными данными или None
        """
        credentials = self.load_credentials()
        if not credentials:
            self.logger.warning("⚠️ Не удалось загрузить учетные данные")
        return credentials
        
    def clear_credentials(self) -> bool:
        """
        Удаляет сохраненные учетные данные
        
        Returns:
            bool: Успех операции
        """
        try:
            if os.path.exists(self.credentials_file):
                os.remove(self.credentials_file)
                self.logger.info("✅ Учетные данные успешно удалены")
            return True
        except Exception as e:
            self.logger.error("❌ Ошибка удаления учетных данных", exc_info=e)
            return False 