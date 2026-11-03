"""Safe request/stage diagnostics. Never log frames, templates, tokens or bodies."""
import logging
import re
import time
import uuid
from contextvars import ContextVar
from fastapi import Response
from .router import registration_response

request_id_context=ContextVar("device_biometric_request_id",default="internal")
logger=logging.getLogger("uvicorn.error")


def trace(stage,**fields):
    safe={k:v for k,v in fields.items() if k in {"code","status","elapsed_ms","width","height","action"}}
    logger.info("device_biometric request_id=%s stage=%s %s",request_id_context.get(),stage,
        " ".join(f"{key}={value}" for key,value in safe.items()))


def dispatch(request,response,action,operation,success_status=200):
    supplied=request.headers.get("x-request-id","")
    request_id=supplied if re.fullmatch(r"[a-zA-Z0-9-]{8,64}",supplied) else uuid.uuid4().hex
    response.headers["X-Request-ID"]=request_id
    context=request_id_context.set(request_id)
    started=time.monotonic()
    trace("received",action=action)
    try:
        result=registration_response(operation)
        status=result.status_code if isinstance(result,Response) else success_status
        if isinstance(result,Response):result.headers["X-Request-ID"]=request_id
        trace("response",status=status,elapsed_ms=round((time.monotonic()-started)*1000))
        return result
    except Exception:
        trace("response",status=500,code="UNEXPECTED_ERROR",elapsed_ms=round((time.monotonic()-started)*1000))
        raise
    finally:request_id_context.reset(context)


def adjustment_code(message):
    message=str(message)
    if "exactly one face" in message:return "FACE_COUNT_INVALID"
    if "Center your face" in message:return "FACE_NOT_CENTERED"
    if "farther away" in message:return "FACE_TOO_CLOSE"
    if "Move closer" in message:return "FACE_TOO_SMALL"
    if "could not be read" in message:return "IMAGE_OR_FACE_UNREADABLE"
    return "CAPTURE_ADJUSTMENT"
