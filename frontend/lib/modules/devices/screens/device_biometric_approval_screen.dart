import 'dart:async';
import 'dart:io';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import '../../../services/api_client.dart';
import '../../../theme.dart';
import '../services/device_biometric_api.dart';
import '../services/device_activation_state.dart';
import '../services/device_activation_service.dart';
import '../widgets/device_camera_preview.dart';
import '../widgets/device_biometric_feedback.dart';
import '../widgets/device_biometric_completion.dart';
import '../services/device_camera_orientation.dart';

/// Device-owned capture workflow. Matching/gestures are checked only by the server.
/// COMPLETED_UNTRUSTED never means registered, trusted, or eligible for activation.
class DeviceBiometricApprovalScreen extends StatefulWidget {
  const DeviceBiometricApprovalScreen({
    super.key,
    required this.pendingRegistrationId,
    required this.expiresAt,
    this.api,
    this.activationService,
    this.cameraLoader,
    this.cameraFactory,
    this.stopwatchFactory,
  });
  final String pendingRegistrationId, expiresAt;
  final DeviceBiometricApi? api;
  final DeviceActivationService? activationService;
  final Future<List<CameraDescription>> Function()? cameraLoader;
  final CameraController Function(CameraDescription)? cameraFactory;
  final Stopwatch Function()? stopwatchFactory;
  @override
  State<DeviceBiometricApprovalScreen> createState() =>
      _DeviceBiometricApprovalScreenState();
}

