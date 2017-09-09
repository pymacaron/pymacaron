import pprint
import jwt
import base64
import logging
from urllib.parse import unquote_plus
from contextlib import contextmanager
from functools import wraps
from flask import request
from klue_microservice.exceptions import AuthInvalidTokenError, AuthTokenExpiredError
from klue_microservice.exceptions import AuthMissingHeaderError, KlueMicroServiceException
from klue_microservice.utils import timenow, to_epoch

try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack


log = logging.getLogger(__name__)


#
# Configuration
#

DEFAULT_JWT_ISSUER = None
DEFAULT_JWT_AUDIENCE = 'HFhAcAZ1VdRt0anWpefDfGYnW8F79uLF'
DEFAULT_USER_ID = None
DEFAULT_TOKEN_TIMEOUT = 86400
# Automatically renew token if expires in less than this time (in sec) 3 hours
# in sec
DEFAULT_TOKEN_RENEW_AFTER = 10800
DEFAULT_JWT_SECRET = None

def set_jwt_defaults(issuer=None, user_id=None, token_timeout=None, token_renew=None, secret=None, audience=None):
    if issuer:
        global DEFAULT_JWT_ISSUER
        log.info("Setting JWT issuer to %s" % issuer)
        DEFAULT_JWT_ISSUER = issuer
    if user_id:
        global DEFAULT_USER_ID
        log.info("Setting JWT default user_id to %s" % user_id)
        DEFAULT_USER_ID = user_id
    if token_timeout:
        global DEFAULT_TOKEN_TIMEOUT
        log.info("Setting JWT timeout to %s" % token_timeout)
        DEFAULT_TOKEN_TIMEOUT = token_timeout
    if token_renew:
        global DEFAULT_TOKEN_RENEW_AFTER
        log.info("Setting JWT renew timeout to %s" % token_renew)
        DEFAULT_TOKEN_RENEW_AFTER = token_renew
    if secret:
        global DEFAULT_JWT_SECRET
        log.info("Setting JWT secret %s*****.." % secret[0:5])
        DEFAULT_JWT_SECRET = base64.b64decode(secret.replace("_", "/").replace("-", "+"))
    if audience:
        global DEFAULT_JWT_AUDIENCE
        log.info("Setting JWT audience: %s" % audience)
        DEFAULT_JWT_AUDIENCE = audience


#
# Decorators used to add authentication to endpoints in swagger specs
#

def requires_auth(f):
    """A decorator for flask api methods that validates auth0 tokens, hence ensuring
    that the user is authenticated. Code coped from:
    https://github.com/auth0/auth0-python/tree/master/examples/flask-api
    """

    @wraps(f)
    def requires_auth_decorator(*args, **kwargs):

        try:
            authenticate_http_request()
        except KlueMicroServiceException as e:
            return e.http_reply()

        return f(*args, **kwargs)

    return requires_auth_decorator


def add_auth(f):
    """A decorator that adds the authentication header to requests arguments"""

    def add_auth_decorator(*args, **kwargs):
        token = get_user_token()
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        kwargs['headers']['Authorization'] = "Bearer %s" % token
        return f(*args, **kwargs)

    return add_auth_decorator


#
# Get and validate a token
#

def load_auth_token(token, load=True):
    """Validate an auth0 token. Returns the token's payload, or an exception
    of the type:"""

    assert DEFAULT_JWT_SECRET

    log.info("Extracting issuer of token")

    # First extract the issuer (default to 'klue')
    issuer = DEFAULT_JWT_ISSUER
    try:
        headers = jwt.get_unverified_header(token)
    except jwt.DecodeError:
        raise AuthInvalidTokenError('token signature is invalid')

    log.debug("Token has headers %s" % headers)

    if 'iss' in headers:
        issuer = headers['iss']

    # Then validate the token against this issuer
    log.info("Validating token in issuer %s" % issuer)
    try:
        payload = jwt.decode(
            token,
            DEFAULT_JWT_SECRET,
            audience=DEFAULT_JWT_AUDIENCE,
            # Allow for a time difference of up to 5min (300sec)
            leeway=300
        )
    except jwt.ExpiredSignature:
        raise AuthTokenExpiredError('Auth token is expired')
    except jwt.InvalidAudienceError:
        raise AuthInvalidTokenError('incorrect audience')
    except jwt.DecodeError:
        raise AuthInvalidTokenError('token signature is invalid')
    except jwt.InvalidIssuedAtError:
        raise AuthInvalidTokenError('Token was issued in the future')

    # Save payload to stack
    payload['token'] = token
    payload['iss'] = issuer

    if load:
        stack.top.current_user = payload

    return payload

