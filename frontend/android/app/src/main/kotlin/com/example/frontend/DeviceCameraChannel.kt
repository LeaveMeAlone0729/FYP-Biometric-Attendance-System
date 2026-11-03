package com.example.frontend

import android.os.Build
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodChannel

/** Read-only camera-workaround metadata. No camera capture, key or data writes. */
internal object DeviceCameraChannel {
    fun register(messenger: BinaryMessenger) {
        MethodChannel(messenger, "attendance/device_camera", io.flutter.plugin.common.StandardMethodCodec.INSTANCE,
            messenger.makeBackgroundTaskQueue()).setMethodCallHandler { call, result ->
            if (call.method != "getEnvironment") { result.notImplemented(); return@setMethodCallHandler }
            val emulator = Build.HARDWARE == "ranchu" || Build.HARDWARE == "goldfish"
            val avd = if (emulator) {
                try {
                    val process = ProcessBuilder("getprop", "ro.boot.qemu.avd_name").start()
                    process.inputStream.bufferedReader().use { it.readText().trim() }.also { process.waitFor() }
                } catch (_: Exception) { "" }
            } else ""
            result.success(mapOf("is_emulator" to emulator, "avd_name" to avd,
                "product" to Build.PRODUCT, "model" to Build.MODEL))
        }
    }
}
