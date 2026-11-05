"""Student diagnostic only; source IP and policy decisions are server-owned."""
from fastapi import APIRouter,Depends,Request,HTTPException
from sqlalchemy.exc import SQLAlchemyError
from api.dependencies import authenticated,get_context,get_db
from api.schemas import ERROR_RESPONSES
from .schemas import NetworkCheckRequest,NetworkCheckResult
from .service import NetworkVerificationService

router=APIRouter(prefix='/api/v1/networks',tags=['Network verification'],responses=ERROR_RESPONSES)

@router.post('/verifications',response_model=NetworkCheckResult)
def verify_network(data:NetworkCheckRequest,request:Request,identity=Depends(authenticated),db=Depends(get_db,scope='function'),context=Depends(get_context)):
    student,auth=identity
    try:return NetworkVerificationService(context).verify(db,student,auth,request.scope)
    except SQLAlchemyError as exc:
        # Never report PASS when policy lookup/audit persistence is unavailable.
        raise HTTPException(503,'Network verification is unavailable. Check backend database connectivity and migrations.') from exc
