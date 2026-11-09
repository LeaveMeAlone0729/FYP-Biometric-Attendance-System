package com.example.frontend

import android.Manifest
import android.app.Activity
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodChannel

/** Bounded foreground scanner only. No pairing, advertising, files, logging or API calls. */
internal class BleDiagnosticsChannel(private val activity: Activity, messenger: BinaryMessenger) {
    companion object { const val PERMISSION_REQUEST = 0x424c; const val ENABLE_REQUEST = 0x4245 }
    private val channel = MethodChannel(messenger, "attendance/ble_diagnostics")
    private val handler = Handler(Looper.getMainLooper())
    private val adapter = (activity.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter
    private val prefs = activity.getSharedPreferences("ble_diagnostics", Context.MODE_PRIVATE)
    private var pending: MethodChannel.Result? = null
    private var pendingOwner: String? = null
    private var permissionReply: MethodChannel.Result? = null
    private var enableReply: MethodChannel.Result? = null
    private var scanner: BluetoothLeScanner? = null
    private var callback: ScanCallback? = null
    private var deadline: Runnable? = null
    private var started = 0L
    private var startedWall = 0L
    private var generation = 0
    private var paused = false
    private var lastStarted = Long.MIN_VALUE
    private val records = linkedMapOf<String, Advertiser>()

    private class Advertiser(val id: Int, var name: String?, var services: List<String>,
        var serviceData: List<Map<String, Any>>, var manufacturerData: List<Map<String, Any>>) {
        var lastSeen = 0L
        var count = 0
        val samples = mutableListOf<Int>()
        val beaconSamples = linkedMapOf<String, MutableList<Map<String, Long>>>()
    }

    init {
        channel.setMethodCallHandler { call, reply ->
            when (call.method) {
                "status" -> reply.success(status())
                "scan" -> scan(reply, call.argument<String>("request_id") ?: "local-diagnostics")
                "stop" -> { if (pendingOwner == (call.argument<String>("request_id") ?: "local-diagnostics")) finish("STOPPED"); reply.success(null) }
                "cancel" -> { if (pendingOwner == (call.argument<String>("request_id") ?: "local-diagnostics")) finish("CANCELLED"); reply.success(null) }
                "requestPermission" -> requestPermission(reply)
                "enableBluetooth" -> enable(reply)
                else -> reply.notImplemented()
            }
        }
    }

    private fun granted(permission: String) = activity.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED
    private fun connectAllowed() = Build.VERSION.SDK_INT < 31 || granted(Manifest.permission.BLUETOOTH_CONNECT)
    private fun scanAllowed() = Build.VERSION.SDK_INT < 31 || granted(Manifest.permission.BLUETOOTH_SCAN)
    private fun scanPermission(): String = when {
        Build.VERSION.SDK_INT < 31 -> "LEGACY_LOCATION_REQUIRED"
        scanAllowed() && connectAllowed() -> "GRANTED"
        !prefs.getBoolean("asked", false) -> "NOT_REQUESTED"
        activity.shouldShowRequestPermissionRationale(Manifest.permission.BLUETOOTH_SCAN) ||
            activity.shouldShowRequestPermissionRationale(Manifest.permission.BLUETOOTH_CONNECT) -> "DENIED"
        else -> "SETTINGS_REQUIRED"
    }
    private fun bluetoothOn(): Boolean? = if (!connectAllowed()) null else try { adapter?.isEnabled } catch (_: SecurityException) { null }
    private fun locationOn(): Boolean = try {
        val m = activity.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        if (Build.VERSION.SDK_INT >= 28) m.isLocationEnabled
        else m.isProviderEnabled(LocationManager.GPS_PROVIDER) || m.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
    } catch (_: Exception) { false }
    private fun status(code: String = "READY"): Map<String, Any?> {
        val supported = adapter != null && activity.packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)
        val actual = if (code != "READY") code else when {
            !supported -> "BLE_UNSUPPORTED"
            !scanAllowed() || !connectAllowed() -> "BLE_PERMISSION_REQUIRED"
            bluetoothOn() != true -> "BLUETOOTH_OFF"
            !granted(Manifest.permission.ACCESS_FINE_LOCATION) -> "LOCATION_PERMISSION_REQUIRED"
            !locationOn() -> "LOCATION_DISABLED"
            else -> code
        }
        return mapOf(
        "status" to actual, "supported" to supported,
        "bluetooth_enabled" to bluetoothOn(), "scan_permission" to scanPermission(),
        "connect_permission" to if (connectAllowed()) "GRANTED" else "DENIED",
        "location_permission" to when { granted(Manifest.permission.ACCESS_FINE_LOCATION) -> "PRECISE_GRANTED"; granted(Manifest.permission.ACCESS_COARSE_LOCATION) -> "APPROXIMATE_ONLY"; else -> "DENIED" },
        "location_enabled" to locationOn(), "android_sdk" to Build.VERSION.SDK_INT)
    }

