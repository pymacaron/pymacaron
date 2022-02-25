from pymacaron.log import pymlogger
from pprint import pformat
from flask import jsonify


log = pymlogger(__name__)


class PyMacaronException(BaseException):
    code = 'UNKNOWN_EXCEPTION'
    status = 500
    error_id = None
    user_message = None
    error_caught = None

    def __str__(self):
        return f'{self.__class__.__name__}({self.status}|{self.code}|{self.user_message})'

    def __init__(self, msg=None):
        self.user_message = msg

    def caught(self, error):
        self.error_caught = error
        return self

    def jsonify(self):
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

    def to_dict(self):
        """Return a dict representation of this pymacaron error"""
        d = {
            'status': self.status,
            'error': self.code.upper(),
        }
        if self.error_id:
            d['error_id'] = self.error_id
        if self.user_message:
            d['user_message'] = self.user_message
        if self.error_caught:
            d['error_caught'] = pformat(self.error_caught)
        return d


class InternalValidationError(PyMacaronException):
    code = 'INTERNAL_VALIDATION_ERROR'
    status = 500


class BadResponseException(PyMacaronException):
    code = 'BAD_RESPONSE'
    status = 500


class UnhandledServerError(PyMacaronException):
    code = 'SERVER_ERROR'
    status = 500


class InvalidParameterError(PyMacaronException):
    code = 'INVALID_PARAMETER'
    status = 400


class RequestTimeout(PyMacaronException):
    code = 'REQUEST_TIMEOUT'
    status = 408


#
# Interface to allow creating further Exception classes
#

code_to_class = {}

def add_error(name=None, code=None, status=None):
    """Create a new Exception class"""
    if not name or not status or not code:
        raise Exception("Can't create Exception class %s: you must set both name, status and code" % name)
    myexception = type(name, (PyMacaronException, ), {"code": code, "status": status})
    globals()[name] = myexception
    if code in code_to_class:
        raise Exception("ERROR! Exception %s is already defined." % code)
    code_to_class[code] = myexception
    return myexception


add_error('InternalServerError', 'SERVER_ERROR', 500)
add_error('AuthMissingHeaderError', 'AUTHORIZATION_HEADER_MISSING', 401)
add_error('AuthTokenExpiredError', 'TOKEN_EXPIRED', 401)
add_error('AuthInvalidTokenError', 'TOKEN_INVALID', 401)
# add_error('ValidationError', 'INVALID_PARAMETER', 400)


def is_error(o):
    """True if o is a Flask error Response"""
    if hasattr(o, 'status') and int(o.status) >= 300:
        return True
    return False
