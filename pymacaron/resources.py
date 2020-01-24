import logging
import multiprocessing
from math import ceil
from pymacaron.config import get_config


log = logging.getLogger(__name__)


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


def get_memory_limit(default_celery_worker_count=None, cpu_count=None):
    """Return the memory in Megabytes required to run pymacaron on this container hardware"""
    # Let's calculate how much memory this pymacaron config requires for 1 container
    # Each celery process takes 300Mb
    # Each gunicorn worker takes 900Mb
    celery_count = default_celery_worker_count
    if not celery_count:
        celery_count = get_celery_worker_count(cpu_count=cpu_count)
    return ceil(get_gunicorn_worker_count(cpu_count=cpu_count) * 900 + celery_count * 300)


def get_celery_worker_memory_limit():
    return 200 * 1024
