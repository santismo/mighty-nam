import Foundation

// Uses only the production controller's bounded MIDI API. No audio, flash,
// reset, persistent preset save, or system audio controls.
@main struct ChainCheck {
    static func main() {
        let args = CommandLine.arguments
        guard args.count == 5, ["--validate","--run","--run-warm"].contains(args[1]) else {
            print("Usage: chain --validate|--run|--run-warm FIRST_TRACE SECOND_TRACE REPORT")
            exit(2)
        }
        let midi = NamMidi()
        var report: [String:Any] = [
            "started":ISO8601DateFormatter().string(from:Date()),
            "audioStreamOpened":false, "macAudioSettingsChanged":false,
            "teamsSettingsChanged":false, "firmwareFlashCommands":false,
            "persistentSave":false, "mode":args[1], "status":"PREPARING"
        ]
        var events: [[String:Any]] = []
        var original: [UInt8]?
        var source: Int?
        var modified = false
        var failed = false
        var lastAccepted: Int64?
        func save() {
            report["events"] = events
            do {
                try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys])
                    .write(to:URL(fileURLWithPath:args[4]),options:.atomic)
            } catch { print("Evidence write failed: \(error)"); exit(2) }
        }
        func event(_ label: String, _ value: [String:Any]) {
            events.append(["step":label,"time":ISO8601DateFormatter().string(from:Date()),"result":value])
            save()
            print(label)
            fflush(stdout)
        }
        func plan(_ preset: [UInt8], heads: [Int:Int]? = nil, order: [Int]? = nil,
                  nam: Bool) throws -> NamStockWire.Plan {
            let controls = NamStockWire.heads.keys.sorted().map { cc in
                [cc, heads?[cc] ?? Int(preset[cc])]
            }
            guard let result = NamStockWire.Plan(controls:controls,
                order:order ?? preset[90..<99].map(Int.init),namEnabled:nam) else {
                throw CheckError.message("Stock snapshot cannot form a bounded restorable plan")
            }
            return result
        }
        do {
            let traces = try [Trace(args[2]),Trace(args[3])]
            report["models"] = traces.enumerated().map { i,t in
                ["name":URL(fileURLWithPath:args[i+2]).lastPathComponent,
                 "crc":t.slotCRC,"sha256":t.slotSHA,"frames":t.frames.count] as [String:Any]
            }
            if args[1] == "--validate" {
                report["status"] = "PASS_FILES_ONLY_VALIDATION"; save(); return
            }
            let devices = try midi.devices()
            try require(devices.count == 1, "Require exactly one matching plug")
            guard let id = devices[0]["source"] as? Int else {
                throw CheckError.message("Missing source")
            }
            source = id
            func snapshot(_ label: String) throws -> [UInt32] {
                let result = try waitFor { midi.inspect(id,completion:$0) }
                event(label,result)
                guard let timing = result["irqTiming"] as? [String:Any],
                      timing["usable"] as? Bool == true,
                      let accepted = timing["accepted"] as? Int64,
                      timing["rejected"] as? Int64 == 0,
                      timing["flags"] as? Int64 == 0,
                      let maximum = timing["maximumCycles"] as? Int64,
                      maximum > 0 else {
                    throw CheckError.message("Missing, rejected or unusable raw IRQ timing")
                }
                if let previous = lastAccepted {
                    try require(accepted > previous, "IRQ timing publication did not advance")
                }
                lastAccepted = accepted
                return try statusWords(result)
            }
            func healthy(_ w: [UInt32], running: Bool) throws {
                try require(w[4] == 0 && w[10] == 0,
                    "Processing fault/context rejection: \(w[4])/\(w[10]); maximum timer \(w[8])")
                if running {
                    try require(w[9] == 1 && w[8] > 0 && w[8] < 150,
                        "Processing stopped or timing limit reached: \(w)")
                }
            }
            func observe(_ label: String, seconds: Double, crc: UInt32) throws {
                let a = try snapshot(label+"-start")
                try healthy(a,running:true)
                pause(seconds)
                let b = try snapshot(label+"-end")
                try healthy(b,running:true)
                try require(a[5] == crc && b[5] == crc && a[6] == b[6],
                    "Model changed during observation")
                try require(b[3] &- a[3] > 0 && b[7] &- a[7] > 0,
                    "Audio callbacks or internal processing did not advance")
            }
            let initial = try snapshot("initial")
            try healthy(initial,running:initial[9] == 1)
            let stock = try waitFor { midi.stock(id,completion:$0) }
            event("original-stock",stock)
            guard let values = stock["preset"] as? [Int], values.count == 128,
                  values.allSatisfy({(0...127).contains($0)}) else {
                throw CheckError.message("Malformed stock snapshot")
            }
            let preset = values.map(UInt8.init)
            _ = try plan(preset,nam:(preset[3] & 64) == 0)
            original = preset
            var heads = Dictionary(uniqueKeysWithValues:
                NamStockWire.heads.keys.map { ($0,Int(preset[$0]) | 64) })
            func apply(_ label: String, _ p: NamStockWire.Plan) throws {
                modified = true
                let r = try waitFor { midi.stock(id,plan:p,completion:$0) }
                event(label,r)
                try require(r["controlsVerified"] as? Bool == true &&
                            r["stockChain"] as? Bool == true,
                            "Control readback did not confirm NAMLNK06")
            }
            let warm = args[1] == "--run-warm"
            try apply("bypass-all-stock",plan(preset,heads:heads,nam:!warm))
            func upload(_ trace: Trace, _ name: String) throws {
                let before = try snapshot(name+"-before-transfer")
                try healthy(before,running:before[9] == 1)
                for (i,frame) in trace.frames.enumerated() {
                    var response: [String:Any]?
                    var lastError: Error?
                    for _ in 0..<3 {
                        do { response = try waitFor { midi.exchange(id,request:frame,completion:$0) }; break }
                        catch { lastError = error }
                    }
                    guard let response = response else { throw lastError! }
                    guard let reply = response["frame"] as? [UInt8],reply.count == 48,
                          NamLinkWire.validPacket(reply),
                          reply[5] == (frame[5] | 128),
                          NamLinkWire.word(reply,8) == NamLinkWire.word(frame,8),
                          NamLinkWire.word(reply,12) == 0 else {
                        throw CheckError.message("Invalid transfer acknowledgement \(i)")
                    }
                    let fields = stride(from:24,to:48,by:4).map { NamLinkWire.word(reply,$0) }
                    try require(fields[0] == 0 && Array(fields[3...]) == [8192,256,3],
                                "Transfer rejected frame \(i): \(fields)")
                    if i > 0 {
                        let count = i == 1 ? 0 : min(8192,(i-1)*256)
                        try require(fields[1] == UInt32(count),"Transfer byte count mismatch")
                    }
                    try require(fields[2] == (i == 34 ? trace.slotCRC : before[5]),
                                "Active checksum mismatch")
                }
                let after = try snapshot(name+"-after-transfer")
                try require(after[5] == trace.slotCRC && after[6] == before[6] &+ 1,
                            "Model did not activate exactly once")
                try healthy(after,running:true)
            }
            try upload(traces[0],"first-model")
            if warm {
                try observe("all-stages-bypassed",seconds:3,crc:traces[0].slotCRC)
                try apply("enable-NAM-after-warmup",plan(preset,heads:heads,nam:true))
            }
            try observe("NAM-stock-bypassed",seconds:3,crc:traces[0].slotCRC)
            for (cc,name) in [(9,"cab"),(4,"EQ"),(2,"drive"),(1,"compressor"),
                              (6,"modulation"),(7,"delay"),(8,"reverb"),(5,"gate")] {
                heads[cc] = heads[cc]! & 63
                try apply("enable-"+name,plan(preset,heads:heads,nam:true))
                try observe("with-"+name,seconds:3,crc:traces[0].slotCRC)
            }
            try observe("all-stock-effects",seconds:60,crc:traces[0].slotCRC)
            let reordered = [1,2,5,3,9,4,6,7,8]
            try apply("reorder-chain",plan(preset,heads:heads,order:reordered,nam:true))
            try observe("reordered-chain",seconds:5,crc:traces[0].slotCRC)
            try apply("bypass-NAM",plan(preset,heads:heads,order:reordered,nam:false))
            try observe("NAM-bypassed",seconds:3,crc:traces[0].slotCRC)
            try apply("resume-NAM",plan(preset,heads:heads,order:reordered,nam:true))
            try observe("NAM-resumed",seconds:3,crc:traces[0].slotCRC)
            try upload(traces[1],"second-model")
            try observe("second-model-full-chain",seconds:60,crc:traces[1].slotCRC)
            report["status"] = "PASS_PHYSICAL_SILENT_STOCK_CHAIN_TRIAL"
            report["audibleOutputTested"] = false
            report["wholeISRDeadlineProven"] = false
            report["testedSettingsOnly"] = true
            report["rawIRQTimingValidated"] = true
            report["counterCalibrated"] = false
            report["heavySettingsTestedOnHardware"] = false
        } catch {
            failed = true
            report["status"] = "FAILED"
            report["error"] = String(describing:error)
            event("failure",["error":String(describing:error)])
        }
        if modified, let id = source, let preset = original {
            do {
                let p = try plan(preset,nam:(preset[3] & 64) == 0)
                let restored = try waitFor { midi.stock(id,plan:p,completion:$0) }
                event("restore-original-controls",restored)
                try require(restored["controlsVerified"] as? Bool == true,"Restore not confirmed")
                try require(restored["preset"] as? [Int] == preset.map(Int.init),
                            "Full preset changed outside the intended head/order controls")
                report["originalControlsRestored"] = true
                report["all128OriginalPresetBytesRestored"] = true
                let final = try waitFor { midi.inspect(id,completion:$0) }
                event("final-status",final)
                if !failed {
                    let words = try statusWords(final)
                    try require(words[4] == 0 && words[9] == 1 && words[8] < 150,
                                "Restoring original settings stopped processing")
                }
            } catch {
                report["originalControlsRestored"] = false
                report["restoreError"] = String(describing:error)
                failed = true
                report["status"] = "FAILED"
            }
        }
        midi.disconnect()
        report["finished"] = ISO8601DateFormatter().string(from:Date())
        save()
        print(report["status"]!)
        if failed { exit(1) }
    }
}
