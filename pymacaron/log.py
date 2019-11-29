import logging
import sys

DEFAULT_LEVEL = logging.DEBUG

root = logging.getLogger()

def setup_logger(celery=False):
    global root

    # Celery setups a default handler: remove it
    root.handlers = []

    ch = logging.StreamHandler(sys.stdout)

    name = 'WORKER' if celery else 'FLASK'
    formatter = logging.Formatter('%(asctime)s - ' + name + ' %(process)d - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)
    root.setLevel(DEFAULT_LEVEL)

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
