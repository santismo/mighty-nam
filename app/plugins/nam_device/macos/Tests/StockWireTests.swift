import Foundation
@main struct StockWireTest {
    static func main() {
        var checks = 0
        func check(_ value: Bool, line: UInt = #line) { precondition(value, "check at line \(line)"); checks += 1 }
        var controls = NamStockWire.heads.keys.sorted().map { [$0, 65] }
        for (range,_) in NamStockWire.groups { for cc in range { controls.append([cc,50]) } }
        let order = [5,1,2,3,9,4,6,7,8]
        let plan = NamStockWire.Plan(controls:controls,order:order)!
        var preset = [UInt8](repeating:0,count:128)
        for (at,value) in plan.expected { preset[at] = value }
        check(plan.matches(preset))
        for bypassed in [true,false] {
            let cab = NamStockWire.Plan(cabinetBypassed:bypassed)
            check(!cab.allowed(on:"NAMLNK01"))
            check(cab.allowed(on:"NAMLNK06") && cab.allowed(on:"NAMLNK07") && cab.allowed(on:"NAMLNK08"))
            check(cab.orderMessage.isEmpty && cab.orderReply.isEmpty)
            var before = preset; before[9] = 19
            let value: UInt8 = bypassed ? 83 : 19
            check(cab.messages(before:before) == [0xb0,9,value])
            var after = before; after[9] = value
            check(cab.matches(after,before:before))
            check(!cab.matches(after))
            for index in 0..<128 {
                var changed = after; changed[index] ^= 1
                check(!cab.matches(changed,before:before))
            }
            before[9] = 35
            check(cab.messages(before:before) == nil)
            check(cab.messages(before:[]) == nil)
        }
        for (at,value) in plan.expected {
            var changed = preset; changed[at] = value ^ 1
            check(!plan.matches(changed))
        }
        for cc in 0...127 where NamStockWire.presetIndex(cc) == nil {
            check(NamStockWire.Plan(controls:controls+[[cc,1]],order:order) == nil)
        }
        for bad in [-1,128,255,Int.max] {
            var values=controls;values[0][1]=bad
            check(NamStockWire.Plan(controls:values,order:order) == nil)
        }
        check(NamStockWire.Plan(controls:controls+[[13,50]],order:order) == nil)
        check(NamStockWire.Plan(controls:Array(controls.dropFirst()),order:order) == nil)
        check(NamStockWire.Plan(controls:controls,order:Array(repeating:1,count:9)) == nil)
        check(NamStockWire.Plan(controls:controls,order:[0,1,2,3,4,5,6,7,8]) == nil)
        for (cc,max) in NamStockWire.heads {
            var bad=controls;bad.removeAll{$0[0]==cc};bad.append([cc,max+1])
            check(NamStockWire.Plan(controls:bad,order:order) == nil)
        }
        let frame:[UInt8] = [0xf0,0x43,0x58,0x70,12,2,0]+preset+[0xf7]
        check(NamStockWire.preset(frame) == preset)
        check(NamLinkWire.supportsModels("NAMLNK01"))
        check(NamLinkWire.supportsModels("NAMLNK02"))
        check(NamLinkWire.supportsModels("NAMLNK03"))
        check(NamLinkWire.supportsModels("NAMLNK06"))
        check(NamLinkWire.supportsModels("NAMLNK07"))
        check(NamLinkWire.supportsModels("NAMLNK08"))
        check(NamLinkWire.supportsModels("NAMLNK09"))
        check(NamLinkWire.supportsModels("NAMLNK10"))
        check(!NamLinkWire.supportsModels("NAMLNK11"))
        check(!NamLinkWire.supportsStockChain("NAMLNK01"))
        check(NamLinkWire.supportsStockChain("NAMLNK03"))
        check(NamLinkWire.supportsModels("NAMLNK04"))
        check(NamLinkWire.supportsStockChain("NAMLNK04"))
        check(NamLinkWire.supportsModels("NAMLNK05"))
        check(NamLinkWire.supportsStockChain("NAMLNK05"))
        check(plan.allowed(on:"NAMLNK01"))
        check(plan.allowed(on:"NAMLNK02"))
        for enabled in [true,false] {
            let bypass=NamStockWire.Plan(controls:controls,order:order,namEnabled:enabled)!
            check(!bypass.allowed(on:"NAMLNK01"))
            check(bypass.allowed(on:"NAMLNK02"))
            check(bypass.allowed(on:"NAMLNK03"))
            check(bypass.allowed(on:"NAMLNK04"))
            check(bypass.allowed(on:"NAMLNK05"))
            check(bypass.allowed(on:"NAMLNK06"))
            check(bypass.allowed(on:"NAMLNK07"))
            check(bypass.allowed(on:"NAMLNK08"))
            check(bypass.allowed(on:"NAMLNK09"))
            check(bypass.allowed(on:"NAMLNK10"))
            check(!bypass.allowed(on:"NAMLNK11"))
            check(!bypass.allowed(on:"NAMA2I01"))
            var before=preset;before[3]=21
            let messages=bypass.messages(before:before)!
            check(Array(messages.suffix(3)) == [0xb0,3,enabled ? 21 : 85])
            before[3]=enabled ? 21 : 85
            check(bypass.matches(before))
            before[3] ^= 64
            check(!bypass.matches(before))
            check(bypass.messages(before:[]) == nil)
        }
        for size in 0..<frame.count { check(NamStockWire.preset(Array(frame.prefix(size))) == nil) }
        for index in 7..<135 {
            var bad=frame;bad[index]=128
            check(NamStockWire.preset(bad) == nil)
        }
        for identity in ["NAMLNK01","NAMLNK06","NAMLNK11","PLUGPRO"] {
            check(NamListening.arm(identity:identity,enabled:true) == nil)
            check(NamListening.arm(identity:identity,enabled:false) == nil)
        }
        for identity in ["NAMLNK07","NAMLNK08","NAMLNK09","NAMLNK10"] { for enabled in [true,false] {
            let command=NamListening.arm(identity:identity,enabled:enabled)!
            check(command.count == 20 && command[8] == (enabled ? 1 : 0))
            check(command[18] == 23)
        }}
        for word: UInt32 in [0,1,2,3,5] { check(NamListening.decode(word) != nil) }
        for word: UInt32 in [4,6,7,8,UInt32.max] { check(NamListening.decode(word) == nil) }
        check(NamListening.decode(3)?["enabled"] as? Bool == true)
        check(NamListening.decode(2)?["enabled"] as? Bool == false)
        for samples in 0...128 {
            let allowed = [8,16,32].contains(samples)
            check((NamOutputBuffer.command(identity:"NAMLNK09",samples:samples) != nil) == allowed)
            let word = (UInt32(48000)<<16) | (1<<8) | UInt32(samples)
            check((NamOutputBuffer.decode(word) != nil) == allowed)
        }
        for identity in ["NAMLNK08","NAMLNK11","PLUGPRO",""] {
            check(NamOutputBuffer.command(identity:identity,samples:8) == nil)
        }
        for word: UInt32 in [0,8,0xffffffff,(44100<<16)|(1<<8)|8,(48000<<16)|(2<<8)|8] {
            check(NamOutputBuffer.decode(word) == nil)
        }
        check(NamOutputBuffer.command(identity:"NAMLNK09",samples:16) == [0xf0,0x43,0x58,0x70,4,2,0x4e,0x42,16,0xf7,0xf0,0x43,0x58,0x70,4,2,0x4e,0x50,24,0xf7])
        check(NamOutputBuffer.command(identity:"NAMLNK10",samples:8) != nil)
        func put(_ a: inout [UInt8],_ at:Int,_ value:UInt32) {
            for i in 0..<4 { a[at+i]=UInt8((value >> (i*8)) & 255) }
        }
        func crc(_ a: inout [UInt8]) { put(&a,a.count-4,NamLinkWire.crc(a[0..<a.count-4])) }
        func packPreset(_ a:[UInt8]) -> [UInt8] {
            var out=NamPresetWire.prefix
            for start in stride(from:0,to:a.count,by:7) {
                let end=min(start+7,a.count);var mask:UInt8=0
                for i in start..<end { mask |= (a[i] >> 7) << (i-start) }
                out.append(mask);out.append(contentsOf:a[start..<end].map{$0 & 127})
            }
            return out+[247]
        }
        for slot in 0..<7 { for op: UInt8 in [1,2,3] {
            var request=[UInt8](repeating:0,count:op==2 ? 132 : 20)
            put(&request,0,0x3031504e);request[4]=1;request[5]=op;request[6]=UInt8(slot)
            put(&request,8,0xf0123456);request[12]=op==2 ? 112 : 0;crc(&request)
            check(NamPresetWire.request(request)==packPreset(request))
            var reply=[UInt8](repeating:0,count:276)
            reply.replaceSubrange(0..<16,with:request[0..<16]);reply[5] |= 128
            reply[12]=0;reply[13]=1;reply[14]=UInt8(slot);reply[15]=127
            crc(&reply);let wire=packPreset(reply)
            check(NamPresetWire.reply(wire,to:request)==reply)
            for at in [4,6,8,14,15,272] {
                var bad=reply;bad[at]=at==14 ? 7 : (at==15 ? 128 : bad[at] ^ 1)
                if at != 272 {crc(&bad)}
                check(NamPresetWire.reply(packPreset(bad),to:request)==nil)
            }
            for length in [0,1,19,325,327] {
                check(NamPresetWire.reply(Array(wire.prefix(length)),to:request)==nil || length==327)
            }
            var noncanonical=wire;noncanonical[321] |= 64
            check(NamPresetWire.reply(noncanonical,to:request)==nil)
            for at in [0,4,5,6,7,8,12,14,15] {
                var bad=request
                if at==5 {bad[at]=4} else if at==6 {bad[at]=7} else if at==8 {put(&bad,8,0)} else {bad[at] ^= 1}
                crc(&bad);check(NamPresetWire.request(bad)==nil)
            }
        }}
        let timing: [UInt32] = [0x54494d31,20,10,0,0,123,456,1,1,7,7]
        check(NamIrqTiming.decode(timing)?["usable"] as? Bool == true)
        check(NamIrqTiming.decode(timing)?["maximumCycles"] as? Int64 == 456)
        check(NamIrqTiming.decode(timing)?["hardwareDeadlineProven"] as? Bool == false)
        for count in 0..<timing.count {
            check(NamIrqTiming.decode(Array(timing.prefix(count))) == nil)
        }
        check(NamIrqTiming.decode(timing+[0]) == nil)
        for (index,value): (Int,UInt32) in [(0,0),(1,21),(4,16),(5,457),(6,0x80000000),(7,0),(8,3),(10,8)] {
            var bad=timing;bad[index]=value
            check(NamIrqTiming.decode(bad) == nil)
        }
        check(NamIrqTiming.decode([0x54494d31]+Array(repeating:0,count:10))?["usable"] as? Bool == false)
        for flag: UInt32 in [1,2,4,8,15] {
            var rejected=timing;rejected[3]=1;rejected[4]=flag;rejected[8]=0
            check(NamIrqTiming.decode(rejected)?["usable"] as? Bool == false)
        }
        print("{\"status\":\"PASS\",\"checks\":\(checks),\"deviceAccess\":false,\"audioStreamOpened\":false}")
    }
}
