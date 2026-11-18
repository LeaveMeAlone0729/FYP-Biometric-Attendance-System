# Public general APIs and trusted classroom LAN

## Confirmed investigation

The previous APK sent every request to `http://192.168.0.162:8000`.
This private address is not normally reachable on mobile data. The HTTP client
used a single connection pool, a 25-second blanket deadline, and no network
change notification. These are the source causes of unreachable mobile login
and prolonged switching waits; changing database settings cannot fix them.

At inspection on 12 November 2026, cloudflared 2026.10.7 was installed, but no
cloudflared process or files under the current user's `.cloudflared` directory
were found. No stable public hostname, tunnel ID, credentials or account/domain
ownership was available to validate. This does not establish the state of an
external Cloudflare account. No tunnel was started and no DNS/account settings
were changed. Physical mobile-data success is BLOCKED until those are supplied.

The original backend identity remained `attendance_proposal_xampp:3306` and the
temporary `network_ble_test_mode` setting was false. Services were not restarted.

## Routing and session lifecycle

* `PUBLIC_API_BASE_URL`: HTTPS origin for `/config`, `/login`, `/logout`, `/me`,
  `/classes`, `/attendance/history` and `/attendance/summary` only.
* `CLASSROOM_API_BASE_URL`: direct LAN origin for all other routes, including
  device management, initial enrollment, face/liveness, verification status,
  attendance PIN/start, preflight, device proofs, Wi-Fi and BLE. There is no
  fallback from a classroom call to HTTPS.
* Legacy `API_BASE_URL` is retained as the classroom default. Without a public
  origin the build remains LAN-only; it cannot provide mobile-data login.
* Both routes consume the same opaque bearer session from the same original
  backend/database. There is no refresh-token endpoint in the current backend;
  its existing expiry/revocation semantics are preserved. Network switching
  retains the bearer and student, but not an expired session. App-process
  restart still requires login; this change does not add token persistence.
* Android's default-network callback only invalidates transport connections and
  outstanding signing work. It never authorizes a network. Current HTTP responses
  and the backend's ASGI source-IP checks establish reachability/authorization.
* General and classroom connection limits are 5 and 3 seconds respectively.
  Response limits are 10 seconds, with existing 25-second multipart processing
  preserved. A general GET may retry once; writes, signatures and uploads never
  retry automatically. A lost final-write response requires checking history.
* On a network change, old attendance attempts cannot resume sending face,
  liveness or final device proofs. Begin again with the PIN for fresh challenges.
  Existing Wi-Fi/BLE/device services use the changed revision to discard stale
  signed work. This can abandon a challenge without deleting its audit history.
* Public down/LAN up: no automatic credential fallback. General APIs fail clearly;
  an already signed-in student can use LAN classroom checks while the same server
  session is valid. Public up/LAN down: general functions work, attendance fails.

## Public ingress boundary

`backend/public_gateway.py` is a separate, loopback-only port 8004 gateway to
the existing original FastAPI backend on 127.0.0.1:8000. It has no database
credentials, migrations or attendance-writing route. Startup verifies the
original backend identity. Its method/path allowlist excludes all admin,
biometric, device, diagnostic, enrollment, debug, OpenAPI and classroom routes.
It rejects unexpected Host values, query strings, oversized bodies and
non-loopback peers. Only Content-Type and the application bearer are forwarded.
No cookies, redirects or authentication credentials are logged.

Cloudflared MUST target 8004, never 8000 or 8003. All requests reaching the
original backend through the gateway have a loopback peer; CF-Connecting-IP,
X-Forwarded-For and similar values are stripped. They are not campus evidence.
CIDR still uses the direct attendance connection's real ASGI peer. The gateway
does not make a Cloudflare egress address or client-declared private IP trusted.

The original login throttle and token validation remain authoritative. Before
public deployment review existing predefined/demo passwords and configure
Cloudflare edge rate limiting as available. Do not publish weak demo accounts.
This is a student API, not the previous email/PIN browser Quick Tunnel gateway.
Browser Access cookies or a reusable Access secret must not be embedded in the
APK. If Access is required, a separate approved per-user native authentication
integration is needed; HTML Access challenges are not API login responses.

