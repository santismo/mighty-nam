import Foundation
@main struct FxCheck{static func main(){
 let midi=NamMidi();var id:Int?;var original:[UInt8]?;var currentCRC:UInt32=0;var active=255;var token=Int.random(in:1...15000);var events:[[String:Any]]=[];var result:[String:Any]=["status":"STARTING","audioStreams":0,"outputEnableCommands":0,"presetWrites":0,"firmwareWrites":0,"MacTeamsAudioChanged":false]
 func record(_ name:String,_ row:[String:Any]){events.append(["step":name,"result":row]);print(name);fflush(stdout)}
 func exchange(_ op:Int,_ c:[UInt8]?=nil)throws->[UInt8]{
  guard let source=id else{throw CheckError.message("Missing source")};token=token%16383+1
  var q=NamFxWire.prefix+[UInt8(op),UInt8(active==255 ? 127:active),UInt8(token&127),UInt8(token>>7)]
  if op==1{q += [0]+(0..<5).map{UInt8((currentCRC>>(7*$0))&127)};q+=c!};q+=[247]
  try require(NamFxWire.request(q),"Invalid FX request");let r=try waitFor{midi.fx(source,request:q,completion:$0)}
  guard let f=r["frame"] as? [UInt8],NamFxWire.reply(f,to:q) != nil,f[13]==0,Int(f[14])==active else{throw CheckError.message("Invalid FX reply")};return Array(f[15..<47])
 }
 do{
  let d=try midi.devices();try require(d.count==1,"One plug required");let source=d[0]["source"] as! Int;id=source
  let first=try waitFor{midi.inspect(source,completion:$0)};let w=try statusWords(first);try require(w[4]==0&&w[10]==0&&w[5]==1854512385&&w[9]==1,"Ready Fender required");active=(first["presetBank"] as! [String:Any])["active"] as! Int;currentCRC=w[5];try require(active==0,"Green required")
  original=try exchange(0);record("original",["config":original!.map(Int.init)])
  var enabled=original!;enabled[0]=6;enabled[16]=2;enabled[1]=1;enabled[17]=1
  var moved=enabled;moved[2]=8;moved[18]=1
  var bypass=moved;bypass[1]=0;bypass[17]=0
  for (name,c) in [("two-FX-enabled",enabled),("FX-moved",moved),("FX-bypassed",bypass),("original-restored",original!)]{
   try require(try exchange(1,c)==c,"FX write mismatch");try require(try exchange(0)==c,"Independent FX read mismatch");pause(2)
   let r=try waitFor{midi.inspect(source,completion:$0)};let s=try statusWords(r);try require(s[4]==0&&s[10]==0&&s[9]==1&&s[5]==currentCRC,"Fault during FX check");record(name,r)
  }
  result["status"]="PASS_NAMLNK15_PHYSICAL_FX_CONTROLS";result["originalSettingsRestored"]=true;result["listeningLatencyMeasured"]=false
 }catch{
  result["status"]="FAILED";result["error"]=String(describing:error)
  if let source=id{_ = try? waitFor{midi.listen(source,enabled:false,completion:$0)}}
  if let c=original{_ = try? exchange(1,c)}
 }
 midi.disconnect();result["events"]=events
 do{try JSONSerialization.data(withJSONObject:result,options:[.prettyPrinted,.sortedKeys]).write(to:URL(fileURLWithPath:CommandLine.arguments[1]),options:.atomic)}catch{print(error);exit(1)}
 print(result["status"]!);if let error=result["error"]{print(error);exit(1)}
}}
