import Foundation
@main struct Test {
 static func main() throws {
  let rows=try JSONSerialization.jsonObject(with:Data(contentsOf:URL(fileURLWithPath:CommandLine.arguments[1]))) as! [[String:Any]]
  var checks=0
  for row in rows {
   let config=(row["config"] as! [Int]).map(UInt8.init),slot=row["slot"] as! Int,nonce=row["nonce"] as! Int,crc=(row["crc"] as! NSNumber).uint32Value
   let read=NamFxWire.make(0,slot,nonce)!,write=NamFxWire.make(1,slot,nonce,config,crc)!
   precondition(read.map(Int.init)==row["read"] as! [Int]);precondition(write.map(Int.init)==row["write"] as! [Int]);checks+=2
   precondition(NamFxWire.validRequest(read)&&NamFxWire.validRequest(write));checks+=2
   for i in [0,6,8,13,18,29,30,31,32,33,34,35,36,45,46,47,48,49,50,51] {var bad=write;bad[i]=255;precondition(!NamFxWire.validRequest(bad));checks+=1}
   let reply=Array(write.prefix(9))+[65,write[10],write[11],write[12],0,write[10]]+config+[247]
   precondition(NamFxWire.reply(reply,to:write)?["config"] as? [Int]==config.map(Int.init));checks+=1
   var bad=reply;bad[11]^=1;precondition(NamFxWire.reply(bad,to:write)==nil);checks+=1
  }
  print("PASS \(checks) NF wire checks against the published controller's exact frames; no device access")
 }
}
