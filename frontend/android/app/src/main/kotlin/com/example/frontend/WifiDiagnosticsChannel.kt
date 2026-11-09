package com.example.frontend

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.LocationManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.Uri
import android.net.wifi.SupplicantState
import android.net.wifi.WifiInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodChannel

/** Read-only, bounded connected-Wi-Fi snapshots. Never scans, signs, logs or uploads. */
internal class WifiDiagnosticsChannel(private val activity: Activity, messenger: BinaryMessenger) {
    companion object { const val PERMISSION_REQUEST = 0x5746 }
    private val channel = MethodChannel(messenger, "attendance/wifi_diagnostics")
    private val handler = Handler(Looper.getMainLooper())
    private val connectivity = activity.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    private val wifi = activity.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
    private val prefs = activity.getSharedPreferences("wifi_diagnostics", Context.MODE_PRIVATE)
    private var callback: ConnectivityManager.NetworkCallback? = null
    private var timeout: Runnable? = null
    private var snapshotResult: MethodChannel.Result? = null
    private var permissionResult: MethodChannel.Result? = null

    init {
        channel.setMethodCallHandler { call, result ->
            when (call.method) {
                "read" -> read(result)
                "requestPermission" -> {
                    if (fineGranted()) result.success(null)
                    else if (permissionResult != null) result.error("PERMISSION_BUSY", "Permission dialog is already open.", null)
                    else {
                        permissionResult = result
                        prefs.edit().putBoolean("asked", true).apply()
                        try { activity.requestPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION), PERMISSION_REQUEST) }
                        catch (_: Exception) {
                            permissionResult = null
                            result.error("PERMISSION_UNAVAILABLE", "Open app permissions in Android Settings.", null)
                        }
                    }
                }
                "openSettings" -> {
                    val page = call.argument<String>("page")
                    val intent = when (page) {
                        "location" -> Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
                        "wifi" -> Intent(Settings.ACTION_WIFI_SETTINGS)
                        "app" -> Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${activity.packageName}"))
                        else -> null
                    }
                    if (intent == null) result.error("INVALID_SETTINGS_PAGE", "Unknown settings page.", null)
                    else try { activity.startActivity(intent); result.success(null) }
                    catch (_: Exception) { result.error("SETTINGS_UNAVAILABLE", "Open Android Settings manually.", null) }
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun fineGranted() = activity.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    private fun permissionState(): String = when {
        fineGranted() -> "PRECISE_GRANTED"
        activity.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED -> "APPROXIMATE_ONLY"
        !prefs.getBoolean("asked", false) -> "NOT_REQUESTED"
        activity.shouldShowRequestPermissionRationale(Manifest.permission.ACCESS_FINE_LOCATION) -> "DENIED"
        else -> "SETTINGS_REQUIRED"
    }

    private fun locationEnabled(): Boolean {
        val manager = activity.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        return if (Build.VERSION.SDK_INT >= 28) manager.isLocationEnabled
        else manager.isProviderEnabled(LocationManager.GPS_PROVIDER) || manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
    }

    private fun snapshot(info: WifiInfo? = null): Map<String, Any?> {
        val caps = connectivity.getNetworkCapabilities(connectivity.activeNetwork)
        val type = when {
            caps == null -> "NONE"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) -> "VPN"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "WIFI"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "MOBILE_DATA"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ETHERNET"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_BLUETOOTH) -> "BLUETOOTH"
            else -> "OTHER"
        }
        val supported = activity.packageManager.hasSystemFeature(PackageManager.FEATURE_WIFI) && wifi != null
        val enabled = supported && wifi?.isWifiEnabled == true
        val location = locationEnabled()
        val permitted = fineGranted() && location
        val connected = if (!enabled) false else if (info != null) info.supplicantState == SupplicantState.COMPLETED
            else if (caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true) true else null
        val ssid = if (permitted && connected == true) info?.ssid?.removeSurrounding("\"")
            ?.takeUnless { it.isBlank() || it.equals(WifiManager.UNKNOWN_SSID, true) } else null
        val bssid = if (permitted && connected == true) info?.bssid?.takeUnless {
            it.equals("02:00:00:00:00:00", true) || it.equals("00:00:00:00:00:00", true) ||
                !it.matches(Regex("(?i)([0-9a-f]{2}:){5}[0-9a-f]{2}")) } else null
        val rssi = if (permitted && connected == true) info?.rssi?.takeIf { it in -126..-1 } else null
        val status = when {
            !supported -> "UNSUPPORTED"
            !enabled -> "WIFI_OFF"
            !fineGranted() -> "PERMISSION_REQUIRED"
            !location -> "LOCATION_DISABLED"
            info == null -> "INFO_UNAVAILABLE"
            connected != true -> "NOT_CONNECTED"
            ssid == null || bssid == null -> "REDACTED"
            else -> "AVAILABLE"
        }
        return mapOf("status" to status, "connection_type" to type, "wifi_enabled" to enabled,
            "wifi_connected" to connected, "permission_status" to permissionState(),
            "location_enabled" to location, "ssid" to ssid, "bssid" to bssid, "rssi_dbm" to rssi,
            "android_sdk" to Build.VERSION.SDK_INT, "observed_at_ms" to System.currentTimeMillis())
    }

    @Suppress("DEPRECATION")
    private fun read(result: MethodChannel.Result) {
        cancelSnapshot("SUPERSEDED", "A newer Wi-Fi refresh replaced this reading.")
        try {
            val initial = snapshot()
            if (initial["wifi_enabled"] != true || !fineGranted() || initial["location_enabled"] != true) {
                result.success(initial); return
            }
            if (Build.VERSION.SDK_INT < 31) {
                result.success(snapshot(wifi?.connectionInfo)); return
            }
            snapshotResult = result
            val listener = object : ConnectivityManager.NetworkCallback(ConnectivityManager.NetworkCallback.FLAG_INCLUDE_LOCATION_INFO) {
                override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) {
                    val info = capabilities.transportInfo as? WifiInfo ?: return
                    if (snapshotResult === result) finish(info)
                }
            }
            callback = listener
            connectivity.registerNetworkCallback(NetworkRequest.Builder()
                .addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build(), listener, handler)
            val deadline = Runnable { if (snapshotResult === result) finish(null) }
            timeout = deadline;handler.postDelayed(deadline, 1800)
        } catch (_: SecurityException) {
            if (snapshotResult != null) cancelSnapshot("WIFI_PERMISSION_CHANGED", "Wi-Fi access changed. Refresh after checking Android permissions.")
            else result.error("WIFI_PERMISSION_CHANGED", "Wi-Fi access changed. Check Android permissions.", null)
        } catch (_: Exception) {
            if (snapshotResult != null) cancelSnapshot("WIFI_UNAVAILABLE", "Android could not return a Wi-Fi reading.")
            else result.error("WIFI_UNAVAILABLE", "Android could not return a Wi-Fi reading.", null)
        }
    }

    private fun cleanupSnapshot() {
        timeout?.let { handler.removeCallbacks(it) };timeout = null
        callback?.let { try { connectivity.unregisterNetworkCallback(it) } catch (_: Exception) {} };callback = null
    }

    private fun finish(info: WifiInfo?) {
        val result = snapshotResult ?: return
        snapshotResult = null;cleanupSnapshot()
        try { result.success(snapshot(info)) }
        catch (_: Exception) { result.error("WIFI_UNAVAILABLE", "Wi-Fi access changed. Refresh the reading.", null) }
    }

    private fun cancelSnapshot(code: String, message: String) {
        val result = snapshotResult;snapshotResult = null;cleanupSnapshot()
        result?.error(code, message, null)
    }

    fun onPermissionResult(requestCode: Int) {
        if (requestCode != PERMISSION_REQUEST) return
        val result = permissionResult;permissionResult = null;result?.success(null)
    }

    fun dispose() {
        channel.setMethodCallHandler(null)
        cancelSnapshot("ACTIVITY_CLOSED", "Wi-Fi diagnostics screen closed.")
        permissionResult?.error("ACTIVITY_CLOSED", "Permission request interrupted.", null);permissionResult = null
    }
}
