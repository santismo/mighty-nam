import Foundation

// Uses the production Mac transport. Only bounded NAM/preset/effect commands;
// no audio streams, output enable, firmware update, reset, or raw memory access.
@main struct PresetTrial {
 static func main() {
  let args=CommandLine.arguments
  guard args.count==5, ["--validate","--save-empty","--verify"].contains(args[1]) else {
   print("Usage: preset-trial --validate|--save-empty|--verify PLAN COUNT REPORT");exit(2)
  }
  let midi=NamMidi();var device:Int?
  var report:[String:Any]=["started":ISO8601DateFormatter().string(from:Date()),"status":"STARTING","mode":args[1],"audioStreamsOpened":0,"macAudioSettingsChanged":false,"teamsSettingsChanged":false,"outputEnableCommands":0,"firmwareUpdateCommands":0,"resetCommands":0]
  var events:[[String:Any]]=[]
  func save(){
   report["events"]=events
   do {try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]).write(to:URL(fileURLWithPath:args[4]),options:.atomic)}
   catch {print("Cannot write evidence: \(error)");exit(2)}
  }
  func record(_ step:String,_ value:[String:Any]) {
   events.append(["step":step,"time":ISO8601DateFormatter().string(from:Date()),"result":value]);save();print(step);fflush(stdout)
  }
  do {
   let plans=try JSONSerialization.jsonObject(with:Data(contentsOf:URL(fileURLWithPath:args[2]))) as! [[String:Any]]
   guard let count=Int(args[3]),(1...7).contains(count),plans.count==7 else {throw CheckError.message("Invalid plan count")}
   var traces:[Trace]=[]
   for (slot,p) in plans.enumerated() {
    try require(p["slot"] as? Int==slot,"Unordered slots")
    let trace=try Trace(p["trace"] as! String);traces.append(trace)
    try require([UInt32(1854512385),UInt32(3399832575)].contains(trace.slotCRC),"Only previously checked captures allowed")
    let name=p["name"] as! String
    try require(!name.isEmpty && name.utf8.count<=63 && name.utf8.allSatisfy{$0>=32 && $0 != 127},"Invalid name")
    try require([8,16,32].contains(p["buffer"] as! Int),"Invalid buffer")
    try require(NamStockWire.Plan(controls:p["controls"] as! [[Int]],order:p["order"] as! [Int],namEnabled:true) != nil,"Invalid effect plan")
   }
   report["plans"]=plans.map {p -> [String:Any] in var q=p;q.removeValue(forKey:"trace");return q}
   if args[1]=="--validate" {report["status"]="PASS_FILES_ONLY";save();return}
   let devices=try midi.devices();try require(devices.count==1,"Require exactly one matching plug")
   let id=devices[0]["source"] as! Int;device=id
   func inspect(_ label:String,crc:UInt32?=nil,active:Int?=nil,buffer:Int?=nil) throws -> [String:Any] {
    let r=try waitFor {midi.inspect(id,completion:$0)};record(label,r)
    let w=try statusWords(r)
    try require(w[4]==0 && w[10]==0,"Processing fault: \(w)")
    let t=r["irqTiming"] as! [String:Any]
    try require(t["usable"] as? Bool==true && (t["rejected"] as? Int64)==0 && (t["flags"] as? Int64)==0,"Unusable IRQ timing")
    if let crc=crc {try require(w[5]==crc && w[9]==1 && w[7]>0 && w[8]>0 && w[8]<150,"Wrong model or stopped processing")}
    if let active=active {try require((r["presetBank"] as? [String:Any])?["active"] as? Int==active,"Wrong active color")}
    if let buffer=buffer {try require((r["audioBuffer"] as? [String:Any])?["samples"] as? Int==buffer,"Wrong buffer")}
    return r
   }
   // Require the exact build before sending even the explicit mute.
   let identity=try waitFor {midi.inspect(id,completion:$0)};record("initial",identity)
   try require(identity["identity"] as? String=="NAMLNK10","Exact NAMLNK10 required")
   record("explicit-mute",try waitFor {midi.listen(id,enabled:false,completion:$0)})
   _=try inspect("muted-before-test")
   var nonce=UInt32.random(in:1...UInt32.max-100)
   func request(_ op:UInt8,_ slot:Int,_ body:[UInt8]=[]) throws -> [UInt8] {
    var q=[UInt8](repeating:0,count:20+body.count)
    writeWord(&q,0,0x3031504e);q[4]=1;q[5]=op;q[6]=UInt8(slot)
    nonce+=1;writeWord(&q,8,nonce);q[12]=UInt8(body.count & 255);q[13]=UInt8(body.count>>8)
    q.replaceSubrange(16..<16+body.count,with:body)
    writeWord(&q,q.count-4,NamLinkWire.crc(q[0..<q.count-4]))
    try require(NamPresetWire.request(q) != nil,"Invalid generated preset request")
    let started=Date()
    let r=try waitFor {midi.preset(id,request:q,completion:$0)}
    guard let raw=r["frame"] as? [UInt8],NamPresetWire.valid(raw),raw.count==276,
     raw[5]==op|128,raw[6]==UInt8(slot),NamLinkWire.word(raw,8)==nonce else {throw CheckError.message("Invalid preset reply")}
    record("preset-op-\(op)-slot-\(slot)",["raw":raw,"elapsedSeconds":Date().timeIntervalSince(started)])
    try require(raw[7]==0,"Preset operation \(op), slot \(slot) rejected with code \(raw[7])")
    return raw
   }
   func checkHeader(_ raw:[UInt8],_ slot:Int,fx:[UInt8]?=nil) throws -> [UInt8] {
    let p=plans[slot],t=traces[slot],h=Array(raw[16..<272])
    try require(raw[15] & (1<<slot) != 0,"Slot is empty")
    try require(NamLinkWire.word(h,0)==0x3142504e && NamLinkWire.word(h,4)==1 && NamLinkWire.word(h,8)==UInt32(slot) && NamLinkWire.word(h,12)>0,"Invalid saved header")
    try require(NamLinkWire.word(h,16)==t.slotCRC && NamLinkWire.word(h,20)==1 && NamLinkWire.word(h,24)==UInt32(p["buffer"] as! Int) && NamLinkWire.word(h,28)==0,"Saved capture/flags/buffer mismatch")
    let sha=h[32..<64].map{String(format:"%02x",$0)}.joined()
    try require(sha==t.slotSHA,"Saved model SHA mismatch")
    if let expected=p["expectedHeader"] as? [Int] {
     try require(h.map(Int.init)==expected,"Saved record metadata changed across power-off")
    }
    let bytes=Array(h[64..<128]);let end=bytes.firstIndex(of:0) ?? 64
    try require(String(bytes:bytes[..<end],encoding:.utf8)==p["name"] as? String && bytes[end...].allSatisfy{$0==0},"Saved name mismatch")
    if let fx=fx {try require(Array(h[128..<256])==fx,"Saved effect bytes differ")}
    return h
   }
   func upload(_ trace:Trace) throws {
    record("mute-before-model",try waitFor {midi.listen(id,enabled:false,completion:$0)})
    var acks:[[String:Any]]=[]
    for (i,f) in trace.frames.enumerated() {
     let r=try waitFor{midi.exchange(id,request:f,completion:$0)}
     guard let raw=r["frame"] as? [UInt8],raw.count==48,NamLinkWire.validPacket(raw),raw[5]==f[5]|128,NamLinkWire.word(raw,8)==NamLinkWire.word(f,8) else {throw CheckError.message("Invalid model reply")}
     let fields=stride(from:24,to:48,by:4).map{NamLinkWire.word(raw,$0)}
     acks.append(["frame":i,"fields":fields]);try require(fields[0]==0 && Array(fields[3...])==[8192,256,3],"Model upload rejected")
     if i>0 {try require(fields[1]==UInt32(i==1 ? 0:min(8192,(i-1)*256)),"Wrong model byte count")}
     if i==34 {try require(fields[2]==trace.slotCRC,"Wrong committed model")}
    }
    record("model-upload",["crc":trace.slotCRC,"sha256":trace.slotSHA,"acks":acks])
   }
   var headers:[Int:[UInt8]]=[:]
   for slot in 0..<count {
    let p=plans[slot],trace=traces[slot]
    let before=try request(1,slot)
    if before[15] & (1<<slot)==0 {
     try require(args[1]=="--save-empty","Cannot verify empty slot")
     // Put inexpensive known controls in place before starting NAM processing.
     let plan=NamStockWire.Plan(controls:p["controls"] as! [[Int]],order:p["order"] as! [Int],namEnabled:true)!
     let fxReply=try waitFor{midi.stock(id,plan:plan,completion:$0)};record("controls-slot-\(slot)",fxReply)
     try require(fxReply["controlsVerified"] as? Bool==true,"Effect controls unconfirmed")
     let fx=(fxReply["preset"] as! [Int]).map{UInt8($0)}
     record("buffer-slot-\(slot)",try waitFor{midi.outputBuffer(id,samples:p["buffer"] as! Int,completion:$0)})
     try upload(trace);pause(1)
     _=try inspect("before-save-\(slot)",crc:trace.slotCRC)
     var body=[UInt8](repeating:0,count:112)
     writeWord(&body,0,trace.slotCRC);writeWord(&body,4,NamLinkWire.crc(fx[...]));writeWord(&body,8,1);writeWord(&body,12,UInt32(p["buffer"] as! Int))
     let sha=trace.slotSHA
     for i in 0..<32 {let a=sha.index(sha.startIndex,offsetBy:i*2);let b=sha.index(a,offsetBy:2);body[16+i]=UInt8(sha[a..<b],radix:16)!}
     body.replaceSubrange(48..<48+(p["name"] as! String).utf8.count,with:Array((p["name"] as! String).utf8))
     let written=try request(2,slot,body)
     let h=try checkHeader(written,slot,fx:fx)
     try require(NamLinkWire.word(h,12)==1,"New slot did not begin at generation 1")
     let reread=try checkHeader(request(1,slot),slot,fx:fx)
     try require(reread==h,"Independent metadata readback differs")
     if slot==0 {
      let duplicate=try checkHeader(request(2,slot,body),slot,fx:fx)
      try require(duplicate==h,"Duplicate save changed generation or contents")
      report["unchangedSaveIsNoOp"]=true
     }
     headers[slot]=h
    } else {
     headers[slot]=try checkHeader(before,slot)
    }
    // Force flash read + model load. Metadata-only reads use the firmware cache.
    let recalled=try checkHeader(request(3,slot),slot)
    try require(recalled==headers[slot],"Recall changed saved metadata")
    pause(1)
    let fxReply=try waitFor{midi.stock(id,completion:$0)};record("recalled-effects-\(slot)",fxReply)
    try require((fxReply["preset"] as? [Int])==Array(recalled[128..<256]).map(Int.init),"Recall did not restore all 128 effect bytes")
    _=try inspect("recall-status-\(slot)",crc:trace.slotCRC,active:slot,buffer:p["buffer"] as? Int)
   }
   // Switch back across every saved slot, without model uploads or saves.
   for slot in (0..<count).reversed() {
    let h=try checkHeader(request(3,slot),slot)
    try require(h==headers[slot],"Saved metadata changed across switching")
    pause(2)
    let fx=try waitFor{midi.stock(id,completion:$0)};record("switch-effects-\(slot)",fx)
    try require(fx["preset"] as? [Int]==Array(h[128..<256]).map(Int.init),"Effects changed across switching")
    _=try inspect("switch-status-\(slot)",crc:traces[slot].slotCRC,active:slot,buffer:plans[slot]["buffer"] as? Int)
   }
   pause(10)
   _=try inspect("final-green-muted",crc:traces[0].slotCRC,active:0,buffer:8)
   report["status"]="PASS_NAMLNK10_PHYSICAL_SAVE_RECALL";report["checkedSlots"]=count
   report["powerOffPersistenceTested"]=false;report["physicalPresetButtonTested"]=false
   report["audibleOutputTested"]=false;report["finalOutputMuted"]=true
  } catch {
   report["status"]="FAILED";report["error"]=String(describing:error)
   if let id=device {
    do {record("failure-mute",try waitFor{midi.listen(id,enabled:false,completion:$0)})}
    catch {report["failureMuteError"]=String(describing:error)}
   }
  }
  midi.disconnect();report["finished"]=ISO8601DateFormatter().string(from:Date());save()
  print(report["status"]!);if let error=report["error"] {print(error);exit(1)}
 }
}
