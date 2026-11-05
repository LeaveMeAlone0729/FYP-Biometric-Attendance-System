from datetime import datetime
from typing import Literal
from fastapi import APIRouter,Depends,Request
from pydantic import BaseModel,ConfigDict,Field
from api.dependencies import authenticated,get_context,get_db
from modules.devices.router import registration_response
from .service import AttendanceAuthorizationService

class AttendanceDeviceRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    attendance_challenge_id: str=Field(min_length=1,max_length=64)
    public_key_fingerprint: str=Field(pattern=r'^[0-9a-f]{64}$')

class AttendanceDeviceResponse(BaseModel):
    success: Literal[True]=True
    challenge_id: str
    attendance_challenge_id: str
    attendance_session_id: int
    device_id: str
    slot_number: Literal[1,2]
    public_key_fingerprint: str
    operation: Literal['attendance_authorization']
    algorithm: Literal['ECDSA_P256_SHA256']
    signature_encoding: Literal['base64-DER']
    signing_payload: str
    expires_at: datetime

router=APIRouter(prefix='/api/v1/attendance',tags=['Final attendance authorization'])

@router.post('/device-challenges',status_code=201,response_model=AttendanceDeviceResponse)
def challenge(data:AttendanceDeviceRequest,identity=Depends(authenticated),db=Depends(get_db,scope='function'),context=Depends(get_context)):
    student,auth=identity
    return registration_response(lambda:AttendanceAuthorizationService(context).issue(db,student,auth,data.attendance_challenge_id,data.public_key_fingerprint))


class AttendancePreflightProof(BaseModel):
    model_config=ConfigDict(extra='forbid')
    attendance_challenge_id: str=Field(min_length=1,max_length=64)
    challenge_id: str=Field(min_length=1,max_length=64)
    signature: str=Field(min_length=1,max_length=256)

class AttendancePreflightChallengeResponse(AttendanceDeviceResponse):
    operation: Literal['attendance_preflight']

@router.post('/preflight-challenges',status_code=201,response_model=AttendancePreflightChallengeResponse)
def preflight_challenge(data:AttendanceDeviceRequest,request:Request,identity=Depends(authenticated),db=Depends(get_db,scope='function'),context=Depends(get_context)):
    student,auth=identity
    return registration_response(lambda:AttendanceAuthorizationService(context).issue(db,student,auth,data.attendance_challenge_id,data.public_key_fingerprint,preflight=True,scope=request.scope))

class AttendancePreflightResponse(BaseModel):
    success: Literal[True]
    result: Literal['PASS']
    attendance_authorized: Literal[False]
    attendance_challenge_id: str
    device_id: str
    network_verification_id: int

@router.post('/preflight',response_model=AttendancePreflightResponse)
def preflight(data:AttendancePreflightProof,request:Request,identity=Depends(authenticated),db=Depends(get_db,scope='function'),context=Depends(get_context)):
    student,auth=identity
    return registration_response(lambda:AttendanceAuthorizationService(context).preflight(db,student,auth,data.attendance_challenge_id,data.challenge_id,data.signature,request.scope))
