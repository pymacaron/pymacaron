![pymacaron logo](https://github.com/pymacaron/pymacaron/blob/master/logo/pymacaron-logo-small.png)

# PyMacaron

Python microservice framework based on Flask, OpenAPI, gunicorn and celery, deployable on GKE and Beanstalk

PyMacaron's documentation is available at
[http://pymacaron.com/](http://pymacaron.com/).

This page dives deeper into internal implementation details.

## Deep dive

### Built-in endpoints

The following endpoints are built-in into every pymacaron instance, based
on [this swagger spec](https://github.com/pymacaron/pymacaron/blob/master/pymacaron/ping.yaml):

```
# Assuming you did in a separate terminal:
# $ python server.py --port 8080

$ curl http://127.0.0.1:8080/ping
{}

$ curl http://127.0.0.1:8080/version
{
  "container": "",
  "name": "ping",
  "version": "0.0.1"
}

$ curl http://127.0.0.1:8080/auth/version
{
  "error_description": "There is no Authorization header in the HTTP request",
  "error_id": "17f900c8-b456-4a64-8b2b-83c7d36353f6",
  "status": 401,
  "error": "AUTHORIZATION_HEADER_MISSING"
}

$ curl -H "Authorization: Bearer eyJpc3M[...]y8kNg" http://127.0.0.1:8080/auth/version
{
  "container": "",
  "name": "ping",
  "version": "0.0.1"
}

```


### Loading api clients from a standalone script

It may come very handy within a standalone script to be able to call REST apis
through the pymacaron framework, to get object marshalling and error
handling out of the box. It is done as follows:

```python
import flask
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.exceptions import is_error
from pymacaron import load_clients

# Declare a Flask app and mock its context
app = flask.Flask(__name__)
with app.test_request_context(''):

    # Then load client libraries against a given set of libraries
    api = API(app)
    api.load_clients(apis=['login', 'search'])

    # And you can now call those apis seamlessly!
    result = ApiPool.login.client.do_login(
        ApiPool.login.model.LoginData(
            name='foobar',
            password='youdontwanttoknow'
        )
    )

    if is_error(result):
        log.error("Oops. Failed to login user")
```

## Author

Erwan Lemonnier<br/>
[github.com/pymacaron](https://github.com/pymacaron)</br>
[github.com/erwan-lemonnier](https://github.com/erwan-lemonnier)<br/>
[www.linkedin.com/in/erwan-lemonnier/](https://www.linkedin.com/in/erwan-lemonnier/)