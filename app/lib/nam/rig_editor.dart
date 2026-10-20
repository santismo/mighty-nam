import 'package:flutter/material.dart';
import 'stock/rig.dart';
import 'stock/catalog.dart';
import 'stock/control_plan.dart';

const rigColors = {
  'gate': Color(0xff9aadc2),
  'comp': Color(0xffe5c779),
  'drive': Color(0xfff4ac75),
  'nam': Color(0xff7bddf3),
  'cab': Color(0xff8aa6ee),
  'eq': Color(0xffa6d88a),
  'mod': Color(0xffc3a0ef),
  'delay': Color(0xff7ce4bd),
  'reverb': Color(0xffeea5c9),
};
const rigIcons = {
  'gate': Icons.multiline_chart,
  'comp': Icons.compress,
  'drive': Icons.bolt,
  'nam': Icons.graphic_eq,
  'cab': Icons.speaker_outlined,
  'eq': Icons.equalizer,
  'mod': Icons.ssid_chart,
  'delay': Icons.repeat,
  'reverb': Icons.waves,
};

class RigEditor extends StatefulWidget {
  final HybridRig rig;
  final Widget namControls;
  final String? modelName;
  final VoidCallback onChanged;
  const RigEditor(
      {super.key,
      required this.rig,
      required this.namControls,
      required this.onChanged,
      this.modelName});
  @override
  State<RigEditor> createState() => _RigEditorState();
}

class _RigEditorState extends State<RigEditor> {
  String selected = 'nam';
  Future<void> chooseEffect(RigBlock block) async {
    final choice = await showDialog<int>(
        context: context, builder: (_) => _EffectPicker(block: block));
    if (mounted && choice != null) change(() => block.choice = choice);
  }

  void change(VoidCallback action) {
    setState(action);
    widget.onChanged();
  }

