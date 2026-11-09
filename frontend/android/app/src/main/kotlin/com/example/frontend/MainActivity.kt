package com.example.frontend

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

class MainActivity : FlutterActivity() {
    private var wifiDiagnostics: WifiDiagnosticsChannel? = null
    private var bleDiagnostics: BleDiagnosticsChannel? = null
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        DeviceKeyStoreChannel.register(flutterEngine.dartExecutor.binaryMessenger)
        DeviceCameraChannel.register(flutterEngine.dartExecutor.binaryMessenger)
        wifiDiagnostics = WifiDiagnosticsChannel(this, flutterEngine.dartExecutor.binaryMessenger)
        bleDiagnostics = BleDiagnosticsChannel(this, flutterEngine.dartExecutor.binaryMessenger)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        wifiDiagnostics?.onPermissionResult(requestCode)
        bleDiagnostics?.onPermissionResult(requestCode)
    }

    override fun onDestroy() {
        bleDiagnostics?.dispose()
        bleDiagnostics = null
        wifiDiagnostics?.dispose()
        wifiDiagnostics = null
        super.onDestroy()
    }

    override fun onPause() { bleDiagnostics?.pause(); super.onPause() }
    override fun onResume() { super.onResume(); bleDiagnostics?.resume() }

    @Deprecated("Activity result callback retained for the Android system Bluetooth enable prompt")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: android.content.Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        bleDiagnostics?.onActivityResult(requestCode)
    }
}
