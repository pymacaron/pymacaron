import logging
import json
import os
import traceback
from pprint import pformat
from flask import jsonify, Response, request
from klue.exceptions import ValidationError, KlueException
from klue.swagger.apipool import ApiPool


log = logging.getLogger(__name__)


class KlueMicroServiceException(KlueException):
    code = 'UNKNOWN_EXCEPTION'
    status = 500
    error_id = None
    user_message = None
    error_caught = None

    def caught(self, error):
        self.error_caught = error
        return self

    def http_reply(self):
        """Return a Flask reply object describing this error"""
        data = {
            'status': self.status,
            'error': self.code.upper(),
            'error_description': str(self)
        }

        if self.error_caught:
            data['error_caught'] = pformat(self.error_caught)

        if self.error_id:
            data['error_id'] = self.error_id

        if self.user_message:
            data['user_message'] = self.user_message

        r = jsonify(data)
        r.status_code = self.status

        if str(self.status) != "200":
            log.warn("ERROR: caught error %s %s [%s]" % (self.status, self.code, str(self)))

        return r

    def to_model(self):
        """Return a bravado-core Error instance"""
        e = ApiPool().current_server_api.model.Error(
            status=self.status,
            error=self.code.upper(),
            error_description=str(self),
        )
        if self.error_id:
            e.error_id = self.error_id
        if self.user_message:
            e.user_message = self.user_message
        if self.error_caught:
            e.error_caught = pformat(self.error_caught)
        return e


class UnhandledServerError(KlueMicroServiceException):
    code = 'UNHANDLED_SERVER_ERROR'
    status = 500

class InternalServerError(KlueMicroServiceException):
    code = 'SERVER_ERROR'
    status = 500

class AuthMissingHeaderError(KlueMicroServiceException):
    code = 'AUTHORIZATION_HEADER_MISSING'
    status = 401

class AuthTokenExpiredError(KlueMicroServiceException):
    code = 'TOKEN_EXPIRED'
    status = 401

class AuthInvalidTokenError(KlueMicroServiceException):
    code = 'TOKEN_INVALID'
    status = 401

class ValidationError(KlueMicroServiceException):
    code = 'INVALID_PARAMETER'
    status = 400


def responsify(error):
    """Take an Error model and return it as a Flask response"""
    assert str(type(error).__name__) == 'Error'
    if error.error in code_to_class:
        e = code_to_class[error.error](error.error_description)
        if error.error_id:
            e.error_id = error.error_id
        if error.user_message:
            e.user_message = error.user_message
        return e.http_reply()
    elif isinstance(error, KlueMicroServiceException):
        return error.http_reply()
    else:
        return KlueMicroServiceException("Caught un-mapped error: %s" % error).http_reply()


def is_error(o):
    """True if o is an instance of a swagger Error model or a flask Response of
    an error model"""
    if hasattr(o, 'error') and hasattr(o, 'error_description') and hasattr(o, 'status'):
        return True
    return False


def report_error(data, msg=None, caught=None, title=None):
    return crash.report_error(data, msg=msg, caught=caught, title=title)


def format_error(e):
    """Take an exception caught within klue-client-server and turn it into a
    bravado-core Error instance"""

    if isinstance(e, KlueMicroServiceException):
        return e.to_model()

    if isinstance(e, KlueException) and e.__class__.__name__ == 'ValidationError':
        return ValidationError(str(e)).to_model()

    # Turn this exception into a PntCommonException
    return UnhandledServerError(str(e)).to_model()


def raise_error(e):
    """Take a bravado-core Error model and raise it as an exception"""
    code = e.error
    if code in code_to_class:
        raise code_to_class[code](e.error_description)
    else:
        raise InternalServerError(e.error_description)
