package com.example.frontend

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.os.Handler
import android.os.Looper
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodChannel

/** Hints only. Dart verifies pinned TLS before any authenticated HTTP request. */
@Suppress("DEPRECATION")
class LanDiscoveryChannel(context: Context, messenger: BinaryMessenger) {
    private val channel = MethodChannel(messenger, "fyp/lan_discovery")
    private val manager = context.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val connectivity = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    private val handler = Handler(Looper.getMainLooper())
    private val executor = java.util.concurrent.Executor { handler.post(it) }
    private var result: MethodChannel.Result? = null
    private var listener: NsdManager.DiscoveryListener? = null
    private var generation = 0
    private val candidates = mutableListOf<Map<String, Any>>()
    private val queue = java.util.ArrayDeque<NsdServiceInfo>()
    private var resolving = false
    private fun wifi(): Boolean {
        val caps = connectivity.getNetworkCapabilities(connectivity.activeNetwork) ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) &&
            !caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)
    }
    init {
        channel.setMethodCallHandler { call, reply ->
            if (call.method != "discover") { reply.notImplemented(); return@setMethodCallHandler }
            finish()
            if (!wifi()) { reply.success(mapOf("wifi" to false, "candidates" to emptyList<Any>())); return@setMethodCallHandler }
            result = reply
            candidates.clear(); queue.clear(); resolving = false
            val epoch = ++generation
            val discovery = object : NsdManager.DiscoveryListener {
                override fun onDiscoveryStarted(type: String) {}
                override fun onDiscoveryStopped(type: String) {}
                override fun onServiceLost(info: NsdServiceInfo) {}
                override fun onStartDiscoveryFailed(type: String, code: Int) { handler.post { if (epoch == generation) finish() } }
                override fun onStopDiscoveryFailed(type: String, code: Int) {}
                override fun onServiceFound(info: NsdServiceInfo) { handler.post {
                    if (epoch == generation && queue.size < 16 && candidates.size < 8 &&
                        info.serviceType == "_fyp-classroom._tcp.") {
                        queue.add(info); resolveNext(epoch)
                    }
                } }
            }
            listener = discovery
            try {
                if (Build.VERSION.SDK_INT >= 33) {
                    manager.discoverServices("_fyp-classroom._tcp.", NsdManager.PROTOCOL_DNS_SD,
                        connectivity.activeNetwork, executor, discovery)
                } else {
                    manager.discoverServices("_fyp-classroom._tcp.", NsdManager.PROTOCOL_DNS_SD, discovery)
                }
                handler.postDelayed({ if (epoch == generation) finish() }, 4000)
            } catch (_: Exception) { finish() }
        }
    }
    private fun resolveNext(epoch: Int) {
        if (resolving || queue.isEmpty() || epoch != generation || candidates.size >= 8) return
        resolving = true
        try {
            manager.resolveService(queue.removeFirst(), object : NsdManager.ResolveListener {
                override fun onResolveFailed(info: NsdServiceInfo, code: Int) { handler.post {
                    if (epoch == generation) { resolving = false; resolveNext(epoch) }
                } }
                override fun onServiceResolved(info: NsdServiceInfo) { handler.post {
                    if (epoch == generation) {
                        val ip = info.host?.hostAddress
                        if (ip != null && info.port == 8005) candidates.add(mapOf("address" to ip, "port" to info.port))
                        resolving = false; resolveNext(epoch)
                    }
                } }
            })
        } catch (_: Exception) { resolving = false; resolveNext(epoch) }
    }
    private fun finish() {
        generation++
        listener?.let { try { manager.stopServiceDiscovery(it) } catch (_: Exception) {} }
        listener = null
        val subnets = connectivity.getLinkProperties(connectivity.activeNetwork)?.linkAddresses
            ?.filter { it.address is java.net.Inet4Address }
            ?.map { mapOf("address" to it.address.hostAddress, "prefix" to it.prefixLength) } ?: emptyList()
        result?.success(mapOf("wifi" to wifi(), "subnets" to subnets, "candidates" to candidates.toList()))
        result = null; queue.clear()
    }
    fun dispose() { finish(); channel.setMethodCallHandler(null) }
}
