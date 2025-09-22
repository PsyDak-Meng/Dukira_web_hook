from celery import Celery
from .config import settings

# Celery configuration
broker_url = settings.redis_url
result_backend = settings.redis_url

# Task settings
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'UTC'
enable_utc = True

# Task routing
task_routes = {
    'app.services.sync_service.sync_store_task': {'queue': 'sync'},
    'app.services.sync_service.process_image_task': {'queue': 'images'},
    'app.services.sync_service.auto_sync_all_stores': {'queue': 'sync'},
}

# Beat schedule for periodic tasks
beat_schedule = {
    'auto-sync-stores': {
        'task': 'app.services.sync_service.auto_sync_all_stores',
        'schedule': 3600.0,  # Run every hour
    },
}

# Worker settings
worker_prefetch_multiplier = 1
task_acks_late = True
worker_max_tasks_per_child = 1000

# Task result settings
result_expires = 3600  # 1 hour

# Error handling
task_reject_on_worker_lost = True
task_ignore_result = False