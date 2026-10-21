import Foundation
@main struct Inspect {
 static func main() {
  let midi=NamMidi()
  do {
   let devices=try midi.devices()
   guard devices.count==1,let id=devices[0]["source"] as? Int else {throw NSError(domain:"Require exactly one plug",code:1)}
   var answer:Result<[String:Any],Error>?
   midi.inspect(id){answer=$0}
   let deadline=Date(timeIntervalSinceNow:15)
   while answer==nil && Date()<deadline {RunLoop.main.run(until:Date(timeIntervalSinceNow:0.02))}
   guard let answer=answer else {throw NSError(domain:"Timeout",code:2)}
   let report=try answer.get()
   let data=try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys])
   if CommandLine.arguments.count==2 {try data.write(to:URL(fileURLWithPath:CommandLine.arguments[1]),options:.atomic)}
   print(String(data:data,encoding:.utf8)!)
  } catch {print("FAILED: \(error)");exit(1)}
  midi.disconnect()
 }
}