## Deployment — requires approval and actual hostname

Obtain a stable hostname and named tunnel under an account/domain you control.
Reuse an existing tunnel only after inspecting its ingress and ownership. Do
not invent a URL or use a changing Quick Tunnel URL as a stable configuration.
The commands below are preparation, not a record of executed public deployment.

1. Keep the existing original backend and admin running. No restart is necessary
   for these client/gateway-only changes. Do not enable diagnostic test mode.
2. Set the real hostname in a new PowerShell terminal and start the gateway:

```powershell
$repo = 'C:\FYP\FYP-Biometric-Attendance-System'
$env:FYP_PUBLIC_HOST = Read-Host 'Actual API hostname (no https://)'
& "$repo\backend\venv\Scripts\python.exe" "$repo\backend\public_gateway.py"
```

3. In a private operator Cloudflare configuration (not committed), use actual
   tunnel ID/credential-file paths, this hostname and the following ingress:

```yaml
ingress:
  - hostname: YOUR_ACTUAL_API_HOSTNAME
    service: http://127.0.0.1:8004
  - service: http_status:404
```

Never put secrets into the repository. Validate a reviewed actual configuration
with `cloudflared tunnel --config <private-config-path> ingress validate` and
`cloudflared tunnel --config <private-config-path> ingress rule https://<actual-host>/me`.
Before starting any public tunnel, obtain approval for exposure and DNS/account
changes, confirm the fixed origin is 8004, and verify sensitive routes return
404. Starting a tunnel is NOT authorized by implementing this code.

4. After separately approved exposure and HTTPS checks, build/install only the
   selected Xiaomi with the actual public URL and current classroom LAN address:

```powershell
$lanIp = (Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress
& "$repo\install-fyp-android.ps1" -Serial 7732690b -LanIp $lanIp -PublicApiUrl "https://$env:FYP_PUBLIC_HOST"
```

This preserves app data and keys with `adb install -r`; no ADB reverse is used.
Confirm the LAN address again before installing. Installation requires separate
approval. The locally built APK without a supplied public hostname is LAN-only
and is NOT a completed mobile-data deployment.

During this investigation the laptop Wi-Fi address changed to `10.46.58.220`.
Do not reuse the former `192.168.0.162` blindly. A new LAN subnet is not
automatically authorized by the existing CIDR or classroom Wi-Fi policies;
policy changes require separate approval and real access-point evidence.

## Xiaomi acceptance (not yet executed)

1. Mobile data: log in, load profile, timetable and history using HTTPS.
2. Switch Wi-Fi → mobile data → classroom Wi-Fi without logout. Repeat profile
   and timetable; expect the same student and valid session.
3. On mobile data attempt attendance: expect prompt LAN failure, no camera or
   attendance insert. A timeout is not a confirmed CIDR rejection.
4. On approved Wi-Fi use a legitimate session/PIN, ACTIVE key, CIDR and BSSID.
   Complete the partner's actual face/head/liveness flow and check exactly one
   attendance record. Repeat to verify duplicate rejection.
5. Switch networks during preflight, BLE scanning and face/liveness. Expect
   abandoned proof or clear failure, no automatic replay. Check history if the
   network was lost while the final request might have committed.
6. Wrong BSSID and spoofed forwarding fields must not authorize attendance.
   BLE remains shadow-only and cannot independently allow/block attendance.
7. Confirm `/config` has `network_ble_test_mode: false`. Public identity,
   admin, test, face, attendance-start and device routes must return 404.

All automated gateway/mobile-transition tests use synthetic responses and
in-memory databases. They do not prove Cloudflare deployment or physical
mobile-data reachability. No original database writes are required by this work.

## Creating a permanent named tunnel (operator steps, NOT executed)

The developer confirmed no stable hostname or tunnel is configured. A permanent
published hostname needs a Cloudflare account and a domain/zone you control.
Stop here if those are unavailable; a Quick Tunnel is not the permanent solution.
Follow Cloudflare's [locally-managed named tunnel guide](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/create-local-tunnel/).

