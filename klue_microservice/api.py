import logging
import pprint
from klue.swagger.apipool import ApiPool
from klue_microservice.utils import get_container_version


log = logging.getLogger(__name__)


def do_ping():
    log.debug("Replying ping:ok")
    v = ApiPool.ping.model.Version()
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
