# klue-microservice

Easily create and deploy a Flask-based REST api running as a Docker container
on amazon AWS Elastic Beanstalk.

[klue-microservice](https://github.com/erwan-lemonnier/klue-microservice) uses
[klue-client-server](https://github.com/erwan-lemonnier/klue-client-server) to
spawn REST apis into a Flask app. These apis are defined as swagger
specifications, describing all API endpoints in a friendly yaml format, and
binding endpoints to Python methods.

[klue-microservice](https://github.com/erwan-lemonnier/klue-microservice) uses
[klue-aws-toolbox](https://github.com/erwan-lemonnier/klue-aws-toolbox) to
easily deploy the micro service as a Docker container running inside Amazon
Elastic Beanstalk.

With [klue-microservice](https://github.com/erwan-lemonnier/klue-microservice),
you get out-of-the-box:

* A best practice auto-scalling setup on Elastic Beanstalk
* Error handling and reporting around your api endpoints
* Endpoint authentication based on JWT tokens
* Python objects for all your api's json data, with silent
marshalling/unmarshalling and validation

Easy peasy now you happy!

WARNING: klue-microservice is under heavy development (as of 2018-09), being
forked out of stable but proprietary production code. It should get stable
within a few weeks.

## Example

See
[klue-microservice-helloworld](https://github.com/erwan-lemonnier/klue-microservice-helloworld)
for an example of a minimal REST api implemented with klue-microservice, and
ready to deploy on docker containers in Amazon EC2.

## Synopsis

A REST api microservice built with klue-microservice has a directory tree
looking like this:

```
.
├── apis                  # Here you put the swagger specifications both of the apis your
│   └── myservice.yaml    # server is implementing, and of eventual other apis your server
│   └── login.yaml        # is in its turn caling
│   └── profile.yaml      # See klue-client-server for the supported yaml formats.
|
├── myservice             # Here is the code implementing your server api's endpoints
│   └── api.py
│
├── LICENSE               # You should always have a licence :-)
├── README.rst            # and a readme!
|
├── env.secrets           # List of environment variables to pass into containers
|
├── server.py             # Code to start your server, see below
|
└── testaccept            # Acceptance tests! Will be run multiple times
    ├── test_pep8.py      # when deploying to Elastic Beanstalk.
    └── test_version.py   # -> Here to test the generic /ping, /version and /auth/version
                          # endpoints
```

And your server simply looks like:

```python
import os
import sys
import logging
from flask import Flask
from klue_microservice import API, letsgo


log = logging.getLogger(__name__)

# Create a flask app. Here you could add custom routes, etc.
app = Flask(__name__)


def start(port=80, debug=False):

    # Your swagger api files are under ./apis, but you could have them anywhere
    # else really.
    here = os.path.dirname(os.path.realpath(__file__))
    path_apis = os.path.join(here, "apis")

    # Tell klue-microservice to spawn apis inside this Flask app.  Set the
    # server's listening port, whether Flask debug mode is on or not, and, if
    # some of your endpoints use klue-microservice's builtin JWT token-based
    # authentication scheme, initialise a jwt token and audience
    api = API(
        app,
        port=port,
        debug=debug,
        jwt_secret=os.environ.get("KLUE_JWT_SECRET"),
        jwt_audience=os.environ.get("KLUE_JWT_AUDIENCE"),
    )

    # Find all swagger files and load them into klue-client-server
    api.load_apis(path_apis)

    # Start the Flask app and serve all endpoints defined in
    # apis/myservice.yaml
    api.start(serve="myservice")


# Run the Flask server, either as standalone in a terminal,
# or via gunicorn
letsgo(__name__, callback=start)
```

You start your server in a terminal like this:

```bash
cd projectroot
python server.py --port 8080
```

You run acceptance tests against the above server like this:

```bash
cd projectroot
run_acceptance_tests --local
```

## Deep dive

### Installing

```
pip install klue-microservice
```

### Swagger specifications

All api endpoints that your service needs, both those it implements and those
it calls as a client, are to be defined as swagger specifications in the format
supported by
[klue-client-server](https://github.com/erwan-lemonnier/klue-client-server).
klue-client-server uses [Bravado](https://github.com/Yelp/bravado) to handle
marshalling/unmarshalling and validation of your api objects to and from json,
and does all the magic of spawning client and server stubs for all api
endpoints, as well as supporting optional database serialization for your api
objects.

### JWT authentication

TODO

### Error handling and reporting

TODO

### Acceptance tests

TODO

### Elastic Beanstalk configuration

TODO

### env.secrets

The file 'env.secrets' contains a list of environemt variables that will be
passed to Elastic Beanstalk and loaded into containers. This allows you to pass
secrets to the container without commiting them inside your code.

In the example above, 'env.secrets' would contain at least:

```
$ cat env.secrets
# Name of environment variables to pass into the docker containers
KLUE_JWT_SECRET
KLUE_JWT_AUDIENCE

```

### Built-in endpoints

The following endpoints are built-in into every klue-microservice instance, based
on [this swagger spec](https://github.com/erwan-lemonnier/klue-microservice/blob/master/klue_microservice/ping.yaml):

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
