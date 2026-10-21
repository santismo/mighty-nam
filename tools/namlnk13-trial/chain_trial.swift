import Foundation

@main struct ChainTrial {
 static func main() {
  let args=CommandLine.arguments
  guard args.count==3 else{print("Usage: chain-trial TRACE_PREFIX REPORT");exit(2)}
  let midi=NamMidi();var source:Int?;var trace:Trace?;var original:[Int]?;var active=255;var nonce=Int.random(in:1...15000)
  var events:[[String:Any]]=[]
  var report:[String:Any]=["status":"STARTING","audioStreams":0,"outputEnableCommands":0,"firmwareCommands":0,"resetCommands":0,"MacTeamsAudioChanged":false,"oldPresetsRestored":false]
  func flush(){do{try JSONSerialization.data(withJSONObject:report.merging(["events":events]){_,new in new},options:[.prettyPrinted,.sortedKeys]).write(to:URL(fileURLWithPath:args[2]),options:.atomic)}catch{print("Evidence write failed: \(error)")}}
  func record(_ step:String,_ value:[String:Any]){events.append(["step":step,"time":ISO8601DateFormatter().string(from:Date()),"result":value]);flush();print(step);fflush(stdout)}
  do {
   let verified=try Trace(args[1]);trace=verified
   let devices=try midi.devices();try require(devices.count==1,"Exactly one plug required");let id=devices[0]["source"] as! Int;source=id
   func inspect(_ label:String,loaded:Bool=true)throws->[String:Any]{
    let s=try waitFor{midi.inspect(id,completion:$0)};record(label,s)
    let w=try statusWords(s);try require(w[4]==0 && w[10]==0,"Processing fault during \(label)")
    if loaded{try require(w[5]==verified.slotCRC && w[9]==1 && w[8]<150,"Wrong capture or stopped processing")}
    let timing=s["irqTiming"] as! [String:Any];try require(timing["usable"] as? Bool==true && timing["flags"] as? Int64==0 && timing["rejected"] as? Int64==0,"Invalid IRQ timing")
    active=(s["presetBank"] as! [String:Any])["active"] as! Int;return s
   }
   let initial=try inspect("initial",loaded:false)
   try require((initial["presetBank"] as! [String:Any])["mask"] as? Int==0,"Trial requires empty bank; will not overwrite a saved preset")
   record("explicit-mute",try waitFor{midi.listen(id,enabled:false,completion:$0)})
   let before=try waitFor{midi.stock(id,completion:$0)};record("stock-before",before);original=before["preset"] as? [Int];try require(original?.count==128,"Missing stock snapshot")
   func stock(_ enabled:Set<Int>)throws {
    let choices=[1:1,2:1,4:1,5:1,6:1,7:1,8:4,9:1]
    let controls=[1,2,4,5,6,7,8,9].map{[$0,choices[$0]!|(enabled.contains($0) ? 0:64)]}
    guard let plan=NamStockWire.Plan(controls:controls,order:[5,1,2,3,9,4,6,7,8],namEnabled:true) else {throw CheckError.message("Invalid stock trial plan")}
    let result=try waitFor{midi.stock(id,plan:plan,completion:$0)};try require(result["controlsVerified"] as? Bool==true,"Stock controls not verified");record("stock-enabled-\(enabled.sorted())",result)
   }
   try stock([])
   record("buffer-8",try waitFor{midi.outputBuffer(id,samples:8,completion:$0)})
   for (i,frame) in verified.frames.enumerated(){
    let response=try waitFor{midi.exchange(id,request:frame,completion:$0)}
    guard let raw=response["frame"] as? [UInt8],raw.count==48,NamLinkWire.validPacket(raw),raw[5]==(frame[5]|128),NamLinkWire.word(raw,8)==NamLinkWire.word(frame,8) else{throw CheckError.message("Invalid model reply")}
    let fields=stride(from:24,to:48,by:4).map{NamLinkWire.word(raw,$0)}
    try require(fields[0]==0 && Array(fields[3...])==[8192,256,3],"Model upload rejected")
    if i>0{try require(fields[1]==UInt32(i==1 ? 0:min(8192,(i-1)*256)),"Wrong model byte count")}
    if i==34{try require(fields[2]==verified.slotCRC,"Wrong committed model")}
   }
   record("Fender-upload",["crc":verified.slotCRC,"sha256":verified.slotSHA,"frames":verified.frames.count]);pause(3)
   _=try inspect("NAM-baseline")
   func fx(_ config:[UInt8])throws {
    nonce=nonce%16383+1;let request=NamFxWire.make(1,active,nonce,config,verified.slotCRC)!
    let result=try waitFor{midi.fx(id,request:request,completion:$0)}
    try require(result["error"] as? Int==0 && result["config"] as? [Int]==config.map(Int.init),"FX write not acknowledged")
    nonce=nonce%16383+1;let read=NamFxWire.make(0,active,nonce)!
    let checked=try waitFor{midi.fx(id,request:read,completion:$0)}
    try require(checked["error"] as? Int==0 && checked["active"] as? Int==active && checked["config"] as? [Int]==config.map(Int.init),"FX readback mismatch")
    record("FX-config",checked)
   }
   for mode in 1...7 {
    var c=NamFxWire.defaults();c[0]=UInt8(mode);c[1]=1;c[3]=24
    try fx(c);pause(3);_=try inspect("FX-A-mode-\(mode)")
   }
   for (index,pair) in [[1,2],[1,1],[3,4],[5,6],[7,2]].enumerated(){
    var c=NamFxWire.defaults();c[0]=UInt8(pair[0]);c[16]=UInt8(pair[1]);c[1]=1;c[17]=1;c[3]=0;c[19]=24
    c[2]=index%2==0 ? 2:10;c[18]=index%2==0 ? 3:0
    try fx(c);pause(3);_=try inspect("dual-FX-\(pair)-reorder-\(index)")
   }
   var c=NamFxWire.defaults();c[1]=1;c[17]=1;c[3]=19
   try fx(c);try stock([1,2,4,5,6,7,8]);pause(5);_=try inspect("NAM-stock-effects-pitch-wah")
   // Leave a dry, quiet baseline and save only a fresh Green preset.
   try stock([]);try fx(NamFxWire.defaults());pause(2);_=try inspect("dry-baseline-restored")
   let current=try waitFor{midi.stock(id,completion:$0)};let effects=(current["preset"] as! [Int]).map(UInt8.init)
   func preset(_ op:UInt8,_ body:[UInt8]=[])throws->[UInt8]{
    var q=[UInt8](repeating:0,count:20+body.count);writeWord(&q,0,0x3031504e);q[4]=1;q[5]=op;q[6]=0
    let ticket=UInt32.random(in:1...UInt32.max);writeWord(&q,8,ticket);q[12]=UInt8(body.count&255);q[13]=UInt8(body.count>>8);q.replaceSubrange(16..<16+body.count,with:body);writeWord(&q,q.count-4,NamLinkWire.crc(q[0..<q.count-4]))
    let result=try waitFor{midi.preset(id,request:q,completion:$0)}
    guard let raw=result["frame"] as? [UInt8],raw.count==276,NamPresetWire.valid(raw),raw[5]==(op|128),raw[6]==0,raw[7]==0,NamLinkWire.word(raw,8)==ticket else{throw CheckError.message("Preset operation failed")};return raw
   }
   var body=[UInt8](repeating:0,count:112);writeWord(&body,0,verified.slotCRC);writeWord(&body,4,NamLinkWire.crc(effects[...]));writeWord(&body,8,0);writeWord(&body,12,8)
   let sha=Array(verified.slotSHA);for i in 0..<32{body[16+i]=UInt8(String(sha[i*2..<i*2+2]),radix:16)!}
   let name=Array("Fender A2 Lite".utf8);body.replaceSubrange(48..<48+name.count,with:name)
   let saved=try preset(2,body);let checked=try preset(1)
   try require(Array(saved[16..<272])==Array(checked[16..<272]) && checked[15]==1 && NamLinkWire.word(checked,32)==verified.slotCRC,"Saved Green mismatch")
   record("fresh-green-saved-muted",["modelCrc":verified.slotCRC,"name":"Fender A2 Lite","occupiedMask":1,"bootPlay":false])
   _=try preset(3);pause(2);_=try inspect("final-green-muted")
   report["status"]="PASS_NAMLNK13_PHYSICAL_MUTED_CHAIN_TRIAL";report["realGuitarInputTested"]=false;report["listeningQualityTested"]=false;report["BluetoothTested"]=false;report["powerCycleTested"]=false;report["savedFreshPresetCount"]=1
  } catch {
   report["status"]="FAILED";report["error"]=String(describing:error)
   if let id=source {
    do {record("failure-mute",try waitFor{midi.listen(id,enabled:false,completion:$0)})}catch{report["muteError"]=String(describing:error)}
    if let t=trace {do{let q=NamFxWire.make(1,active,16383,NamFxWire.defaults(),t.slotCRC)!;record("failure-bypass-FX",try waitFor{midi.fx(id,request:q,completion:$0)})}catch{report["FXCleanupError"]=String(describing:error)}}
   }
  }
  midi.disconnect();flush();print(report["status"]!);if let error=report["error"]{print(error);exit(1)}
 }
}
