"""Official Python client for EnCarAPI: Korean used car data (Encar, KB Chachacha,
K Car) and Chinese used car data (Dongchedi, Che168) in one package.

Get an API key at https://encarapi.com (a key is required).
"""
from .client import (
    ChinaCarAPI,
    ChinaCarAPIError,
    ChinaClient,
    DiagnosisBulkResponse,
    DiagnosisItem,
    DiagnosisReport,
    DiagnosisResponse,
    EnCarAPI,
    EnCarAPIError,
    HistoryEvent,
    HistoryFlags,
    HistoryMileageReading,
    HistoryOwnershipPeriod,
    KoreaClient,
    MissingApiKeyError,
    VehicleHistory,
)

__version__ = "1.11.0"
__all__ = [
    "EnCarAPI",
    "ChinaCarAPI",
    "KoreaClient",
    "ChinaClient",
    "EnCarAPIError",
    "ChinaCarAPIError",
    "MissingApiKeyError",
    "DiagnosisItem",
    "DiagnosisReport",
    "DiagnosisResponse",
    "DiagnosisBulkResponse",
    "HistoryMileageReading",
    "HistoryOwnershipPeriod",
    "HistoryFlags",
    "HistoryEvent",
    "VehicleHistory",
    "__version__",
]
