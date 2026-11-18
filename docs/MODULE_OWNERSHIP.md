# Module ownership

Facial recognition and liveness module owner: **Chew Zhexuan**.

Keep teammate-owned account, device, network, department and attendance business
logic within its agreed API boundary. Biometric changes in shared screens use
the marked imports, callbacks and UI sections.

| Area | Backend | Flutter / Android |
| --- | --- | --- |
| Face matching and liveness | `backend/modules/biometrics/` | `frontend/lib/modules/biometrics/` |
| Device keys, registration and replacement | `backend/modules/devices/` | `frontend/lib/modules/devices/`; `DeviceKeyStoreChannel.kt` |
| Source-network policies | `backend/modules/networks/` | `frontend/lib/modules/networks/` |
| Final attendance proof | `backend/modules/authorization/` | Device-owned attendance signing adapter |
| Classroom observations | `backend/modules/classroom_wifi/`, `classroom_ble/` | Network services and native Wi-Fi/BLE bridges |
| Shared accounts and attendance | `backend/api/`, `backend/services/attendance.py` | `frontend/lib/screens/`, `frontend/lib/services/` |

`application_factory.py` composes the routers. `app.py` and `main.py` preserve
the development entry points; Local and Full launchers add their identity guards.
Downloaded models in `backend/models/` and third-party licenses remain required.

Device/network PASS alone cannot authorize attendance. The final attendance
request requires fresh signed device proof and actual-source network checks
alongside facial matching and liveness. Preflight is only a readiness check.
Uvicorn proxy headers must remain disabled. Classroom Wi-Fi requirements depend
on the session; experimental BLE does not authorize attendance.

Use the [API guide](API_INTEGRATION.md), [device workflow](SELF_SERVICE_DEVICE_MANAGEMENT.md)
and [provider contract](TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md) for integration.
First enrollment follows the explicit [account-bound policy](FYP_ACCOUNT_BOUND_ENROLLMENT.md);
faculty recovery and face replacement remain external.
