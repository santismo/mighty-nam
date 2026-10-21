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
  print("PASS native FX validation: \(count+4) checks")
 }
}
