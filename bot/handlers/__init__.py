from .admin import router as admin_router
from .admin_support import router as admin_support_router
from .default import router as default_router
from .errors import router as errors_router
from .inline import router as inline_router
from .operator import router as operator_router
from .phasalo_drollery import router as phasalo_drollery_router
from .relay import router as relay_router

__all__ = [
    'admin_router',
    'admin_support_router',
    'default_router',
    'errors_router',
    'inline_router',
    'operator_router',
    'phasalo_drollery_router',
    'relay_router',
]
