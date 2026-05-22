from arq import cron
from arq.connections import RedisSettings

from src.config import settings
from src.pipeline.tasks import process_document


class WorkerSettings:
    functions = [process_document]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 300  # 5 minutes per job
