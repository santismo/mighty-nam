import Foundation
import CryptoKit

// Exercise the app's unchanged native MIDI transport with previously verified
// Dart traces. Only the fixed RAM model protocol is supported. No audio/DFU API.
enum CheckError: Error, CustomStringConvertible {
    case message(String)
    var description: String { switch self { case .message(let text): return text } }
}
func require(_ condition: Bool, _ text: String) throws {
    if !condition { throw CheckError.message(text) }
}
func writeWord(_ bytes: inout [UInt8], _ at: Int, _ value: UInt32) {
    for i in 0..<4 { bytes[at+i] = UInt8(truncatingIfNeeded: value >> (8*i)) }
}
func pause(_ seconds: Double) {
    let until = Date(timeIntervalSinceNow: seconds)
    while Date() < until { RunLoop.main.run(until: min(until, Date(timeIntervalSinceNow: 0.05))) }
}
func waitFor(_ operation: (@escaping (Result<[String:Any],Error>) -> Void) -> Void) throws -> [String:Any] {
    var result: Result<[String:Any],Error>?
    operation { result = $0 }
    let deadline = Date(timeIntervalSinceNow: 15)
    while result == nil && Date() < deadline { pause(0.01) }
    guard let result = result else { throw CheckError.message("Operation exceeded 15 seconds") }
    return try result.get()
}
func statusWords(_ report: [String:Any]) throws -> [UInt32] {
    try require(report["identity"] as? String == "NAMLNK08", "Exact NAMLNK08 firmware required")
    try require(report["modelTransfer"] as? Bool == true, "Model transfer is not supported")
    try require(report["listeningSupported"] as? Bool == true &&
                (report["listening"] as? [String:Any])?["enabled"] as? Bool == false,
                "NAMLNK08 must remain explicitly muted for this check")
    guard let words = report["words"] as? [Int64], words.count == 12,
          words.allSatisfy({ $0 >= 0 && $0 <= Int64(UInt32.max) }) else {
        throw CheckError.message("Unexpected status layout")
    }
    let result = words.map { UInt32($0) }
    try require(result[0] == 0x4e4c4b31 && result[1] == 1 && result[2] == 1,
                "Unexpected status schema or firmware not ready")
    return result
}
struct Trace {
    let frames: [[UInt8]]
    let slotCRC: UInt32
    let slotSHA: String
    let session: UInt32
    init(_ prefix: String) throws {
        let slot = Array(try Data(contentsOf: URL(fileURLWithPath: prefix + ".slot")))
        let metadata = try JSONSerialization.jsonObject(with:
            Data(contentsOf: URL(fileURLWithPath: prefix + ".json"))) as! [String:Any]
        try require(slot.count == 8192, "Slot must be exactly 8192 bytes")
        let header: [UInt32] = [0x3241504d, 1, 48000, 1871, 7484]
        for i in 0..<header.count {
            try require(NamLinkWire.word(slot,4*i) == header[i], "Unsupported A2 slot")
        }
        try require(NamLinkWire.word(slot,24) == 1 && NamLinkWire.word(slot,28) == 0,
                    "Invalid slot format")
        try require(NamLinkWire.word(slot,20) == NamLinkWire.crc(slot[32..<7516]),
                    "Slot weight checksum mismatch")
        for i in stride(from: 32, to: 7516, by: 4) {
            try require((NamLinkWire.word(slot,i) & 0x7f800000) != 0x7f800000,
                        "Non-finite model weight")
        }
        try require(slot[7516...].allSatisfy({ $0 == 255 }), "Invalid slot padding")
        slotCRC = NamLinkWire.crc(slot[...])
        slotSHA = SHA256.hash(data: Data(slot)).map { String(format: "%02x", $0) }.joined()
        try require((metadata["crc32"] as? NSNumber)?.uint32Value == slotCRC,
                    "Trace metadata checksum mismatch")
        let bytes = Array(try Data(contentsOf: URL(fileURLWithPath: prefix + ".requests")))
        var raw: [[UInt8]] = []
        var at = 0
        while at < bytes.count {
            try require(at+4 <= bytes.count, "Truncated frame length")
            let count = Int(NamLinkWire.word(bytes,at)); at += 4
            try require(count >= 24 && count <= 280 && at+count <= bytes.count,
                        "Invalid frame length")
            let frame = Array(bytes[at..<at+count]); at += count
            try require(NamLinkWire.request(frame) != nil, "Invalid frame checksum")
            raw.append(frame)
        }
        try require(raw.count == 35, "Expected hello, begin, 32 data frames, and commit")
        let oldSession = NamLinkWire.word(raw[1],8)
        try require(oldSession != 0, "Missing original transfer session")
        var newSession = UInt32.random(in: 1...UInt32.max)
        while newSession == oldSession { newSession = UInt32.random(in: 1...UInt32.max) }
        for i in 0..<raw.count {
            let frame = raw[i]
            let op: UInt8 = i == 0 ? 1 : i == 1 ? 2 : i == 34 ? 4 : 3
            try require(frame[5] == op, "Unexpected trace operation")
            try require(NamLinkWire.word(frame,8) == (i == 0 ? 0 : oldSession),
                        "Mixed trace sessions")
            if op == 1 || op == 4 {
                try require(frame.count == 24 && NamLinkWire.word(frame,12) == 0,
                            "Invalid hello/commit")
            } else if op == 2 {
                try require(frame.count == 32 && NamLinkWire.word(frame,12) == 0 &&
                            NamLinkWire.word(frame,24) == 8192 &&
                            NamLinkWire.word(frame,28) == slotCRC, "Invalid begin")
            } else {
                let offset = (i-2)*256
                try require(frame.count == 280 && NamLinkWire.word(frame,12) == UInt32(offset),
                            "Non-sequential data")
                try require(Array(frame[24...]) == Array(slot[offset..<offset+256]),
                            "Trace differs from the verified slot")
            }
            if i > 0 {
                writeWord(&raw[i],8,newSession)
                let crc = NamLinkWire.crc(raw[i][0..<20])
                writeWord(&raw[i],20,crc)
            }
            try require(NamLinkWire.request(raw[i]) != nil, "Session rewrite failed validation")
        }
        session = newSession
        frames = raw
    }
}
