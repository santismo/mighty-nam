import Foundation
@main struct PresetInterop {
 static func main() throws {
  let prefix=CommandLine.arguments[1]
  let requests=try JSONDecoder().decode([[UInt8]].self,from:Data(contentsOf:URL(fileURLWithPath:prefix+".requests.json")))
  let wire=requests.map { NamPresetWire.request($0)! }
  try JSONEncoder().encode(wire).write(to:URL(fileURLWithPath:prefix+".swift-wire.json"))
  let returned=URL(fileURLWithPath:prefix+".arm-wire.json")
  if FileManager.default.fileExists(atPath:returned.path) {
   let replies=try JSONDecoder().decode([[UInt8]].self,from:Data(contentsOf:returned))
   precondition(replies.count==requests.count)
   let raw=zip(replies,requests).map{NamPresetWire.reply($0,to:$1)!}
   try JSONEncoder().encode(raw).write(to:URL(fileURLWithPath:prefix+".replies.json"))
  }
 }
}