The following account/DNS actions require explicit approval. They create no
database and do not change the existing backend. Run interactively so browser
account authorization stays with the owner, never send certificate/tunnel secrets
to chat, and do not install a Windows service for this first deployment.

```powershell
$cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
& $cf tunnel login
& $cf tunnel list
# Only if no suitable existing named tunnel exists:
& $cf tunnel create fyp-general-api
```

After the owner has selected a real hostname under the authorized domain and
obtained the actual tunnel UUID, prepare the private configuration (no overwrite):

```powershell
$env:FYP_PUBLIC_HOST = (Read-Host 'Actual API hostname, without scheme').Trim().ToLowerInvariant()
$tunnelId = Read-Host 'Actual tunnel UUID from tunnel create/list'
if ($tunnelId -notmatch '^[0-9a-fA-F-]{36}$') { throw 'Supply the actual tunnel UUID' }
$credentials = Join-Path $env:USERPROFILE ".cloudflared\$tunnelId.json"
if (-not (Test-Path -LiteralPath $credentials)) { throw 'Tunnel credentials are not installed for this identity' }
$configPath = Join-Path $env:USERPROFILE '.cloudflared\fyp-general-api.yml'
if (Test-Path -LiteralPath $configPath) { throw 'Existing configuration requires review; do not overwrite' }
@"
tunnel: $tunnelId
credentials-file: '$credentials'
ingress:
  - hostname: $env:FYP_PUBLIC_HOST
    service: http://127.0.0.1:8004
  - service: http_status:404
"@ | Set-Content -LiteralPath $configPath -Encoding utf8
& $cf tunnel --config $configPath ingress validate
& $cf tunnel --config $configPath ingress rule "https://$env:FYP_PUBLIC_HOST/me"
# This changes DNS; only after approval. Do not use --overwrite-dns.
& $cf tunnel route dns $tunnelId $env:FYP_PUBLIC_HOST
```

Review the hostname and private config before DNS/exposure. Keep its credentials
and Cloudflare account certificate outside Git. In a separate terminal, start
the loopback gateway with the same actual FYP_PUBLIC_HOST as documented above.
Verify locally using `Invoke-WebRequest http://127.0.0.1:8004/config -Headers
@{Host=$env:FYP_PUBLIC_HOST}`. `/me` without a bearer must return 401; `/local-fyp/identity`,
`/attendance/start`, `/api/v1/devices` and `/ble` must return 404. The gateway
must not have a listener on a LAN address.

Only after public-deployment approval, use the named tunnel command below in
its own terminal. This is NOT a Quick Tunnel and does not change DNS by itself.

```powershell
& $cf tunnel --config $configPath run $tunnelId
```

Verify HTTPS `/config` and the same blocked routes externally with normal TLS
validation, then obtain installation approval and use the documented installer
with `-PublicApiUrl`. Login still uses the application's original credentials
and server throttle, not a Cloudflare shared secret. Ctrl+C in the tunnel's
terminal stops public ingress; Ctrl+C in the gateway terminal stops port 8004.
Neither operation stops backend 8000, admin 8003 or MariaDB. Do not restart a
tunnel automatically or publish any additional origin to make tests pass.

## Executed validation — 12 November 2026

* Backend gateway + network + attendance authorization + classroom Wi-Fi + BLE
  + shadow + disabled-diagnostic regressions: **117 passed, 3 skipped**.
  The skipped cases require database concurrency/row-lock integration support.
  A final expanded gateway-only run passed **17 tests**, including original
  authentication 401/403, login throttle 429 and origin-unavailable 503 handling.
* Full Flutter suite: **299 passed, 1 skipped**. Eight new tests exercise
  central routing, transitions, bearer retention, interrupted proofs, one-shot
  general GET recovery, unavailable LAN/public endpoints, fast timeout and
  unsafe endpoint configuration. Existing two timeout expectations now assert
  the earlier 10-second transport error rather than their old 15-second wrapper.
* Flutter analyze: **no issues**. Debug APK build: **PASS**, LAN-only URL
  `http://10.46.58.220:8000`. No public URL was fabricated for the build.
