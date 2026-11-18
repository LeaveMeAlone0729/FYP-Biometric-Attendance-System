import 'package:flutter/material.dart';
import '../../../services/api_client.dart';

/// Manual input supplies only an address hint; the installed TLS pin is mandatory.
class ClassroomConnectionCard extends StatefulWidget {
  const ClassroomConnectionCard({super.key});
  @override
  State<ClassroomConnectionCard> createState() =>
      _ClassroomConnectionCardState();
}

class _ClassroomConnectionCardState extends State<ClassroomConnectionCard> {
  final _address = TextEditingController();
  bool _busy = false;
  String? _message;
  Future<void> _connect({bool manual = false}) async {
    final api = ApiClient.instance;
    final discovery = api.lanDiscovery;
    if (discovery == null) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      api.networkChanged(); // Abandon any in-progress classroom proof.
      if (manual) discovery.manualAddress(_address.text.trim());
      await discovery.ensureReady();
      if (mounted) {
        setState(
          () => _message =
              'Paired classroom server connected: ${discovery.address}',
        );
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _message =
              'Cannot verify the paired classroom server. Check Wi-Fi and the server address. A different server requires explicit re-pairing.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    _address.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (ApiClient.instance.lanDiscovery == null) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Classroom connection',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const Text('Connect to the paired server on classroom Wi-Fi.'),
            const SizedBox(height: 8),
            OutlinedButton(
              onPressed: _busy ? null : _connect,
              child: Text(_busy ? 'Checking…' : 'Refresh classroom connection'),
            ),
            TextField(
              controller: _address,
              enabled: !_busy,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Server IPv4 address (if discovery is blocked)',
              ),
            ),
            TextButton(
              onPressed: _busy ? null : () => _connect(manual: true),
              child: const Text('Verify paired server at this address'),
            ),
            if (_message != null) Text(_message!, semanticsLabel: _message),
          ],
        ),
      ),
    );
  }
}
