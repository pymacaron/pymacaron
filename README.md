# klue-microservice

Easily create and deploy a Flask-based REST api running as a Docker container
on amazon AWS Elastic Beanstalk.

[klue-microservice](https://github.com/erwan-lemonnier/klue-microservice) uses
[klue-client-server](https://github.com/erwan-lemonnier/klue-client-server) to
spawn REST apis into a Flask app. These apis are defined as swagger
specifications, defining all API endpoints in a friendly yaml format, and
binding endpoints to Python methods.

[klue-microservice](https://github.com/erwan-lemonnier/klue-microservice) uses
[klue-aws-toolbox](https://github.com/erwan-lemonnier/klue-aws-toolbox) to
easily deploy the micro service as a Docker container running inside Amazon
Elastic Beanstalk.

With [klue-microservice](https://github.com/erwan-lemonnier/klue-microservice),
you get out-of-the-box:

* a best practice auto-scalling setup on Elastic Beanstalk

* error handling and reporting around your api endpoints

* endpoint authentication based on JWT tokens

* Python objects for all you api's json data, with silent
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
├── server.py             # Code to start your server, see below
|
└── testaccept            # Acceptance tests! Will be run multiple times
    ├── test_pep8.py      # when deploying to Elastic Beanstalk.
    └── test_version.py   # -> Here to test the generic /ping, /version and /auth/version
                          # endpoints
```

And your server simply looks like:

```python
import click
import os
import sys
import logging
from flask import Flask
from klue_microservice import API


log = logging.getLogger(__name__)


@click.command()
@click.option('--port', help="Set server listening port (default: 80)", default=80)
@click.option('--debug/--no-debug', default=True)
def main(port, debug):
    """"""

    # Your swagger api files are under ./apis, but you could have them anywhere
    # else really.
    here = os.path.dirname(os.path.realpath(__file__))
    path_apis = os.path.join(here, "apis")

    # Create a flask app. Here you could add custom routes, etc.
    app = Flask(__name__)

    # Tell klue-microservice to spawn apis inside this Flask app.  Set th
    # server's listening port, whether Flask debug is on or not, and if some of
    # your endpoints use klue-microservice's builtin JWT token-based
    # authentication scheme, initialise a wt token and audience
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


if __name__ == "__main__":
    main()

# In docker containers, your Flask app will run in gunicorn
if os.path.basename(sys.argv[0]) == 'gunicorn':
    start()

```

And you start your server in a terminal like this:

```bash
cd projectroot
python server.py --port 8080
```

And run acceptance tests against the above server like this:

```bash
cd projectroot
run_acceptance_tests --local
```

## Deep dive

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

### Acceptance tests

TODO

### Elastic Beanstalk configuration

TODO