* PowerShell installer parser and Git whitespace checks: **PASS**.
* Existing Gradle/AGP/Kotlin deprecation warnings remain; no bypass flags used.
* No original database writes, migrations, service restarts, APK installation,
  Cloudflare launch or account/DNS changes were performed. The partner's face
  and liveness source files were not modified.

Local test output is in `%TEMP%\fyp-dual-routing-backend-tests.log` and
`%TEMP%\fyp-dual-routing-flutter-tests.log`. Those logs contain test outcomes,
not a real Cloudflare/Xiaomi success claim. All physical acceptance cases above
are **NOT RUN/BLOCKED** pending the actual hostname and deployment approval.

## Gateway deployment preflight — 14 November 2026

Developer-reported Cloudflare setup now uses active zone `bioattsys.xyz`, named
tunnel `fyp-attendance-gateway` and intended hostname `api.bioattsys.xyz`. The
Windows Cloudflared service was locally confirmed running. Its command line
was not printed because service arguments may contain a tunnel token. No
Cloudflare route, account setting or service configuration was changed.

Local checks found no listeners on 8000, 8003, 8004 or 3306. Requests to the
original backend identity and configuration endpoints were refused. Therefore
original database identity, backend health, live diagnostic flag and live
gateway forwarding are currently **UNVERIFIED/BLOCKED**, not PASS. No original
service was started or restarted. The gateway was not started either.

The gateway now additionally limits aggregate login traffic to 60 requests per
rolling 60 seconds, independent of untrusted source/forwarding headers. This
single-process, in-memory limit supplements the existing backend per-account
eight-failed-logins/15-minute limit and returns 429/Retry-After when exhausted.
It resets with the gateway process and is not a distributed rate limiter.
The existing 8,192-byte request-body cap, strict method/path/Host checks and
bearer validation by the original backend remain unchanged.

Offline gateway and CIDR regression tests passed **47 tests, 1 skipped**. Tests
cover blocked admin, biometric, device, attendance, diagnostic and encoded
routes; rejected non-loopback peers; spoofed forwarding headers; invalid Host,
methods, query strings and oversized bodies; auth/throttle failures; identity
mismatch; origin failure; and aggregate login-limit expiry. Tests use synthetic
HTTP responses/in-memory fixtures, not original records or live student logins.

After the original backend is available, its identity and disabled diagnostic
flag must be rechecked. Then, only with gateway-start approval, run:

```powershell
$repo = 'C:\FYP\FYP-Biometric-Attendance-System'
$env:FYP_PUBLIC_HOST = 'api.bioattsys.xyz'
& "$repo\backend\venv\Scripts\python.exe" "$repo\backend\public_gateway.py"
```

This starts only 127.0.0.1:8004 and aborts if the original backend identity probe
fails. It does not start the backend, admin or database. Before adding a public
hostname route, verify its listener and `/config` with Host `api.bioattsys.xyz`,
unauthenticated `/me` rejection, and 404 on all sensitive routes. The Cloudflare
route's service must be `http://127.0.0.1:8004`, never 8000, 8003 or 3306.
Current decision: **BLOCKED for public exposure** until these live checks pass.

## Live public-route verification — 14 November 2026

This supersedes the earlier offline preflight status above. On branch SH, the
gateway was already running as PID 41440 on **127.0.0.1:8004**. It was not started
or restarted by this verification. The existing public route was tested at
`https://api.bioattsys.xyz`; Cloudflare configuration was not changed.

* Direct backend `/config`, localhost gateway `/config` with Host
  `api.bioattsys.xyz`, and public HTTPS `/config` all returned **200**. JSON
  fields matched except the fresh per-request server timestamp. In all three,
  `network_ble_test_mode` was false, verification_seconds was 90 and
  required_frames was 3. Public response cache status was DYNAMIC.
* Local and public gateway responses had application/json, Cache-Control
  no-store and X-Content-Type-Options nosniff. Public Server was Cloudflare;
  local gateway Server was uvicorn. Cookies/tokens were not printed.
* Local and public `/me` without a bearer returned **401**, with the original
  backend's sign-in-required JSON message. Together with the gateway's fixed
  ORIGIN and original identity response, this confirms general requests reach
  the original backend, rather than a Cloudflare documentation page.
