"""Public demo health and camera configuration."""

from app_time import iso_time
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from modules.biometrics.constants import REQUIRED_LIVENESS_FRAMES

from . import API_VERSION
from .context import AppContext
from .dependencies import get_context

router = APIRouter(tags=["Demo system"])


@router.get("/")
def home(request: Request, context: AppContext = Depends(get_context)):
    if getattr(request.app.state, 'staff_portal_enabled', False):
        return RedirectResponse('/portal/', status_code=303)
    return health(context)


@router.get('/health')
def health(context: AppContext = Depends(get_context)):
    return {
        "message": "Backend running",
        "version": API_VERSION,
        "demo_mode": context.settings.demo_mode,
    }


@router.get("/config")
def config(context: AppContext = Depends(get_context)):
    return {
        "demo_mode": context.settings.demo_mode,
        "server_time": iso_time(context.now(), context.settings),
        "network_ble_test_mode": context.settings.network_ble_test_mode,
        "verification_seconds": context.settings.challenge_seconds,
        "required_frames": REQUIRED_LIVENESS_FRAMES,
    }
