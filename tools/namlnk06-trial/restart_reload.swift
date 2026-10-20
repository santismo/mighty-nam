import Foundation

// Read status/presets and reload one verified RAM model using production MIDI.
// No effect writes, flash/reset commands, audio streams or system audio changes.
@main struct RestartReload {
    static func main() {
        let args = CommandLine.arguments
        guard args.count == 4, ["--validate", "--run"].contains(args[1]) else {
            print("Usage: restart-reload --validate|--run TRACE_PREFIX REPORT")
            exit(2)
        }
        let midi = NamMidi()
        var report: [String:Any] = [
            "started": ISO8601DateFormatter().string(from: Date()),
            "status": "PREPARING", "mode": args[1], "audioStreamOpened": false,
            "macAudioSettingsChanged": false, "teamsSettingsChanged": false,
            "firmwareFlashCommands": false, "resetCommands": false,
            "effectControlWrites": false, "persistentSave": false
        ]
        var events: [[String:Any]] = []
        var replies: [[String:Any]] = []
        var failed = false
        var previousAccepted: Int64?
        func save() {
            report["events"] = events
            report["replies"] = replies
            do {
                try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted,.sortedKeys])
                    .write(to: URL(fileURLWithPath: args[3]), options: .atomic)
            } catch { print("Evidence save failed: \(error)"); exit(2) }
        }
        func record(_ name: String, _ value: [String:Any]) {
            events.append(["step": name, "time": ISO8601DateFormatter().string(from: Date()), "result": value])
            save(); print(name); fflush(stdout)
        }
        do {
            let trace = try Trace(args[2])
            report["model"] = ["name": URL(fileURLWithPath: args[2]).lastPathComponent,
                               "crc": trace.slotCRC, "sha256": trace.slotSHA,
                               "frames": trace.frames.count, "session": trace.session]
            if args[1] == "--validate" {
                report["status"] = "PASS_FILES_ONLY_VALIDATION"; save(); return
            }
            let devices = try midi.devices()
            try require(devices.count == 1, "Require exactly one matching plug")
            guard let id = devices[0]["source"] as? Int else { throw CheckError.message("Missing MIDI source") }
            func snapshot(_ label: String) throws -> [UInt32] {
                let value = try waitFor { midi.inspect(id, completion: $0) }
                record(label, value)
                guard let timing = value["irqTiming"] as? [String:Any],
                      timing["usable"] as? Bool == true,
                      timing["rejected"] as? Int64 == 0,
                      timing["flags"] as? Int64 == 0,
                      let accepted = timing["accepted"] as? Int64 else {
                    throw CheckError.message("No clean IRQ timing snapshot")
                }
                if let previous = previousAccepted {
                    try require(accepted > previous, "IRQ timing did not advance")
                }
                previousAccepted = accepted
                return try statusWords(value)
            }
            func healthy(_ words: [UInt32]) throws {
                try require(words[4] == 0 && words[10] == 0 && words[9] == 1
                            && words[8] > 0 && words[8] < 150,
                            "Processing fault/stopped/over limit: \(words)")
                try require(words[5] == trace.slotCRC && words[6] == 1, "Unexpected model or activation count")
            }
            let before = try snapshot("after-user-restart")
            try require(before[4...10].allSatisfy({ $0 == 0 }), "Expected clean boot and empty RAM model")
            report["restartClearedModelAndCounters"] = true
            let stock = try waitFor { midi.stock(id, completion: $0) }
            record("stock-before-reload", stock)
            guard let preset = stock["preset"] as? [Int], preset.count == 128 else {
                throw CheckError.message("Malformed preset")
            }
            try require((preset[3] & 64) == 0, "NAM is bypassed; cannot verify model processing without a control change")
            report["NAMBlockEnabled"] = true
            for (i, frame) in trace.frames.enumerated() {
                var response: [String:Any]?
                var lastError: Error?
                var attempts = 0
                for attempt in 1...3 {
                    attempts = attempt
                    do { response = try waitFor { midi.exchange(id, request: frame, completion: $0) }; break }
                    catch { lastError = error }
                }
                guard let response = response else { throw lastError! }
                guard let reply = response["frame"] as? [UInt8], reply.count == 48,
                      NamLinkWire.validPacket(reply), reply[5] == (frame[5] | 128),
                      NamLinkWire.word(reply, 8) == NamLinkWire.word(frame, 8),
                      NamLinkWire.word(reply, 12) == 0 else {
                    throw CheckError.message("Invalid transfer acknowledgement \(i)")
                }
                let fields = stride(from: 24, to: 48, by: 4).map { NamLinkWire.word(reply, $0) }
                replies.append(["frame": i, "attempts": attempts, "fields": fields])
                try require(fields[0] == 0 && Array(fields[3...]) == [8192,256,3], "Transfer rejected/capabilities changed")
                if i > 0 {
                    try require(fields[1] == UInt32(i == 1 ? 0 : min(8192,(i-1)*256)), "Wrong transfer byte count")
                }
                try require(fields[2] == (i == 34 ? trace.slotCRC : 0), "Active checksum mismatch")
            }
            var previous = try snapshot("after-reload")
            try healthy(previous)
            for (seconds, name) in [(1.0,"after-1-second"), (4.0,"after-5-seconds"), (25.0,"after-30-seconds")] {
                pause(seconds)
                let current = try snapshot(name)
                try healthy(current)
                try require(current[3] &- previous[3] > 0 && current[7] &- previous[7] > 0,
                            "Audio callbacks or processing stopped")
                previous = current
            }
            let afterStock = try waitFor { midi.stock(id, completion: $0) }
            record("stock-after-reload", afterStock)
            try require(afterStock["preset"] as? [Int] == preset, "Preset changed during reload")
            report["all128PresetBytesUnchanged"] = true
            let final = try snapshot("final-status")
            try healthy(final)
            report["peakTimerTicks"] = final[8]
            report["observationSeconds"] = 30
            report["status"] = "PASS_NAMLNK06_PHYSICAL_RESTART_RELOAD"
            report["wholeISRDeadlineProven"] = false
            report["audibleOutputTested"] = false
            report["rawIRQTimingValidated"] = true
            report["counterCalibrated"] = false
            report["modelPersistsAfterRestart"] = false
        } catch {
            failed = true
            report["status"] = "FAILED"
            report["error"] = String(describing: error)
        }
        midi.disconnect()
        report["finished"] = ISO8601DateFormatter().string(from: Date())
        save()
        print(report["status"]!)
        if failed { print(report["error"]!); exit(1) }
    }
}
