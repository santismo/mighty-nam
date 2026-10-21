import Foundation
@main struct TunerWireTests {
 static func main() {
  var checks=0
  func check(_ ok:Bool){precondition(ok);checks+=1}
  func put(_ a:inout [UInt8],_ at:Int,_ v:UInt32){for i in 0..<4 {a[at+i]=UInt8(truncatingIfNeeded:v>>(i*8))}}
  func encode(_ a:[UInt8])->[UInt8]{
   var result=NamTunerWire.prefix
   for start in stride(from:0,to:a.count,by:7){var mask:UInt8=0
    for i in 0..<7 {mask |= (a[start+i]>>7)<<i}
    result.append(mask);result+=a[start..<start+7].map{$0&127}
   }
   return result+[247]
  }
  for op in 0...2 {for page in 0..<16 {for nonce in [1,127,128,16383] {
   guard let request=NamTunerWire.request(operation:op,page:page,nonce:nonce) else {check(op != 2 && page != 0);continue}
   var raw=[UInt8](repeating:0,count:280);put(&raw,0,0x31554e4d);raw[4]=1;raw[5]=UInt8(op|128);raw[6]=UInt8(page)
   put(&raw,8,UInt32(nonce));put(&raw,12,UInt32.max);raw[16]=224;raw[17]=46;raw[19]=8
   for i in 20..<276{raw[i]=UInt8(truncatingIfNeeded:i*43)}
   put(&raw,276,NamLinkWire.crc(raw[0..<276]));let wire=encode(raw)
   check(wire.count==330);check(NamTunerWire.reply(wire,to:request)==raw)
   for at in [0,4,5,6,8,16,18,276]{var bad=raw;bad[at]^=1;put(&bad,276,NamLinkWire.crc(bad[0..<276]));if at==276{bad[at]^=1};check(NamTunerWire.reply(encode(bad),to:request)==nil)}
   check(NamTunerWire.reply(Array(wire.dropLast()),to:request)==nil)
  }}}
  for op in [-1,3,255]{check(NamTunerWire.request(operation:op,page:0,nonce:1)==nil)}
  for page in [-1,16,255]{check(NamTunerWire.request(operation:2,page:page,nonce:1)==nil)}
  for nonce in [-1,0,16384]{check(NamTunerWire.request(operation:1,page:0,nonce:nonce)==nil)}
  print("PASS: \(checks) tuner wire cases; no device/audio access")
 }
}
