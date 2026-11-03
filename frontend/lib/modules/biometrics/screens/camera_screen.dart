// Module owner: Chew Zhexuan
// Module: Facial Recognition and Liveness Detection
import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import '../../../services/api_client.dart';
import '../../../theme.dart';
import '../services/biometric_api.dart';

enum _ScanFeedback { waiting, checking, adjust, ready }

class CameraScreen extends StatefulWidget {
  const CameraScreen({
    super.key,
    this.challenge,
    this.enrollment = false,
    this.cameraLoader,
    this.cameraFactory,
    this.stopwatchFactory,
  });
  final Map<String, dynamic>? challenge;
  final bool enrollment;
  final Future<List<CameraDescription>> Function()? cameraLoader;
  final CameraController Function(CameraDescription)? cameraFactory;
  final Stopwatch Function()? stopwatchFactory;
  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen>
    with WidgetsBindingObserver {
  CameraController? _camera;
  bool _busy = false, _consent = false, _finished = false, _success = false;
  bool _initializing = false, _paused = false, _deadlineReached = false;
  bool _cancelSent = false;
  int _cameraGeneration = 0, _readyChecks = 0, _faceRemaining = 30;
  _ScanFeedback _feedback = _ScanFeedback.waiting;
  Future<void> _cameraDisposal = Future.value();
  String _stage = 'face',
      _message =
          'Center your face in the circle. Capture happens automatically.';
  String? _cameraError, _recordedAt;
  int _fingers = 0, _valid = 0, _remaining = 90;
  Timer? _clock, _captureTimer;
  late final Stopwatch _elapsed, _faceElapsed;
  late int _allowedSeconds;
  final _api = ApiClient.instance;
  final _biometrics = BiometricApi();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _elapsed = (widget.stopwatchFactory ?? Stopwatch.new)();
    _faceElapsed = (widget.stopwatchFactory ?? Stopwatch.new)();
    _allowedSeconds =
        (widget.challenge?['expires_in'] ??
                _api.config['verification_seconds'] ??
                90)
            as int;
    _remaining = _allowedSeconds;
    if (!widget.enrollment) {
      _elapsed.start();
      _ensureClock();
    } else {
      _message = 'Give consent below to start your automatic face scan.';
    }
    _initializeCamera();
  }

  void _ensureClock() {
    _clock ??= Timer.periodic(const Duration(milliseconds: 500), (_) {
      if (!mounted || _finished) return;
      final total = _allowedSeconds - _elapsed.elapsed.inSeconds;
      final face = 30 - _faceElapsed.elapsed.inSeconds;
      setState(() {
        _remaining = total.clamp(0, _allowedSeconds);
        _faceRemaining = face.clamp(0, 30);
      });
      if ((!widget.enrollment && total <= 0) ||
          (_stage == 'face' && _faceElapsed.isRunning && face <= 0)) {
        _deadlineReached = true;
        _captureTimer?.cancel();
        // A final attendance response may already be on its way. Read it before
        // displaying a failure so a committed attendance is never called failed.
        if (_busy) {
          setState(() => _message = 'Waiting for the last server check…');
        } else {
          _finish(false, _timeoutMessage);
        }
      }
    });
  }

  String get _timeoutMessage => _stage == 'face'
      ? 'No clear face was confirmed in time. Improve the lighting and try again.'
      : 'Verification timed out. Enter the PIN to start again.';

  bool get _canScan =>
      mounted &&
      !_finished &&
      !_paused &&
      !_deadlineReached &&
      _camera?.value.isInitialized == true &&
      (!widget.enrollment || _consent);

  void _scheduleScan([Duration delay = const Duration(milliseconds: 900)]) {
    _captureTimer?.cancel();
    if (!_canScan) return;
    if (_stage == 'face' && !_faceElapsed.isRunning) _faceElapsed.start();
    _ensureClock();
    _captureTimer = Timer(delay, _scanFrame);
  }

  void _setConsent(bool value) {
    setState(() {
      _consent = value;
      _readyChecks = 0;
      _feedback = _ScanFeedback.waiting;
      _message = value
          ? 'Center your face in the circle. Hold still for automatic capture.'
          : 'Give consent below to start your automatic face scan.';
    });
    if (value) {
      _scheduleScan(const Duration(milliseconds: 1200));
    } else {
      _captureTimer?.cancel();
      _clock?.cancel();
      _clock = null;
      _faceElapsed.stop();
      _faceElapsed.reset();
      setState(() => _faceRemaining = 30);
    }
  }

