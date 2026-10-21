import Foundation
@main struct VerifyRestart{static func main(){
 let midi=NamMidi();var source:Int?;var result:[String:Any]=["status":"STARTING","audioStreams":0,"outputEnableCommands":0,"presetWrites":0,"firmwareWrites":0,"MacTeamsAudioChanged":false]
 do{
  let plans=try JSONSerialization.jsonObject(with:Data(contentsOf:URL(fileURLWithPath:CommandLine.arguments[1]))) as! [[String:Any]];try require(plans.count==7,"Seven plans required")
  let d=try midi.devices();try require(d.count==1,"One plug required");let id=d[0]["source"] as! Int;source=id
  let before=try waitFor{midi.inspect(id,completion:$0)};result["beforeMute"]=before
  try require(before["identity"] as? String=="NAMLNK16","Wrong firmware")
  result["standaloneOutputWasOn"]=(before["listening"] as? [String:Any])?["enabled"] as? Bool==true
  _=try waitFor{midi.listen(id,enabled:false,completion:$0)}
  let muted=try waitFor{midi.inspect(id,completion:$0)};let w=try statusWords(muted)
  try require(w[4]==0&&w[10]==0&&w[5]==1854512385&&w[9]==1,"Green capture not healthy")
  try require((muted["presetBank"] as! [String:Any])["mask"] as? Int==127&&(muted["presetBank"] as! [String:Any])["active"] as? Int==0,"Seven-color bank or Green missing")
  try require((muted["audioBuffer"] as! [String:Any])["samples"] as? Int==8,"Green buffer not 8")
  var checked:[[String:Any]]=[]
  for (slot,p) in plans.enumerated(){
   var q=[UInt8](repeating:0,count:20);writeWord(&q,0,0x3031504e);q[4]=1;q[5]=1;q[6]=UInt8(slot);let nonce=UInt32.random(in:1...UInt32.max);writeWord(&q,8,nonce);writeWord(&q,16,NamLinkWire.crc(q[0..<16]))
   let r=try waitFor{midi.preset(id,request:q,completion:$0)}
   guard let raw=r["frame"] as? [UInt8],raw.count==276,NamPresetWire.valid(raw),raw[5]==129,raw[6]==slot,raw[7]==0,raw[15]==127,NamLinkWire.word(raw,8)==nonce else{throw CheckError.message("Preset read invalid")}
   try require(Array(raw[16..<272]).map(Int.init)==p["expectedHeader"] as? [Int],"Saved record changed after power-off")
   let token=Int.random(in:1...16383);let fq=NamFxWire.prefix+[2,UInt8(slot),UInt8(token&127),UInt8(token>>7),247]
   let fr=try waitFor{midi.fx(id,request:fq,completion:$0)}
   guard let f=fr["frame"] as? [UInt8],NamFxWire.reply(f,to:fq) != nil,f[13]==0,Array(f[15..<47]).map(Int.init)==p["extraFx"] as? [Int] else{throw CheckError.message("FX saved state changed")}
   checked.append(["slot":slot,"name":p["name"]!,"captureEffectsBufferStartupAndFxMatch":true])
  }
  let stock=try waitFor{midi.stock(id,completion:$0)};try require(stock["preset"] as? [Int]==Array((plans[0]["expectedHeader"] as! [Int]).suffix(128)),"Green live effects differ")
  result["checkedPresets"]=checked;result["final"]=try waitFor{midi.inspect(id,completion:$0)}
  _=try statusWords(result["final"] as! [String:Any]);result["status"]="PASS_NAMLNK16_PHYSICAL_POWER_CYCLE";result["userReportedSevenColorButtonCycle"]=true;result["finalOutputMuted"]=true
 }catch{result["status"]="FAILED";result["error"]=String(describing:error);if let id=source{_ = try? waitFor{midi.listen(id,enabled:false,completion:$0)}}}
 midi.disconnect()
 do{try JSONSerialization.data(withJSONObject:result,options:[.prettyPrinted,.sortedKeys]).write(to:URL(fileURLWithPath:CommandLine.arguments[2]),options:.atomic)}catch{print(error);exit(1)}
 print(result["status"]!);if let error=result["error"]{print(error);exit(1)}
}}
