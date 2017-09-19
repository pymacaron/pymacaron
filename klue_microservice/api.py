import logging
import pprint
from flask import make_response
from time import sleep
from klue.swagger.apipool import ApiPool
from klue_microservice.utils import get_container_version
from klue_microservice.crash import report_error
from klue_microservice.exceptions import KlueMicroServiceException


log = logging.getLogger(__name__)


class MyFatalCustomError(KlueMicroServiceException):
    code = 'FATAL_CUSTOM_ERROR'
    status = 543

class MyNonFatalCustomError(KlueMicroServiceException):
    code = 'NON_FATAL_CUSTOM_ERROR'
    status = 401


def do_ping():
    log.debug("Replying ping:ok")
    v = ApiPool.ping.model.Ok()
    return v

def do_version():
    """Return version details of the running server api"""
    v = ApiPool.ping.model.Version(
        name=ApiPool().current_server_name,
        version=ApiPool().current_server_api.get_version(),
        container=get_container_version(),
    )
    log.info("/version: " + pprint.pformat(v))
    return v

def do_crash_internal_exception():
    raise Exception("Raising an internal exception")

def do_crash_klue_exception():
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
