import 'dart:io';
import 'dart:convert';
import 'package:nam_link/nam_link.dart';
void main(List<String> args){File(args[0]).writeAsStringSync('${const JsonEncoder.withIndent('  ').convert({'schema':'nam-plug-effects-1','sample_rate':48000,'maximum_blocks':12,'routing':'ordered mono serial','effects':effectCatalog.map((e)=>{'id':e.id,'key':e.key,'name':e.name,'category':e.category,'repeatable':e.repeatable,'parameters':e.parameters.map((p)=>{'name':p.name,'min':p.min,'max':p.max,'default':p.initial,'unit':p.unit}).toList()}).toList(),'extensions':{'ids':[64,127],'maximum_registered':4,'loading':'compiled-in C++ callbacks; not arbitrary downloaded executable code'},'hardware_effects_validation':'pending; portable engine only'} )}\n');}
