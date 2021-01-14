import logging
import sys

DEFAULT_LEVEL = logging.DEBUG

root = logging.getLogger()

class ContextFilter(logging.Filter):
    """Add the viewer's user_id (if defined in JWT token) to the log string"""
    def filter(self, record):
        if not hasattr(record, 'USER_ID'):
            record.USER_ID = ''
        return True

def setup_logger(celery=False):
    global root

    # Celery setups a default handler: remove it
    root.handlers = []

    ch = logging.StreamHandler(sys.stdout)

    name = 'WORKER' if celery else 'FLASK'

    FORMAT = '%(asctime)s - ' + name + ' %(process)d%(USER_ID)s %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(FORMAT)

    ch.setFormatter(formatter)
    ch.addFilter(ContextFilter())
    root.addHandler(ch)
    root.setLevel(DEFAULT_LEVEL)

    # NOTE: 2020-06-22 disabled since supervisord should handle it...
    # # If setting up celery logger, also log to a file (for debugging purpose)
    # if celery:
    #     fh = logging.FileHandler('/var/log/celery-workers.log')
    #     fh.setFormatter(formatter)
    #     root.addHandler(fh)

    # Make an exception for boto and bravado: its debug level is just too verbose...
    logging.getLogger('boto').setLevel(logging.INFO)
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('bravado_core.spec').setLevel(logging.INFO)
    logging.getLogger('bravado_core.model').setLevel(logging.INFO)
    logging.getLogger('bravado_core.operation').setLevel(logging.INFO)
    logging.getLogger('swagger_spec_validator.ref_validators').setLevel(logging.INFO)
    logging.getLogger('celery').setLevel(logging.INFO)
    logging.getLogger('scout_apm.core').setLevel(logging.INFO)
    logging.getLogger('elasticsearch').setLevel(logging.INFO)


setup_logger()

def get_logger():
    global root
    return root

def set_level(newlevel):
    global root
    root.setLevel(newlevel)


#
# A custom wrapper around the logger object, injecting user_id and call_id from
# the flask context
#

class PymacaronLogger():

    def __init__(self, name=None):
        self.logger = logging.getLogger(name)

    def get_extra(self, extra):
        from pymacaron.auth import get_userid
        s = get_userid()
        extra.update({
            'USER_ID': ' [%s]' % s if s else '',
        })
        return extra

    def error(self, s, extra={}, **kwargs):
        self.logger.error(s, extra=self.get_extra(extra), **kwargs)

    def info(self, s, extra={}, **kwargs):
        self.logger.info(s, extra=self.get_extra(extra), **kwargs)

    def warn(self, s, extra={}, **kwargs):
        self.logger.warn(s, extra=self.get_extra(extra), **kwargs)

    def warning(self, s, extra={}, **kwargs):
        self.logger.warning(s, extra=self.get_extra(extra), **kwargs)

    def debug(self, s, extra={}, **kwargs):
        self.logger.debug(s, extra=self.get_extra(extra), **kwargs)


def pymlogger(name=None):
    if not name:
        name = __name__
    return PymacaronLogger(name)
