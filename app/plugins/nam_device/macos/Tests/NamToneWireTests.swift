import Foundation
@main struct NamToneTest {static func main(){
 let q:[UInt8]=[240,67,88,112,4,2,78,71,1,1,0,1,0,0,1,2,3,4,5,48,12,12,12,100,48,247]
 precondition(NamToneWire.request(q));var r=Array(q.prefix(13));r[9]=65;r += [0,0,48,12,12,12,100,48,247];precondition(NamToneWire.reply(r,to:q) != nil)
 for i in 0..<q.count {var b=q;b[i]=255;precondition(!NamToneWire.request(b))}
 for i in [0,7,8,9,10,11,12,21] {var b=r;b[i]^=1;precondition(NamToneWire.reply(b,to:q)==nil)}
 let record=NamRecordWire.prefix+[1,5,23,1,0,1,2,3,4,5,60,247]
 precondition(NamRecordWire.request(record))
 let recorded=NamRecordWire.prefix+[65,5,23,1,0,5,60,247]
 precondition(NamRecordWire.reply(recorded,to:record) != nil)
 for count in 0..<record.count {precondition(!NamRecordWire.request(Array(record.prefix(count))))}
 for i in 0..<record.count {var bad=record;bad[i]=255;precondition(!NamRecordWire.request(bad))}
 for i in [7,8,9,10,11,12,16] {var bad=recorded;bad[i]^=1;precondition(NamRecordWire.reply(bad,to:record)==nil)}
 var outOfRange=record;outOfRange[19]=97;precondition(!NamRecordWire.request(outOfRange))
 precondition(NamLinkWire.supportsModels("NAMLNK21"));precondition(!NamLinkWire.supportsModels("NAMLNK31") && NamLinkWire.supportsModels("NAMLNK22"));print("PASS native NAM control wire")
}}
