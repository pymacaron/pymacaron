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
from klue_microservice.config import get_config

try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack


log = logging.getLogger(__name__)


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

    assert get_config().jwt_secret, "No JWT secret configured for klue-microservice"
    assert get_config().jwt_issuer, "No JWT issuer configured for klue-microservice"
    assert get_config().jwt_audience, "No JWT audience configured for klue-microservice"

    log.info("Validating token, using issuer:%s, audience:%s, secret:%s***" % (
        get_config().jwt_issuer,
        get_config().jwt_audience,
        get_config().jwt_secret[1:8],
    ))

    # First extract the issuer (default to 'klue')
    issuer = get_config().jwt_issuer
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
            get_config().jwt_secret,
            audience=get_config().jwt_audience,
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

def authenticate_http_request(token=None):
    """Validate auth0 tokens passed in the request's header, hence ensuring
    that the user is authenticated. Code copied from:
    https://github.com/auth0/auth0-python/tree/master/examples/flask-api

    Return a PntCommonException if failed to validate authentication.
    Otherwise, return the token's payload (Also stored in stack.top.current_user)
    """

    if token:
        auth = token
    else:
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
    assert user_id, "No user_id passed to generate_token()"
    assert isinstance(data, dict), "generate_token(data=) should be a dictionary"
    assert get_config().jwt_secret, "No JWT secret configured in klue-microservice"

    if not issuer:
        issuer = get_config().jwt_issuer

    assert issuer, "No JWT issuer configured for klue-microservice"

    if expire_in is None:
        expire_in = get_config().jwt_token_timeout

    if iat:
        epoch_now = iat
    else:
        epoch_now = to_epoch(timenow())
    epoch_end = epoch_now + expire_in

    data['iss'] = issuer
    data['sub'] = user_id
    data['aud'] = get_config().jwt_audience
    data['exp'] = epoch_end
    data['iat'] = epoch_now

    headers = {
        "typ": "JWT",
        "alg": "HS256",
        "iss": issuer,
    }

    log.debug("Encoding token with data %s and headers %s (secret:%s****)" % (data, headers, get_config().jwt_secret[0:8]))

    t = jwt.encode(
        data,
        get_config().jwt_secret,
        headers=headers,
    )

    if type(t) is bytes:
        t = t.decode("utf-8")

    return t


@contextmanager
def backend_token(issuer=None, user_id=None, data={}):

    if not issuer:
        issuer = get_config().jwt_issuer
    if not user_id:
        user_id = get_config().default_user_id

    assert issuer, "No JWT issuer configured for klue-microservice"
    assert user_id, "No user_id passed to generate_token()"

    cur_token = ''

    if stack.top is None:
        raise RuntimeError('working outside of request context')

    if not hasattr(stack.top, 'current_user'):
        stack.top.current_user = {}
    else:
        cur_token = stack.top.current_user.get('token', '')

    tmp_token = generate_token(user_id, issuer=issuer, data=data)

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


def get_user_token_data():
    """Return the authenticated user's id, i.e. its auth0 id"""
    return stack.top.current_user


def get_user_token():
    """Return the authenticated user's auth token"""
    if not hasattr(stack.top, 'current_user'):
        return ''
    current_user = stack.top.current_user
    return current_user.get('token', '')


def get_token_issuer():
    """Return the issuer in which this user's token was created"""
    try:
        current_user = stack.top.current_user
        return current_user.get('iss', get_config().jwt_issuer)
    except Exception:
        pass
    return get_config().jwt_issuer
