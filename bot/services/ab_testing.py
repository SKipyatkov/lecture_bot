import logging
import random
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class ABTesting:
    """
    Система A/B тестирования для сравнения различных методов обработки
    и улучшения качества работы бота
    """
    
    def __init__(self):
        self.experiments: Dict[str, Dict] = {}
        self.user_assignments: Dict[str, Dict[str, str]] = {}  # user_id -> {experiment: group}
        self.results: Dict[str, List[Dict]] = {}  # experiment -> list of results
        self.metrics: Dict[str, List] = {}  # experiment -> list of metrics
        
        # Загружаем предопределенные эксперименты
        self._setup_default_experiments()
        
        logger.info("✅ Система A/B тестирования инициализирована")
    
    def _setup_default_experiments(self):
        """Настраивает эксперименты по умолчанию"""
        # Эксперимент методов улучшения текста
        self.create_experiment(
            experiment_id="text_enhancement_method",
            groups=["enhancer_v1", "enhancer_v2", "control"],
            description="Сравнение методов улучшения распознанного текста",
            weights=[40, 40, 20]  # Распределение по группам в процентах
        )
        
        # Эксперимент методов синтеза речи
        self.create_experiment(
            experiment_id="voice_synthesis_method", 
            groups=["espeak_standard", "espeak_enhanced", "control"],
            description="Сравнение методов синтеза речи",
            weights=[50, 30, 20]
        )
        
        # Эксперимент обработки аудио
        self.create_experiment(
            experiment_id="audio_processing_pipeline",
            groups=["pipeline_v1", "pipeline_v2"],
            description="Сравнение пайплайнов обработки аудио",
            weights=[50, 50]
        )
    
    def create_experiment(self, experiment_id: str, groups: List[str], 
                         description: str = "", weights: List[int] = None):
        """
        Создает новый эксперимент A/B тестирования
        """
        if experiment_id in self.experiments:
            logger.warning(f"Эксперимент {experiment_id} уже существует")
            return
        
        # Нормализуем веса
        if weights is None:
            weights = [100 // len(groups)] * len(groups)
        
        if len(weights) != len(groups):
            raise ValueError("Количество весов должно совпадать с количеством групп")
        
        # Нормализуем веса к 100%
        total_weight = sum(weights)
        normalized_weights = [int(w * 100 / total_weight) for w in weights]
        
        self.experiments[experiment_id] = {
            'groups': groups,
            'weights': normalized_weights,
            'description': description,
            'created_at': datetime.now(),
            'is_active': True,
            'total_participants': 0,
            'group_stats': {group: 0 for group in groups}
        }
        
        self.results[experiment_id] = []
        self.metrics[experiment_id] = []
        
        logger.info(f"✅ Создан эксперимент: {experiment_id} - {description}")
        logger.info(f"   Группы: {groups} с весами: {normalized_weights}")
    
    def assign_group(self, user_id: int, experiment_id: str) -> str:
        """
        Назначает пользователя в группу эксперимента
        Использует детерминированную случайность на основе user_id
        """
        if experiment_id not in self.experiments:
            logger.error(f"Эксперимент {experiment_id} не найден")
            return 'control'
        
        experiment = self.experiments[experiment_id]
        
        if not experiment['is_active']:
            return 'control'
        
        user_key = str(user_id)
        
        # Проверяем, есть ли уже назначение для этого пользователя
        if user_key not in self.user_assignments:
            self.user_assignments[user_key] = {}
        
        if experiment_id in self.user_assignments[user_key]:
            return self.user_assignments[user_key][experiment_id]
        
        # Детерминированная случайность на основе user_id
        random.seed(int(hashlib.md5(f"{user_id}_{experiment_id}".encode()).hexdigest(), 16))
        
        # Выбираем группу на основе весов
        groups = experiment['groups']
        weights = experiment['weights']
        
        # Создаем взвешенный выбор
        total = sum(weights)
        r = random.randint(1, total)
        
        current = 0
        for i, weight in enumerate(weights):
            current += weight
            if r <= current:
                group = groups[i]
                break
        else:
            group = groups[-1]  # fallback
        
        # Сохраняем назначение
        self.user_assignments[user_key][experiment_id] = group
        experiment['total_participants'] += 1
        experiment['group_stats'][group] += 1
        
        logger.debug(f"🎯 Пользователь {user_id} назначен в группу {group} эксперимента {experiment_id}")
        
        return group
    
    def track_result(self, experiment_id: str, user_id: int, group: str, 
                    success: bool, metrics: Dict[str, Any] = None):
        """
        Записывает результат эксперимента для пользователя
        """
        if experiment_id not in self.experiments:
            logger.error(f"Эксперимент {experiment_id} не найден")
            return
        
        result = {
            'user_id': user_id,
            'group': group,
            'success': success,
            'metrics': metrics or {},
            'timestamp': datetime.now(),
            'experiment_id': experiment_id
        }
        
        self.results[experiment_id].append(result)
        
        # Сохраняем метрики отдельно для анализа
        if metrics:
            metric_record = {
                'user_id': user_id,
                'group': group,
                'timestamp': datetime.now(),
                **metrics
            }
            self.metrics[experiment_id].append(metric_record)
        
        logger.debug(f"📊 Записан результат для эксперимента {experiment_id}, пользователь {user_id}, группа {group}")
    
    def get_experiment_stats(self, experiment_id: str) -> Dict[str, Any]:
        """
        Возвращает подробную статистику по эксперименту
        """
        if experiment_id not in self.experiments:
            return {'error': 'Experiment not found'}
        
        experiment = self.experiments[experiment_id]
        results = self.results.get(experiment_id, [])
        
        if not results:
            return {
                'experiment_id': experiment_id,
                'description': experiment['description'],
                'total_participants': experiment['total_participants'],
                'groups': experiment['groups'],
                'group_distribution': experiment['group_stats'],
                'total_results': 0,
                'message': 'No results yet'
            }
        
        stats = {
            'experiment_id': experiment_id,
            'description': experiment['description'],
            'total_participants': experiment['total_participants'],
            'groups': experiment['groups'],
            'group_distribution': experiment['group_stats'],
            'total_results': len(results),
            'groups': {}
        }
        
        # Статистика по группам
        for group in experiment['groups']:
            group_results = [r for r in results if r['group'] == group]
            group_metrics = [m for m in self.metrics.get(experiment_id, []) if m['group'] == group]
            
            if not group_results:
                stats['groups'][group] = {
                    'total': 0,
                    'successful': 0,
                    'success_rate': 0,
                    'metrics': {}
                }
                continue
            
            successful = len([r for r in group_results if r['success']])
            success_rate = successful / len(group_results) if group_results else 0
            
            # Анализ метрик
            metrics_analysis = {}
            if group_metrics:
                for metric_name in group_metrics[0].keys():
                    if metric_name not in ['user_id', 'group', 'timestamp']:
                        values = [m[metric_name] for m in group_metrics if metric_name in m]
                        if values:
                            metrics_analysis[metric_name] = {
                                'count': len(values),
                                'avg': sum(values) / len(values),
                                'min': min(values),
                                'max': max(values)
                            }
            
            stats['groups'][group] = {
                'total': len(group_results),
                'successful': successful,
                'success_rate': round(success_rate * 100, 2),
                'metrics': metrics_analysis
            }
        
        # Статистическая значимость (простая версия)
        if len(experiment['groups']) == 2:
            stats['significance'] = self._calculate_significance(stats)
        
        return stats
    
    def _calculate_significance(self, stats: Dict) -> Dict:
        """Вычисляет статистическую значимость различий между группами"""
        try:
            groups = list(stats['groups'].keys())
            if len(groups) != 2:
                return {}
            
            group_a, group_b = groups
            stats_a = stats['groups'][group_a]
            stats_b = stats['groups'][group_b]
            
            # Простой расчет confidence interval
            n1, n2 = stats_a['total'], stats_b['total']
            p1, p2 = stats_a['success_rate'] / 100, stats_b['success_rate'] / 100
            
            if n1 == 0 or n2 == 0:
                return {}
            
            # Standard error
            se = (p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2) ** 0.5
            
            # Z-score для 95% confidence
            z_score = 1.96
            margin = z_score * se
            
            # Difference and confidence interval
            diff = p1 - p2
            ci_lower = diff - margin
            ci_upper = diff + margin
            
            # Is significant?
            is_significant = (ci_lower > 0 or ci_upper < 0) and margin < abs(diff)
            
            return {
                'difference_percent': round(diff * 100, 2),
                'confidence_interval': [round(ci_lower * 100, 2), round(ci_upper * 100, 2)],
                'is_significant': is_significant,
                'confidence_level': 95
            }
            
        except Exception as e:
            logger.error(f"Ошибка расчета статистической значимости: {e}")
            return {}
    
    def get_user_experiments(self, user_id: int) -> Dict[str, str]:
        """Возвращает эксперименты пользователя"""
        user_key = str(user_id)
        return self.user_assignments.get(user_key, {})
    
    def stop_experiment(self, experiment_id: str):
        """Останавливает эксперимент (прекращает новые назначения)"""
        if experiment_id in self.experiments:
            self.experiments[experiment_id]['is_active'] = False
            logger.info(f"⏹️ Эксперимент остановлен: {experiment_id}")
    
    def resume_experiment(self, experiment_id: str):
        """Возобновляет эксперимент"""
        if experiment_id in self.experiments:
            self.experiments[experiment_id]['is_active'] = True
            logger.info(f"▶️ Эксперимент возобновлен: {experiment_id}")
    
    def get_winning_group(self, experiment_id: str, metric: str = 'success_rate') -> Optional[str]:
        """
        Определяет победившую группу на основе указанной метрики
        """
        stats = self.get_experiment_stats(experiment_id)
        if 'groups' not in stats or not stats['groups']:
            return None
        
        best_group = None
        best_value = -1
        
        for group, group_stats in stats['groups'].items():
            if metric in group_stats:
                value = group_stats[metric]
                if value > best_value:
                    best_value = value
                    best_group = group
            elif metric == 'success_rate':
                value = group_stats.get('success_rate', 0)
                if value > best_value:
                    best_value = value
                    best_group = group
        
        return best_group
    
    def export_data(self, experiment_id: str = None) -> Dict:
        """Экспортирует данные экспериментов"""
        data = {
            'exported_at': datetime.now().isoformat(),
            'experiments': {},
            'user_assignments': self.user_assignments
        }
        
        if experiment_id:
            if experiment_id in self.experiments:
                data['experiments'][experiment_id] = {
                    'config': self.experiments[experiment_id],
                    'results': self.results.get(experiment_id, []),
                    'metrics': self.metrics.get(experiment_id, [])
                }
        else:
            for exp_id in self.experiments:
                data['experiments'][exp_id] = {
                    'config': self.experiments[exp_id],
                    'results': self.results.get(exp_id, []),
                    'metrics': self.metrics.get(exp_id, [])
                }
        
        return data
    
    def cleanup_old_data(self, max_age_days: int = 30):
        """Очищает старые данные экспериментов"""
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        cleaned_count = 0
        
        for experiment_id in list(self.results.keys()):
            # Очищаем старые результаты
            original_count = len(self.results[experiment_id])
            self.results[experiment_id] = [
                r for r in self.results[experiment_id] 
                if r['timestamp'] > cutoff_time
            ]
            cleaned_count += original_count - len(self.results[experiment_id])
            
            # Очищаем старые метрики
            if experiment_id in self.metrics:
                original_count = len(self.metrics[experiment_id])
                self.metrics[experiment_id] = [
                    m for m in self.metrics[experiment_id]
                    if m['timestamp'] > cutoff_time
                ]
                cleaned_count += original_count - len(self.metrics[experiment_id])
        
        if cleaned_count > 0:
            logger.info(f"🧹 Очищено {cleaned_count} устаревших записей A/B тестирования")

# Глобальная система A/B тестирования
ab_testing = ABTesting()