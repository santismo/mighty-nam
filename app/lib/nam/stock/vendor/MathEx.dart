// ignore_for_file: file_names
class MathEx {
  static double map(
      double x, double inMin, double inMax, double outMin, double outMax) {
    return (x - inMin) * (outMax - outMin) / (inMax - inMin) + outMin;
  }
}
