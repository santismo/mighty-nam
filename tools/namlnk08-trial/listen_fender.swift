import Foundation

// Production MIDI control only. No model/effect writes, flash, reset or audio API.
@main struct ListeningTrial {
    static func main() {
        let args = CommandLine.arguments
        guard args.count == 3, ["--inspect", "--listen", "--mute"].contains(args[1]) else {
            print("Usage: listening-trial --inspect|--listen|--mute REPORT")
            exit(2)
        }
        let midi = NamMidi()
        var device: Int?
        var armed = false
        var failed = false
        var events: [[String:Any]] = []
        var report: [String:Any] = [
            "status":"PREPARING", "mode":args[1],
            "started":ISO8601DateFormatter().string(from:Date()),
            "expectedIdentity":"NAMLNK08", "expectedModelCRC":Int64(1854512385),
            "audioStreamsOpened":0, "macAudioSettingsChanged":false,
            "teamsSettingsChanged":false, "effectControlWrites":0,
            "modelTransferCommands":0, "firmwareFlashCommands":0,
            "resetCommands":0, "persistentSave":false,
            "listeningArmCommands":0, "listeningMuteCommands":0
        ]
        func save() {
            report["events"] = events
            do {
                try JSONSerialization.data(withJSONObject:report, options:[.prettyPrinted,.sortedKeys])
                    .write(to:URL(fileURLWithPath:args[2]), options:.atomic)
            } catch { print("Could not save evidence: \(error)") }
        }
        func record(_ label:String, _ result:[String:Any]) {
            events.append(["step":label,"time":ISO8601DateFormatter().string(from:Date()),"result":result])
            save(); print(label); fflush(stdout)
        }
        func healthy(_ value:[String:Any], enabled:Bool) throws -> [Int64] {
            try require(value["identity"] as? String == "NAMLNK08", "Exact NAMLNK08 identity required")
            guard let words = value["words"] as? [Int64], words.count == 12 else {
                throw CheckError.message("Invalid status words")
            }
            try require(words[0] == 0x4e4c4b31 && words[1] == 1 && words[2] == 1,
                        "Firmware not ready")
            try require(words[4] == 0 && words[10] == 0 && words[9] == 1,
                        "Processing fault or stopped: \(words)")
            try require(words[5] == 1854512385 && words[6] == 1,
                        "Fender Super Reverb A2 Lite generation 1 is no longer loaded")
            try require(words[8] > 0 && words[8] < 150, "DSP guard margin unavailable")
            guard let listening = value["listening"] as? [String:Any],
                  listening["enabled"] as? Bool == enabled,
                  listening["settling"] as? Bool == false else {
                throw CheckError.message("Unexpected listening or settling state")
            }
            guard let timing = value["irqTiming"] as? [String:Any],
                  timing["usable"] as? Bool == true,
                  timing["rejected"] as? Int64 == 0,
                  timing["flags"] as? Int64 == 0 else {
                throw CheckError.message("Unusable IRQ timing")
            }
            return words
        }
        do {
            let devices = try midi.devices()
            try require(devices.count == 1, "Exactly one matching plug required")
            guard let id = devices[0]["source"] as? Int else { throw CheckError.message("Missing MIDI source") }
            device = id
            let before = try waitFor { midi.inspect(id, completion:$0) }
            record("before",before)
            if args[1] == "--mute" {
                try require(before["identity"] as? String == "NAMLNK08", "Exact NAMLNK08 required")
                report["listeningMuteCommands"] = 1
                let muted = try waitFor { midi.listen(id,enabled:false,completion:$0) }
                record("muted",muted)
                try require((muted["listening"] as? [String:Any])?["enabled"] as? Bool == false,
                            "Mute was not confirmed")
                report["status"] = "PASS_EXPLICIT_PLUG_MUTE"
            } else {
                var previous = try healthy(before,enabled:false)
                let stock = try waitFor { midi.stock(id,completion:$0) }
                record("stock-before",stock)
                guard let preset = stock["preset"] as? [Int], preset.count == 128 else {
                    throw CheckError.message("Invalid preset")
                }
                try require(preset[3] & 64 == 0 && (1...9).filter { $0 != 3 }.allSatisfy { preset[$0] & 64 != 0 }, "NAM-only comparison required")
                if args[1] == "--inspect" {
                    report["status"] = "PASS_MUTED_LISTENING_PREFLIGHT"
                } else {
                    // User confirmed headphones on the plug and its volume at minimum.
                    report["headphonePreparationUserConfirmed"] = true
                    report["listeningArmCommands"] = 1
                    armed = true // Also mute on an uncertain arm acknowledgement.
                    let result = try waitFor { midi.listen(id,enabled:true,completion:$0) }
                    record("LISTENING_ENABLED",result)
                    try require((result["listening"] as? [String:Any])?["enabled"] as? Bool == true,
                                "Listening was not confirmed")
                    var priorSeconds = 0.0
                    var previousAccepted = (before["irqTiming"] as? [String:Any])?["accepted"] as? Int64 ?? 0
                    for seconds in [0.5, 1.0, 5.0, 15.0, 30.0, 60.0] {
                        pause(seconds-priorSeconds); priorSeconds = seconds
                        let value = try waitFor { midi.inspect(id,completion:$0) }
                        record("after-\(seconds)-seconds",value)
                        let current = try healthy(value,enabled:true)
                        try require((value["listening"] as? [String:Any])?["fadeComplete"] as? Bool == true,
                                    "Output fade did not complete")
                        let accepted = (value["irqTiming"] as? [String:Any])?["accepted"] as? Int64 ?? 0
                        try require(current[3] > previous[3] && current[7] > previous[7] && accepted > previousAccepted,
                                    "Processing/timing did not advance")
                        previous = current; previousAccepted = accepted
                    }
                    let afterStock = try waitFor { midi.stock(id,completion:$0) }
                    record("stock-after",afterStock)
                    report["all128PresetBytesUnchanged"] = afterStock["preset"] as? [Int] == preset
                    report["peakTimerTicks"] = previous[8]
                    report["observationSeconds"] = 60
                    report["listeningLeftEnabled"] = true
                    report["audibleQualityUserFeedbackPending"] = true
                    report["calibratedWholeISRDeadlineProven"] = false
                    report["status"] = "PASS_NAMLNK08_ARMED_PROCESSING_OBSERVATION"
                }
            }
        } catch {
            failed = true; report["status"] = "FAILED"; report["error"] = String(describing:error)
            if armed, let id = device {
                report["listeningMuteCommands"] = 1
                do {
                    let muted = try waitFor { midi.listen(id,enabled:false,completion:$0) }
                    record("failure-mute",muted)
                    report["failureMuteConfirmed"] = (muted["listening"] as? [String:Any])?["enabled"] as? Bool == false
                } catch { report["failureMuteError"] = String(describing:error) }
            }
        }
        midi.disconnect()
        report["finished"] = ISO8601DateFormatter().string(from:Date()); save()
        print(report["status"]!); fflush(stdout)
        if failed { print(report["error"]!); exit(1) }
    }
}
