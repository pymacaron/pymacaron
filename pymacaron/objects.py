import logging
from pymacaron_core.swagger.apipool import apis
from pymacaron.exceptions import PyMacaronException


log = logging.getLogger(__name__)


def get_model_instantiator(name):
    def dynamic_instantiator(*args, **kwargs):
        for api_name, api in apis.items():
            log.debug("Looking for %s in %s" % (name, api_name))
            log.debug("models are %s (%s)" % (type(api.model), dir(api.model)))
            if api.model and hasattr(api.model, name):
                log.debug("Instantiating object %s from API %s" % (name, api_name))
                m = getattr(api.model, name)
                return m(*args, **kwargs)
        raise PyMacaronException("Cannot find swagger definition for object '%s' in PyMacaron apis" % name)
    return dynamic_instantiator
