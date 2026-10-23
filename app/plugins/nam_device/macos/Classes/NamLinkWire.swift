import Foundation

// Looper status/settings travel over MIDI only; no host audio capture.
public enum NamLoopWire {
    static let prefix:[UInt8] = [240,67,88,112,4,2,78,79,1]
    static func request(_ q:[UInt8])->Bool {
        guard q.count==14,Array(q.prefix(9))==prefix,q.last==247,
              q[1..<13].allSatisfy({$0<128}),q[11]|q[12] != 0 else{return false}
        let op=q[9],arg=q[10]
        return (op==0 && arg<=6) || (op==1 && arg>=1 && arg<=10) ||
            (op==2 && arg>=12 && arg<=60) || (op==3 && arg<=100) ||
            (op==4 && (arg==30 || arg==60))
    }
    static func supports(_ identity:String,request q:[UInt8])->Bool {
        guard request(q) else{return false}
        return identity=="NAMLNK27" || (identity=="NAMLNK26" && !(q[9]==0 && q[10]==6))
    }
    static func reply(_ r:[UInt8],to q:[UInt8])->[UInt8]? {
        guard request(q),r.count==55,r.last==247,Array(r.prefix(9))==prefix,
            r[9]==q[9]|64,Array(r[10..<13])==Array(q[10..<13]),r[13]<=3,
            r[1..<54].allSatisfy({$0<128}),
            (0..<8).allSatisfy({r[18+$0*5]<16}) else{return nil}
        return r
    }
}

// Cached startup observations, not an electrical latency or part-ID test.
enum NamCodecStatus {
    static func decode(_ word: UInt32) -> [String:Any]? {
        guard word >> 24 == 0xc1, (word >> 16) & 255 <= 15 else { return nil }
        return ["raw":Int64(word), "verified":word == 0xc10f220a,
                "flags":Int((word >> 16) & 15), "adc":Int((word >> 8) & 255), "dac":Int(word & 255)]
    }
    static func statusPage(index:Int, identity:String) -> UInt8 {
        UInt8(["NAMLNK17", "NAMLNK18", "NAMLNK19", "NAMLNK20", "NAMLNK21", "NAMLNK22", "NAMLNK23", "NAMLNK24", "NAMLNK25", "NAMLNK26", "NAMLNK27"].contains(identity) && index == 26 ? 117 : index)
    }
}

