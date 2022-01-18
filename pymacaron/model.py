import ujson
from datetime import datetime
from pymacaron.log import pymlogger


log = pymlogger(__name__)


class PymacaronBaseModel(object):
    """The base class from which all pymacaron model classes inherit. Some of these
    methods are redundant with pydantic, but kept for backward compatibility
    with code using older versions of pymacaron.

    """

    # See https://pydantic-docs.helpmanual.io/usage/exporting_models/ about ujson vs orjson
    class Config:
        # Do type validation each time a property is set
        validate_assignment = True

        json_loads = ujson.loads
        json_encoders = {
            # TODO: make the datetime encoding configurable
            datetime: lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }


    def __str__(self):
        """Return a generic string representation of a pymacaron model instance"""
        return f'{self.get_model_name()}(self.dict())'


    def __set_nullable(self):
        # Set all x-nullable model properties to None, recursively
        for k in self.get_property_names():
            if k in self.get_nullable_properties():
                setattr(self, k, None)
            else:
                v = getattr(self, k)
                if isinstance(v, PymacaronBaseModel):
                    v.__set_nullable()
                elif type(v) is list:
                    for vv in v:
                        if isinstance(vv, PymacaronBaseModel):
                            vv.__set_nullable()


    def __prune_none(self, j, o, keep_nullable=False):
        # Remove all None keys in a dictionary, recursively
        for k in list(j.keys()):
            v = j[k]
            if v is None:
                if keep_nullable and k in o.get_nullable_properties():
                    pass
                else:
                    del j[k]
            elif type(v) is dict:
                self.__prune_none(v, getattr(o, k), keep_nullable=keep_nullable)
            elif type(v) is list:
                for i in range(len(v)):
                    jj = v[i]
                    if type(jj) is dict:
                        self.__prune_none(jj, getattr(o, k)[i], keep_nullable=keep_nullable)


    def to_json(self, keep_datetime=False, keep_nullable=False):
        """Return a json dictionary representation of this PyMacaron object"""

        if keep_datetime:
            j = self.dict()
        else:
            # Else let pydantic serialize datetimes to json and back
            s = self.json()
            j = ujson.loads(s)

        # pydantic sets all undefined properties to None. We want to remove them, except
        # optionally those that are defined as x-nullable in swagger.
        self.__prune_none(j, self, keep_nullable=keep_nullable)

        return j


    @classmethod
    def from_json(cls, j):
        """Take a json dictionary and return a model instance"""
        return cls.parse_obj(j)


    def clone(self):
        # Deprecated: should use pydantic.copy() instead
        return self.copy()


    def get_model_name(self):
        """Return the name of the OpenAPI schema object describing this pymacaron Model instance"""
        return type(self).__name__


    def get_model_api(self):
        """Return the name of the api to which this model belongs"""
        raise Exception("Should be overriden in model declaration")


    def get_property_names(self):
        """Return the names of all of the model's properties"""
        raise Exception("Should be overriden in model declaration")
