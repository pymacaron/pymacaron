import os
import sys
import logging
import datetime
from dateutil import parser
import socket
import logging
import pytz


log = logging.getLogger(__name__)


def is_ec2_instance():
    """Try fetching instance metadata at 'curl http://169.254.169.254/latest/meta-data/'
    to see if host is on an ec2 instance"""

    # Note: this code assumes that docker containers running on ec2 instances
    # inherit instances metadata, which they do as of 2016-08-25

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    try:
        s.connect(("169.254.169.254", 80))
        return True
    except socket.timeout:
        return False
    except socket.error:
        return False


def is_https_request():
    """Find out if the original request came over https (true) or just http
    (false)"""

    log.info("is_https_request: Got request url: %s" % request.url)
    log.info("is_https_request: Got request headers: %s" % request.headers)

    if 'X-Forwarded-Proto' in request.headers:
        if request.headers.get('X-Forwarded-Proto', '').lower() == 'https':
            log.debug("Called over https, according to X-Forwarded-Proto")
            return True
        else:
            log.debug("Called over http, according to X-Forwarded-Proto")
            return False

    if 'https' in request.url.lower():
        log.debug("Called over https, according to url (%s)" % request.url)
        return True

    log.debug("Request was made over http (url:%s) (X-Forwarded-Proto:%s)" % (request.url, request.headers.get('X-Forwarded-Proto', '')))
    return False


def timenow():
    return datetime.datetime.now(pytz.timezone('utc'))


def to_epoch(t):
    """Take a datetime, either as a string or a datetime.datetime object,
    and return the corresponding epoch"""
    if isinstance(t, str):
        if '+' not in t:
            t = t + '+00:00'
        t = parser.parse(t)
    elif t.tzinfo is None or t.tzinfo.utcoffset(t) is None:
        t = t.replace(tzinfo=pytz.timezone('utc'))

    t0 = datetime.datetime(1970, 1, 1, 0, 0, 0, 0, pytz.timezone('utc'))
    delta = t - t0
    return int(delta.total_seconds())


def to_datetime(e):
    """Take an epoch and return a timezone aware datetime"""
    return datetime.datetime.fromtimestamp(e, pytz.timezone('utc'))


def get_container_version():
    """Return the version of the docker container running the present server,
    or '' if not in a container"""
    root_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    version_file = os.path.join(root_dir, 'VERSION')
    if os.path.exists(version_file):
        with open(version_file) as f:
            return f.read()
    return ''
