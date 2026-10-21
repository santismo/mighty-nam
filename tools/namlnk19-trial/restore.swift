import Foundation
@main struct Restore19 {
 static func main(){
  let args=CommandLine.arguments
  guard args.count==4,["--validate","--restore"].contains(args[1]) else{print("Usage: restore --validate|--restore PLAN REPORT");exit(2)}
  let midi=NamMidi();var events:[[String:Any]]=[]
  var report:[String:Any]=["identity":"NAMLNK19","started":ISO8601DateFormatter().string(from:Date()),"status":"STARTING","audioStreamsOpened":0,"outputEnableCommands":0,"firmwareUpdateCommands":0,"resetCommands":0,"MacTeamsAudioChanged":false]
  func flush(){do{try JSONSerialization.data(withJSONObject:report.merging(["events":events]){_,new in new},options:[.prettyPrinted,.sortedKeys]).write(to:URL(fileURLWithPath:args[3]),options:.atomic)}catch{print("Report failed: \(error)")}}
  func record(_ label:String,_ data:[String:Any]){events.append(["step":label,"result":data]);flush();print(label);fflush(stdout)}
  do {
   let plans=try JSONSerialization.jsonObject(with:Data(contentsOf:URL(fileURLWithPath:args[2]))) as! [[String:Any]]
   try require(plans.count==7,"Seven plans required");var traces:[Trace]=[]
   for (index,p) in plans.enumerated(){
    try require(p["slot"] as? Int==index,"Ordered slots required");let t=try Trace(p["trace"] as! String);traces.append(t)
    try require([UInt32(1854512385),UInt32(3399832575)].contains(t.slotCRC),"Only checked Fender/Marshall captures allowed")
    let h=(p["expectedHeader"] as! [Int]).map(UInt8.init);try require(h.count==256&&NamLinkWire.word(h,16)==t.slotCRC&&NamLinkWire.word(h,20)==1,"Invalid restore header")
    try require(h[32..<64].map{String(format:"%02x",$0)}.joined()==t.slotSHA,"Model hash differs")
    try require(NamStockWire.Plan(controls:p["controls"] as! [[Int]],order:p["order"] as! [Int],namEnabled:p["namEnabled"] as? Bool) != nil,"Invalid control plan")
    try require(NamFxWire.config((p["extraFx"] as! [Int]).map(UInt8.init)),"Invalid FX plan")
    _=try RestoreSupplement.messages(Array(p["expectedHeader"] as! [Int]).suffix(128).map{$0})
   }
   if args[1]=="--validate"{report["status"]="PASS_FILES_ONLY";flush();return}
   let devices=try midi.devices();try require(devices.count==1,"Exactly one plug required");let source=devices[0]["source"] as! Int
   let first=try waitFor{midi.inspect(source,completion:$0)};record("initial",first);try require(first["identity"] as? String=="NAMLNK19","Exact NAMLNK19 required")
   var nonce=Int.random(in:1...15000);var active=255
   func inspect(_ label:String,_ expected:UInt32?=nil)throws->[String:Any]{
    let s=try waitFor{midi.inspect(source,completion:$0)};record(label,s);let w=try statusWords(s)
    try require(w[4]==0&&w[10]==0,"Processing fault");if let expected=expected{try require(w[5]==expected&&w[9]==1,"Capture not running")}
    let timing=s["irqTiming"] as! [String:Any];try require(timing["usable"] as? Bool==true&&(timing["flags"] as? Int64)==0&&(timing["rejected"] as? Int64)==0,"Invalid IRQ timing")
    active=(s["presetBank"] as! [String:Any])["active"] as! Int;return s
   }
   let start=try inspect("before-restore-no-mute-command");try require((start["presetBank"] as! [String:Any])["mask"] as? Int==0,"Refuse to overwrite occupied bank")
   var ticket=UInt32.random(in:1...UInt32.max-100)
   func preset(_ op:UInt8,_ slot:Int,_ body:[UInt8]=[])throws->[UInt8]{
    var q=[UInt8](repeating:0,count:20+body.count);writeWord(&q,0,0x3031504e);q[4]=1;q[5]=op;q[6]=UInt8(slot);ticket+=1;writeWord(&q,8,ticket);q[12]=UInt8(body.count&255);q[13]=UInt8(body.count>>8);q.replaceSubrange(16..<16+body.count,with:body);writeWord(&q,q.count-4,NamLinkWire.crc(q[0..<q.count-4]))
    let r=try waitFor{midi.preset(source,request:q,completion:$0)};guard let raw=r["frame"] as? [UInt8],raw.count==276,NamPresetWire.valid(raw),raw[5]==op|128,raw[6]==slot,NamLinkWire.word(raw,8)==ticket,raw[7]==0 else{throw CheckError.message("Preset request failed")};return raw
   }
   func fx(_ op:Int,_ config:[UInt8]?=nil,_ crc:UInt32=0,_ saved:Int?=nil)throws->[UInt8]{
    nonce=nonce%16383+1;let slot=saved ?? active
    var q=NamFxWire.prefix+[UInt8(op),UInt8(slot==255 ? 127:slot),UInt8(nonce&127),UInt8(nonce>>7)]
    if op==1{q += [0]+(0..<5).map{UInt8((crc>>(7*$0))&127)}};if let c=config{q+=c};q+=[247];try require(NamFxWire.request(q),"Invalid FX request")
    let r=try waitFor{midi.fx(source,request:q,completion:$0)};guard let raw=r["frame"] as? [UInt8],NamFxWire.reply(raw,to:q) != nil,raw[13]==0 else{throw CheckError.message("FX request failed")};return Array(raw[15..<47])
   }
   func upload(_ trace:Trace)throws {
    for (i,f) in trace.frames.enumerated(){let r=try waitFor{midi.exchange(source,request:f,completion:$0)}
     guard let raw=r["frame"] as? [UInt8],raw.count==48,NamLinkWire.validPacket(raw),raw[5]==f[5]|128,NamLinkWire.word(raw,8)==NamLinkWire.word(f,8) else{throw CheckError.message("Invalid model reply")}
     let fields=stride(from:24,to:48,by:4).map{NamLinkWire.word(raw,$0)};try require(fields[0]==0&&Array(fields[3...])==[8192,256,3],"Transfer failed")
     if i>0{try require(fields[1]==UInt32(i==1 ? 0:min(8192,(i-1)*256)),"Incomplete model transfer")};if i==34{try require(fields[2]==trace.slotCRC,"Wrong active model")}
    }
   }
   for (slot,p) in plans.enumerated(){
    let trace=traces[slot],expected=(p["expectedHeader"] as! [Int]).map(UInt8.init),expectedFx=Array(expected[128..<256]),extra=(p["extraFx"] as! [Int]).map(UInt8.init)
    let empty=try preset(1,slot);try require(empty[15]&(1<<slot)==0,"Occupied destination; stopping")
    record("restore-supplement-\(slot)",try RestoreSupplement.apply(midi,source,expectedFx.map(Int.init)))
    let plan=NamStockWire.Plan(controls:p["controls"] as! [[Int]],order:p["order"] as! [Int],namEnabled:p["namEnabled"] as? Bool)!
    let applied=try waitFor{midi.stock(source,plan:plan,completion:$0)};try require(applied["controlsVerified"] as? Bool==true&&applied["preset"] as? [Int]==expectedFx.map(Int.init),"All 128 preset bytes must match before save")
    _=try waitFor{midi.outputBuffer(source,samples:p["buffer"] as! Int,completion:$0)}
    try upload(trace);pause(1);_=try inspect("loaded-slot-\(slot)",trace.slotCRC)
    try require(try fx(1,extra,trace.slotCRC)==extra,"FX write mismatch");try require(try fx(0)==extra,"FX readback mismatch")
    var body=[UInt8](repeating:0,count:112);writeWord(&body,0,trace.slotCRC);writeWord(&body,4,NamLinkWire.crc(expectedFx[...]));writeWord(&body,8,1);writeWord(&body,12,UInt32(p["buffer"] as! Int));body.replaceSubrange(16..<48,with:expected[32..<64]);body.replaceSubrange(48..<112,with:expected[64..<128])
    let written=try preset(2,slot,body);let read=try preset(1,slot)
    try require(Array(written[16..<272])==expected&&Array(read[16..<272])==expected,"Saved metadata differs from restore plan")
    try require(try fx(2,nil,0,slot)==extra,"Saved extra FX differ")
    record("saved-verified-slot-\(slot)",["name":p["name"]!,"captureCRC":trace.slotCRC,"buffer":p["buffer"]!,"all128EffectBytesMatch":true,"extraFxMatch":true,"bootPlay":true]);active=slot
   }
   for slot in (0..<7).reversed(){
    let p=plans[slot],expected=(p["expectedHeader"] as! [Int]).map(UInt8.init),extra=(p["extraFx"] as! [Int]).map(UInt8.init)
    let recalled=try preset(3,slot);try require(Array(recalled[16..<272])==expected,"Recall changed saved metadata");pause(1)
    let s=try inspect("recall-slot-\(slot)",traces[slot].slotCRC);try require(active==slot&&(s["audioBuffer"] as! [String:Any])["samples"] as? Int==p["buffer"] as? Int,"Wrong recalled color/buffer")
    let stock=try waitFor{midi.stock(source,completion:$0)};try require(stock["preset"] as? [Int]==Array(expected[128..<256]).map(Int.init),"Recalled stock effects differ")
    try require(try fx(0)==extra,"Recalled FX differ")
   }
   // Restore the saved startup playback preference; never send an explicit mute.
   record("enable-restored-green-playback",try waitFor{midi.listen(source,enabled:true,completion:$0)})
   pause(3);let final=try inspect("final-green-playing",traces[0].slotCRC)
   try require((final["listening"] as? [String:Any])?["enabled"] as? Bool==true,"Restored Green playback not enabled")
   try require((final["presetBank"] as! [String:Any])["mask"] as? Int==127,"Seven-color bank not occupied")
   report["status"]="PASS_NAMLNK19_PHYSICAL_RESTORE";report["restoredSlots"]=7;report["finalOutputMuted"]=false;report["outputEnableCommands"]=1;report["explicitMuteCommands"]=0;report["backupSource"]="NAMLNK17-preset-backup (taken before NAMLNK17; no fresh pre-NAMLNK19 backup)";report["physicalButtonTested"]=false;report["powerCycleTested"]=false;report["physicalBluetoothTested"]=false;report["listeningLatencyMeasured"]=false;report["inputPitchAccuracyMeasured"]=false
  }catch{
   report["status"]="FAILED";report["error"]=String(describing:error)
   print("FAILED: \(error)")
  }
  midi.disconnect();flush();if report["status"] as? String=="FAILED"{exit(1)}
 }
}
