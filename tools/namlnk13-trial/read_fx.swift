import Foundation
@main struct ReadFX {
 static func main() {
  guard CommandLine.arguments.count==2 else{exit(2)};let midi=NamMidi()
  do {let devices=try midi.devices();try require(devices.count==1,"Exactly one plug required");let id=devices[0]["source"] as! Int
   let state=try waitFor{midi.inspect(id,completion:$0)};let w=try statusWords(state);try require(w[4]==0&&w[10]==0,"Existing fault")
   let q=NamFxWire.make(0,255,Int.random(in:1...16383))!
   let fx=try waitFor{midi.fx(id,request:q,completion:$0)};try require(fx["error"] as? Int==0,"FX query failed");try require(fx["config"] as? [Int]==NamFxWire.defaults().map(Int.init),"Unexpected initial FX config")
   let stock=try waitFor{midi.stock(id,completion:$0)}
   let report:[String:Any]=["status":"PASS_NAMLNK13_PHYSICAL_DEFAULT_FX_READ","state":state,"fx":fx,"stock":stock,"audioStreams":0,"effectWrites":0,"presetWrites":0]
   try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]).write(to:URL(fileURLWithPath:CommandLine.arguments[1]),options:.atomic)
   print("PASS: NAMLNK13, both new FX slots readable, bypassed defaults, output muted.")
  } catch {print("FAILED: \(error)");exit(1)};midi.disconnect()
 }
}
