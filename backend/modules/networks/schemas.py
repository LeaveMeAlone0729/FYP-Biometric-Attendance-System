from datetime import datetime
from typing import Literal
from pydantic import BaseModel,ConfigDict

class NetworkCheckRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')

class NetworkCheckResult(BaseModel):
    success: Literal[True]=True
    verification_id: int
    result: Literal['PASS','FAIL']
    reason_code: str
    message: str
    source_ip: str | None
    matched_policy_id: str | None
    matched_policy_name: str | None
    verified_at: datetime
    operation: Literal['network_diagnostic']='network_diagnostic'
    attendance_authorized: Literal[False]=False
