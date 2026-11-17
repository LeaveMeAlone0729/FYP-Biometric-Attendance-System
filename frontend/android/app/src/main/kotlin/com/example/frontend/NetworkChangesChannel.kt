package com.example.frontend

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.LinkProperties
import android.os.Handler
import android.os.Looper
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.EventChannel

/** Transport lifecycle only; never an attendance authorization signal. */
class NetworkChangesChannel(context: Context, messenger: BinaryMessenger) : EventChannel.StreamHandler {
    private val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    private val channel = EventChannel(messenger, "fyp/network_changes")
    private val handler = Handler(Looper.getMainLooper())
    private var sink: EventChannel.EventSink? = null
    private var last: Network? = manager.activeNetwork
    private var registered = false
    private var addresses: List<String> = emptyList()
    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            if (network != last) { last = network; changed() }
        }
        override fun onLost(network: Network) {
            if (network == last) { last = null; changed() }
        }
        override fun onLinkPropertiesChanged(network: Network, properties: LinkProperties) {
            if (network == last) {
                val next = properties.linkAddresses.map { it.toString() }.sorted()
                if (addresses.isNotEmpty() && next != addresses) changed()
                addresses = next
            }
        }
    }
    private fun changed() { handler.post { sink?.success("changed") } }
    init { channel.setStreamHandler(this) }
    override fun onListen(arguments: Any?, events: EventChannel.EventSink) {
        sink = events
        last = manager.activeNetwork
        addresses = emptyList()
        if (!registered) { manager.registerDefaultNetworkCallback(callback); registered = true }
    }
    override fun onCancel(arguments: Any?) {
        sink = null
        if (registered) { manager.unregisterNetworkCallback(callback); registered = false }
    }
    fun dispose() { onCancel(null); channel.setStreamHandler(null) }
}