* Public `/docs`, `/api/v1/devices`, `/api/v1/network-ble-tests/sessions`,
  `/local-fyp/identity`, `/attendance/start`, `/verify-face` and `/sessions`
  returned **404 PUBLIC_ROUTE_NOT_AVAILABLE**. This is intentional. The raw-path,
  method and query guard in public_gateway.py runs before any origin forwarding.
  A correct Host passes only the Host guard; it does not permit extra routes.
* Login is **POST /login**, not a GET login page. Other allowlisted methods are
  GET /config, GET /me, GET /classes, GET /attendance/history,
  GET /attendance/summary and POST /logout. Authenticated endpoints still need
  a valid application bearer. No route was added to this allowlist.
* Expanded gateway tests: **33 passed**. A new test logs into the actual backend
  using an isolated synthetic SQLite account, verifies its bearer against /me,
  then verifies sensitive requests remain 404 and never reach that origin.
  The fixture finishes with zero attendance rows. Original credentials were
  not used for this test.
* Focused Flutter dual routing, client, preflight and classroom attendance tests:
  **40 passed**. No runtime source fix or restart was needed for this verification.
* Original identity remained attendance_proposal_xampp:3306, with the same
  pinned identity digest. Original attendance count was **8 before and 8 after**.
  Only read-only live probes were made; no login, logout or attendance submission
  was performed against original accounts. No database or policy changes occurred.

Two existing backend listeners were observed: PID 33884 on localhost:8000
(`serve-backend`) and PID 15856 on 0.0.0.0:8000
(`serve-backend --lan --local-demo-slot2`). The gateway's loopback origin reaches
the localhost backend. Neither was terminated. Reconcile duplicate backend
ownership separately before further deployment changes; no automatic cleanup
is authorized by these checks. Admin PID 40144 and database PID 29132 were also
left unchanged.

Decision: **public API READY for mobile-data login testing**. Actual Xiaomi
mobile-data login and switching remain NOT RUN by this verification. The app
must be built with PUBLIC_API_BASE_URL=https://api.bioattsys.xyz and the current
correct CLASSROOM_API_BASE_URL before that physical acceptance test. APK build
or installation requires its separately approved deployment step. Do not open
public /docs or broaden the allowlist to make a browser page appear.

## Dual-path Xiaomi APK prepared — 14 November 2026

Current Wi-Fi IPv4 was freshly verified as **192.168.0.162/24**. Xiaomi
7732690b was the connected ADB target, with current wlan0 address
192.168.0.94/24. No ADB reverse was used. Both original backend listeners and
the existing Cloudflare gateway were left running without restart.

Build command actually executed (build only, no installation):

```powershell
.\install-fyp-android.ps1 -BuildOnly -LanIp 192.168.0.162 -PublicApiUrl https://api.bioattsys.xyz
```

The resulting debug APK contains both verified URL strings:

* PUBLIC_API_BASE_URL=https://api.bioattsys.xyz
* CLASSROOM_API_BASE_URL=http://192.168.0.162:8000
* API_BASE_URL compatibility default=http://192.168.0.162:8000
* APK: frontend/build/app/outputs/flutter-apk/app-debug.apk
* SHA-256: 0f7530ab88b0b2e8ca60298250ca97ef5db68ad2571f01c8226a8de39f145e41

Gateway security tests: **33 passed**. Flutter dual routing/client/classroom
preflight tests: **40 passed**. Flutter analysis: clean. Android build: PASS,
with existing toolchain deprecation warnings. Public config was 200, public me
without a bearer was 401, sensitive public routes were 404, original identity
matched and diagnostic mode remained false on localhost, LAN and public config.

Installation awaits explicit approval for `adb -s 7732690b install -r` of that
APK. Do not install on another serial, uninstall or clear app data. Real Xiaomi
mobile-data login, network switching and fresh classroom acceptance remain
**PENDING**, not established by these automated/host HTTP checks. Physical public
security has host-side HTTPS evidence only so far. No account, policy, device
binding, biometric template or attendance record was modified for this build.
