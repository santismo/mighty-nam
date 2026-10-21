import Foundation
import CoreMIDI

// Private-backup restoration only. The regular app intentionally does not expose
// these retired amp fields, patch level or tempo. Never sends routing/system CCs.
enum RestoreSupplement {
 static let offsets=Set([3,84,85,86,87]+Array(27...34))
 static func messages(_ fx:[Int]) throws -> [[UInt8]] {
  try require(fx.count==128 && fx.allSatisfy{(0...127).contains($0)},"Invalid backup effects")
  try require(fx[3]&63==1 && fx[27...34].allSatisfy{$0<=100} && fx[84]<=100,"Unsupported backup amp/patch level")
  try require(fx[85]<=1 && (40...240).contains((fx[86]<<7)|fx[87]),"Invalid saved tempo")
  return [[176,3,UInt8(fx[3])]] + (0..<8).map{[176,UInt8(23+$0),UInt8(fx[27+$0])]} +
   [[176,73,UInt8(fx[84])],[240,67,88,112,3,1,UInt8(fx[86]),UInt8(fx[87]),UInt8(fx[85]),247]]
 }
 static func apply(_ midi:NamMidi,_ id:Int,_ expected:[Int]) throws -> [String:Any] {
  let commands=try messages(expected)
  let identity=try waitFor{midi.inspect(id,completion:$0)}
  let words=try statusWords(identity)
  try require(words[4]==0 && words[10]==0,"Processing fault before restore")
  let before=try waitFor{midi.stock(id,completion:$0)}
  guard let old=before["preset"] as? [Int],old.count==128 else {throw CheckError.message("Invalid effect readback")}
  guard let match=try midi.devices().first(where:{$0["source"] as? Int==id}),let destination=match["destination"] as? Int else {throw CheckError.message("Plug disconnected")}
  var client:MIDIClientRef=0,port:MIDIPortRef=0
  defer {if port != 0 {MIDIPortDispose(port)};if client != 0 {MIDIClientDispose(client)}}
  try require(MIDIClientCreateWithBlock("NAM preset backup restore" as CFString,&client,nil)==noErr,"MIDI client unavailable")
  try require(MIDIOutputPortCreate(client,"Verified preset fields" as CFString,&port)==noErr,"MIDI port unavailable")
  for bytes in commands {
   let storage=UnsafeMutableRawPointer.allocate(byteCount:1024,alignment:MemoryLayout<MIDIPacketList>.alignment)
   defer {storage.deallocate()}
   let list=storage.bindMemory(to:MIDIPacketList.self,capacity:1);let first=MIDIPacketListInit(list)
   let sent=bytes.withUnsafeBufferPointer {data -> OSStatus in
    guard let base=data.baseAddress else{return -1}
    let added=MIDIPacketListAdd(list,1024,first,0,data.count,base)
    guard UInt(bitPattern:added) != 0 else{return -1}
    return MIDISend(port,MIDIEndpointRef(destination),list)
   }
   try require(sent==noErr,"Backup restore command failed")
   pause(0.02)
  }
  pause(0.1)
  let after=try waitFor{midi.stock(id,completion:$0)}
  guard let actual=after["preset"] as? [Int],actual.count==128 else {throw CheckError.message("Invalid effect readback after restore")}
  try require((0..<128).allSatisfy{actual[$0]==(offsets.contains($0) ? expected[$0]:old[$0])},"Unexpected restore field change")
  _=try statusWords(waitFor{midi.inspect(id,completion:$0)})
  return ["exactBackedUpFieldsRestored":true,"otherEffectBytesUnchanged":true,"muted":true,"commands":commands.count]
 }
}
