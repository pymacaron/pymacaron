from pymacaron.log import pymlogger
import json
import uuid
import os
import inspect
import sys
import traceback
from functools import wraps
from pprint import pformat
from flask import request, Response
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.config import get_config
from pymacaron.utils import timenow, is_ec2_instance
from pymacaron.exceptions import UnhandledServerError


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


def populate_error_report(data):
    """Add generic stats to the error report"""

    # Did pymacaron_core set a call_id and call_path?
    call_id, call_path = '', ''
    if hasattr(stack.top, 'call_id'):
        call_id = stack.top.call_id
    if hasattr(stack.top, 'call_path'):
        call_path = stack.top.call_path

    # Unique ID associated to all responses associated to a given
    # call to apis, across all micro-services
    data['call_id'] = call_id
    data['call_path'] = call_path

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
        raw_data = ''
        try:
            raw_data = str(request.get_data())
        except Exception:
            pass

        data['endpoint'] = {
            'id': "%s %s %s" % (ApiPool().current_server_name, request.method, request.path),
            'url': request.url,
            'base_url': request.base_url,
            'path': request.path,
            'method': request.method,
            'data': raw_data,
        }


def generate_crash_handler_decorator(error_decorator=None):
    """Return the crash_handler to pass to pymacaron_core, with optional error decoration"""

    def crash_handler(f):
        """Return a decorator that reports failed api calls via the error_reporter,
        for use on every server endpoint"""

        @wraps(f)
        def wrapper(*args, **kwargs):
            """Generate a report of this api call, and if the call failed or was too slow,
            forward this report via the error_reporter"""

            data = {}
            t0 = timenow()
            exception_string = ''

            # Call endpoint and log execution time
            try:
                res = f(*args, **kwargs)
            except Exception as e:
                # An unhandled exception occured!
                exception_string = str(e)
                exc_type, exc_value, exc_traceback = sys.exc_info()
                trace = traceback.format_exception(exc_type, exc_value, exc_traceback, 30)
                data['trace'] = trace

                # If it is a PyMacaronException, just call its http_reply()
                if hasattr(e, 'http_reply'):
                    res = e.http_reply()
                else:
                    # Otherwise, forge a Response
                    e = UnhandledServerError(exception_string)
                    log.error("UNHANDLED EXCEPTION: %s" % '\n'.join(trace))
                    res = e.http_reply()

            t1 = timenow()

            # Is the response an Error instance?
            response_type = type(res).__name__
            status_code = 200
            is_an_error = 0
            error = ''
            error_description = ''
            error_user_message = ''

            error_id = ''

            if isinstance(res, Response):
                # Got a flask.Response object
                res_data = None

                status_code = str(res.status_code)

                if str(status_code) == '200':

                    # It could be any valid json response, but it could also be an Error model
                    # that pymacaron_core handled as a status 200 because it does not know of
                    # pymacaron Errors
                    if res.content_type == 'application/json':
                        s = str(res.data)
                        if '"error":' in s and '"error_description":' in s and '"status":' in s:
                            # This looks like an error, let's decode it
                            res_data = res.get_data()
                else:
                    # Assuming it is a PyMacaronException.http_reply()
                    res_data = res.get_data()

                if res_data:
                    if type(res_data) is bytes:
                        res_data = res_data.decode("utf-8")

                    is_json = True
                    try:
                        j = json.loads(res_data)
                    except ValueError as e:
                        # This was a plain html response. Fake an error
                        is_json = False
                        j = {'error': res_data, 'status': status_code}

                    # Make sure that the response gets the same status as the PyMacaron Error it contained
                    status_code = j['status']
                    res.status_code = int(status_code)

                    # Patch Response to contain a unique id
                    if is_json:
                        if 'error_id' not in j:
                            # If the error is forwarded by multiple micro-services, we
                            # want the error_id to be set only on the original error
                            error_id = str(uuid.uuid4())
                            j['error_id'] = error_id
                            res.set_data(json.dumps(j))

                        if error_decorator:
                            # Apply error_decorator, if any defined
                            res.set_data(json.dumps(error_decorator(j)))

                    # And extract data from this error
                    error = j.get('error', 'NO_ERROR_IN_JSON')
                    error_description = j.get('error_description', res_data)
                    if error_description == '':
                        error_description = res_data

                    if not exception_string:
                        exception_string = error_description

                    error_user_message = j.get('user_message', '')
                    is_an_error = 1


            request_args = []
            if len(args):
                request_args.append(args)
            if kwargs:
                request_args.append(kwargs)

            data.update({
                # Set only on the original error, not on forwarded ones, not on
                # success responses
                'error_id': error_id,

                # Call results
                'time': {
                    'start': t0.isoformat(),
                    'end': t1.isoformat(),
                    'microsecs': (t1.timestamp() - t0.timestamp()) * 1000000,
                },

                # Response details
                'response': {
                    'type': response_type,
                    'status': str(status_code),
                    'is_error': is_an_error,
                    'error_code': error,
                    'error_description': error_description,
                    'user_message': error_user_message,
                },

                # Request details
                'request': {
                    'params': pformat(request_args),
                },
            })

            populate_error_report(data)

            # inspect may raise a UnicodeDecodeError...
            fname = function_name(f)

            #
            # Should we report this call?
            #

            # If it is an internal errors, report it
            if data['response']['status'] and int(data['response']['status']) >= 500:
                report_error(
                    title="%s(): %s" % (fname, exception_string),
                    data=data,
                    is_fatal=True
                )

            log.info("")
            log.info(" <= Done!")
            log.info("")

            return res

        return wrapper

    return crash_handler

#
# Generic crash-handler as a decorator
#

def crash_handler(f):
    """Decorate method with pymacaron's generic crash handler"""
    return generate_crash_handler_decorator(None)(f)
