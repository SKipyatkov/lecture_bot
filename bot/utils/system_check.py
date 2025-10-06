import os
import platform
import subprocess
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class SystemChecker:
    """Проверка системных зависимостей для Windows"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.dependencies = {
            'ffmpeg': {
                'check_command': ['ffmpeg', '-version'] if self.system != 'windows' else ['where', 'ffmpeg'],
                'install_windows': 'Скачайте ffmpeg с https://ffmpeg.org/download.html и добавьте в PATH',
                'install_linux': 'sudo apt-get install ffmpeg',
                'required': True
            },
            'espeak': {
                'check_command': ['espeak', '--version'] if self.system != 'windows' else ['where', 'espeak'],
                'install_windows': 'Скачайте eSpeak с http://espeak.sourceforge.net/download.html',
                'install_linux': 'sudo apt-get install espeak espeak-data',
                'required': False
            },
            'python': {
                'check_command': ['python', '--version'],
                'install_windows': 'Скачайте с https://python.org',
                'install_linux': 'sudo apt-get install python3',
                'required': True
            }
        }
    
    def check_dependencies(self) -> Dict[str, Dict]:
        """Проверяет все системные зависимости"""
        results = {}
        
        for dep_name, dep_info in self.dependencies.items():
            try:
                if self.system == 'windows':
                    result = subprocess.run(dep_info['check_command'], 
                                          capture_output=True, text=True, shell=True)
                else:
                    result = subprocess.run(dep_info['check_command'], 
                                          capture_output=True, text=True)
                
                is_available = result.returncode == 0
                results[dep_name] = {
                    'available': is_available,
                    'message': f"{dep_name} {'найден' if is_available else 'не найден'}",
                    'install_guide': dep_info[f'install_{self.system}'] if self.system in ['windows', 'linux'] else dep_info['install_linux'],
                    'required': dep_info['required']
                }
                
                if is_available:
                    logger.info(f"✅ {dep_name} доступен")
                else:
                    if dep_info['required']:
                        logger.warning(f"❌ {dep_name} не найден (обязательный)")
                    else:
                        logger.warning(f"⚠️ {dep_name} не найден (опциональный)")
                        
            except Exception as e:
                results[dep_name] = {
                    'available': False,
                    'message': f"Ошибка проверки {dep_name}: {e}",
                    'install_guide': dep_info[f'install_{self.system}'] if self.system in ['windows', 'linux'] else dep_info['install_linux'],
                    'required': dep_info['required']
                }
                logger.error(f"❌ Ошибка проверки {dep_name}: {e}")
        
        return results
    
    def get_system_info(self) -> Dict:
        """Возвращает информацию о системе"""
        return {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'architecture': platform.architecture(),
            'processor': platform.processor(),
            'python_version': platform.python_version()
        }
    
    def check_disk_space(self, path='.') -> Dict:
        """Проверяет свободное место на диске"""
        try:
            import shutil
            total, used, free = shutil.disk_usage(path)
            return {
                'total_gb': round(total / (1024**3), 2),
                'used_gb': round(used / (1024**3), 2),
                'free_gb': round(free / (1024**3), 2),
                'free_percent': round((free / total) * 100, 2)
            }
        except Exception as e:
            logger.error(f"Ошибка проверки дискового пространства: {e}")
            return {'error': str(e)}
    
    def generate_setup_guide(self) -> str:
        """Генерирует руководство по настройке системы"""
        deps_status = self.check_dependencies()
        system_info = self.get_system_info()
        
        guide = f"""
=== РУКОВОДСТВО ПО НАСТРОЙКЕ СИСТЕМЫ ===

Система: {system_info['system']} {system_info['release']}
Python: {system_info['python_version']}

СТАТУС ЗАВИСИМОСТЕЙ:
"""
        
        for dep_name, status in deps_status.items():
            icon = "✅" if status['available'] else "❌"
            guide += f"\n{icon} {dep_name}: {status['message']}"
            if not status['available']:
                guide += f"\n   Установка: {status['install_guide']}"
        
        # Добавляем рекомендации для Windows
        if self.system == 'windows':
            guide += """

РЕКОМЕНДАЦИИ ДЛЯ WINDOWS:

1. Установите FFmpeg:
   - Скачайте с https://ffmpeg.org/download.html
   - Распакуйте в C:\\ffmpeg
   - Добавьте C:\\ffmpeg\\bin в системный PATH

2. Установите eSpeak (опционально для синтеза речи):
   - Скачайте с http://espeak.sourceforge.net/download.html
   - Установите и добавьте в PATH

3. Перезапустите командную строку после изменения PATH
"""
        
        return guide

# Глобальный проверщик системы
system_checker = SystemChecker()