package com.example.frontend

import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodChannel
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.Signature
import java.security.spec.ECGenParameterSpec

/** Registration keys stay in AndroidKeyStore. No export, deletion or replacement method. */
internal object DeviceKeyStoreChannel {
    private const val CHANNEL = "attendance/device_registration"
    private fun alias(studentId: String): String {
        require(studentId.matches(Regex("[A-Za-z0-9]{1,11}"))) { "Invalid student account." }
        val hash = MessageDigest.getInstance("SHA-256")
            .digest(studentId.uppercase(java.util.Locale.ROOT).toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        return "attendance.device.v1.$hash"
    }

    fun register(messenger: BinaryMessenger) {
        val channel = MethodChannel(messenger, CHANNEL,
            io.flutter.plugin.common.StandardMethodCodec.INSTANCE, messenger.makeBackgroundTaskQueue())
        channel.setMethodCallHandler { call, result ->
            try {
                if (call.method !in listOf("getPublicKey", "getOrCreateKey", "sign")) {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                val studentId = call.argument<String>("student_id")
                    ?: throw IllegalArgumentException("Sign in before registering a device.")
                val keyAlias = alias(studentId)
                val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
                if (call.method == "getOrCreateKey" && !store.containsAlias(keyAlias)) {
                    val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore")
                    generator.initialize(KeyGenParameterSpec.Builder(keyAlias, KeyProperties.PURPOSE_SIGN)
                        .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                        .setDigests(KeyProperties.DIGEST_SHA256)
                        .setUserAuthenticationRequired(false)
                        .build())
                    generator.generateKeyPair()
                }
                if (!store.containsAlias(keyAlias)) {
                    if (call.method == "getPublicKey") result.success(null)
                    else result.error("KEY_MISSING", "The installation key is unavailable. Replacement requires approval.", null)
                    return@setMethodCallHandler
                }
                val privateKey = store.getKey(keyAlias, null) as? PrivateKey
                    ?: throw IllegalStateException("Android Keystore key is unavailable.")
                check(privateKey.encoded == null) { "A non-exportable Android Keystore key is required." }
                if (call.method == "sign") {
                    val encoded = call.argument<String>("signing_payload")
                        ?: throw IllegalArgumentException("Missing signing payload.")
                    require(encoded.length <= 8192) { "Signing payload is too large." }
                    val signature = Signature.getInstance("SHA256withECDSA")
                    signature.initSign(privateKey)
                    signature.update(Base64.decode(encoded, Base64.DEFAULT))
                    result.success(Base64.encodeToString(signature.sign(), Base64.NO_WRAP))
                } else {
                    val publicKey = store.getCertificate(keyAlias).publicKey.encoded
                    val fingerprint = MessageDigest.getInstance("SHA-256").digest(publicKey)
                        .joinToString("") { "%02x".format(it.toInt() and 0xff) }
                    result.success(mapOf(
                        "public_key_spki" to Base64.encodeToString(publicKey, Base64.NO_WRAP),
                        "public_key_fingerprint" to fingerprint,
                        "device_model" to "${Build.MANUFACTURER} ${Build.MODEL}".take(150)))
                }
            } catch (e: IllegalArgumentException) {
                result.error("INVALID_ARGUMENT", e.message, null)
            } catch (e: Exception) {
                // Fail closed: never generate an exportable software fallback key.
                result.error("KEYSTORE_UNAVAILABLE", "Android Keystore could not complete this operation. Restart the app and retry. No replacement was made.", null)
            }
        }
    }
}
