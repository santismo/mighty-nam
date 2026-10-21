import Foundation
@main struct Global19 {
 static func main(){
  let args=CommandLine.arguments
  guard args.count==3 else{print("Usage: global PLAN REPORT");exit(2)}
  let midi=NamMidi();var source:Int?;var events:[[String:Any]]=[];var report:[String:Any]=["status":"STARTING","audioStreamsOpened":0,"explicitOutputCommands":0,"presetSaves":0,"firmwareUpdateCommands":0,"globalSettingWritesPlanned":2,"MacTeamsAudioChanged":false]
  func record(_ name:String,_ result:[String:Any]){events.append(["step":name,"result":result]);print(name);fflush(stdout)}
  do {
   let plans=try JSONSerialization.jsonObject(with:Data(contentsOf:URL(fileURLWithPath:args[1]))) as! [[String:Any]]
   try require(plans.count==7,"Seven verified plans required")
   let devices=try midi.devices();try require(devices.count==1,"Exactly one plug required");let id=devices[0]["source"] as! Int;source=id
   func check(_ label:String,_ samples:Int,_ slot:Int?=nil)throws {
    let s=try waitFor{midi.inspect(id,completion:$0)};let w=try statusWords(s)
    try require(w[4]==0&&w[10]==0&&w[9]==1,"Processing fault or model not running")
    let b=s["audioBuffer"] as! [String:Any],bank=s["presetBank"] as! [String:Any]
    try require(b["samples"] as? Int==samples && b["global"] as? Bool==true && b["storageError"] as? Int==0,"Wrong global buffer")
    try require(bank["mask"] as? Int==127,"Incomplete bank")
    try require((s["listening"] as? [String:Any])?["enabled"] as? Bool==true,"Playback intent changed")
    if let slot=slot{try require(bank["active"] as? Int==slot,"Wrong color")}
    record(label,s)
   }
   try check("initial",8,0)
   var ticket=UInt32.random(in:1...UInt32.max-100)
   for samples in [16,8] {
    let s=try waitFor{midi.outputBuffer(id,samples:samples,completion:$0)}
    try require((s["listening"] as? [String:Any])?["enabled"] as? Bool==true,"Buffer edit changed playback intent")
    record("global-buffer-\(samples)",s)
    for slot in (0..<7).reversed(){
     var q=[UInt8](repeating:0,count:20);writeWord(&q,0,0x3031504e);q[4]=1;q[5]=3;q[6]=UInt8(slot);ticket+=1;writeWord(&q,8,ticket);writeWord(&q,16,NamLinkWire.crc(q[0..<16]))
     let r=try waitFor{midi.preset(id,request:q,completion:$0)}
     guard let raw=r["frame"] as? [UInt8],raw.count==276,NamPresetWire.valid(raw),raw[7]==0,NamLinkWire.word(raw,8)==ticket else{throw CheckError.message("Recall failed")}
     var expected=(plans[slot]["expectedHeader"] as! [Int]).map(UInt8.init);writeWord(&expected,24,UInt32(samples))
     try require(Array(raw[16..<272])==expected,"Preset data changed beyond effective global buffer")
     pause(0.5);try check("buffer-\(samples)-color-\(slot)",samples,slot)
    }
   }
   report["status"]="PASS_GLOBAL_BUFFER_16_AND_8_ACROSS_ALL_SEVEN_COLORS_OUTPUT_PRESERVED"
  } catch {
   report["status"]="FAILED";report["error"]=String(describing:error)
   // Restore the requested global value only, with no explicit output commands.
   if let id=source{do{record("restore-global-eight",try waitFor{midi.outputBuffer(id,samples:8,completion:$0)})}catch{report["restoreError"]=String(describing:error)}}
  }
  midi.disconnect();report["events"]=events
  do{try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]).write(to:URL(fileURLWithPath:args[2]),options:.atomic)}catch{print(error);exit(1)}
  print(report["status"]!);if let error=report["error"]{print(error);exit(1)}
 }
}
