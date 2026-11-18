# Full and Partner Local connectivity: verified comparison and recovery fix

Date: 18 November 2026. Branch SH. The initial audit below preceded deployment; see the physical validation update at the end for subsequent approved actions. Snapshot IPs/PIDs are historical evidence, not configuration defaults.

## Confirmed connection difference

| Build | General APIs | My Device, registration, replacement, biometric/device proofs | Attendance |
|---|---|---|---|
| Full, paired | Approved Cloudflare general allowlist | Direct pinned HTTPS 8005, discovered or manually supplied address | Direct pinned HTTPS 8005 only |
| Local, unpaired | Explicit private HTTP 8000 | Same explicit private HTTP 8000 | Same private HTTP 8000, existing backend enforcement |
| Local, paired | Its own pinned HTTPS 8005 | Its own pinned HTTPS 8005 | Its own pinned HTTPS 8005 |

The user confirmed the partner uses port 8000; his Windows profile/firewall is unknown. We have not inspected his laptop or installed APK. We cannot claim the partner uses the same firewall or trust configuration. Source: `frontend/lib/services/api_routes.dart`, `api_client.dart`, `lan_discovery.dart`, `scripts/install-fyp-android.ps1`.

My Device is deliberately outside the approved public allowlist. Its listing, key challenge and signature confirmation share the device-security boundary. It is not accidentally routed as a public general API. Changing it to public or plaintext would change the approved security boundary; neither was done.

## Evidence and root causes

Current laptop: Wi-Fi BEN GONG_5GHz 2, Windows Public, IPv4 192.168.0.113/24. Original backend PID 31944 owns HTTP 0.0.0.0:8000 and HTTPS 192.168.0.113:8005. Admin PID 54844; gateway PID 23180. PIDs and addresses are snapshots, not commands for later termination.

Enabled FYP inbound TCP 8000, TCP 8005 and UDP 5353 rules are Private-only. Broad Python rules are disabled; the remaining temporary Public mDNS rule is disabled and refers to old hotspot peers. These rules do not authorize current Public-profile phone-to-server traffic. This is an evidenced deployment limitation; no packet capture on school Wi-Fi was performed, so additional school client isolation/VLAN/multicast restrictions remain unverified. No firewall rule or network profile was changed.

A separate code defect was reproduced by regression testing: `ApiClient.networkChanged()` discarded the explicit manual server hint. With multicast blocked, a later connectivity event made rediscovery fail even though the same pinned endpoint remained reachable. My Device also lacked the existing direct connection-recovery controls.

Cloudflare is not a prerequisite for My Device TLS. Current public /config succeeds. Earlier school HTTPS connect timeouts are historical evidence, not proof of a current Cloudflare failure. BLE is not consulted to establish this transport.

## Small safe changes

- `frontend/lib/services/api_client.dart`: retain a manual address hint across network callbacks. Close the authenticated socket and invalidate pending signed work as before. Every reconnect still requires current Wi-Fi/subnet, pinned TLS and matching environment identity. No persisted credential or trusted connection is retained.
- `frontend/lib/services/lan_discovery.dart`: clarify hint-versus-transport comment; no validation change.
- `frontend/lib/modules/devices/screens/my_device_screen.dart`: on a connection-specific failure, show the existing classroom connection widget. Authentication/key/policy failures are not converted to PASS.
- `frontend/lib/modules/networks/widgets/classroom_connection_card.dart`: optional success callback; My Device refreshes its listing and obtains a new device challenge after connection recovery.
- `frontend/test/secure_lan_discovery_test.dart`: Full/Local regression for blocked mDNS, retained hint, new subnet, mobile data, wrong identity and no public fallback.
- `frontend/test/my_device_connection_recovery_test.dart`: widget recovery and fresh status reload; a genuine key error remains a failure.

Other pre-existing uncommitted work was preserved. No backend, partner biometric algorithms, gateway allowlist, database, firewall, TLS identity or Cloudflare settings changed in this task.

## Fresh operational checks

- Original backend /config: 200; network_ble_test_mode=false.
- /local-fyp/identity: original, attendance_proposal_xampp, port 3306.
- Admin /login: 200.
- Gateway /config with approved Host: 200.
- Public https://api.bioattsys.xyz/config: 200.
- Gateway /api/v1/devices with approved Host: 404.
- Host-to-listener pinned TLS and discovery identity on 8005: PASS; this does not prove tablet reachability.
- Cloudflared service Running; existing BleProbe.exe process present. No new BLE physical observation performed.
- No live write requests, registration actions or attendance submissions performed.

## Tests

Focused Flutter discovery, recovery, both-mode routing and signed-device suites: 64 passed.
Offline gateway tests: 33 passed (one existing Starlette/httpx deprecation warning). Live mysql.connector.connect was blocked throughout pytest.
Flutter analyze: clean.
Full Flutter suite: 345 passed, 1 skipped.

## Deployment and school/public Wi-Fi retest

At initial review a rebuilt paired Full APK was required. That signing-matched in-place update was subsequently installed; no backend restart was needed for the connection recovery fix. See the update below.

1. On the actual authorized Wi-Fi, record current laptop and tablet IPv4/subnets and Windows profile. Do not reuse the snapshot IP above.
2. Verify phone-to-laptop TCP 8005 is permitted. On Public Windows profile, obtain explicit approval for the existing narrowly scoped, temporary exact-peer firewall procedure; do not enable broad Public or Python rules, and do not open 8000 to Public merely to emulate Local.
3. Open My Device; if discovery fails, enter the current laptop IP in the exposed recovery control and verify the paired server. Installed pin and backend identity must pass before any credential is sent.
4. If manual verification succeeds but automatic discovery fails, investigate UDP 5353/multicast separately. If both fail, investigate TCP firewall/client isolation/VLAN routing; changing Cloudflare will not fix this direct path.
5. After connecting, check My Device. Change connectivity and return to the same Wi-Fi; retry explicitly. The manual hint must recover without replaying any old signed operation. A moved laptop requires discovery or entry of its new IP.
6. Check registration/replacement only through authorized fresh proofs; do not activate/revoke devices merely for this connection test.
7. Test standalone network verification and normal attendance separately. Existing CIDR, Wi-Fi, PIN, device, face/PAD and duplicate checks remain mandatory. Public/mobile-data attendance must remain blocked. No actual attendance test executed here.

School physical reliability remains NOT TESTED after this code change. Future firewall changes and installations require approval. This fix does not promise automatic connectivity through a network that blocks all peer traffic.

## Subsequent approved deployment and physical validation

The paired Full APK was installed in-place on Xiaomi 7732690b after package and signing-certificate verification; app UID and first-install time were preserved. A second signing-matched update exposed the non-sensitive discovery reason code. The approved temporary Public-profile rule allowed only TCP 8005 from that phone to the current laptop address, on Wi-Fi, for the existing Python executable. It armed and rehearsed independent 30-minute cleanup before enabling access. No public mDNS or HTTP 8000 access was added.

Phone TCP reachability and certificate/hostname/backend identity checks passed. The user then confirmed manual paired connection, My Device listing, and Wi-Fi OFF/ON recovery without re-entering the manual address: PASS. Automatic mDNS discovery and a new school-network deployment remain NOT TESTED. The temporary rule was subsequently observed absent; no persistent rule was applied during preparation.

Persistent exact-peer configuration is prepared in scripts/Set-FypApprovedPhoneFirewall.ps1 and documented in APPROVED_PHONE_PUBLIC_FIREWALL.md. It discovers current addresses afresh and requires explicit approval; it is not enabled automatically by startup. Connection success does not authorize attendance or change enrollment provenance.
