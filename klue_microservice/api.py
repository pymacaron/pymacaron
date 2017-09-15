import logging
import pprint
from flask import make_response
from time import sleep
from klue.swagger.apipool import ApiPool
from klue_microservice.utils import get_container_version
from klue_microservice.crash import report_error


log = logging.getLogger(__name__)


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

def do_crash_report_error():
    report_error("called crash/reporterror to test error reporting")
    return ApiPool.crash.model.Ok()

def do_crash_slow_call():
    sleep(6)
    return ApiPool.crash.model.Ok()

def do_crash_return_error_model():
    return ApiPool.crash.model.Error(
        status=543,
        error="CRASH_TEST",
        error_description="endpoint returns an Error model",
    )

def do_crash_return_error_response():
    return make_response('', 543)