def authenticate_http_request():
    """Validate auth0 tokens passed in the request's header, hence ensuring
    that the user is authenticated. Code copied from:
    https://github.com/auth0/auth0-python/tree/master/examples/flask-api

    Return a PntCommonException if failed to validate authentication.
    Otherwise, return the token's payload (Also stored in stack.top.current_user)
    """


    auth = request.headers.get('Authorization', None)

    if not auth:
        auth = request.cookies.get('token', None)
        if auth:
            auth = unquote_plus(auth)

    log.debug("Validating Auth header [%s]" % auth)

    if not auth:
        raise AuthMissingHeaderError('There is no Authorization header in the HTTP request')

    parts = auth.split()

    if parts[0].lower() != 'bearer':
        raise AuthInvalidTokenError('Authorization header must start with Bearer')
    elif len(parts) == 1:
        raise AuthInvalidTokenError('Token not found in Authorization header')
    elif len(parts) > 2:
        raise AuthInvalidTokenError('Authorization header must be Bearer + \s + token')

    token = parts[1]

    return load_auth_token(token)

#
# Generate tokens
#

def generate_token(user_id, expire_in=None, data={}, issuer=None, iat=None):
    """Generate a new JWT token for this user_id. Default expiration date
    is 1 year from creation time"""
    assert user_id
    assert isinstance(data, dict)
    assert DEFAULT_JWT_SECRET

    if not issuer:
        issuer = DEFAULT_JWT_ISSUER

    assert issuer

    if expire_in is None:
        expire_in = DEFAULT_TOKEN_TIMEOUT

    if iat:
        epoch_now = iat
    else:
        epoch_now = to_epoch(timenow())
    epoch_end = epoch_now + expire_in

    data['iss'] = issuer
    data['sub'] = user_id
    data['aud'] = DEFAULT_JWT_AUDIENCE
    data['exp'] = epoch_end
    data['iat'] = epoch_now

    headers = {
        "typ": "JWT",
        "alg": "HS256",
        "iss": issuer,
    }

    log.debug("Encoding token with data %s and headers %s" % (data, headers))

    t = jwt.encode(
        data,
        DEFAULT_JWT_SECRET,
        headers=headers,
    )

    if type(t) is bytes:
        t = t.decode("utf-8")

    return t


@contextmanager
def backend_token(issuer=None, user_id=None):

    if not issuer:
        issuer = DEFAULT_JWT_ISSUER
    if not user_id:
        user_id = DEFAULT_USER_ID

    assert issuer
    assert user_id

    cur_token = ''

    if stack.top is None:
        raise RuntimeError('working outside of request context')

    if not hasattr(stack.top, 'current_user'):
        stack.top.current_user = {}
    else:
        cur_token = stack.top.current_user.get('token', '')

    tmp_token = generate_token(user_id, issuer=issuer)

    log.debug("Temporarily using custom token for %s and issuer %s: %s" % (user_id, issuer, tmp_token))
    stack.top.current_user['token'] = tmp_token
    yield tmp_token
    log.debug("Restoring token %s" % cur_token)
    stack.top.current_user['token'] = cur_token


#
# Access token data during runtime
#


def get_userid():
    """Return the authenticated user's id, i.e. its auth0 id"""
    current_user = stack.top.current_user
    return current_user.get('sub', '')


def get_user_token():
    """Return the authenticated user's auth token"""
    current_user = stack.top.current_user
    return current_user.get('token', '')


def get_token_issuer():
    """Return the issuer in which this user's token was created"""
    try:
        current_user = stack.top.current_user
        return current_user.get('iss', DEFAULT_JWT_ISSUER)
    except Exception:
        pass
    return DEFAULT_JWT_ISSUER