class _DeviceBiometricApprovalScreenState
    extends State<DeviceBiometricApprovalScreen>
    with WidgetsBindingObserver {
  late final _api = widget.api ?? DeviceBiometricApi();
  late final Stopwatch _elapsed = (widget.stopwatchFactory ?? Stopwatch.new)();
  late final _activation =
      widget.activationService ?? DeviceActivationService();
  bool _activationBusy = false;
  String _activationStatus = 'CHECKING', _trustedStatus = 'CHECKING';
  String? _activationError;
  CameraController? _camera;
  Future<void> _disposal = Future.value();
  Timer? _scanTimer, _clock;
  Map<String, dynamic>? _result;
  String? _error, _cameraError;
  DeviceGuideFeedback _guideFeedback = DeviceGuideFeedback.checking;
  String _status = 'Camera ready to start', _feedback = '';
  bool _busy = false, _initializing = false, _paused = false, _ended = false;
  int _generation = 0, _budget = 90, _remaining = 90, _runId = 0;
  int _previewQuarterTurns = 0, _adjustments = 0;

  bool get _running => _result != null && !_ended;
  bool get _complete => _result?['stage'] == 'COMPLETED_UNTRUSTED';
  void _log(String stage) => debugPrint('B3_SCAN run=$_runId stage=$stage');

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  Future<void> _release() {
    final camera = _camera;
    _camera = null;
    if (camera != null) {
      _disposal = _disposal
          .then((_) => camera.dispose().timeout(const Duration(seconds: 3)))
          .catchError((Object _) {
            _log('camera_release_failed');
          });
    }
    return _disposal;
  }

  void _end(String? error, {String status = 'Scan stopped'}) {
    _ended = true;
    _runId++;
    _generation++;
    _scanTimer?.cancel();
    _clock?.cancel();
    _elapsed.stop();
    unawaited(_release());
    if (mounted) {
      setState(() {
        _error = error;
        _guideFeedback = error == null
            ? DeviceGuideFeedback.confirmed
            : DeviceGuideFeedback.adjust;
        _status = status;
        _busy = false;
        _initializing = false;
      });
    }
    _log(error == null ? 'completed_untrusted' : 'stopped');
  }

  String _errorStatus(Object error) {
    if (error is TimeoutException) return 'Camera capture timed out';
    if (error is ApiException) {
      if (error.status == 401 ||
          error.code == 'SESSION_CHANGED' ||
          error.status == 410) {
        return 'Session expired';
      }
      if (error.code == 'FACE_NOT_MATCHED' ||
          error.code == 'FACE_SUBSTITUTED') {
        return 'Face mismatch';
      }
      if (error.code == 'REQUEST_TIMEOUT') return 'Request timed out';
      if (error.status == 0 && error.code != 'INVALID_BIOMETRIC_RESPONSE') {
        return 'Network error';
      }
    }
    return 'Scan failed';
  }

  String _errorMessage(Object error) {
    if (error is TimeoutException) {
      return 'Camera capture or file read timed out. Restart the scan; no frame was accepted as a match.';
    }
    if (error is ApiException &&
        (error.status == 410 ||
            error.status == 401 ||
            error.code == 'SESSION_CHANGED')) {
      return 'Your biometric session expired or your login changed. Restart the scan; renew device preparation if needed.';
    }
    return error.toString();
  }

  Future<void> _start() async {
    if (_busy || _running) return;
    final run = ++_runId;
    setState(() {
      _busy = true;
      _error = null;
      _cameraError = null;
      _ended = false;
      _result = null;
      _adjustments = 0;
      _guideFeedback = DeviceGuideFeedback.checking;
      _status = 'Connecting to device verification server';
      _feedback = '';
    });
    try {
      final result = await _api
          .begin(widget.pendingRegistrationId)
          .timeout(
            const Duration(seconds: 16),
            onTimeout: () => throw const ApiException(
              'Device biometric request timed out. Restart the scan.',
              0,
              'REQUEST_TIMEOUT',
            ),
          );
      if (!mounted || run != _runId) return;
      setState(() => _result = result);
      if (result['complete'] == true) {
        _end(null);
        unawaited(_activateAutomatically());
        return;
      }
      if (result['stage'] != 'FACE' && result['stage'] != 'LIVENESS') {
        _end(
          'This biometric test has ended. Start a new test.',
          status: result['stage'] == 'EXPIRED'
              ? 'Session expired'
              : 'Verification failed',
        );
        return;
      }
      _budget = (result['expires_in'] as int).clamp(0, 90);
      _remaining = _budget;
      _elapsed
        ..reset()
        ..start();
      _clock?.cancel();
      _clock = Timer.periodic(const Duration(milliseconds: 500), (_) {
        if (!mounted || _ended || run != _runId) return;
        setState(
          () => _remaining = (_budget - _elapsed.elapsed.inSeconds).clamp(
            0,
            _budget,
          ),
        );
        // Expiry must also stop a hung camera/HTTP operation, not wait on _busy.
        if (_remaining == 0) {
          _end(
            'Device biometric session expired. Restart the scan while key preparation is valid.',
            status: 'Session expired',
          );
        }
      });
      setState(() => _status = 'Opening front camera');
      await _initializeCamera();
    } catch (error) {
      if (mounted && run == _runId) {
        _end(_errorMessage(error), status: _errorStatus(error));
      }
    } finally {
      if (mounted && run == _runId) {
        setState(() => _busy = false);
        _schedule();
      }
    }
  }

  Future<void> _initializeCamera() async {
    if (_initializing || _paused || !_running) return;
    _initializing = true;
    final generation = ++_generation, run = _runId;
    CameraController? pending;
    try {
      await _disposal;
      final cameras = await (widget.cameraLoader ?? availableCameras)().timeout(
        const Duration(seconds: 12),
      );
      if (!mounted ||
          _paused ||
          !_running ||
          generation != _generation ||
          run != _runId) {
        return;
      }
      final front = cameras
          .where((c) => c.lensDirection == CameraLensDirection.front)
          .toList();
      if (front.isEmpty) {
        throw const ApiException(
          'A front-facing camera is required. Enable the emulator webcam or use your Android front camera.',
        );
      }
      pending =
          widget.cameraFactory?.call(front.first) ??
          CameraController(
            front.first,
            ResolutionPreset.high,
            enableAudio: false,
          );
      await pending.initialize().timeout(const Duration(seconds: 20));
      final correction = await DeviceCameraOrientation.previewCorrection(
        front.first,
      ).timeout(const Duration(seconds: 3), onTimeout: () => 0);
      if (!mounted ||
          _paused ||
          !_running ||
          generation != _generation ||
          run != _runId) {
        await pending.dispose();
        pending = null;
        return;
      }
      setState(() {
        _camera = pending;
        _previewQuarterTurns = correction;
        _cameraError = null;
        _guideFeedback = DeviceGuideFeedback.checking;
        _status = 'Camera ready';
        _feedback =
            'Scanning starts automatically. Move close enough to fill the oval with one face, centered and well lit.';
      });
      pending = null;
      _log('camera_ready');
    } catch (error) {
      if (pending != null) {
        unawaited(
          pending
              .dispose()
              .timeout(const Duration(seconds: 3))
              .catchError((Object _) {}),
        );
      }
      if (mounted && generation == _generation && _running && run == _runId) {
        setState(() {
          _guideFeedback = DeviceGuideFeedback.adjust;
          _status = 'Camera unavailable';
          _cameraError = error is CameraException
              ? 'Camera unavailable: ${error.description ?? error.code}. Enable camera permission in Settings and retry.'
              : error is TimeoutException
              ? 'The camera did not start. Check camera settings and retry.'
              : error.toString();
        });
      }
    } finally {
      _initializing = false;
      if (mounted &&
          !_paused &&
          _running &&
          _camera == null &&
          _cameraError == null) {
        unawaited(_initializeCamera());
      } else {
        _schedule();
      }
    }
  }

  void _schedule() {
    _scanTimer?.cancel();
    if (!mounted ||
        _paused ||
        !_running ||
        _busy ||
        _camera == null ||
        _cameraError != null ||
        !_camera!.value.isInitialized ||
        _remaining == 0) {
      return;
    }
    _scanTimer = Timer(
      Duration(milliseconds: _adjustments > 0 ? 2000 : 1000),
      _scan,
    );
  }

  Future<void> _deleteCapture(XFile picture) async {
    if (picture.path.isEmpty) return;
    try {
      final file = File(picture.path);
      if (await file.exists().timeout(const Duration(seconds: 2))) {
        await file.delete().timeout(const Duration(seconds: 2));
      }
    } catch (_) {
      _log('temporary_capture_cleanup_failed');
    }
  }

  Future<void> _scan() async {
    if (!mounted || _paused || !_running || _busy || _camera == null) return;
    final generation = _generation, run = _runId;
    setState(() {
      _busy = true;
      _guideFeedback = DeviceGuideFeedback.checking;
      if (_adjustments == 0) {
        _status = _result!['stage'] == 'FACE'
            ? 'Scanning face'
            : 'Checking liveness';
      }
    });
    try {
      _log('capture_started');
      final capture = _camera!.takePicture();
      unawaited(
        capture.then((picture) async {
          if (!mounted ||
              run != _runId ||
              generation != _generation ||
              _ended) {
            await _deleteCapture(picture);
          }
        }, onError: (Object _) {}),
      );
      final picture = await capture.timeout(const Duration(seconds: 8));
      final bytes = await (() async {
        try {
          return await picture.readAsBytes().timeout(
            const Duration(seconds: 5),
          );
        } finally {
          await _deleteCapture(picture);
        }
      })();
      if (!mounted ||
          _paused ||
          generation != _generation ||
          !_running ||
          run != _runId) {
        return;
      }
      _log('frame_upload_started');
      final before = _result!;
      Map<String, dynamic> result;
      try {
        result = await _api
            .frame(bytes, liveness: before['stage'] == 'LIVENESS')
            .timeout(
              const Duration(seconds: 18),
              onTimeout: () => throw const ApiException(
                'Device biometric frame timed out. Restart the scan.',
                0,
                'REQUEST_TIMEOUT',
              ),
            );
      } on ApiException catch (error) {
        if (error.status != 0 ||
            (error.code != null &&
                error.code != 'NETWORK_ERROR' &&
                error.code != 'REQUEST_TIMEOUT')) {
          rethrow;
        }
        // Resolve an uncertain response once; never hide a failed upload behind
        // an unchanged FACE state and start an uncontrolled retry loop.
        final recovered = await _api.status().timeout(
          const Duration(seconds: 5),
        );
        final advanced =
            recovered['complete'] == true ||
            recovered['stage'] != before['stage'] ||
            (recovered['valid_frames'] as int) >
                (before['valid_frames'] as int);
        if (!advanced) rethrow;
        result = recovered;
      }
      if (!mounted || _ended || run != _runId) return;
      setState(() => _result = result);
      _log('frame_response_${result['stage']}');
      if (result['complete'] == true) {
        _end(null);
        unawaited(_activateAutomatically());
        return;
      }
      if (result['stage'] != 'FACE' && result['stage'] != 'LIVENESS') {
        _end(
          result['message'] as String,
          status: result['stage'] == 'EXPIRED'
              ? 'Session expired'
              : 'Verification failed',
        );
        return;
      }
      if (result['stage'] == 'LIVENESS' &&
          result['face_verified'] == true &&
          before['stage'] == 'FACE') {
        _adjustments = 0;
        setState(() {
          _guideFeedback = DeviceGuideFeedback.confirmed;
          _status = 'Face verified';
          _feedback =
              'Face matched on the server. Follow the liveness challenge below.';
        });
      } else if (result['ready'] == false &&
          !((result['valid_frames'] as int) >
              (before['valid_frames'] as int))) {
        _adjustments++;
        final code = result['feedback_code'];
        final message = result['message'] as String;
        setState(() {
          _guideFeedback = DeviceGuideFeedback.adjust;
          _feedback = message;
          _status = switch (code) {
            'FACE_COUNT_INVALID' => 'No single face detected',
            'FACE_TOO_SMALL' => 'Face too small — move closer',
            'FACE_TOO_CLOSE' => 'Move a little farther away',
            'FACE_NOT_CENTERED' => 'Center your face',
            _ =>
              result['stage'] == 'FACE'
                  ? 'Adjust your face position'
                  : 'Gesture not confirmed',
          };
        });
        if (_adjustments >= 8) {
          _end(
            'Scan paused after 8 unsuccessful frames. $message Adjust your position, then restart while the session is valid.',
            status: 'Scan paused',
          );
        }
      } else {
        _adjustments = 0;
        setState(() {
          _guideFeedback = (result['valid_frames'] as int) > 0
              ? DeviceGuideFeedback.confirmed
              : DeviceGuideFeedback.checking;
          _status = 'Liveness check accepted';
          _feedback = result['message'] as String;
        });
      }
    } catch (error) {
      if (mounted && !_ended && run == _runId) {
        if (error is CameraException) {
          setState(() {
            _guideFeedback = DeviceGuideFeedback.adjust;
            _status = 'Camera capture failed';
            _cameraError =
                'Camera capture failed. Check permission and retry the camera.';
          });
        } else {
          _end(_errorMessage(error), status: _errorStatus(error));
        }
      }
    } finally {
      if (mounted && run == _runId) {
        setState(() => _busy = false);
        _schedule();
      }
    }
  }

  Future<void> _activateAutomatically() async {
    if (_activationBusy || !mounted) return;
    setState(() {
      _activationBusy = true;
      _activationError = null;
    });
    try {
      await _activation.activate(
        widget.pendingRegistrationId,
        isCurrent: () => mounted,
        expectedCandidateId: _result!['candidate_device_id'] as String,
        expectedFingerprint: _result!['public_key_fingerprint'] as String,
        onProgress: (stage) {
          if (mounted) {
            setState(() {
              _activationStatus = stage;
              if (stage == 'Signing activation challenge' ||
                  stage == 'Waiting for server activation confirmation') {
                _trustedStatus = 'AVAILABLE';
              }
            });
          }
        },
      );
      if (mounted) {
        Navigator.pop(
          context,
          true,
        ); // My Device refreshes server registrations.
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _activationStatus = 'NOT ACTIVE';
          _trustedStatus = 'NOT CONFIRMED';
          if (error is ApiException &&
              (error.code == 'APPROVAL_UNAVAILABLE' ||
                  error.code == 'BIOMETRIC_TRUST_REQUIRED')) {
            _activationStatus = 'UNAVAILABLE';
            _trustedStatus = 'NOT YET AVAILABLE';
          }
          _activationError = error.toString();
        });
      }
    } finally {
      if (mounted) setState(() => _activationBusy = false);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      _paused = true;
      _generation++;
      _scanTimer?.cancel();
      unawaited(_release());
    } else {
      _paused = false;
      if (_running) unawaited(_initializeCamera());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _generation++;
    _scanTimer?.cancel();
    _clock?.cancel();
    _elapsed.stop();
    unawaited(_release());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_complete) {
      return DeviceBiometricCompletion(
        replacement: _result!['operation'] == 'replace_device',
        activationState: DeviceActivationState.fromBiometricResult(_result!),
        activationStatus: _activationStatus,
        trustedApprovalStatus: _trustedStatus,
        activationBusy: _activationBusy,
        activationError: _activationError,
        onBack: () => Navigator.pop(context, true),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Device facial verification')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const InfoNotice(
            'Face and liveness checks are an untrusted test result. This device remains inactive until institutional biometric approval is implemented.',
          ),
          const SizedBox(height: 12),
          ...[
            Text(
              _result?['stage'] == 'LIVENESS'
                  ? 'Step 2: Liveness challenge'
                  : 'Step 1: Face recognition',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            Text(
              _status,
              key: const ValueKey('device-scan-status'),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (_feedback.isNotEmpty)
              Text(_feedback, key: const ValueKey('device-scan-feedback')),
            if (_error != null) InfoNotice(_error!, warning: true),
            if (_busy || _initializing)
              const Row(
                children: [
                  SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  SizedBox(width: 8),
                  Expanded(child: Text('Processing current frame...')),
                ],
              ),
            const SizedBox(height: 12),
            if (_camera != null && _camera!.value.isInitialized)
              DeviceCameraPreview(
                key: const ValueKey('device-camera-preview'),
                controller: _camera!,
                previewQuarterTurns: _previewQuarterTurns,
                overlay: DeviceBiometricGuide(
                  feedback: _guideFeedback,
                  liveness: _result?['stage'] == 'LIVENESS',
                  acceptedFrames: (_result?['valid_frames'] as int?) ?? 0,
                ),
              )
            else
              const AspectRatio(
                aspectRatio: 4 / 3,
                child: Card(
                  child: Center(
                    child: Icon(Icons.camera_front_outlined, size: 48),
                  ),
                ),
              ),
            if (_result != null) ...[
              Text('Time remaining: $_remaining seconds'),
              if (_running && _result!['stage'] == 'LIVENESS')
                DeviceLivenessPanel(
                  fingers: _result!['fingers'] as int,
                  acceptedFrames: _result!['valid_frames'] as int,
                  requiredFrames: _result!['required_frames'] as int,
                ),
            ],
            if (!_running)
              FilledButton(
                onPressed: _busy ? null : _start,
                child: const Text('Start facial verification'),
              ),
            if (_cameraError != null) ...[
              InfoNotice(_cameraError!, warning: true),
              TextButton(
                onPressed: _busy || _initializing
                    ? null
                    : () async {
                        setState(() => _cameraError = null);
                        await _release();
                        await _initializeCamera();
                      },
                child: const Text('Retry camera'),
              ),
            ],
          ],
          const SizedBox(height: 12),
          Text('Pending registration expires: ${widget.expiresAt}'),
          const Text(
            'Your retained Android Keystore key and existing trusted device are unchanged.',
          ),
        ],
      ),
    );
  }
}
