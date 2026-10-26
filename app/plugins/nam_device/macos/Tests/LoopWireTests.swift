import Foundation
@main struct LoopWireTest {
 static func main(){
  var checks=0
  for op:UInt8 in [0,1,2,3,4,5] {
   for arg:UInt8 in [0,1,5,6,10,11,12,30,60,100,101,127] {
    let q=NamLoopWire.prefix+[op,arg,1,0,247]
    let valid=(op==0 && arg<=6)||(op==1 && arg>=1 && arg<=10)||(op==2 && arg>=12 && arg<=60)||(op==3 && arg<=100)||(op==4 && (arg==30||arg==60))||(op==5 && arg==1)
    precondition(NamLoopWire.request(q)==valid);checks+=1
    precondition(NamLoopWire.supports("NAMLNK27",request:q)==(valid && op != 5));checks+=1
    precondition(NamLoopWire.supports("NAMLNK28",request:q)==valid);precondition(NamLoopWire.supports("NAMLNK29",request:q)==valid);precondition(!NamLoopWire.supports("NAMLNK30",request:q));checks+=1
    if valid {
     var r=NamLoopWire.prefix+[op|64,arg,1,0,0]+Array(repeating:UInt8(0),count:40)+[247]
     precondition(NamLoopWire.reply(r,to:q) != nil);checks+=1
     r[18]=16;precondition(NamLoopWire.reply(r,to:q)==nil);checks+=1
    }
   }
  }
  let meter=NamLoopWire.prefix+[0,6,1,0,247]
  precondition(!NamLoopWire.supports("NAMLNK26",request:meter));checks+=1
  print("PASS_LOOP_WIRE \(checks) checks")
 }
}
