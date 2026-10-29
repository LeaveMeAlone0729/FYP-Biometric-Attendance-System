import 'package:flutter/services.dart';

/// Private keys never cross this channel; signing returns only a DER signature.
class DeviceKeyStore {
  const DeviceKeyStore();
  static const channel = MethodChannel('attendance/device_registration');

  Future<Map<String, dynamic>?> getPublicKey(String studentId) async {
    final data = await channel.invokeMapMethod<String, dynamic>(
      'getPublicKey',
      {'student_id': studentId},
    );
    return data;
  }

  Future<Map<String, dynamic>> getOrCreateKey(String studentId) async {
    final data = await channel.invokeMapMethod<String, dynamic>(
      'getOrCreateKey',
      {'student_id': studentId},
    );
    if (data == null) {
      throw StateError('Android Keystore returned no public key.');
    }
    return data;
  }

  Future<String> sign(String studentId, String payload) async {
    final signature = await channel.invokeMethod<String>('sign', {
      'student_id': studentId,
      'signing_payload': payload,
    });
    if (signature == null) {
      throw StateError('Android Keystore returned no signature.');
    }
    return signature;
  }
}