// Fixed RAM-model protocol only. No stock writes, firmware update or audio API.
public enum NamLinkWire {
    static func isPlugName(_ label: String) -> Bool {
        let normalized = label.uppercased().filter { $0.isLetter || $0.isNumber }
        // Public V3 uses NUX NMP-03. A fresh firmware identity is still
        // required before any custom control or model command is sent.
        return normalized.contains("MIGHTYPLUGPRO") || normalized == "NUXNMP03"
    }
    static func supportsModels(_ identity: String) -> Bool {
        identity == "NAMLNK01" || supportsStockChain(identity)
    }
    static func supportsStockChain(_ identity: String) -> Bool {
        ["NAMLNK02", "NAMLNK03", "NAMLNK04", "NAMLNK05", "NAMLNK06", "NAMLNK07", "NAMLNK08","NAMLNK09","NAMLNK10","NAMLNK11","NAMLNK12","NAMLNK13","NAMLNK14","NAMLNK15", "NAMLNK16", "NAMLNK17", "NAMLNK18", "NAMLNK19", "NAMLNK20", "NAMLNK21", "NAMLNK22", "NAMLNK23", "NAMLNK24", "NAMLNK25", "NAMLNK26", "NAMLNK27"].contains(identity)
    }
    static let prefix: [UInt8] = [0xf0,0x43,0x58,0x70,4,2,0x4e,0x4c,1]
    static func crc(_ bytes: ArraySlice<UInt8>) -> UInt32 {
        var c: UInt32 = 0xffffffff
        for b in bytes {
            c ^= UInt32(b)
            for _ in 0..<8 { c = (c >> 1) ^ ((c & 1) == 0 ? 0 : 0xedb88320) }
        }
        return c ^ 0xffffffff
    }
    static func word(_ bytes: [UInt8], _ at: Int) -> UInt32 {
        var value: UInt32 = 0
        for i in 0..<4 { value |= UInt32(bytes[at+i]) << (8*i) }
        return value
    }
    static func validPacket(_ raw: [UInt8]) -> Bool {
        guard (24...280).contains(raw.count), word(raw,0) == 0x314c504d, raw[4] == 1,
              Int(raw[6]) + 256*Int(raw[7]) == raw.count-24 else { return false }
        return word(raw,20) == crc(raw[0..<20]) && word(raw,16) == crc(raw[24...])
    }
    public static func request(_ raw: [UInt8]) -> [UInt8]? {
        guard validPacket(raw), (1...6).contains(raw[5]) else { return nil }
        var wire = prefix
        for start in stride(from: 0, to: raw.count, by: 7) {
            let end = min(start+7,raw.count)
            var mask: UInt8 = 0
            for i in start..<end { mask |= (raw[i] >> 7) << (i-start) }
            wire.append(mask)
            wire.append(contentsOf: raw[start..<end].map { $0 & 127 })
        }
        wire.append(0xf7)
        return wire
    }
    public static func reply(_ wire: [UInt8], to request: [UInt8]) -> [UInt8]? {
        guard validPacket(request), wire.count == 65, Array(wire.prefix(9)) == prefix,
              wire.last == 0xf7 else { return nil }
        let packed = Array(wire[9..<64])
        guard packed.allSatisfy({ $0 < 128 }), packed[48] < 64 else { return nil }
        var raw: [UInt8] = []
        for start in stride(from: 0, to: packed.count, by: 8) {
            let end = min(start+8,packed.count)
            for i in (start+1)..<end { raw.append(packed[i] | (((packed[start] >> (i-start-1)) & 1) << 7)) }
        }
        guard validPacket(raw), raw[5] == (request[5] | 128),
              raw[8..<12] == request[8..<12], word(raw,12) == 0 else { return nil }
        return raw
    }
}

// A separate, explicit listening command. Older silent builds never receive it.
public enum NamOutputBuffer {
    static let choices = [8,16,32]
    static func command(identity: String, samples: Int) -> [UInt8]? {
        guard ["NAMLNK09","NAMLNK10","NAMLNK11","NAMLNK12","NAMLNK13","NAMLNK14","NAMLNK15", "NAMLNK16", "NAMLNK17", "NAMLNK18", "NAMLNK19", "NAMLNK20", "NAMLNK21", "NAMLNK22", "NAMLNK23", "NAMLNK24", "NAMLNK25", "NAMLNK26", "NAMLNK27"].contains(identity), choices.contains(samples) else { return nil }
        return [0xf0,0x43,0x58,0x70,4,2,0x4e,0x42,UInt8(samples),0xf7] +
            [0xf0,0x43,0x58,0x70,4,2,0x4e,0x50,24,0xf7]
    }
    static func decode(_ word: UInt32, identity: String? = nil) -> [String:Any]? {
        let samples=Int(word & 255), format=Int((word >> 8) & 255)
        let global=(format & 15) == 2, error=format >> 4
        guard word >> 16 == 48000, choices.contains(samples),
              format == 1 || (global && error <= 4),
              identity == nil || global == (["NAMLNK18", "NAMLNK19", "NAMLNK20", "NAMLNK21", "NAMLNK22", "NAMLNK23", "NAMLNK24", "NAMLNK25", "NAMLNK26", "NAMLNK27"].contains(identity ?? "")) else { return nil }
        return ["samples":samples,"sampleRate":48000,"processingSamples":8,"choices":choices,
                "scope":global ? "global" : "preset","global":global,"storageError":error,"minimumSamples":8]
    }
}

