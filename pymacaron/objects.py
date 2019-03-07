import logging
from pymacaron_core.swagger.apipool import apis
from pymacaron.exceptions import PyMacaronException
from bravado_core.model import Model


log = logging.getLogger(__name__)


def get_model_instantiator(name):
    def init_model(self, *args, **kwargs):
        log.info("Instantiating api model %s" % name)
        for api_name, api in apis.items():
            log.debug("Looking for %s in %s" % (name, api_name))
            log.debug("models are %s (%s)" % (type(api.model), dir(api.model)))
            if api.model and hasattr(api.model, name):
                log.debug("Instantiating object %s from API %s" % (name, api_name))
                m = getattr(api.model, name)

                # Now, monkey-patch all of m's methods into self
                o = m(*args, **kwargs)

                # Patch self into a swagger object
                cls = self.__class__
                self.__class__ = cls.__class__(cls.__name__ + "WithModel", (cls, Model), {})

                log.debug("Got: type(%s) %s" % (type(o), o))
                for s in dir(o):

                    if s not in ('__heap__'):
                        log.debug("Patching in %s" % s)
                        setattr(self, s, getattr(o, s))

                return

        raise PyMacaronException("Cannot find swagger definition for object '%s' in PyMacaron apis" % name)

        # TODO: monkey patch persistence if needed
        #

    return init_model


# TODO: add to_jon() from_json() to instance
# TODO: add save/load if x-persist

types = {}

class SwaggerObjects(object):

    def __getattr__(self, name):
        global types
        if not name in types:
            log.info("Creating class object %s" % name)
            types[name] = type(
                'Swagger' + name,
                (object, ),
                {
                    '__init__': get_model_instantiator(name),
                },
            )
        return types[name]
