List<int> neutralNamTone() => [48, 12, 12, 12, 100, 48];
void validateNamTone(List<int> c) {
  if (c.length != 6 ||
      List.generate(6, (i) => c[i] < 0 || c[i] > [96, 24, 24, 24, 100, 96][i])
          .any((v) => v)) {
    throw const FormatException('Invalid NAM controls');
  }
}

List<int> readNamTone(List<int> p) {
  if (p[33] != 78 || ![1, 2].contains(p[34])) return neutralNamTone();
  final c = p.sublist(27, 33);
  validateNamTone(c);
  return c;
}
