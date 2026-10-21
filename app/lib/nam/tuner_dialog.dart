import 'dart:async';
import 'package:flutter/material.dart';
import 'tuner.dart';

class TunerDialog extends StatefulWidget {
  final TunerClient client;
  const TunerDialog({super.key, required this.client});
  @override
  State<TunerDialog> createState() => _TunerDialogState();
}

class _TunerDialogState extends State<TunerDialog> {
  TunerReading? reading;
  String? error;
  bool closing = false;
  int reference = 440;
  late Future<void> work;
  @override
  void initState() {
    super.initState();
    work = run();
  }

  Future<void> run() async {
    try {
      while (mounted && !closing) {
        final samples =
            await widget.client.capture(cancelled: () => closing || !mounted);
        if (!mounted || closing) break;
        setState(() {
          reading = samples == null
              ? null
              : detectPitch(samples, referenceHz: reference.toDouble());
        });
        await Future<void>.delayed(const Duration(milliseconds: 30));
      }
    } catch (_) {
      if (mounted && !closing) {
        setState(() {
          reading = null;
          error = 'Tuner connection lost. Close and reconnect the plug.';
        });
      }
    }
  }

  Future<void> close() async {
    if (closing) return;
    setState(() => closing = true);
    await work;
    String? failure;
    try {
      await widget.client.stop();
    } catch (_) {
      failure =
          'Plug disconnected. Its tuner capture stops automatically; reconnect to check its state.';
    }
    if (mounted) Navigator.of(context).pop(failure);
  }

  @override
  Widget build(BuildContext context) {
    final pitch = reading;
    final color = pitch?.inTune == true
        ? const Color(0xff95d0ae)
        : const Color(0xff8ebcef);
    return PopScope(
        canPop: false,
        onPopInvokedWithResult: (didPop, result) {
          if (!didPop) unawaited(close());
        },
        child: Dialog(
            child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 480),
                child: SingleChildScrollView(
                    child: Padding(
                        padding: const EdgeInsets.all(28),
                        child:
                            Column(mainAxisSize: MainAxisSize.min, children: [
                          Row(children: [
                            const Text('Tuner',
                                style: TextStyle(
                                    fontSize: 22, fontWeight: FontWeight.w600)),
                            const Spacer(),
                            IconButton(
                                key: const ValueKey('close-tuner'),
                                tooltip: 'Close tuner',
                                onPressed: closing ? null : close,
                                icon: const Icon(Icons.close))
                          ]),
                          const SizedBox(height: 12),
                          const Text('USB guitar input · Plug muted',
                              style: TextStyle(color: Colors.white60)),
                          const SizedBox(height: 20),
                          SizedBox(
                              height: 116,
                              child: Center(
                                  child: Text(
                                      pitch == null
                                          ? '—'
                                          : '${pitch.note}${pitch.octave}',
                                      key: const ValueKey('tuner-note'),
                                      style: TextStyle(
                                          fontSize: 82,
                                          fontWeight: FontWeight.w500,
                                          color: color)))),
                          SizedBox(
                              height: 48,
                              child: LayoutBuilder(
                                  builder: (context, constraints) => Stack(
                                          alignment: Alignment.center,
                                          children: [
                                            Container(
                                                height: 2,
                                                color: Colors.white24),
                                            Container(
                                                width:
                                                    constraints.maxWidth * 0.06,
                                                height: 24,
                                                decoration: BoxDecoration(
                                                    color:
                                                        const Color(0xff95d0ae)
                                                            .withValues(
                                                                alpha: .15),
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                            4))),
                                            for (final x in [
                                              -50,
                                              -25,
                                              0,
                                              25,
                                              50
                                            ])
                                              Positioned(
                                                  left: ((x + 50) /
                                                      100 *
                                                      (constraints.maxWidth -
                                                          2)),
                                                  child: Container(
                                                      width: 2,
                                                      height: x == 0 ? 30 : 14,
                                                      color: Colors.white38)),
                                            if (pitch != null)
                                              Positioned(
                                                  left: ((pitch.cents
                                                              .clamp(-50, 50) +
                                                          50) /
                                                      100 *
                                                      (constraints.maxWidth -
                                                          4)),
                                                  child: Container(
                                                      width: 4,
                                                      height: 40,
                                                      decoration: BoxDecoration(
                                                          color: color,
                                                          borderRadius:
                                                              BorderRadius
                                                                  .circular(
                                                                      2)))),
                                          ]))),
                          const Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text('Flat'),
                                Text('In tune'),
                                Text('Sharp')
                              ]),
                          const SizedBox(height: 18),
                          Text(
                              error ??
                                  (pitch == null
                                      ? 'Play one string and let it ring'
                                      : '${pitch.cents >= 0 ? '+' : ''}${pitch.cents.toStringAsFixed(1)} cents  ·  ${pitch.frequency.toStringAsFixed(1)} Hz'),
                              key: const ValueKey('tuner-detail'),
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                  color: error == null
                                      ? Colors.white70
                                      : Colors.orangeAccent)),
                          const SizedBox(height: 22),
                          Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Text('Reference A'),
                                const SizedBox(width: 14),
                                DropdownButton<int>(
                                    value: reference,
                                    onChanged: closing
                                        ? null
                                        : (v) {
                                            if (v != null) {
                                              setState(() {
                                                reference = v;
                                                reading = null;
                                              });
                                            }
                                          },
                                    items: [
                                      for (var i = 430; i <= 450; i++)
                                        DropdownMenuItem(
                                            value: i, child: Text('$i Hz'))
                                    ])
                              ]),
                          const SizedBox(height: 10),
                          const Text(
                              'Close, then press Listen on plug to resume playing.',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                  fontSize: 12, color: Colors.white54)),
                          if (closing)
                            const Padding(
                                padding: EdgeInsets.only(top: 12),
                                child: LinearProgressIndicator()),
                        ]))))));
  }
}
