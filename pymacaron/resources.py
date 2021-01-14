from pymacaron.log import pymlogger
import multiprocessing
from math import ceil
from pymacaron.config import get_config


log = pymlogger(__name__)


# Calculate resources available on this container hardware.
# Used by pymacaron-async, pymacaron-gcp and pymacaron-docker

def get_gunicorn_worker_count(cpu_count=None):
    """Return the number of gunicorn worker to run on this container hardware"""
    if cpu_count:
        return cpu_count * 2 + 1
    return multiprocessing.cpu_count() * 2 + 1


def get_celery_worker_count(cpu_count=None):
    """Return the number of celery workers to run on this container hardware"""
    conf = get_config()
    if hasattr(conf, 'worker_count'):
        # Start worker_count parrallel celery workers
        return conf.worker_count
    if cpu_count:
        return cpu_count * 2
    c = multiprocessing.cpu_count() * 2
    # Minimum worker count == 2
    if c < 2:
        c == 2
    return c


# Memory required, in Mb, by one gunicorn or celery worker:
GUNICORN_WORKER_MEM = 400
CELERY_WORKER_MEM = 200

def get_memory_limit(default_celery_worker_count=None, cpu_count=None):
    """Return the memory in Megabytes required to run pymacaron on this container hardware"""
    # Let's calculate how much memory this pymacaron config requires for 1 container
    celery_count = default_celery_worker_count
    if not celery_count:
        celery_count = get_celery_worker_count(cpu_count=cpu_count)
    return ceil(get_gunicorn_worker_count(cpu_count=cpu_count) * GUNICORN_WORKER_MEM + celery_count * CELERY_WORKER_MEM)


def get_celery_worker_memory_limit():
    return CELERY_WORKER_MEM * 1024
