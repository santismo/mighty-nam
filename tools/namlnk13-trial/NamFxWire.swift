import Foundation

enum NamFxWire {
    static let prefix: [UInt8] = [240, 67, 88, 112, 4, 2, 78, 70, 1]

    static func valid(_ config: [UInt8]) -> Bool {
        guard config.count == 32, config[2] != config[18] else { return false }
        for i in [0, 16] {
            if !(1...7).contains(config[i]) || config[i + 1] > 1 || config[i + 2] > 10 || config[i + 3] > 24 { return false }
            if config[(i + 4)..<(i + 10)].contains(where: { $0 > 100 }) { return false }
            if config[(i + 10)..<(i + 16)].contains(where: { $0 != 0 }) { return false }
        }
        return true
    }

    static func defaults() -> [UInt8] {
        var c = [UInt8](repeating: 0, count: 32)
        for j in 0..<2 {
            let i = j * 16
            c[i] = UInt8(j + 1); c[i + 2] = UInt8(j + 2); c[i + 3] = 12
            c[i + 4] = 100; c[i + 5] = 30
            for offset in [6, 8, 9] { c[i + offset] = 50 }
        }
        return c
    }

    static func make(_ op: Int, _ slot: Int, _ nonce: Int, _ config: [UInt8]? = nil, _ crc: UInt32 = 0) -> [UInt8]? {
        guard (0...2).contains(op), ((0...6).contains(slot) || slot == 255), op != 2 || slot < 7, (1...16383).contains(nonce) else { return nil }
        var message = prefix + [UInt8(op), UInt8(slot == 255 ? 127 : slot), UInt8(nonce & 127), UInt8(nonce >> 7)]
        if op == 1 {
            guard let c = config, valid(c) else { return nil }
            message.append(0)
            for i in 0..<5 { message.append(UInt8((crc >> (7 * i)) & 127)) }
            message += c
        }
        return message + [247]
    }

    static func validRequest(_ m: [UInt8]) -> Bool {
        guard [14, 52].contains(m.count), Array(m.prefix(9)) == prefix, m.last == 247, m.dropFirst().dropLast().allSatisfy({ $0 < 128 }) else { return false }
        let op = Int(m[9]), slot = m[10] == 127 ? 255 : Int(m[10])
        var crc: UInt32 = 0
        if op == 1 {
            guard m.count == 52, m[13] == 0, m[18] < 16 else { return false }
            for i in 0..<5 { crc |= UInt32(m[14 + i]) << (7 * i) }
        }
        return make(op, slot, Int(m[11]) + 128 * Int(m[12]), op == 1 ? Array(m[19..<51]) : nil, crc) == m
    }

    static func reply(_ m: [UInt8], to q: [UInt8]) -> [String: Any]? {
        guard m.count == 48, Array(m.prefix(9)) == prefix, m.last == 247, m.dropFirst().dropLast().allSatisfy({ $0 < 128 }), m[9] == (q[9] | 64), Array(m[10...12]) == Array(q[10...12]), m[13] <= 2, m[14] <= 6 || m[14] == 127 else { return nil }
        let c = Array(m[15..<47])
        guard valid(c) else { return nil }
        return ["error": Int(m[13]), "active": m[14] == 127 ? 255 : Int(m[14]), "config": c.map(Int.init)]
    }
}
