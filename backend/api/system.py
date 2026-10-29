"""Public demo health and camera configuration."""

from config import iso_time
from fastapi import APIRouter, Depends
from modules.biometrics.constants import REQUIRED_LIVENESS_FRAMES

from . import API_VERSION
from .context import AppContext
from .dependencies import get_context

router = APIRouter(tags=["Demo system"])


@router.get("/")
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
        "verification_seconds": context.settings.challenge_seconds,
        "required_frames": REQUIRED_LIVENESS_FRAMES,
    }
