from pymacaron.log import pymlogger
import json
import uuid
import os
import inspect
import sys
import traceback
from flask import request
from pymacaron.utils import get_container_version
from pymacaron.utils import get_app_name
from pymacaron.utils import is_ec2_instance
from pymacaron.config import get_config
from pymacaron.exceptions import PyMacaronException


log = pymlogger(__name__)


try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack


def function_name(f):
    return "%s.%s" % (inspect.getmodule(f).__name__, f.__name__)


#
# Default error reporting
#

def default_error_reporter(title=None, data=None, exception=None):
    """By default, error messages are just logged"""
    log.error(f"error: {title}")
    log.error(f"exception: {exception}")
    log.error(f"details:\n{json.dumps(data, indent=4, sort_keys=True)}")


error_reporter = default_error_reporter


def set_error_reporter(f):
    global error_reporter
    error_reporter = f


def do_report_error(title=None, data=None, exception=None):
    global error_reporter
    log.info("Reporting error...")

    error_reporter(
        title=title,
        data=data,
    )

    try:
        pass
    except Exception as e:
        # Don't block on replying to api caller
        log.error(f"An error occured while trying to report this error: {e}\n")
        exc_type, exc_value, exc_traceback = sys.exc_info()
        trace = traceback.format_exception(exc_type, exc_value, exc_traceback, 30)
        log.error(trace)


def postmortem(f=None, t0=None, t1=None, exception=None, args=[], kwargs={}):
    """Print the error's trace, and call the error reporter with a bunch of data on what happened"""

    data = {}

    # Gather data about the exception that occured
    exc_type, exc_value, exc_traceback = sys.exc_info()
    trace = traceback.format_exception(exc_type, exc_value, exc_traceback, 30)

    status = 500
    if isinstance(exception, PyMacaronException):
        status = exception.status

    if status < 500:
        return

    str_trace = '\n'.join(trace)
    log.error(f"ERROR - ERROR - ERROR - ERROR - ERROR - ERROR:\n{str_trace}")

    data.update({
        'trace': trace,

        # Set only on the original error, not on forwarded ones, not on
        # success responses
        'error_id': str(uuid.uuid4()),

        'is_fatal_error': True if status >= 500 else False,

        # Call results
        'time': {
            'start': t0.isoformat(),
            'end': t1.isoformat(),
            'microsecs': (t1.timestamp() - t0.timestamp()) * 1000000,
        },

        # Response details
        'response': {
            'status': status,
            'error_code': exception.code if hasattr(exception, 'code') else 'UNKNOWN',
            'error_description': str(exception),
            'user_message': exception.user_message if hasattr(exception, 'user_message') else None,
        },
    })

    populate_error_report(data)

    fname = function_name(f)
    do_report_error(
        title=f"{fname}(): {exception}",
        data=data,
        exception=exception,
    )


def report_warning(title=None, data={}, exception=None):
    populate_error_report(data)
    do_report_error(
        title=title,
        data=data,
    )


def populate_error_report(data):
    """Add generic stats to the error report"""

    # Are we in aws?
    data['is_ec2_instance'] = is_ec2_instance()

    # If user is authenticated, get her id
    user_data = {
        'id': '',
        'is_auth': 0,
        'ip': '',
    }

    if stack.top:
        # We are in a request context
        user_data['ip'] = request.remote_addr

        if 'X-Forwarded-For' in request.headers:
            user_data['forwarded_ip'] = request.headers.get('X-Forwarded-For', '')

        if 'User-Agent' in request.headers:
            user_data['user_agent'] = request.headers.get('User-Agent', '')

    if hasattr(stack.top, 'current_user'):
        user_data['is_auth'] = 1
        user_data['id'] = stack.top.current_user.get('sub', '')
        for k in ('name', 'email', 'is_expert', 'is_admin', 'is_support', 'is_tester', 'language'):
            v = stack.top.current_user.get(k, None)
            if v:
                user_data[k] = v

    data['user'] = user_data

    # Server info
    server = request.base_url
    server = server.replace('http://', '')
    server = server.replace('https://', '')
    server = server.split('/')[0]
    parts = server.split(':')
    fqdn = parts[0]
    port = parts[1] if len(parts) == 2 else ''

    data['server'] = {
        'fqdn': fqdn,
        'port': port,
        'api_name': get_app_name(),
        'api_version': get_container_version(),
        'PYM_ENV': os.environ.get('PYM_ENV', ''),
    }

    # Endpoint data
    body_str = ''
    query_str = ''
    try:
        body_str = str(request.get_data())
        query_str = str(request.get.args)
    except Exception:
        pass

    data['request'] = {
        'id': f"{get_app_name()}, {request.method}, {request.path}",
        'url': request.url,
        'base_url': request.base_url,
        'path': request.path,
        'method': request.method,
        'request_body': body_str,
        'request_query': query_str,
    }


#
# DEPRECATED
#

def report_error(title=None, data={}, caught=None, is_fatal=False):
    """Format a crash report and send it somewhere relevant. There are two
    types of crashes: fatal crashes (backend errors) or non-fatal ones (just
    reporting a glitch, but the api call did not fail)"""

    log.info("Caught error: %s\ndata=%s" % (title, json.dumps(data, indent=4)))

    # Don't report errors if NO_ERROR_REPORTING set to 1 (set by run_acceptance_tests)
    if os.environ.get('DO_REPORT_ERROR', None):
        # Force error reporting
        pass
    elif os.environ.get('NO_ERROR_REPORTING', '') == '1':
        log.info("NO_ERROR_REPORTING is set: not reporting error!")
        return
    elif 'is_ec2_instance' in data:
        if not data['is_ec2_instance']:
            # Not running on amazon: no reporting
            log.info("DATA[is_ec2_instance] is False: not reporting error!")
            return
    elif not is_ec2_instance():
        log.info("Not running on an EC2 instance: not reporting error!")
        return

    # Fill error report with tons of usefull data
    if 'user' not in data:
        populate_error_report(data)

    # Add the message
    data['title'] = title
    data['is_fatal_error'] = is_fatal

    # Add the error caught, if any:
    if caught:
        data['error_caught'] = "%s" % caught

    # Add a trace - Formatting traceback may raise a UnicodeDecodeError...
    data['stack'] = []
    try:
        data['stack'] = [l for l in traceback.format_stack()]
    except Exception:
        data['stack'] = 'Skipped trace - contained non-ascii chars'

    # inspect may raise a UnicodeDecodeError...
    fname = ''
    try:
        fname = inspect.stack()[1][3]
    except Exception as e:
        fname = 'unknown-method'

    # Format the error's title
    status, code = 'unknown_status', 'unknown_error_code'
    app_name = get_config().name
    if 'response' in data:
        status = data['response'].get('status', status)
        code = data['response'].get('error_code', code)
        title_details = "%s %s %s" % (app_name, status, code)
    else:
        title_details = "%s %s()" % (app_name, fname)

    if is_fatal:
        title_details = 'FATAL ERROR %s' % title_details
    else:
        title_details = 'NON-FATAL ERROR %s' % title_details

    if title:
        title = "%s: %s" % (title_details, title)
    else:
        title = title_details

    global error_reporter
    log.info("Reporting crash...")

    try:
        error_reporter(title, json.dumps(data, sort_keys=True, indent=4))
    except Exception as e:
        # Don't block on replying to api caller
        log.error("Failed to send email report: %s" % str(e))



#
# Generic crash-handler as a decorator
#

def crash_handler(f):
    """Decorate method with pymacaron's generic crash handler"""
    return generate_crash_handler_decorator(None)(f)