public enum NamListening {
    static func supports(_ identity: String) -> Bool {
        ["NAMLNK07", "NAMLNK08","NAMLNK09","NAMLNK10","NAMLNK11","NAMLNK12","NAMLNK13","NAMLNK14","NAMLNK15", "NAMLNK16", "NAMLNK17", "NAMLNK18", "NAMLNK19", "NAMLNK20", "NAMLNK21", "NAMLNK22", "NAMLNK23", "NAMLNK24", "NAMLNK25", "NAMLNK26", "NAMLNK27"].contains(identity)
    }
    static func arm(identity: String, enabled: Bool) -> [UInt8]? {
        guard supports(identity) else { return nil }
        return [0xf0,0x43,0x58,0x70,4,2,0x4e,0x41,enabled ? 1 : 0,0xf7] +
            [0xf0,0x43,0x58,0x70,4,2,0x4e,0x50,23,0xf7]
    }
    static func decode(_ word: UInt32) -> [String:Any]? {
        guard word & ~UInt32(7) == 0, word & 6 != 6,
              word & 4 == 0 || word & 1 == 1 else { return nil }
        return ["enabled":word & 1 != 0,"settling":word & 2 != 0,
                "fadeComplete":word & 4 != 0,"levelPadDB":-18.0618]
    }
}

// Frozen NAMLNK06 diagnostic snapshot. Values are raw counter cycles, never
// elapsed microseconds or a claim that the hardware deadline has been met.
public enum NamIrqTiming {
    public static func decode(_ words: [UInt32]) -> [String:Any]? {
        guard words.count == 11, words[0] == 0x54494d31 else { return nil }
        let s = Array(words.dropFirst())
        guard s[0] & 1 == 0, s[3] & ~UInt32(15) == 0 else { return nil }
        if s[1] == 0 {
            guard s[4] == 0, s[5] == 0 else { return nil }
        } else {
            guard s[4] > 0, s[4] <= s[5], s[5] < 0x80000000 else { return nil }
        }
        if s[3] == 0 {
            guard s[2] == 0 else { return nil }
            if s[1] > 0 {
                guard s[6] & 1 == 1, s[6] == s[7], s[8] == s[9] else { return nil }
            }
        }
        return ["sequence":Int64(s[0]), "accepted":Int64(s[1]), "rejected":Int64(s[2]),
                "flags":Int64(s[3]), "lastCycles":Int64(s[4]), "maximumCycles":Int64(s[5]),
                "entryControl":Int64(s[6]), "exitControl":Int64(s[7]),
                "entryResetEpoch":Int64(s[8]), "exitResetEpoch":Int64(s[9]),
                "usable":s[1] > 0 && s[2] == 0 && s[3] == 0,
                "unit":"raw counter cycles", "hardwareDeadlineProven":false]
    }
}

