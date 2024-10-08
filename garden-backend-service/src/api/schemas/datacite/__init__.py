"""
This module exposes a few useful pydantic models for dealing with the datacite
rest api from the automatically generated `_full_schema` module. The
automatically generated module was built from
https://github.com/datacite/lupo/blob/master/openapi.yaml using the
`datamodel-codegen` cli tool for pydantic.

In some cases, the actual behavior of the datacite API might not correspond to
the auto-generated schema. It's fine to tweak the auto-generated models in those cases,
otherwise if we want to change the behavior of some sub-field prefer inheriting with our own
pydantic class (like below).
"""

from ._full_schema import Data3, DoiAttributes
from ._full_schema import Doi as _Doi


class DoiData(Data3):
    # inherits all fields from auto-generated schema model
    # but makes attributes field non-optional in request body
    attributes: DoiAttributes


class Doi(_Doi):
    # make data field non-optional
    data: DoiData


__all__ = ["Doi", "DoiAttributes"]
