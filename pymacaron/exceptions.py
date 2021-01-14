from pymacaron.log import pymlogger
from pprint import pformat
from flask import jsonify
from pymacaron_core.exceptions import ValidationError, PyMacaronCoreException
from pymacaron_core.models import get_model


log = pymlogger(__name__)


class PyMacaronException(PyMacaronCoreException):
    code = 'UNKNOWN_EXCEPTION'
    status = 500
    error_id = None
    user_message = None
    error_caught = None

    def tell_user(self, msg):
        self.user_message = msg
        return self

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
        e = get_model('Error')(
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


add_error('UnhandledServerError', 'UNHANDLED_SERVER_ERROR', 500)
add_error('InternalServerError', 'SERVER_ERROR', 500)
add_error('AuthMissingHeaderError', 'AUTHORIZATION_HEADER_MISSING', 401)
add_error('AuthTokenExpiredError', 'TOKEN_EXPIRED', 401)
add_error('AuthInvalidTokenError', 'TOKEN_INVALID', 401)
add_error('ValidationError', 'INVALID_PARAMETER', 400)

#
# Manipulate various error objects
#

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
    elif isinstance(error, PyMacaronException):
        return error.http_reply()
    else:
        return PyMacaronException("Caught un-mapped error: %s" % error).http_reply()


def is_error(o):
    """True if o is an instance of a swagger Error model or a flask Response of
    an error model"""
    if hasattr(o, 'error') and hasattr(o, 'error_description') and hasattr(o, 'status'):
        return True
    return False


def format_error(e):
    """Take an exception caught within pymacaron_core and turn it into a
    bravado-core Error instance
    """

    if isinstance(e, PyMacaronException):
        return e.to_model()

    if isinstance(e, PyMacaronCoreException) and e.__class__.__name__ == 'ValidationError':
        return ValidationError(str(e)).to_model()

    # Turn this exception into a PyMacaron Error model
    return UnhandledServerError(str(e)).to_model()


def raise_error(e):
    """Take a bravado-core Error model and raise it as an exception"""
    code = e.error
    if code in code_to_class:
        raise code_to_class[code](e.error_description)
    else:
        raise InternalServerError(e.error_description)