// Exact V1.5.6 volatile effect controls. No preset save, reset, routing, volume,
// custom IR storage, amplifier type/parameters, or arbitrary SysEx escape hatch.
// NAMLNK02 through 06 additionally permit NAM's bypass bit, preserving amp type.
public enum NamStockWire {
    static let read: [UInt8] = [0xf0,0x43,0x58,0x70,12,2,0xf7]
    static let heads: [Int:Int] = [1:3,2:14,4:4,5:1,6:13,7:5,8:6,9:34]
    static let groups: [(ClosedRange<Int>,Int)] = [
        (13...16,15),(17...22,20),(31...42,36),(43...46,49),
        (47...52,54),(53...60,61),(61...64,70),(65...70,75)]
    static func presetIndex(_ cc: Int) -> Int? {
        if cc == 73 { return 84 }
        if heads[cc] != nil { return cc }
        for (range,base) in groups where range.contains(cc) { return base+cc-range.lowerBound }
        return nil
    }
    public struct Plan {
        let midi: [UInt8]
        let orderMessage: [UInt8]
        let orderReply: [UInt8]
        let expected: [Int:UInt8]
        let namEnabled: Bool?
        let cabinetBypassed: Bool?
        public init(cabinetBypassed: Bool) {
            midi = []; orderMessage = []; orderReply = []; expected = [:]
            namEnabled = nil
            self.cabinetBypassed = cabinetBypassed
        }
        public init?(controls: [[Int]], order: [Int], namEnabled: Bool? = nil) {
            guard (8...64).contains(controls.count), order.count == 9,
                  Set(order) == Set(1...9) else { return nil }
            var values: [Int:UInt8] = [:]
            var commands: [UInt8] = []
            var seen = Set<Int>()
            for pair in controls {
                guard pair.count == 2 else { return nil }
                let cc = pair[0], value = pair[1]
                guard seen.insert(cc).inserted, let at = NamStockWire.presetIndex(cc),
                      (0...127).contains(value) else { return nil }
                if let maximum = heads[cc] {
                    guard (1...maximum).contains(value & 63) else { return nil }
                } else if value > 100 { return nil }
                commands += [0xb0,UInt8(cc),UInt8(value)]
                values[at] = UInt8(value)
            }
            guard Set(heads.keys).isSubset(of:seen) else { return nil }
            for (index,value) in order.enumerated() { values[90+index] = UInt8(value) }
            midi = commands
            orderMessage = [0xf0,0x43,0x58,0x70,13,1,9]+order.map(UInt8.init)+[0xf7]
            orderReply = [0xf0,0x43,0x58,0x70,13,2,9]+order.map(UInt8.init)+[0xf7]
            expected = values
            self.namEnabled = namEnabled
            cabinetBypassed = nil
        }
        func messages(before preset: [UInt8]) -> [UInt8]? {
            guard preset.count == 128 else { return nil }
            if let bypassed = cabinetBypassed {
                guard (1...34).contains(preset[9] & 63) else { return nil }
                return [0xb0,9,(preset[9] & 63) | (bypassed ? 64 : 0)]
            }
            guard let enabled = namEnabled else { return midi }
            return midi + [0xb0,3,(preset[3] & 63) | (enabled ? 0 : 64)]
        }
        func allowed(on identity: String) -> Bool {
            NamLinkWire.supportsModels(identity) &&
                (["NAMLNK24", "NAMLNK25", "NAMLNK26", "NAMLNK27"].contains(identity) || (expected[2].map { ($0 & 63) <= 13 } ?? true)) &&
                (["NAMLNK14","NAMLNK15", "NAMLNK16", "NAMLNK17", "NAMLNK18", "NAMLNK19", "NAMLNK20", "NAMLNK21", "NAMLNK22", "NAMLNK23", "NAMLNK24", "NAMLNK25", "NAMLNK26", "NAMLNK27"].contains(identity) || (expected[4].map { ($0 & 63) <= 2 } ?? true)) &&
                ((namEnabled == nil && cabinetBypassed == nil) || NamLinkWire.supportsStockChain(identity))
        }
        func matches(_ preset: [UInt8], before: [UInt8]? = nil) -> Bool {
            if let bypassed = cabinetBypassed {
                guard preset.count == 128, let before = before, before.count == 128,
                      messages(before: before) != nil else { return false }
                return preset[9] == ((before[9] & 63) | (bypassed ? 64 : 0)) &&
                    (0..<128).allSatisfy { $0 == 9 || preset[$0] == before[$0] }
            }
            return preset.count == 128 && expected.allSatisfy { preset[$0.key] == $0.value }
                && (namEnabled == nil || ((preset[3] & 64) == 0) == namEnabled!)
        }
    }
    static func preset(_ message: [UInt8]) -> [UInt8]? {
        guard message.count == 136,
              Array(message.prefix(6)) == [0xf0,0x43,0x58,0x70,12,2],
              message[6] < 7, message.last == 0xf7,
              message[7..<135].allSatisfy({ $0 < 128 }) else { return nil }
        return Array(message[7..<135])
    }
}

