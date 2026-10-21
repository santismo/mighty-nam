import Foundation
@main struct Tests {static func main()throws{
 let rows=try JSONSerialization.jsonObject(with:Data(contentsOf:URL(fileURLWithPath:CommandLine.arguments[1]))) as! [[String:[Int]]]
 var checks=0
 for r in rows{let q=r["request"]!.map(UInt8.init),m=r["wire"]!.map(UInt8.init);precondition(CompactPitch.reply(m,to:q) != nil);checks+=1
  var bad=m;bad[20]^=1;precondition(CompactPitch.reply(bad,to:q)==nil);checks+=1
  var wrong=q;wrong[11]^=1;precondition(CompactPitch.reply(m,to:wrong)==nil);checks+=1
 }
 precondition(CompactPitch.request(2,1)==nil && CompactPitch.request(3,0)==nil)
 print("PASS compact native wire: \(checks+2) checks")
}}