  Future<void> _releaseCamera() {
    final camera = _camera;
    _camera = null;
    if (camera != null) {
      _cameraDisposal = _cameraDisposal
          .then((_) => camera.dispose())
          .catchError((Object _) {});
    }
    return _cameraDisposal;
  }

  Future<void> _initializeCamera() async {
    if (_initializing || _finished || _paused) return;
    _initializing = true;
    final generation = ++_cameraGeneration;
    CameraController? pending;
    try {
      await _cameraDisposal;
      final cameras = await (widget.cameraLoader ?? availableCameras)().timeout(
        const Duration(seconds: 12),
      );
      if (!mounted || _paused || _finished || generation != _cameraGeneration) {
        return;
      }
      final front = cameras
          .where((c) => c.lensDirection == CameraLensDirection.front)
          .toList();
      if (front.isEmpty) {
        throw const ApiException(
          'A front-facing camera is required. Enable it on your phone or emulator.',
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
      if (!mounted || _paused || _finished || generation != _cameraGeneration) {
        await pending.dispose();
        return;
      }
      setState(() {
        _camera = pending;
        _cameraError = null;
      });
      _scheduleScan(const Duration(milliseconds: 1200));
    } catch (e) {
      if (mounted &&
          !_finished &&
          !_paused &&
          generation == _cameraGeneration) {
        setState(
          () => _cameraError = e is CameraException
              ? 'Camera unavailable: ${e.description ?? e.code}. Enable camera permission in Settings and retry.'
              : e is TimeoutException
              ? 'The camera did not start. Check camera permission and your device camera settings, then retry.'
              : e.toString(),
        );
      }
      if (pending != null) {
        unawaited(pending.dispose().catchError((Object _) {}));
      }
    } finally {
      _initializing = false;
      if (mounted &&
          !_paused &&
          !_finished &&
          _camera == null &&
          _cameraError == null) {
        unawaited(_initializeCamera());
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      _paused = true;
      _cameraGeneration++;
      _readyChecks = 0;
      _feedback = _ScanFeedback.waiting;
      _captureTimer?.cancel();
      unawaited(_releaseCamera());
    } else if (state == AppLifecycleState.resumed) {
      _paused = false;
      _initializeCamera();
    }
  }

  Future<Uint8List> _capture() async {
    final camera = _camera;
    if (camera == null || !camera.value.isInitialized) {
      throw const ApiException('Wait for the camera to be ready.');
    }
    final picture = await camera.takePicture();
    try {
      return await picture.readAsBytes();
    } finally {
      if (picture.path.isNotEmpty) {
        final file = File(picture.path);
        if (await file.exists()) await file.delete();
      }
    }
  }

  Future<void> _scanFrame() async {
    if (!_canScan || _busy) return;
    final generation = _cameraGeneration;
    final isFace = _stage == 'face';
    var nextDelay = const Duration(milliseconds: 900);
    setState(() {
      _busy = true;
      if (_feedback == _ScanFeedback.waiting) {
        _feedback = _ScanFeedback.checking;
      }
    });
    try {
      final bytes = await _capture();
      if (!mounted || _finished || _paused || generation != _cameraGeneration) {
        return;
      }
      final Map<String, dynamic> response;
      if (isFace && widget.enrollment) {
        response = await _biometrics.registerFace(
          bytes,
          consent: _consent,
          previewOnly: _readyChecks == 0,
        );
      } else if (isFace) {
        response = await _biometrics.verifyFace(
          widget.challenge!['challenge_id'] as String,
          bytes,
          previewOnly: _readyChecks == 0,
        );
      } else {
        response = await _biometrics.submitLivenessFrame(
          widget.challenge!['challenge_id'] as String,
          bytes,
        );
      }
      if (!mounted || _finished) return;
      // Apply responses even while paused: the server may have advanced the
      // challenge. Only scheduling and camera capture are suspended.
      if (isFace && response['ready'] == false) {
        setState(() {
          _readyChecks = 0;
          _feedback = _ScanFeedback.adjust;
          _message = response['message'] as String;
        });
      } else if (isFace && response['preview_only'] == true) {
        setState(() {
          _readyChecks = _paused || generation != _cameraGeneration ? 0 : 1;
          _feedback = _ScanFeedback.ready;
          _message = response['message'] as String;
        });
      } else if (isFace &&
          widget.enrollment &&
          response['registered'] == true) {
        // Successful registration remains successful even if profile refresh
        // has a temporary network error.
        _api.student?['biometric_status'] = 'active';
        _finish(
          true,
          'Your face is registered. You can now verify attendance.',
        );
        unawaited(_api.refreshStudent().catchError((Object _) {}));
      } else if (isFace && response['face_verified'] == true) {
        _faceElapsed.stop();
        setState(() {
          _stage = 'liveness';
          _feedback = _ScanFeedback.ready;
          _fingers = response['fingers'] as int;
          _message =
              'Face verified. Show $_fingers finger${_fingers == 1 ? '' : 's'} with your palm toward the camera. Your face and hand can be anywhere in the frame; keep them separate and fully visible.';
        });
        nextDelay = const Duration(milliseconds: 1600);
      } else if (!isFace && response['complete'] == true) {
        _recordedAt = response['recorded_at'] as String?;
        _finish(
          true,
          'Your identity and gesture were verified. Your attendance has been recorded.',
        );
      } else if (!isFace) {
        setState(() {
          _valid = response['valid_frames'] as int;
          _feedback = _valid > 0 ? _ScanFeedback.ready : _ScanFeedback.adjust;
          _message = response['message'] as String;
        });
      } else {
        _finish(
          false,
          'The server could not confirm this scan. Restart the backend and try again.',
        );
      }
    } catch (e) {
      if (mounted && !_finished) {
        if (e is CameraException) {
          setState(() {
            _readyChecks = 0;
            _feedback = _ScanFeedback.adjust;
            _message =
                'Keep the app open and hold still while the camera adjusts.';
          });
        } else {
          _finish(
            false,
            !isFace && e is ApiException && e.status == 0
                ? 'Could not confirm the last server check. Check your attendance history before trying again.'
                : e.toString(),
          );
        }
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        if (_deadlineReached && !_finished) {
          _finish(false, _timeoutMessage);
        } else {
          _scheduleScan(nextDelay);
        }
      }
    }
  }

  void _finish(bool success, String message) {
    if (_finished) return;
    _clock?.cancel();
    _captureTimer?.cancel();
    _elapsed.stop();
    _faceElapsed.stop();
    unawaited(_releaseCamera());
    if (mounted) {
      setState(() {
        _finished = true;
        _success = success;
        _message = message;
      });
    }
    if (!success) _cancelChallenge();
  }

  void _cancelChallenge() {
    if (widget.enrollment || _success || _cancelSent) return;
    _cancelSent = true;
    unawaited(
      _biometrics
          .cancel(widget.challenge!['challenge_id'] as String)
          .catchError((_) => null),
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _clock?.cancel();
    _captureTimer?.cancel();
    _elapsed.stop();
    _faceElapsed.stop();
    unawaited(_releaseCamera());
    _cancelChallenge();
    super.dispose();
  }

  Color get _guideColor =>
      _cameraError != null || _feedback == _ScanFeedback.adjust
      ? const Color(0xFFEF5350)
      : _feedback == _ScanFeedback.ready
      ? const Color(0xFF35D596)
      : Colors.white70;

  String get _guideLabel => switch (_feedback) {
    _ScanFeedback.waiting =>
      widget.enrollment && !_consent
          ? 'CONSENT TO START'
          : _stage == 'face'
          ? 'POSITION YOUR FACE'
          : 'SHOW YOUR HAND ANYWHERE IN FRAME',
    _ScanFeedback.checking => 'CHECKING AUTOMATICALLY',
    _ScanFeedback.adjust =>
      _stage == 'face' ? 'ADJUST YOUR POSITION' : 'ADJUST YOUR GESTURE',
    _ScanFeedback.ready =>
      _stage == 'face'
          ? 'FACE DETECTED · HOLD STILL'
          : 'FACE VERIFIED · HOLD YOUR GESTURE',
  };

  Widget _check(String text, bool done) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 9),
    child: Row(
      children: [
        Icon(
          done ? Icons.check_circle : Icons.radio_button_unchecked,
          size: 21,
          color: done ? teal : muted,
        ),
        const SizedBox(width: 10),
        Expanded(child: Text(text)),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    if (_finished) {
      return Scaffold(
        appBar: AppBar(title: const Text('Verification result')),
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(28),
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.all(26),
                    decoration: BoxDecoration(
                      color: _success
                          ? const Color(0xFFE1F3EB)
                          : const Color(0xFFFFEBEE),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      _success ? Icons.check_rounded : Icons.refresh_rounded,
                      color: _success ? teal : const Color(0xFFD32F2F),
                      size: 58,
                    ),
                  ),
                  const SizedBox(height: 24),
                  Text(
                    _success
                        ? (widget.enrollment
                              ? 'Face registered'
                              : 'Attendance accepted')
                        : 'Verification incomplete',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 12),
                  Text(_message, textAlign: TextAlign.center),
                  const SizedBox(height: 24),
                  if (!widget.enrollment)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              widget.challenge!['course_name'] as String,
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            const SizedBox(height: 10),
                            _check('Class attendance code', true),
                            _check('Facial identity', _stage == 'liveness'),
                            _check('Live gesture challenge', _success),
                            if (_recordedAt != null)
                              Text('Recorded ${friendlyTime(_recordedAt)}'),
                          ],
                        ),
                      ),
                    ),
                  const SizedBox(height: 28),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: () => Navigator.pop(context, _success),
                      child: Text(
                        widget.enrollment
                            ? 'Back to profile'
                            : 'Back to attendance',
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }
    final camera = _camera;
    final initialized = camera != null && camera.value.isInitialized;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.enrollment ? 'Register your face' : 'Verify attendance',
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 20),
            child: Center(
              child: Text(
                _stage == 'face'
                    ? '${!widget.enrollment && _remaining < _faceRemaining ? _remaining : _faceRemaining}s scan'
                    : '${_remaining}s left',
                style: TextStyle(
                  fontWeight: FontWeight.w700,
                  color: (_stage == 'face' ? _faceRemaining : _remaining) <= 10
                      ? const Color(0xFFD32F2F)
                      : teal,
                ),
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(22, 8, 22, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (!widget.enrollment)
                Row(
                  children: [
                    for (final step in ['1  Face', '2  Gesture', '3  Result'])
                      Expanded(
                        child: Container(
                          margin: const EdgeInsets.only(right: 6),
                          padding: const EdgeInsets.symmetric(vertical: 10),
                          decoration: BoxDecoration(
                            color:
                                (step.startsWith('1') && _stage == 'face') ||
                                    (step.startsWith('2') &&
                                        _stage == 'liveness')
                                ? teal
                                : const Color(0xFFE0E8EB),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            step,
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color:
                                  (step.startsWith('1') && _stage == 'face') ||
                                      (step.startsWith('2') &&
                                          _stage == 'liveness')
                                  ? Colors.white
                                  : muted,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              const SizedBox(height: 22),
              Text(
                _stage == 'liveness'
                    ? 'Show $_fingers finger${_fingers == 1 ? '' : 's'}'
                    : 'Center your face',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 8),
              Text(
                _stage == 'liveness'
                    ? 'Keep your face and one full hand visible, palm toward the camera. Neither needs to be centered. Leave space between them.'
                    : 'Look into the camera. Hold still when the circle turns green; we’ll capture automatically.',
              ),
              const SizedBox(height: 20),
              Center(
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    maxHeight: MediaQuery.sizeOf(context).height * .5,
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(24),
                    child: AspectRatio(
                      key: const ValueKey('camera-frame'),
                      // Match the camera rather than squeezing its preview into a
                      // fixed box, so the guide outlines the entire visible frame.
                      aspectRatio: initialized
                          ? (MediaQuery.orientationOf(context) ==
                                    Orientation.portrait
                                ? 1 / camera.value.aspectRatio
                                : camera.value.aspectRatio)
                          : 3 / 4,
                      child: ColoredBox(
                        color: ink,
                        child: Stack(
                          fit: StackFit.expand,
                          children: [
                            if (initialized)
                              CameraPreview(camera)
                            else
                              Center(
                                child: _cameraError == null
                                    ? const CircularProgressIndicator(
                                        color: Colors.white,
                                      )
                                    : Padding(
                                        padding: const EdgeInsets.all(24),
                                        child: Text(
                                          _cameraError!,
                                          textAlign: TextAlign.center,
                                          style: const TextStyle(
                                            color: Colors.white,
                                          ),
                                        ),
                                      ),
                              ),
                            if (initialized && _stage == 'face')
                              IgnorePointer(
                                child: Semantics(
                                  label: _guideLabel,
                                  liveRegion: true,
                                  child: Center(
                                    child: FractionallySizedBox(
                                      widthFactor: .78,
                                      child: AspectRatio(
                                        aspectRatio: 1,
                                        child: AnimatedContainer(
                                          key: const ValueKey('face-guide'),
                                          duration: const Duration(
                                            milliseconds: 220,
                                          ),
                                          decoration: BoxDecoration(
                                            shape: BoxShape.circle,
                                            border: Border.all(
                                              color: _guideColor,
                                              width: 5,
                                            ),
                                            boxShadow: [
                                              BoxShadow(
                                                color: _guideColor.withValues(
                                                  alpha: .22,
                                                ),
                                                blurRadius: 15,
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            if (initialized && _stage == 'liveness')
                              Positioned.fill(
                                child: IgnorePointer(
                                  child: Semantics(
                                    label: _guideLabel,
                                    liveRegion: true,
                                    child: Padding(
                                      padding: const EdgeInsets.all(8),
                                      child: AnimatedContainer(
                                        key: const ValueKey('gesture-guide'),
                                        duration: const Duration(
                                          milliseconds: 220,
                                        ),
                                        decoration: BoxDecoration(
                                          borderRadius: BorderRadius.circular(
                                            18,
                                          ),
                                          border: Border.all(
                                            color: _guideColor,
                                            width: 4,
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            if (initialized)
                              Positioned(
                                left: 12,
                                right: 12,
                                bottom: 18,
                                child: Center(
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 12,
                                      vertical: 9,
                                    ),
                                    decoration: BoxDecoration(
                                      color: Colors.black87,
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: Text(
                                      _guideLabel,
                                      textAlign: TextAlign.center,
                                      style: TextStyle(
                                        color: _guideColor,
                                        fontSize: 10,
                                        fontWeight: FontWeight.w700,
                                        letterSpacing: .5,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            Positioned(
                              left: 14,
                              top: 14,
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                  vertical: 7,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.black54,
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: Row(
                                  children: [
                                    Icon(
                                      Icons.circle,
                                      size: 8,
                                      color: initialized
                                          ? const Color(0xFF68DFC3)
                                          : Colors.white54,
                                    ),
                                    const SizedBox(width: 6),
                                    Text(
                                      initialized
                                          ? 'LIVE CAMERA'
                                          : _cameraError == null
                                          ? 'STARTING CAMERA'
                                          : 'CAMERA UNAVAILABLE',
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 10,
                                        letterSpacing: 1,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            if (_busy)
                              const Positioned(
                                bottom: 0,
                                left: 0,
                                right: 0,
                                child: LinearProgressIndicator(),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              InfoNotice(
                _message,
                icon: _stage == 'liveness'
                    ? Icons.back_hand_outlined
                    : Icons.face_outlined,
              ),
              if (_stage == 'face') ...[
                const SizedBox(height: 12),
                LinearProgressIndicator(
                  value: _faceRemaining / 30,
                  minHeight: 5,
                  color: _faceRemaining <= 10 ? const Color(0xFFD32F2F) : teal,
                ),
                const SizedBox(height: 8),
                const Text(
                  '30-second face scan · No capture button needed',
                  style: TextStyle(fontSize: 12, color: muted),
                ),
              ],
              if (_stage == 'liveness') ...[
                const SizedBox(height: 16),
                LinearProgressIndicator(
                  value: _valid / 3,
                  minHeight: 7,
                  borderRadius: BorderRadius.circular(8),
                ),
                const SizedBox(height: 8),
                Text(
                  '$_valid of 3 consecutive camera checks confirmed',
                  style: const TextStyle(fontSize: 12),
                ),
              ],
              if (_cameraError != null)
                TextButton(
                  onPressed: _initializeCamera,
                  child: const Text('Retry camera'),
                ),
              if (widget.enrollment) ...[
                const SizedBox(height: 16),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: _consent,
                  controlAffinity: ListTileControlAffinity.leading,
                  onChanged: _busy
                      ? null
                      : (value) => _setConsent(value ?? false),
                  title: const Text(
                    'I consent to facial biometric processing for this attendance research prototype.',
                    style: TextStyle(fontSize: 13),
                  ),
                  subtitle: const Text(
                    'An encrypted face template is stored. Captured photos are removed after processing. You can remove your template from Profile.',
                    style: TextStyle(fontSize: 12),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
