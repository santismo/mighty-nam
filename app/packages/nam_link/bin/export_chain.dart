import 'dart:io';
import 'package:nam_link/nam_link.dart';
void main(List<String> args){
 final p=args.length>1?ChainPreset.parse(File(args[1]).readAsStringSync()):ChainPreset('All effects',effectCatalog.map((s)=>ChainBlock(s.key,s)).toList());
 File(args[0]).writeAsBytesSync(p.compile());print(p.encodeJson());
}
