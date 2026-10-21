import Foundation

// Authorized, headphones-unplugged trial only. Production bounded CoreMIDI
// controls; no host audio, firmware/preset writes, reset or output-enable call.
@main struct TimingTrial {
 static func main() {
  let args=CommandLine.arguments
  guard args.count==3,["NAMLNK16","NAMLNK17"].contains(args[1]) else {print("Usage: timing NAMLNK16|NAMLNK17 REPORT");exit(2)}
  let midi=NamMidi();var source:Int?;var original:[UInt8]?;var originalFx:[UInt8]?;var oldBuffer:Int?
  var crc:UInt32=0;var active=255;var nonce=1;var events:[[String:Any]]=[]
  var report:[String:Any]=["status":"STARTING","identity":args[1],"hostAudioAccess":false,"MacTeamsAudioChanged":false,"firmwareWrites":0,"presetWrites":0,"outputEnableCommands":0,"physicalLatencyMeasured":false,"hardwareDeadlineProven":false,"inputStimulus":"Uncontrolled quiet guitar input; no injected test signal","history":"Existing model/effect history retained; not a fresh-boot baseline"]
  func record(_ label:String,_ result:[String:Any]){events.append(["step":label,"result":result]);print(label);fflush(stdout)}
  func words(_ value:[String:Any]) throws -> [Int64] {
   try require(value["identity"] as? String==args[1],"Unexpected firmware identity")
   if args[1]=="NAMLNK17" {try require((value["codecStartup"] as? [String:Any])?["verified"] as? Bool==true,"Converter startup readback did not verify")}
   guard let w=value["words"] as? [Int64],w.count==12 else{throw CheckError.message("Invalid status")}
   try require(w[4]==0 && w[10]==0 && w[9]==1 && UInt32(w[5])==crc,"Processing fault, stopped NAM or capture changed")
   try require((value["listening"] as? [String:Any])?["enabled"] as? Bool==false,"Output must remain muted")
   return w
  }
  func fx(_ op:UInt8,_ config:[UInt8]?=nil) throws -> [UInt8] {
   guard let id=source else{throw CheckError.message("No source")};nonce=nonce%16383+1
   var q=NamFxWire.prefix+[op,UInt8(active==255 ? 127:active),UInt8(nonce&127),UInt8(nonce>>7)]
   if op==1{q += [0]+(0..<5).map{UInt8((crc>>(7*$0))&127)};q+=config!};q+=[247]
   try require(NamFxWire.request(q),"Invalid bounded FX request")
   let r=try waitFor{midi.fx(id,request:q,completion:$0)}
   guard let f=r["frame"] as? [UInt8],NamFxWire.reply(f,to:q) != nil,f[13]==0,Int(f[14])==active else{throw CheckError.message("FX reply mismatch")}
   return Array(f[15..<47])
  }
  func apply(_ values:[UInt8]) throws {
   guard let id=source else{throw CheckError.message("No source")}
   var controls=NamStockWire.heads.keys.sorted().map{[$0,Int(values[$0])]}
   for (range,start) in NamStockWire.groups{for cc in range{controls.append([cc,Int(values[start+cc-range.lowerBound])])}}
   guard let plan=NamStockWire.Plan(controls:controls,order:values[90..<99].map(Int.init),namEnabled:values[3]&64==0) else{throw CheckError.message("Unrestorable effect settings")}
   let r=try waitFor{midi.stock(id,plan:plan,completion:$0)}
   try require(r["controlsVerified"] as? Bool==true && r["preset"] as? [Int]==values.map(Int.init),"Exact stock control readback failed")
  }
  func restore() throws {
   guard let id=source else{return}
   _=try waitFor{midi.listen(id,enabled:false,completion:$0)}
   if let p=original{try apply(p)}
   if let f=originalFx{try require(try fx(1,f)==f,"FX restore mismatch")}
   if let b=oldBuffer{_=try waitFor{midi.outputBuffer(id,samples:b,completion:$0)}}
   pause(1)
   let final=try waitFor{midi.inspect(id,completion:$0)};_=try words(final);record("original-settings-restored-muted",final)
   report["originalSettingsRestored"]=true
  }
  do {
   let devices=try midi.devices();try require(devices.count==1,"Exactly one plug required");let id=devices[0]["source"] as! Int;source=id
   let first=try waitFor{midi.inspect(id,completion:$0)};try require(first["identity"] as? String==args[1],"Unexpected firmware identity")
   if args[1]=="NAMLNK17" {try require((first["codecStartup"] as? [String:Any])?["verified"] as? Bool==true,"Converter startup readback did not verify")}
   guard let w=first["words"] as? [Int64],w.count==12,w[5]>0,w[4]==0,w[10]==0 else{throw CheckError.message("Load a healthy saved capture first")}
   crc=UInt32(w[5]);active=(first["presetBank"] as! [String:Any])["active"] as! Int
   oldBuffer=(first["audioBuffer"] as! [String:Any])["samples"] as? Int;report["captureCRC"]=crc;record("initial",first)
   _=try waitFor{midi.listen(id,enabled:false,completion:$0)}
   let stock=try waitFor{midi.stock(id,completion:$0)}
   guard let values=stock["preset"] as? [Int],values.count==128,values.allSatisfy({(0...127).contains($0)}) else{throw CheckError.message("Invalid stock snapshot")}
   original=values.map(UInt8.init);originalFx=try fx(0)
   _=try waitFor{midi.outputBuffer(id,samples:8,completion:$0)}
   var disabled=originalFx!;disabled[1]=0;disabled[17]=0;try require(try fx(1,disabled)==disabled,"FX bypass mismatch")
   var minimal=original!;for key in NamStockWire.heads.keys{minimal[key]|=64};minimal[3]&=63
   var spring=minimal;spring[8]=4;spring[70]=20;spring[71]=20;spring[72]=50;spring[73]=0
   for (label,p) in [("NAM-only",minimal),("NAM-plus-Spring",spring),("NAM-after-bypassing-Spring",minimal)] {
    try apply(p);pause(2);var rows:[[String:Any]]=[];var lastAccepted:Int64=0
    for _ in 0..<24 {
     let s=try waitFor{midi.inspect(id,completion:$0)};_=try words(s)
     guard let t=s["irqTiming"] as? [String:Any],t["usable"] as? Bool==true,let accepted=t["accepted"] as? Int64,accepted>lastAccepted else{throw CheckError.message("Invalid or stalled timing snapshot")}
     try require((s["audioBuffer"] as? [String:Any])?["samples"] as? Int==8,"Buffer changed")
     lastAccepted=accepted;rows.append(t);pause(0.1)
    }
    record(label,["rawIRQTiming":rows,"stockEffects":p.map(Int.init),"fx":disabled.map(Int.init),"bufferSamples":8])
   }
   try restore();report["status"]="PASS_"+args[1]+"_SILENT_MINIMAL_CHAIN_TIMING"
  }catch {
   report["status"]="FAILED";report["error"]=String(describing:error)
   do{try restore()}catch{report["restoreError"]=String(describing:error)}
  }
  midi.disconnect();report["events"]=events
  do{try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]).write(to:URL(fileURLWithPath:args[2]),options:.atomic)}catch{print(error);exit(1)}
  print(report["status"]!);if let error=report["error"]{print(error);exit(1)}
 }
}
