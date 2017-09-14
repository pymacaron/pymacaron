import logging
import json
import uuid
import os
import sys
import traceback
import inspect
from functools import wraps
from pprint import pformat
from flask import request, Response
from klue.swagger.apipool import ApiPool
from klue_microservice.utils import timenow
from klue_microservice.exceptions import UnhandledServerError


log = logging.getLogger(__name__)


try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack


#
# Default error reporting
#

def default_error_reporter(title, message):
    """By default, error messages are just logged"""
    log.error("error: %s" % title)
    log.error("details:\n%s" % message)

error_reporter = default_error_reporter

def set_error_reporter(callback=None):
    """Here you can override the default crash reporter (and send yourself
    emails, sms, slacks...)"""

    global error_reporter
    if error_reporter:
        error_reporter = callback


def report_error(data, msg=None, caught=None, title=None):
    """Format a crash report and send it somewhere relevant. There are two
    types of crashes: fatal crashes (backend errors) or non-fatal ones (just
    reporting a glitch, but the api call did not fail)"""

    if isinstance(data, dict):
        # That's a fatal error

        status, code = 'unknown_status', 'unknown_error_code'
        if 'response' in data:
            status = data['response'].get('status', status)
            code = data['response'].get('error_code', code)
        if not title:
            title = "BACKEND ERROR"
        if not msg:
            msg = "%s: %s %s %s" % (title, status, code, ApiPool().current_server_name)
    else:
        # That's a non-fatal error

        message = data
        log.error(message)

        data = {}
        data['message'] = message

        # Formatting traceback may raise a UnicodeDecodeError...
        data['stack'] = []
        try:
            data['stack'] = [l for l in traceback.format_stack()]
        except Exception as ee:
            pass

        populate_error_report(data)
        if caught:
            data['error_caught'] = "%s" % caught

        # inspect may raise a UnicodeDecodeError...
        fname = ''
        try:
            fname = inspect.stack()[1][3]
        except Exception as e:
            pass

        if title:
            msg = title
        else:
            title = "NON-FATAL BACKEND ERROR"
            msg = "%s %s %s(): %s" % (title, ApiPool().current_server_name, fname, message)

    if os.environ.get('NO_ERROR_REPORTING', '') == '1':
        log.info("NO_ERROR_REPORTING is set: not sending error to slack or email")
        return

    global error_reporter
    log.info("Reporting crash...")

    try:
        error_reporter(msg, json.dumps(data, sort_keys=True, indent=4))
    except Exception as e:
        # Don't block on replying to api caller
        log.error("Failed to send email report: %s" % str(e))


def populate_error_report(data):
    """Add generic stats to the error report"""

    # Did klue-client-server set a call_id and call_path?
    call_id, call_path = '', ''
    if hasattr(stack.top, 'call_id'):
        call_id = stack.top.call_id
    if hasattr(stack.top, 'call_path'):
        call_path = stack.top.call_path

    # Unique ID associated to all responses associated to a given
    # call to klue-api, across all micro-services
    data['call_id'] = call_id
    data['call_path'] = call_path


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
            log.info("Got %s=%s" % (k, v))
            if v:
                user_data[k] = v

    data['user'] = user_data

    # Is the current code running as a server?
    if ApiPool().current_server_api:
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
            'api_name': ApiPool().current_server_name,
            'api_version': ApiPool().current_server_api.get_version(),
        }

        # Endpoint data
        data['endpoint'] = {
            'id': "%s %s %s" % (ApiPool().current_server_name, request.method, request.path),
            'url': request.url,
            'base_url': request.base_url,
            'path': request.path,
            'method': request.method
        }


def crash_handler(f):
    """Return a decorator that reports failed api calls via the error_reporter,
    for use on every server endpoint"""

    @wraps(f)
    def wrapper(*args, **kwargs):
        """Generate a report of this api call, and if the call failed or was too slow,
        forward this report via the error_reporter"""

        data = {}
        t0 = timenow()

        # Call endpoint and log execution time
        try:
            res = f(*args, **kwargs)
        except Exception as e:
            # An unhandled exception occured. Forge a Response
            exc_type, exc_value, exc_traceback = sys.exc_info()
            s = ''.join((traceback.format_exception(exc_type, exc_value, exc_traceback, 30)))
            e = UnhandledServerError(s)
            log.error("UNHANDLED EXCEPTION: %s" % s)
            res = e.http_reply()

        t1 = timenow()

        # Is the response an Error instance?
        response_type = type(res).__name__
        status_code = ''
        is_an_error = 0
        error = ''
        error_description = ''
        error_user_message = ''

        error_id = ''

        if isinstance(res, Response):
            # Got a flask.Response object
            status_code = res.status_code
            if (str(status_code) != '200'):
                # Assuming it is a PntCommonError.http_reply()

                res_data = res.get_data()

                if type(res_data) is bytes:
                    res_data = res_data.decode("utf-8")

                is_json = True
                try:
                    j = json.loads(res_data)
                except ValueError as e:
                    # This was a plain html response. Fake an error
                    is_json = False
                    j = {'error': res_data}

                error = j.get('error', 'NO_ERROR_IN_JSON')
                error_description = j.get('error_description', res_data)
                if error_description == '':
                    error_description = res_data

                error_user_message = j.get('user_message', '')
                is_an_error = 1

                # Patch Response to contain a unique id
                if is_json and 'error_id' not in j:
                    # If the error is forwarded by multiple micro-services, we
                    # want the error_id to be set only on the original error
                    error_id = str(uuid.uuid4())
                    j['error_id'] = error_id
                    res.set_data(json.dumps(j))
            else:
                status_code = 200

        request_args = []
        if len(args):
            request_args.append(args)
        if kwargs:
            request_args.append(kwargs)

        data = {
            # Set only on the original error, not on forwarded ones, not on
            # success responses
            'error_id': error_id,

            # Call results
            'time': {
                'start': t0.isoformat(),
                'end': t1.isoformat(),
                'microsecs': (t1 - t0).microseconds,
            },

            # Response details
            'response': {
                'type': response_type,
                'status': status_code,
                'is_error': is_an_error,
                'error_code': error,
                'error_description': error_description,
                'user_message': error_user_message,
            },

            # Request details
            'request': {
                'params': pformat(request_args),
            },
        }

        populate_error_report(data)
        log.info("Analytics: " + pformat(data))

        #
        # Should we report this call?
        #

        if 'server' not in data:
            log.info("This is a unitest running: not reporting error")
            pass
        else:
            fqdn = data['server']['fqdn']
            if '192.168' in fqdn or '127.0.0' in fqdn:
                log.info("This is a test setup: not reporting error")
                pass
            else:
                # If it is an internal errors, report it
                # If it is too slow, report it
                if str(data['response']['status']) in ('500'):
                    report_error(data)
                elif int(data['time']['microsecs']) > 3000000:
                    report_error(data, msg="SLOW BACKEND CALL: %s %s" % (ApiPool().current_server_name, data['endpoint']['path']))

        return res

    return wrapper