  @override
  Widget build(BuildContext context) {
    final b = widget.rig.blocks.firstWhere((b) => b.slot == selected);
    final color = rigColors[b.slot]!;
    final index = widget.rig.blocks.indexOf(b);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Row(children: [
        Text('INPUT', style: TextStyle(fontSize: 11, color: Colors.white54)),
        SizedBox(width: 12),
        Expanded(child: Divider(color: Color(0xff404449))),
        SizedBox(width: 12),
        Text('OUTPUT', style: TextStyle(fontSize: 11, color: Colors.white54)),
      ]),
      const SizedBox(height: 16),
      SizedBox(
          height: 122,
          child: LayoutBuilder(
              builder: (context, width) => ReorderableListView.builder(
                    key: const ValueKey('signal-chain'),
                    scrollDirection: Axis.horizontal,
                    itemExtent: (width.maxWidth / widget.rig.blocks.length)
                        .clamp(94.0, 108.0),
                    buildDefaultDragHandles: false,
                    itemCount: widget.rig.blocks.length,
                    onReorder: (old, next) => change(() {
                      if (next > old) next--;
                      selected = widget.rig.blocks[old].slot;
                      widget.rig.reorder(old, next);
                    }),
                    proxyDecorator: (child, _, animation) =>
                        Material(color: Colors.transparent, child: child),
                    itemBuilder: (context, i) {
                      final item = widget.rig.blocks[i],
                          c = rigColors[item.slot]!;
                      return Padding(
                        key: ValueKey('block-${item.slot}'),
                        padding: const EdgeInsets.only(right: 10),
                        child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              onTap: () => setState(() => selected = item.slot),
                              borderRadius: BorderRadius.circular(6),
                              child: Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                    color: selected == item.slot
                                        ? const Color(0xff2b3036)
                                        : const Color(0xff202327),
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(
                                        color: selected == item.slot
                                            ? c
                                            : const Color(0xff3d4147),
                                        width: 1)),
                                child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Row(children: [
                                        IconButton(
                                            key:
                                                ValueKey('toggle-${item.slot}'),
                                            tooltip: item.enabled
                                                ? 'Turn off ${item.name}'
                                                : 'Turn on ${item.name}',
                                            padding: EdgeInsets.zero,
                                            constraints: const BoxConstraints(
                                                minWidth: 30, minHeight: 30),
                                            visualDensity:
                                                VisualDensity.compact,
                                            onPressed: () => change(() {
                                                  selected = item.slot;
                                                  item.enabled = !item.enabled;
                                                }),
                                            icon: Icon(rigIcons[item.slot],
                                                size: 21,
                                                color: item.enabled
                                                    ? c
                                                    : Colors.white30)),
                                        const Spacer(),
                                        ReorderableDragStartListener(
                                            index: i,
                                            child: MouseRegion(
                                                cursor: SystemMouseCursors.grab,
                                                child: Icon(
                                                    Icons.drag_indicator,
                                                    key: ValueKey(
                                                        'drag-${item.slot}'),
                                                    size: 20,
                                                    color: Colors.white38))),
                                      ]),
                                      const Spacer(),
                                      Text(item.name,
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: TextStyle(
                                              fontSize: 12,
                                              color: item.enabled
                                                  ? Colors.white
                                                  : Colors.white38,
                                              fontWeight: FontWeight.w600)),
                                      const SizedBox(height: 4),
                                      Text(
                                          item.enabled
                                              ? (item.effect?.name ??
                                                  widget.modelName ??
                                                  'Choose tone')
                                              : 'Bypassed',
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: TextStyle(
                                              fontSize: 10, color: c)),
                                    ]),
                              ),
                            )),
                      );
                    },
                  ))),
      const Padding(
          padding: EdgeInsets.symmetric(vertical: 12),
          child: Text(
              'Click a symbol to turn an effect on or off. Select a block to edit. Drag to reorder.',
              style: TextStyle(fontSize: 11, color: Colors.white38))),
      Container(
        key: const ValueKey('selected-controls'),
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
            color: const Color(0xff202327),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color.withValues(alpha: .25))),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            Icon(rigIcons[b.slot], color: color),
            const SizedBox(width: 12),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(b.slot == 'nam' ? 'NAM amplifier' : b.name,
                      style: const TextStyle(
                          fontWeight: FontWeight.w600, fontSize: 20)),
                  Text(
                      b.slot == 'nam'
                          ? 'Your captures and favorites'
                          : 'Mighty Plug Pro · ${b.choices.length} ${b.choices.length == 1 ? 'effect' : 'effects'}',
                      style:
                          const TextStyle(fontSize: 12, color: Colors.white54)),
                ])),
            Tooltip(
                message: b.enabled ? 'Bypass ${b.name}' : 'Enable ${b.name}',
                child: Switch(
                    key: ValueKey('bypass-${b.slot}'),
                    value: b.enabled,
                    onChanged: (v) => change(() => b.enabled = v))),
          ]),
          const SizedBox(height: 22),
          if (b.slot == 'nam')
            widget.namControls
          else ...[
            OutlinedButton(
                key: ValueKey('choose-effect-${b.slot}'),
                onPressed: () => chooseEffect(b),
                style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 16)),
                child: Row(children: [
                  Expanded(
                      child: Text(b.effect!.name,
                          maxLines: 1, overflow: TextOverflow.ellipsis)),
                  const SizedBox(width: 12),
                  const Icon(Icons.unfold_more, size: 20),
                ])),
            const SizedBox(height: 18),
            LayoutBuilder(
                builder: (context, constraints) => Wrap(
                      spacing: 24,
                      runSpacing: 12,
                      children: [
                        for (final p in b.effect!.parameters)
                          SizedBox(
                              width: constraints.maxWidth >= 650
                                  ? (constraints.maxWidth - 24) / 2
                                  : constraints.maxWidth,
                              child: parameter(b, p, color))
                      ],
                    )),
          ],
          const SizedBox(height: 12),
          Row(children: [
            IconButton(
                tooltip: 'Move earlier',
                onPressed: index == 0
                    ? null
                    : () => change(() => widget.rig.reorder(index, index - 1)),
                icon: const Icon(Icons.arrow_back)),
            IconButton(
                tooltip: 'Move later',
                onPressed: index == widget.rig.blocks.length - 1
                    ? null
                    : () => change(() => widget.rig.reorder(index, index + 1)),
                icon: const Icon(Icons.arrow_forward)),
            const Spacer(),
            Text(b.enabled ? 'On' : 'Off',
                style: const TextStyle(fontSize: 12, color: Colors.white54)),
          ]),
        ]),
      ),
    ]);
  }

  Widget parameter(RigBlock b, Parameter p, Color color) {
    final f = p.formatter;
    if (f is SwitchFormatter) {
      return DropdownButtonFormField<int>(
          menuMaxHeight: 280,
          key: ValueKey('${b.slot}-${b.choice}-${p.handle}'),
          decoration: InputDecoration(labelText: p.name),
          value: p.value.round(),
          items: [
            for (var i = 0; i < f.midiValues.length; i++)
              DropdownMenuItem(
                  value: f.midiValues[i], child: Text(f.labelValues[i]))
          ],
          onChanged: !b.enabled
              ? null
              : (v) {
                  if (v != null) change(() => p.value = v.toDouble());
                });
    }
    return Column(children: [
      Row(children: [
        Text(p.name),
        const Spacer(),
        Text(f.toLabel(p.value), style: TextStyle(color: color))
      ]),
      Slider(
          key: ValueKey('${b.slot}-${b.choice}-${p.handle}'),
          value: p.value,
          min: f.min.toDouble(),
          max: f.max.toDouble(),
          activeColor: color,
          onChanged: b.enabled ? (v) => change(() => p.value = v) : null),
    ]);
  }
}

