from pymacaron.log import pymlogger
import pprint
import os
from time import sleep
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.utils import get_container_version
from pymacaron.utils import get_app_name
from pymacaron.crash import report_error
from pymacaron.exceptions import PyMacaronException


log = pymlogger(__name__)


class MyFatalCustomError(PyMacaronException):
    code = 'FATAL_CUSTOM_ERROR'
    status = 543

class MyNonFatalCustomError(PyMacaronException):
    code = 'NON_FATAL_CUSTOM_ERROR'
    status = 401


ping_hooks = []

def add_ping_hook(hook):
    global ping_hooks
    assert callable(hook), "Ping hook %s should be a function" % str(hook)
    ping_hooks.append(hook)

def do_ping():
    log.debug("Replying ping:ok")
    v = ApiPool.ping.model.Ok()
    for h in ping_hooks:
        log.info("Calling ping hook %s" % str(h))
        h()
    return v

def do_version():
    """Return version details of the running server api"""
    v = ApiPool.ping.model.Version(
        name=get_app_name(),
        version=ApiPool().current_server_api.get_version(),
        container=get_container_version(),
        pym_env=os.environ.get('PYM_ENV', ''),
    )
    log.info("/version: " + pprint.pformat(v))
    return v

def do_crash_internal_exception():
    raise Exception("Raising an internal exception")

def do_crash_pymacaron_exception():
    raise MyNonFatalCustomError("Raising a non-fatal custom error")

def do_crash_report_error():
    report_error("called crash/reporterror to test error reporting")
    return ApiPool.crash.model.Ok()

def do_crash_slow_call():
    sleep(6)
    return ApiPool.crash.model.Ok()

def do_crash_return_fatal_error_response():
    return MyFatalCustomError("endpoint returns an Error response").http_reply()

def do_crash_return_non_fatal_error_response():
    return MyNonFatalCustomError("endpoint returns a non-fatal Error response").http_reply()

def do_crash_return_error_model():
    return ApiPool.crash.model.Error(
        status=543,
        error='ANOTHER_CUSTOM_ERROR',
        error_description='Testing error model',
    )

def do_crash_return_error_instance():
    return MyFatalCustomError("endpoint returns an Error instance")
