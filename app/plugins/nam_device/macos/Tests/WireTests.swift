import Foundation
@main struct WireTests {
 static func frames(_ path: String) throws -> [[UInt8]] {
  let bytes=Array(try Data(contentsOf:URL(fileURLWithPath:path)))
  var pos=0, result:[[UInt8]]=[]
  while pos<bytes.count {
   let n=Int(NamLinkWire.word(bytes,pos));pos+=4
   precondition(n<=280 && pos+n<=bytes.count)
   result.append(Array(bytes[pos..<pos+n]));pos+=n
  }
  return result
 }
 static func wire(_ raw:[UInt8]) -> [UInt8] {
  // Independent reference encoder, also used for response frames.
  var result=NamLinkWire.prefix
  for start in stride(from:0,to:raw.count,by:7) {
   let block=Array(raw[start..<min(start+7,raw.count)])
   result.append(block.enumerated().reduce(UInt8(0)){$0 | (($1.element>>7)<<$1.offset)})
   result += block.map{$0&127}
  }
  return result+[0xf7]
 }
 static func main() throws {
  var count=0, corrupted=0
  for prefix in CommandLine.arguments.dropFirst() {
   let requests=try frames(prefix+".requests"),replies=try frames(prefix+".replies")
   precondition(requests.count==replies.count)
   var exported=Data()
   for (request,reply) in zip(requests,replies) {
    if let frame=NamLinkWire.request(request) {
     precondition(frame==wire(request) && frame.count<=330)
     let response=wire(reply)
     precondition(NamLinkWire.reply(response,to:request)==reply)
     var size=UInt32(frame.count).littleEndian
     withUnsafeBytes(of:&size){exported.append(contentsOf:$0)}
     exported.append(contentsOf:frame)
     for i in response.indices {
      var bad=response;bad[i] ^= 1
      precondition(NamLinkWire.reply(bad,to:request)==nil);corrupted+=1
     }
     var noncanonical=response;noncanonical[57] |= 64
     precondition(NamLinkWire.reply(noncanonical,to:request)==nil)
     precondition(NamLinkWire.reply(Array(response.dropLast()),to:request)==nil)
     precondition(NamLinkWire.reply(response+[0],to:request)==nil)
     count+=1
    } else { precondition(!NamLinkWire.validPacket(request) || !(1...6).contains(request[5])) }
   }
   try exported.write(to:URL(fileURLWithPath:prefix+".swift-sysex"))
  }
  for n in 0..<24 {precondition(NamLinkWire.request([UInt8](repeating:0,count:n))==nil)}
  print("PASS Swift/Dart wire interop: \(count) valid frames; \(corrupted) damaged replies rejected; no device or audio access")
 }
}