class _EffectPicker extends StatefulWidget {
  final RigBlock block;
  const _EffectPicker({required this.block});
  @override
  State<_EffectPicker> createState() => _EffectPickerState();
}

class _EffectPickerState extends State<_EffectPicker> {
  final scroll = ScrollController();
  String query = '';
  @override
  void dispose() {
    scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final block = widget.block;
    final matches = [
      for (var i = 0; i < block.choices.length; i++)
        if (block.choices[i].name.toLowerCase().contains(query.toLowerCase())) i
    ];
    return Dialog(
        insetPadding: const EdgeInsets.all(24),
        child: SizedBox(
            key: const ValueKey('effect-picker'),
            width: 460,
            height:
                (MediaQuery.sizeOf(context).height * .65).clamp(240.0, 480.0),
            child: Column(children: [
              Padding(
                  padding: const EdgeInsets.fromLTRB(20, 12, 8, 8),
                  child: Row(children: [
                    Expanded(
                        child: Text('Choose ${block.name.toLowerCase()}',
                            style: const TextStyle(
                                fontSize: 20, fontWeight: FontWeight.w600))),
                    IconButton(
                        key: const ValueKey('close-effect-picker'),
                        tooltip: 'Close effect list',
                        onPressed: () => Navigator.pop(context),
                        icon: const Icon(Icons.close)),
                  ])),
              Padding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
                  child: TextField(
                      key: const ValueKey('search-effects'),
                      decoration: const InputDecoration(
                          hintText: 'Search effects',
                          prefixIcon: Icon(Icons.search)),
                      onChanged: (value) {
                        if (scroll.hasClients) scroll.jumpTo(0);
                        setState(() => query = value);
                      })),
              const Divider(height: 1),
              Expanded(
                  child: matches.isEmpty
                      ? const Center(child: Text('No matching effects'))
                      : Scrollbar(
                          controller: scroll,
                          thumbVisibility: true,
                          child: ListView.builder(
                              key: const ValueKey('effect-options'),
                              controller: scroll,
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              itemCount: matches.length,
                              itemBuilder: (context, row) {
                                final index = matches[row];
                                final supported =
                                    block.choices[index].nuxIndex <=
                                        StockControlPlan
                                            .supportedTypes[block.slot]!;
                                return ListTile(
                                    key: ValueKey('effect-option-$index'),
                                    title: Text(block.choices[index].name,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis),
                                    enabled: supported,
                                    subtitle: supported
                                        ? null
                                        : const Text(
                                            'Unavailable on this firmware'),
                                    selected: index == block.choice,
                                    trailing: index == block.choice
                                        ? const Icon(Icons.check, size: 20)
                                        : null,
                                    onTap: supported
                                        ? () => Navigator.pop(context, index)
                                        : null);
                              }))),
            ])));
  }
}
