import logging
import sys

DEFAULT_LEVEL = logging.DEBUG

root = logging.getLogger()
ch = logging.StreamHandler(sys.stdout)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)
root.setLevel(DEFAULT_LEVEL)

# Make an exception for boto and bravado: its debug level is just too verbose...
logging.getLogger('boto').setLevel(logging.INFO)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('bravado_core.spec').setLevel(logging.INFO)
logging.getLogger('swagger_spec_validator.ref_validators').setLevel(logging.INFO)
logging.getLogger('celery').setLevel(logging.INFO)


def get_logger():
    global root
    return root

def set_level(newlevel):
    global root
    root.setLevel(newlevel)
