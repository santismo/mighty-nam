import 'dart:async';
import 'package:flutter/material.dart';
import 'looper.dart';

class LooperDialog extends StatefulWidget {
  final LooperClient client;
  const LooperDialog({super.key, required this.client});
  @override
  State<LooperDialog> createState() => _LooperDialogState();
}

class _LooperDialogState extends State<LooperDialog>
    with WidgetsBindingObserver {
  LoopReading? reading;
  String? error;
  Timer? timer;
  Future<void>? work;
  bool busy = false, changing = false, closing = false, visible = true;
  double threshold = -50, volume = 100;
  bool actionWaiting = false;
  final Map<int, int> pending = {};
  final Set<int> dragging = {};
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    run();
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    visible = state == AppLifecycleState.resumed;
    timer?.cancel();
    if (visible) run();
  }

  void run({int? op, int? arg}) {
    if (busy || closing || !visible || !mounted) return;
    timer?.cancel();
    if (op == null && pending.isNotEmpty) {
      op = pending.keys.first;
      arg = pending.remove(op);
    }
    work = exchange(op, arg);
  }

  Future<void> exchange(int? op, int? arg) async {
    setState(() {
      busy = true;
      changing = op != null;
    });
    bool good = false;
    try {
      final s = op == null
          ? await widget.client.read()
          : await widget.client.change(op, arg!);
      if (!mounted || closing) return;
      setState(() {
        reading = s;
        error = null;
        if (!dragging.contains(2) && !pending.containsKey(2))
          threshold = -s.threshold.toDouble();
        if (!dragging.contains(3) && !pending.containsKey(3))
          volume = s.volume.toDouble();
      });
      good = true;
    } catch (e) {
      if (mounted && !closing)
        setState(() {
          error = e.toString();
          reading = null;
          pending.clear();
        });
    } finally {
      if (mounted)
        setState(() {
          busy = false;
          changing = false;
        });
    }
    if (good && !closing && visible)
      timer = Timer(Duration(milliseconds: pending.isNotEmpty ? 0 : 125), run);
  }

  Future<void> close() async {
    if (closing) return;
    setState(() => closing = true);
    timer?.cancel();
    pending.clear();
    await work;
    if (mounted) Navigator.of(context).pop();
  }

  void setting(int op, int value) {
    pending[op] = value;
    run();
  }

  Future<void> transport(int arg) async {
    if (changing || actionWaiting || closing) return;
    setState(() => actionWaiting = true);
    timer?.cancel();
    await work;
    if (!mounted || closing || !visible) return;
    setState(() => actionWaiting = false);
    run(op: 1, arg: arg);
  }

  Widget action(String text, int arg, {bool allowed = true}) => OutlinedButton(
      onPressed: changing ||
              actionWaiting ||
              closing ||
              reading == null ||
              reading!.faults != 0 ||
              !allowed
          ? null
          : () => transport(arg),
      child: Text(text));
  @override
  Widget build(BuildContext context) {
    final s = reading,
        can = s != null &&
            s.faults == 0 &&
            !closing &&
            !changing &&
            !actionWaiting;
    final db = s?.inputDb, above = s?.reaches(threshold) == true;
    return PopScope(
        canPop: false,
        onPopInvokedWithResult: (p, r) {
          if (!p) unawaited(close());
        },
        child: Dialog(
            child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 620),
                child: SingleChildScrollView(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Row(children: [
                            const Text('Looper',
                                style: TextStyle(fontSize: 22)),
                            const Spacer(),
                            IconButton(
                                key: const ValueKey('close-looper'),
                                onPressed: closing ? null : close,
                                tooltip: 'Close looper',
                                icon: const Icon(Icons.close))
                          ]),
                          const SizedBox(height: 12),
                          Row(children: [
                            Text(
                                s?.faults != null && s!.faults != 0
                                    ? 'Memory check failed'
                                    : s?.label ?? 'Reading…',
                                key: const ValueKey('loop-state'),
                                style:
                                    const TextStyle(color: Color(0xff7ce4bd))),
                            const Spacer(),
                            Text(s == null
                                ? '—'
                                : '${(s.length / (s.seconds == 60 ? 12000 : 24000)).toStringAsFixed(1)} / ${s.seconds} s')
                          ]),
                          const SizedBox(height: 16),
                          Wrap(spacing: 8, runSpacing: 8, children: [
                            action('Arm', 1, allowed: s?.state == 0),
                            action(
                                s?.state == 1
                                    ? 'Cancel arm'
                                    : s?.state == 2
                                        ? 'Finish loop'
                                        : s?.state == 3
                                            ? 'Pause'
                                            : 'Play',
                                2,
                                allowed: s != null && s.state != 0),
                            action(
                                s?.overdub == true ? 'Finish layer' : 'Overdub',
                                6,
                                allowed: s?.state == 3),
                            action('Stop', 4,
                                allowed: s != null && s.state != 0),
                            action('Clear', 5,
                                allowed: s != null && s.state != 0),
                          ]),
                          const SizedBox(height: 24),
                          Row(children: [
                            const Text('Trigger threshold'),
                            const Spacer(),
                            Text('${threshold.round()} dB')
                          ]),
                          Stack(alignment: Alignment.center, children: [
                            Padding(
                                padding:
                                    const EdgeInsets.symmetric(horizontal: 24),
                                child: ClipRRect(
                                    borderRadius: BorderRadius.circular(2),
                                    child: LinearProgressIndicator(
                                        key: const ValueKey('loop-input-meter'),
                                        value: s?.meterFraction ?? 0,
                                        minHeight: 10,
                                        backgroundColor: Colors.white10,
                                        color: above
                                            ? const Color(0xff7ce4bd)
                                            : const Color(0xff74a9cc)))),
                            SliderTheme(
                                data: SliderTheme.of(context).copyWith(
                                    activeTrackColor: Colors.transparent,
                                    inactiveTrackColor: Colors.transparent,
                                    thumbColor: Colors.white,
                                    trackHeight: 10),
                                child: Slider(
                                    key: const ValueKey('loop-threshold'),
                                    value: threshold,
                                    min: -60,
                                    max: -12,
                                    divisions: 48,
                                    label: '${threshold.round()} dB',
                                    onChangeStart:
                                        can ? (_) => dragging.add(2) : null,
                                    onChanged: can
                                        ? (v) => setState(() => threshold = v)
                                        : null,
                                    onChangeEnd: can
                                        ? (v) {
                                            dragging.remove(2);
                                            setting(2, -v.round());
                                          }
                                        : null)),
                          ]),
                          Text(
                              db == null
                                  ? (s == null
                                      ? 'Input —'
                                      : 'Live level needs NAMLNK27')
                                  : 'Input ${db < -60 ? 'below −60' : db.toStringAsFixed(0)} dB · ${above ? 'above' : 'below'} threshold',
                              key: const ValueKey('loop-input-label'),
                              style: const TextStyle(
                                  color: Colors.white60, fontSize: 12)),
                          const SizedBox(height: 20),
                          Row(children: [
                            const Text('Loop level'),
                            const Spacer(),
                            Text('${volume.round()}%')
                          ]),
                          Slider(
                              key: const ValueKey('loop-volume'),
                              value: volume,
                              min: 0,
                              max: 100,
                              divisions: 100,
                              onChangeStart:
                                  can ? (_) => dragging.add(3) : null,
                              onChanged: can
                                  ? (v) => setState(() => volume = v)
                                  : null,
                              onChangeEnd: can
                                  ? (v) {
                                      dragging.remove(3);
                                      setting(3, v.round());
                                    }
                                  : null),
                          Wrap(
                              spacing: 16,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                DropdownButton<int>(
                                    value: s?.seconds ?? 30,
                                    onChanged: can && s.state == 0
                                        ? (v) {
                                            if (v != null) setting(4, v);
                                          }
                                        : null,
                                    items: const [
                                      DropdownMenuItem(
                                          value: 30,
                                          child: Text('30 s · 24 kHz')),
                                      DropdownMenuItem(
                                          value: 60,
                                          child: Text('60 s · 12 kHz'))
                                    ]),
                                action(
                                    s?.mode == true
                                        ? 'Preset controls'
                                        : 'Looper controls',
                                    s?.mode == true ? 10 : 9),
                                TextButton(
                                    onPressed: busy || closing ? null : run,
                                    child: const Text('Refresh')),
                              ]),
                          const SizedBox(height: 16),
                          Wrap(
                              spacing: 12,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                OutlinedButton(
                                    key: const ValueKey('save-loop-settings'),
                                    onPressed: can &&
                                            s.saveSupported &&
                                            s.state == 0 &&
                                            s.length == 0 &&
                                            (!s.saved || pending.isNotEmpty)
                                        ? () => setting(5, 1)
                                        : null,
                                    child: const Text('Save looper settings')),
                                Text(
                                    s?.saveSupported != true
                                        ? 'Saving needs NAMLNK28'
                                        : s!.state != 0 || s.length != 0
                                            ? 'Clear loop before saving'
                                            : s.saved
                                                ? 'Saved on plug'
                                                : 'Live · not saved',
                                    style: const TextStyle(
                                        color: Colors.white54, fontSize: 12)),
                              ]),
                          ExpansionTile(
                              title: const Text('Plug buttons'),
                              children: [
                                Padding(
                                    padding: const EdgeInsets.all(12),
                                    child: Text(s?.saveSupported == true
                                        ? 'PRESET: tap next preset; hold previous. In Looper: tap to arm, finish, pause or play; hold to toggle overdub; tap then hold within 300 ms to clear. POWER: double tap enters Looper, or stops and exits; single tap switches loop/preset controls. Hold POWER to turn off.'
                                        : 'PRESET: tap next preset; hold reverses direction. In Looper: tap to arm, finish, pause or play; hold to clear. POWER: double tap enters Looper, or stops and exits; single tap switches loop/preset controls. Use the Overdub button to layer. Hold POWER to turn off.'))
                              ]),
                          const Text(
                              'Loops stay in memory until cleared or powered off. Close this panel to select presets; playback continues.',
                              style: TextStyle(
                                  color: Colors.white54, fontSize: 12)),
                          if (error != null)
                            Padding(
                                padding: const EdgeInsets.only(top: 12),
                                child: Text(error!,
                                    style: const TextStyle(
                                        color: Colors.orangeAccent))),
                        ])))));
  }
}
