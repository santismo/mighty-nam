import Foundation

// Bounded dry-input capture through the production transport. No Mac audio,
// model transfers, effect edits, preset saves, output enable, reset or update.
@main struct TunerTrial {
 static func main() {
  guard CommandLine.arguments.count==2 else {print("Usage: tuner-trial PRIVATE_REPORT");exit(2)}
  let midi=NamMidi();var id:Int?
  var report:[String:Any]=["status":"STARTING","audioStreams":0,"presetWrites":0,"modelWrites":0,"effectWrites":0,"outputEnableCommands":0,"firmwareCommands":0]
  var events:[[String:Any]]=[]
  func record(_ step:String,_ result:[String:Any]) {events.append(["step":step,"result":result])}
  do {
   let devices=try midi.devices();try require(devices.count==1,"Exactly one plug required")
   let device=devices[0]["source"] as! Int;id=device
   let initial=try waitFor{midi.inspect(device,completion:$0)};record("initial",initial)
   try require(initial["identity"] as? String=="NAMLNK12","Exact NAMLNK12 required before any write")
   record("mute",try waitFor{midi.listen(device,enabled:false,completion:$0)})
   pause(0.3)
   let before=try waitFor{midi.inspect(device,completion:$0)};record("before",before)
   let baseline=try statusWords(before);try require(baseline[4]==0 && baseline[10]==0,"Existing processing fault")
   let fxBefore=try waitFor{midi.stock(device,completion:$0)};record("effects-before",fxBefore)
   var nonce=Int.random(in:1...16000)
   func request(_ op:Int,_ page:Int=0) throws -> [UInt8] {
    nonce=nonce%16383+1
    let response=try waitFor{midi.tuner(device,operation:op,page:page,nonce:nonce,completion:$0)}
    guard let raw=response["frame"] as? [UInt8],raw.count==280,
     raw[7]==0,raw[5]==UInt8(op|128),raw[6]==UInt8(page),NamLinkWire.word(raw,8)==UInt32(nonce) else {throw CheckError.message("Invalid tuner result")}
    return raw
   }
   var captures:[[String:Any]]=[];var previous:UInt32?
   for attempt in 0..<3 {
    let started=Date();let start=try request(1);let generation=NamLinkWire.word(start,12)
    try require(previous==nil || generation != previous!,"Capture generation did not advance")
    previous=generation;pause(0.2)
    var samples:[Int]=[]
    for page in 0..<16 {
     let raw=try request(2,page)
     try require(NamLinkWire.word(raw,12)==generation && Int(raw[18])+256*Int(raw[19])==2048,"Incomplete or mixed capture")
     for i in 0..<128 {samples.append(Int(Int16(bitPattern:UInt16(raw[20+2*i])|UInt16(raw[21+2*i])<<8)))}
    }
    let repeatPage=try request(2,0)
    let repeated=(0..<128).map{Int(Int16(bitPattern:UInt16(repeatPage[20+2*$0])|UInt16(repeatPage[21+2*$0])<<8))}
    try require(Array(samples.prefix(128))==repeated && NamLinkWire.word(repeatPage,12)==generation,"Snapshot was not frozen")
    captures.append(["attempt":attempt,"generation":generation,"samples":samples,"elapsedSeconds":Date().timeIntervalSince(started),"peakInt16":samples.map{abs($0)}.max() ?? 0])
   }
   report["captures"]=captures
   let stopped=try request(0);try require(stopped[18]==0 && stopped[19]==0,"Stop did not clear capture")
   record("stop",["generation":NamLinkWire.word(stopped,12),"count":0])
   let after=try waitFor{midi.inspect(device,completion:$0)};record("after",after)
   let final=try statusWords(after);try require(final[4]==0 && final[10]==0 && final[5]==baseline[5] && final[9]==baseline[9],"Processing/model state changed")
   for key in ["audioBuffer","presetBank"] {
    try require(NSDictionary(dictionary:before[key] as! [String:Any]).isEqual(to:after[key] as! [String:Any]),"Saved state changed: \(key)")
   }
   let fxAfter=try waitFor{midi.stock(device,completion:$0)};record("effects-after",fxAfter)
   try require(fxBefore["preset"] as? [Int]==fxAfter["preset"] as? [Int],"Effects changed")
   let timing=after["irqTiming"] as! [String:Any]
   try require(timing["usable"] as? Bool==true && (timing["rejected"] as? Int64)==0 && (timing["flags"] as? Int64)==0,"IRQ timing became invalid")
   report["status"]="PASS_NAMLNK12_PHYSICAL_TUNER_TRANSPORT"
   report["realGuitarPitchAccuracyVerified"]=false
   report["finalMuted"]=true
  } catch {
   report["status"]="FAILED";report["error"]=String(describing:error)
   if let device=id {
    do {
     let current=try waitFor{midi.inspect(device,completion:$0)}
     if current["identity"] as? String=="NAMLNK12" {
      record("failure-mute",try waitFor{midi.listen(device,enabled:false,completion:$0)})
      record("failure-stop",try waitFor{midi.tuner(device,operation:0,page:0,nonce:16383,completion:$0)})
     }
    } catch {report["cleanupError"]=String(describing:error)}
   }
  }
  midi.disconnect();report["events"]=events
  do {try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]).write(to:URL(fileURLWithPath:CommandLine.arguments[1]),options:.atomic)}
  catch {print("Evidence write failed: \(error)");exit(2)}
  print(report["status"]!);if let error=report["error"] {print(error);exit(1)}
 }
}
