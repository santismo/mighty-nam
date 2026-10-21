import Foundation
// Trial-only bounded compact tuner. No host audio or arbitrary MIDI entrypoint.
enum CompactPitch {
 static func request(_ op:Int,_ nonce:Int)->[UInt8]? {
  guard (3...5).contains(op),(1...16383).contains(nonce) else{return nil}
  return NamTunerWire.prefix+[UInt8(op),0,UInt8(nonce&127),UInt8(nonce>>7),247]
 }
 static func reply(_ m:[UInt8],to q:[UInt8])->[UInt8]? {
  guard q.count==14,request(Int(q[9]),Int(q[11])+128*Int(q[12]))==q,
   m.count==42,Array(m.prefix(9))==[240,67,88,112,4,2,78,86,2],m.last==247,m[9..<41].allSatisfy({$0<128}) else{return nil}
  var raw:[UInt8]=[]
  for start in stride(from:9,to:41,by:8){for i in 1...7{raw.append(m[start+i]|(((m[start]>>(i-1))&1)<<7))}}
  guard NamLinkWire.word(raw,0)==0x32554e4d,raw[4]==2,raw[5]==q[9]|128,raw[6]==0,[0,1,3].contains(raw[7]),NamLinkWire.word(raw,8)==UInt32(q[11])+128*UInt32(q[12]),NamLinkWire.word(raw,24)==NamLinkWire.crc(raw[0..<24]) else{return nil}
  let f=NamLinkWire.word(raw,16),c=NamLinkWire.word(raw,20)
  guard (f==0||(40000...1400000).contains(f))&&c<=1000000 else{return nil}
  return raw
 }
}
