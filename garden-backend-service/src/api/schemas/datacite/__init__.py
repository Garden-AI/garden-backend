from .full_schema import Doi as _Doi
from .full_schema import Data3, DoiAttributes


class DoiData(Data3):
    # inherits all fields from auto-generated schema model
    # but makes attributes field non-optional in request body
    attributes: DoiAttributes


class Doi(_Doi):
    data: DoiData


__all__ = ["Doi", "DoiAttributes"]