// Bounded preset operations only: metadata, save current checked model/chain,
// and recall a color. Never exposes a raw flash address or an erase command.
public enum NamPresetWire {
    static let prefix: [UInt8] = [0xf0,0x43,0x58,0x70,4,2,0x4e,0x53,1]
    static func valid(_ raw: [UInt8]) -> Bool {
        guard raw.count >= 20, raw.count <= 276, NamLinkWire.word(raw,0) == 0x3031504e,
              raw[4] == 1, raw[6] < 7, NamLinkWire.word(raw,8) != 0,
              Int(raw[12])+256*Int(raw[13])+20 == raw.count else { return false }
        return NamLinkWire.word(raw,raw.count-4) == NamLinkWire.crc(raw[0..<raw.count-4])
    }
    public static func request(_ raw: [UInt8]) -> [UInt8]? {
        guard valid(raw), raw[7] == 0, raw[14] == 0, raw[15] == 0,
              ((raw[5] == 1 || raw[5] == 3) && raw.count == 20) || (raw[5] == 2 && raw.count == 132) else { return nil }
        var out=prefix
        for start in stride(from:0,to:raw.count,by:7) {
            let end=min(start+7,raw.count);var mask:UInt8=0
            for i in start..<end { mask |= (raw[i] >> 7) << (i-start) }
            out.append(mask);out.append(contentsOf:raw[start..<end].map { $0 & 127 })
        }
        out.append(247);return out
    }
    public static func reply(_ wire:[UInt8],to request:[UInt8]) -> [UInt8]? {
        guard valid(request), wire.count == 326, Array(wire.prefix(9)) == prefix, wire.last == 247 else { return nil }
        let packed=Array(wire[9..<325]);var raw:[UInt8]=[]
        for start in stride(from:0,to:packed.count,by:8) {
            let end=min(start+8,packed.count),count=end-start-1
            guard count > 0, packed[start] < (1 << count), packed[start+1..<end].allSatisfy({$0<128}) else { return nil }
            for i in start+1..<end {raw.append(packed[i] | (((packed[start] >> (i-start-1)) & 1) << 7))}
        }
        guard valid(raw),raw.count == 276,raw[5] == (request[5] | 128),raw[6] == request[6],
              raw[8..<12] == request[8..<12],(raw[14]<7 || raw[14]==255),raw[15]<128 else {return nil}
        return raw
    }
}

// NAMLNK12 and NAMLNK13 USB. Bounded dry-input snapshots over MIDI, never a host audio stream.
public enum NamTunerWire {
    static let prefix:[UInt8] = [0xf0,0x43,0x58,0x70,4,2,0x4e,0x55,1]
    static func request(operation:Int,page:Int,nonce:Int)->[UInt8]? {
        guard (0...2).contains(operation),(0...15).contains(page),(1...16383).contains(nonce),
              operation == 2 || page == 0 else {return nil}
        return prefix+[UInt8(operation),UInt8(page),UInt8(nonce&127),UInt8(nonce>>7),0xf7]
    }
    static func reply(_ wire:[UInt8],to request:[UInt8])->[UInt8]? {
        guard request.count==14,Array(request.prefix(9))==prefix,request.last==247,
              Self.request(operation:Int(request[9]),page:Int(request[10]),nonce:Int(request[11])+(Int(request[12])<<7))==request,
              wire.count==330,Array(wire.prefix(9))==prefix,wire.last==247,
              wire[9..<329].allSatisfy({$0<128}) else {return nil}
        var raw:[UInt8]=[]
        for start in stride(from:9,to:329,by:8) {
            for i in 1...7 {raw.append(wire[start+i] | (((wire[start]>>(i-1))&1)<<7))}
        }
        guard raw.count==280,NamLinkWire.word(raw,0)==0x31554e4d,raw[4]==1,
              raw[5]==request[9]|128,raw[6]==request[10],[0,1,3].contains(raw[7]),
              NamLinkWire.word(raw,8)==UInt32(request[11])+(UInt32(request[12])<<7),
              Int(raw[16])+256*Int(raw[17])==12000,Int(raw[18])+256*Int(raw[19])<=2048,
              NamLinkWire.word(raw,276)==NamLinkWire.crc(raw[0..<276]) else {return nil}
        if request[9]==2 && raw[7]==0 && Int(raw[18])+256*Int(raw[19]) != 2048 {return nil}
        return raw
    }
}