    private fun requestPermission(reply: MethodChannel.Result) {
        if (permissionReply != null) { reply.error("PERMISSION_PENDING", "A Nearby Devices prompt is already open.", null); return }
        if (Build.VERSION.SDK_INT < 31 || (scanAllowed() && connectAllowed())) { reply.success(null); return }
        permissionReply = reply; prefs.edit().putBoolean("asked", true).apply()
        try { activity.requestPermissions(arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT), PERMISSION_REQUEST) }
        catch (_: Exception) { permissionReply = null; reply.error("PERMISSION_UNAVAILABLE", "Open Android app permissions manually.", null) }
    }
    fun onPermissionResult(code: Int) {
        if (code != PERMISSION_REQUEST) return
        val reply = permissionReply; permissionReply = null; reply?.success(null)
    }
    @Suppress("DEPRECATION")
    private fun enable(reply: MethodChannel.Result) {
        if (!connectAllowed()) { reply.error("BLE_PERMISSION_REQUIRED", "Allow Nearby Devices before enabling Bluetooth.", null); return }
        if (adapter == null) { reply.error("BLE_UNSUPPORTED", "Bluetooth LE is unavailable.", null); return }
        if (bluetoothOn() == true) { reply.success(null); return }
        if (enableReply != null) { reply.error("ENABLE_PENDING", "The Android Bluetooth prompt is already open.", null); return }
        enableReply = reply
        try { activity.startActivityForResult(Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE), ENABLE_REQUEST) }
        catch (_: Exception) { enableReply = null; reply.error("ENABLE_UNAVAILABLE", "Enable Bluetooth in Android Settings.", null) }
    }
    fun onActivityResult(code: Int) {
        if (code != ENABLE_REQUEST) return
        val reply = enableReply; enableReply = null; reply?.success(null)
    }

    @Suppress("MissingPermission")
    private fun scan(reply: MethodChannel.Result, owner: String) {
        if (owner.length > 64 || owner.isBlank()) { reply.error("BLE_SCAN_OWNER_INVALID", "Invalid scan request.", null); return }
        if (pending != null) { reply.error("BLE_SCAN_BUSY", "One BLE scan is already running.", null); return }
        val info = status()
        val problem = when {
            paused -> "CANCELLED"
            info["supported"] != true -> "BLE_UNSUPPORTED"
            !scanAllowed() || !connectAllowed() -> "BLE_PERMISSION_REQUIRED"
            bluetoothOn() != true -> "BLUETOOTH_OFF"
            !granted(Manifest.permission.ACCESS_FINE_LOCATION) -> "LOCATION_PERMISSION_REQUIRED"
            !locationOn() -> "LOCATION_DISABLED"
            lastStarted != Long.MIN_VALUE && SystemClock.elapsedRealtimeNanos() - lastStarted < 2_000_000_000L -> "BLE_SCAN_RATE_LIMITED"
            else -> null
        }
        if (problem != null) { reply.success(status(problem) + mapOf("devices" to emptyList<Any>(), "scan_duration_ms" to 0)); return }
        records.clear(); started = SystemClock.elapsedRealtimeNanos(); startedWall = System.currentTimeMillis(); lastStarted = started
        val token = ++generation; pending = reply; pendingOwner = owner
        try {
            val active = adapter?.bluetoothLeScanner
            if (active == null) { finish("BLE_UNAVAILABLE"); return }
            scanner = active
            val listener = object : ScanCallback() {
                override fun onScanResult(type: Int, item: ScanResult) { handler.post { accept(item, token) } }
                override fun onBatchScanResults(items: MutableList<ScanResult>) { handler.post { items.forEach { accept(it, token) } } }
                override fun onScanFailed(code: Int) { handler.post { if (token == generation) finish("BLE_SCAN_FAILED", code) } }
            }
            callback = listener
            active.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .setReportDelay(0).setCallbackType(ScanSettings.CALLBACK_TYPE_ALL_MATCHES).build(), listener)
            val timeout = Runnable { if (token == generation) finish("COMPLETE") }
            deadline = timeout; handler.postDelayed(timeout, 8000)
        } catch (_: SecurityException) { finish("BLE_PERMISSION_REQUIRED") }
          catch (_: Exception) { finish("BLE_UNAVAILABLE") }
    }

    private fun hex(bytes: ByteArray) = bytes.take(32).joinToString("") { "%02x".format(it.toInt() and 255) }
    @Suppress("MissingPermission")
    private fun accept(item: ScanResult, token: Int) {
        try { acceptRecord(item, token) }
        catch (_: SecurityException) { if (token == generation) finish("BLE_PERMISSION_REQUIRED") }
        catch (_: Exception) { /* Ignore malformed advertisements; never log identifiers. */ }
    }

    @Suppress("MissingPermission")
    private fun acceptRecord(item: ScanResult, token: Int) {
        if (pending == null || token != generation || paused) return
        if (!scanAllowed() || !connectAllowed()) { finish("BLE_PERMISSION_REQUIRED"); return }
        if (bluetoothOn() != true) { finish("BLUETOOTH_OFF"); return }
        val now = SystemClock.elapsedRealtimeNanos()
        if (item.timestampNanos < started || item.timestampNanos > now || item.rssi !in -127..126) return
        val ad = item.scanRecord ?: return
        // Address is used ONLY for deduplication in this eight-second scan and
        // is never returned, logged, persisted or used as classroom identity.
        val key = try { item.device.address } catch (_: SecurityException) { return }
        val existing = records[key]
        if (existing == null && records.size >= 40) return
        val observed = Advertiser(existing?.id ?: (records.size + 1),
            ad.deviceName?.filter { !it.isISOControl() }?.take(40),
            ad.serviceUuids?.take(8)?.map { it.toString() } ?: emptyList(),
            ad.serviceData?.entries?.take(4)?.map { mapOf("uuid" to it.key.toString(), "data_hex" to hex(it.value)) } ?: emptyList(),
            (0 until (ad.manufacturerSpecificData?.size() ?: 0)).take(4).map {
                mapOf("company_id" to ad.manufacturerSpecificData.keyAt(it), "data_hex" to hex(ad.manufacturerSpecificData.valueAt(it))) })
        val record = existing ?: observed.also { records[key] = it }
        if (item.timestampNanos <= record.lastSeen) return
        // Scan-response metadata may arrive after the first advertisement.
        // Retain only metadata actually observed in this bounded window.
        if (observed.name != null) record.name = observed.name
        if (observed.services.isNotEmpty()) record.services = observed.services
        if (observed.serviceData.isNotEmpty()) record.serviceData = observed.serviceData
        if (observed.manufacturerData.isNotEmpty()) record.manufacturerData = observed.manufacturerData
        record.lastSeen = item.timestampNanos; record.count++
        record.samples.add(item.rssi); if (record.samples.size > 50) record.samples.removeAt(0)
        // Samples are tagged only with UUIDs in THIS received packet, not cached
        // metadata from earlier packets. Distinct offsets survive to verification.
        ad.serviceUuids?.take(8)?.forEach { uuid ->
            if (uuid.toString() !in record.beaconSamples && record.beaconSamples.size >= 8) return@forEach
            val observations = record.beaconSamples.getOrPut(uuid.toString()) { mutableListOf() }
            val offset = (item.timestampNanos - started) / 1000
            if (observations.lastOrNull()?.get("offset_us") != offset) {
                observations.add(mapOf("offset_us" to offset, "rssi_dbm" to item.rssi.toLong()))
                if (observations.size > 50) observations.removeAt(0)
            }
        }
    }

    private fun finish(code: String, error: Int? = null) {
        val reply = pending ?: return
        pending = null; pendingOwner = null; generation++
        deadline?.let { handler.removeCallbacks(it) }; deadline = null
        try { callback?.let { scanner?.stopScan(it) } } catch (_: Exception) {}
        callback = null; scanner = null
        val now = SystemClock.elapsedRealtimeNanos()
        val effectiveCode = if (code != "COMPLETE") code else when {
            !scanAllowed() || !connectAllowed() -> "BLE_PERMISSION_REQUIRED"
            bluetoothOn() != true -> "BLUETOOTH_OFF"
            !granted(Manifest.permission.ACCESS_FINE_LOCATION) -> "LOCATION_PERMISSION_REQUIRED"
            !locationOn() -> "LOCATION_DISABLED"
            else -> code
        }
        val devices = if (effectiveCode in listOf("COMPLETE", "STOPPED")) records.values.map { ad ->
            val sorted = ad.samples.sorted()
            val median = if (sorted.size % 2 == 1) sorted[sorted.size / 2].toDouble() else (sorted[sorted.size / 2 - 1] + sorted[sorted.size / 2]) / 2.0
            val age = (now - ad.lastSeen) / 1_000_000
            mapOf("scan_id" to ad.id, "name" to ad.name, "service_uuids" to ad.services,
                "service_data" to ad.serviceData, "manufacturer_data" to ad.manufacturerData,
                "rssi_dbm" to ad.samples.last(), "rssi_samples" to ad.samples.toList(), "median_rssi_dbm" to median,
                "advertisement_count" to ad.count, "last_seen_age_ms" to age,
                "beacon_observations" to ad.beaconSamples.map { (uuid, samples) -> mapOf("service_uuid" to uuid, "samples" to samples.toList()) },
                "last_seen_at_ms" to (System.currentTimeMillis() - age))
        } else emptyList()
        val response = status(effectiveCode) + mapOf("devices" to devices, "scan_duration_ms" to ((now - started) / 1_000_000),
            "scan_started_at_ms" to startedWall,
            "scan_error_code" to error, "completed_at_ms" to System.currentTimeMillis())
        records.clear(); reply.success(response)
    }
    fun pause() { paused = true; finish("CANCELLED") }
    fun resume() { paused = false }
    fun dispose() {
        finish("CANCELLED"); channel.setMethodCallHandler(null)
        permissionReply?.error("ACTIVITY_CLOSED", "Nearby Devices prompt closed.", null); permissionReply = null
        enableReply?.error("ACTIVITY_CLOSED", "Bluetooth prompt closed.", null); enableReply = null
    }
}
