"""Consistent public error responses without raw inputs or biometric data."""

import logging

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


def register_error_handlers(app):
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo passwords, biometric data, or whole request bodies in errors.
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Check the fields and try again.",
                "fields": [
                    {"field": str(e["loc"][-1]), "message": e["msg"]}
                    for e in exc.errors()
                ],
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": str(exc.detail)},
            headers=exc.headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logging.error("Database operation failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "The database is unavailable. Please try again.",
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logging.error("Request failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Verification is temporarily unavailable. Please try again.",
            },
        )