// Two custom FX blocks; all writes carry expected active preset and model CRC.
public enum NamFxWire {
    static let prefix: [UInt8] = [240,67,88,112,4,2,78,70,1]
    static func config(_ c:[UInt8]) -> Bool {
        guard c.count==32,c[2] != c[18] else {return false}
        for i in [0,16] {if c[i]<1 || c[i]>7 || c[i+1]>1 || c[i+2]>10 || c[i+3]>24 || c[(i+4)..<(i+10)].contains(where:{$0>100}) || c[(i+10)..<(i+16)].contains(where:{$0 != 0}) {return false}}
        return true
    }
    static func request(_ q:[UInt8]) -> Bool {
        guard [14,52].contains(q.count),Array(q.prefix(9))==prefix,q.last==247,q.dropFirst().dropLast().allSatisfy({$0<128}),q[9]<=2,[0,1,2,3,4,5,6,127].contains(q[10]),q[11]|q[12] != 0 else {return false}
        if q[9]==1 {return q.count==52 && q[13]==0 && q[18]<16 && config(Array(q[19..<51]))}
        return q.count==14 && (q[9] != 2 || q[10]<7)
    }
    static func reply(_ m:[UInt8],to q:[UInt8]) -> [UInt8]? {
        guard request(q),m.count==48,Array(m.prefix(9))==prefix,m.last==247,m.dropFirst().dropLast().allSatisfy({$0<128}),m[9]==q[9]|64,Array(m[10...12])==Array(q[10...12]),m[13]<=2,[0,1,2,3,4,5,6,127].contains(m[14]),config(Array(m[15..<47])) else {return nil}
        return m
    }
}

public enum NamToneWire {
 static let prefix:[UInt8]=[240,67,88,112,4,2,78,71,1]
 static func config(_ c:[UInt8])->Bool {c.count==6 && zip(c,[96,24,24,24,100,96]).allSatisfy{Int($0.0)<=$0.1}}
 static func request(_ q:[UInt8])->Bool {
  guard [14,26].contains(q.count),Array(q.prefix(9))==prefix,q.last==247,q.dropFirst().dropLast().allSatisfy({$0<128}),q[9]<=1,[0,1,2,3,4,5,6,127].contains(q[10]),q[11]|q[12] != 0 else{return false}
  return q[9]==0 ? q.count==14 : q.count==26 && q[13]==0 && q[18]<16 && config(Array(q[19..<25]))
 }
 static func reply(_ m:[UInt8],to q:[UInt8])->[UInt8]? {
  guard request(q),m.count==22,Array(m.prefix(9))==prefix,m.last==247,m.dropFirst().dropLast().allSatisfy({$0<128}),m[9]==q[9]|64,Array(m[10...12])==Array(q[10...12]),m[13]<=2,[0,1,2,3,4,5,6,127].contains(m[14]),config(Array(m[15..<21])) else{return nil};return m
 }
}

public enum NamRecordWire {
 static let prefix:[UInt8]=[240,67,88,112,4,2,78,86,1]
 static func config(_ c:[UInt8])->Bool {c.count==1 && c[0]<=96}
 static func request(_ q:[UInt8])->Bool {
  guard [14,21].contains(q.count),Array(q.prefix(9))==prefix,q.last==247,q.dropFirst().dropLast().allSatisfy({$0<128}),q[9]<=1,[0,1,2,3,4,5,6,127].contains(q[10]),q[11]|q[12] != 0 else{return false}
  return q[9]==0 ? q.count==14 : q.count==21 && q[13]==0 && q[18]<16 && config(Array(q[19..<20]))
 }
 static func reply(_ m:[UInt8],to q:[UInt8])->[UInt8]? {
  guard request(q),m.count==17,Array(m.prefix(9))==prefix,m.last==247,m.dropFirst().dropLast().allSatisfy({$0<128}),m[9]==q[9]|64,Array(m[10...12])==Array(q[10...12]),m[13]<=2,[0,1,2,3,4,5,6,127].contains(m[14]),config(Array(m[15..<16])) else{return nil};return m
 }
}
