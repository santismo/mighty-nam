import Foundation
@main struct FxTest {
 static func main(){
  let c:[UInt8]=[1,0,2,12,100,30,50,0,50,50,0,0,0,0,0,0,2,0,3,12,100,30,50,0,50,50,0,0,0,0,0,0]
  var count=0
  for op:UInt8 in [0,1,2] {for slot:UInt8 in [0,1,2,3,4,5,6] {
   let q=NamFxWire.prefix+[op,slot,24,3]+(op==1 ? [0,1,58,38,116,6]+c:[])+[247]
   precondition(NamFxWire.request(q));let reply=NamFxWire.prefix+[op|64,slot,24,3,0,slot]+c+[247]
   precondition(NamFxWire.reply(reply,to:q) != nil)
   var bad=reply;bad[11]^=1;precondition(NamFxWire.reply(bad,to:q)==nil)
   count+=3
  }}
  var bad=c;bad[18]=2;precondition(!NamFxWire.config(bad));bad=c;bad[3]=25;precondition(!NamFxWire.config(bad))
  precondition(NamLinkWire.supportsModels("NAMLNK15"));precondition(NamListening.supports("NAMLNK15"))
  precondition(NamLinkWire.supportsModels("NAMLNK16"));precondition(NamListening.supports("NAMLNK16"))
  precondition(NamOutputBuffer.command(identity:"NAMLNK16",samples:8) != nil)
  precondition(!NamLinkWire.supportsModels("NAMLNK30") && NamLinkWire.supportsModels("NAMLNK22"));precondition(NamLinkWire.supportsModels("NAMLNK20"));precondition(NamListening.supports("NAMLNK20"));count+=6
  precondition(NamLinkWire.supportsModels("NAMLNK17"));precondition(NamListening.supports("NAMLNK17"))
  precondition(NamOutputBuffer.command(identity:"NAMLNK17",samples:8) != nil)
  precondition(NamCodecStatus.decode(0xc10f220a)?["verified"] as? Bool == true)
  for word:UInt32 in [0xc103ffff,0xc10b000a,0xc10722ff] { precondition(NamCodecStatus.decode(word)?["verified"] as? Bool == false) }
  for word:UInt32 in [0,0xc11f220a,0xc20f220a] { precondition(NamCodecStatus.decode(word)==nil) }
  precondition((0..<27).map{NamCodecStatus.statusPage(index:$0,identity:"NAMLNK17")} == Array(UInt8(0)...25)+[117])
  precondition(NamCodecStatus.statusPage(index:26,identity:"NAMLNK16")==26);count+=12
  print("PASS native FX validation: \(count+4) checks")
 }
}
