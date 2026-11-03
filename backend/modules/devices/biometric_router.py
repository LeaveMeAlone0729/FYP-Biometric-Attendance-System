"""Device-owned biometric tests. No attendance or trusted-approval issuance."""
from fastapi import APIRouter,Depends,File,UploadFile,Request,Response
from starlette.concurrency import run_in_threadpool
from api.dependencies import authenticated,get_context,get_db
from .biometric_diagnostics import dispatch
from .biometric_service import DeviceBiometricService
from .biometric_schemas import DeviceBiometricResult
from .pending_schemas import DeviceApprovalRequest
from .schemas import DeviceErrorResponse

router=APIRouter(prefix="/api/v1/device-approvals",tags=["Untrusted device biometric checks"],responses={code:{"model":DeviceErrorResponse} for code in (403,404,409,410,422,429,503)})


def service(context=Depends(get_context)):return DeviceBiometricService(context)


@router.post("",status_code=201,response_model=DeviceBiometricResult)
def create(data:DeviceApprovalRequest,request:Request,response:Response,identity=Depends(authenticated),db=Depends(get_db,scope="function"),bio=Depends(service)):
    student,auth=identity
    return dispatch(request,response,"create",lambda:bio.create(db,student,auth,data.pending_registration_id),201)


@router.get("/{approval_id}",response_model=DeviceBiometricResult)
def status(approval_id:str,request:Request,response:Response,identity=Depends(authenticated),db=Depends(get_db,scope="function"),bio=Depends(service)):
    student,auth=identity
    return dispatch(request,response,"status",lambda:bio.status(db,student,auth,approval_id))


@router.post("/{approval_id}/face",response_model=DeviceBiometricResult)
async def face(approval_id:str,request:Request,response:Response,file:UploadFile=File(...),identity=Depends(authenticated),db=Depends(get_db,scope="function"),bio=Depends(service)):
    student,auth=identity
    if set((await request.form()).keys()) != {"file"}:
        return await run_in_threadpool(dispatch,request,response,"invalid_frame",lambda:bio.fail(db,student,422,"INVALID_FRAME_INPUT","Send only a fresh camera file; biometric flags are not accepted."))
    return await run_in_threadpool(dispatch,request,response,"face",lambda:bio.face(db,student,auth,approval_id,file))


@router.post("/{approval_id}/liveness/frame",response_model=DeviceBiometricResult)
async def liveness(approval_id:str,request:Request,response:Response,file:UploadFile=File(...),identity=Depends(authenticated),db=Depends(get_db,scope="function"),bio=Depends(service)):
    student,auth=identity
    if set((await request.form()).keys()) != {"file"}:
        return await run_in_threadpool(dispatch,request,response,"invalid_frame",lambda:bio.fail(db,student,422,"INVALID_FRAME_INPUT","Send only a fresh camera file; biometric flags are not accepted."))
    return await run_in_threadpool(dispatch,request,response,"liveness",lambda:bio.liveness(db,student,auth,approval_id,file))
