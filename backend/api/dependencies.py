"""Common authentication and transaction dependencies for all API routers."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models import AuthSession, Student
from security import digest

from .context import AppContext

bearer = HTTPBearer(auto_error=False)


def get_context(request: Request) -> AppContext:
    return request.app.state.context


def get_db(context: AppContext = Depends(get_context)):
    # Commit before the response is sent; never return an uncommitted success.
    with context.sessions() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def authenticated(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    context: AppContext = Depends(get_context),
    db=Depends(get_db, scope="function"),
):
    if credentials is None:
        raise HTTPException(401, "Please sign in to continue.")
    auth = db.get(AuthSession, digest(credentials.credentials))
    if auth is None or auth.expires_at <= context.now():
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    student = db.get(Student, auth.student_id)
    if student is None or student.account_status != "active":
        raise HTTPException(403, "This account is not active.")
    return student, auth
