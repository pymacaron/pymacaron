import logging
from klue.swagger.apipool import ApiPool
from flask_cors import cross_origin


log = logging.getLogger(__name__)


@cross_origin(headers=['Content-Type', 'Authorization'])
def do_ping():
    log.debug("Replying ping:ok")
    return "{}"
