"""Official Python client for the EnCarAPI — Korean car data API (Encar.com).

Get an API key at https://encarapi.com (a key is required).
"""
from .client import EnCarAPI, EnCarAPIError, MissingApiKeyError

__version__ = "0.1.0"
__all__ = ["EnCarAPI", "EnCarAPIError", "MissingApiKeyError", "__version__"]
