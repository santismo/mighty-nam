import Foundation

// Bounded, cumulative Fender/effects comparisons through production CoreMIDI.
// No model transfer, host audio API, flash, reset, or persistent preset save.
@main struct SpringListening {
    static var stage = "spring"
    static let stages = ["spring","delay","chorus","drive"]
    static var changes: [Int:Int] {
        switch stage {
        case "delay": return [7:2,53:15,54:20,55:25]
        case "chorus": return [6:1,47:15,48:30,49:25]
        case "drive": return [2:5,17:20,18:50,19:35]
        default: return [8:4,61:30,62:15]
        }
    }
    static func preset(_ value: [String:Any]) throws -> [Int] {
        guard let p = value["preset"] as? [Int], p.count == 128,
              p.allSatisfy({ (0...127).contains($0) }) else {
            throw CheckError.message("Invalid preset snapshot")
        }
        return p
    }
    static func plan(_ p: [Int]) throws -> NamStockWire.Plan {
        let controls = (NamStockWire.heads.keys.sorted() + [17,18,19,47,48,49,53,54,55,61,62]).map {
            [$0,p[NamStockWire.presetIndex($0)!]]
        }
        guard let plan = NamStockWire.Plan(controls:controls,order:Array(p[90..<99]),
                                          namEnabled:(p[3] & 64) == 0) else {
            throw CheckError.message("Cannot build bounded restorable plan")
        }
        return plan
    }
    static func target(_ before: [Int]) throws -> [Int] {
        let previous = stages.prefix(stages.firstIndex(of:stage)!)
        var enabled: [Int:Int] = [:]
        if previous.contains("spring") { enabled[8] = 4 }
        if previous.contains("delay") { enabled[7] = 2 }
        if previous.contains("chorus") { enabled[6] = 1 }
        try require(before[3] & 64 == 0 && NamStockWire.heads.keys.allSatisfy {
            if let expected = enabled[$0] { return before[$0] == expected }
            return before[$0] & 64 != 0
        }, "Expected the previous verified cumulative effect stage")
        try require(before[8] & 63 == 4, "Expected existing Spring algorithm")
        let order = Array(before[90..<99])
        guard Set(order) == Set(1...9), let reverb = order.firstIndex(of:8),
              let nam = order.firstIndex(of:3), reverb > nam else {
            throw CheckError.message("Valid chain with reverb after NAM required")
        }
        var result = before
        for (cc,value) in changes { result[NamStockWire.presetIndex(cc)!] = value }
        if stage == "delay" {
            // Move delay from before NAM to just before the final reverb block.
            var nextOrder = order.filter { $0 != 7 }
            nextOrder.insert(7,at:nextOrder.firstIndex(of:8)!)
            result.replaceSubrange(90..<99,with:nextOrder)
        }
        return result
    }
    static func validate(_ before: [Int]) throws -> [Int] {
        let after = try target(before)
        let p = try plan(after), restore = try plan(before)
        var predicted = before
        for (at,value) in p.expected { predicted[at] = Int(value) }
        try require(predicted == after, "Plan alters unexpected preset bytes")
        let ordered = p.expected.sorted { $0.key < $1.key }
        for count in 0...ordered.count {
            var partial = before
            for (at,value) in ordered.prefix(count) { partial[at] = Int(value) }
            for (at,value) in restore.expected { partial[at] = Int(value) }
            try require(partial == before, "Partial write cannot be restored exactly")
        }
        try require(after[9] & 64 != 0, "Cabinet must stay bypassed")
        return after
    }
    static func main() {
        let args = CommandLine.arguments
        let modes = ["--validate","--run"] + stages.flatMap { ["--validate-"+$0,"--run-"+$0] }
        guard args.count == 4, modes.contains(args[1]) else {
            print("Usage: effect-listen --validate[-STAGE]|--run[-STAGE] FIXTURE_REPORT REPORT"); exit(2)
        }
        stage = stages.first { args[1].hasSuffix("-"+$0) } ?? "spring"
        var report: [String:Any] = [
            "started":ISO8601DateFormatter().string(from:Date()), "status":"PREPARING",
            "mode":args[1],"audioStreamsOpened":0,"macAudioSettingsChanged":false,
            "teamsSettingsChanged":false,"modelTransferCommands":0,"firmwareFlashCommands":0,
            "resetCommands":0,"persistentSave":false,"wholeISRDeadlineProven":false,
            "effect":stage,"cumulativeStages":Array(stages.prefix(stages.firstIndex(of:stage)!+1)),
            "changes":changes.keys.sorted().map { [$0,changes[$0]!] },"cabinetBypassed":true]
        var events: [[String:Any]] = []
        let midi = NamMidi()
        var source: Int?
        var supported = false
        var modified = false
        var original: [Int]?
        var failed = false
        var lastAccepted: Int64?
        var lastRuns: Int64?
        func save() {
            report["events"] = events
            do {
                try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys])
                    .write(to:URL(fileURLWithPath:args[3]),options:.atomic)
            } catch { print("Evidence save failed: \(error)") }
        }
        func record(_ label: String, _ value: [String:Any]) {
            events.append(["step":label,"time":ISO8601DateFormatter().string(from:Date()),"result":value])
            save(); print(label); fflush(stdout)
        }
        do {
            let fixture = try JSONSerialization.jsonObject(with:Data(contentsOf:URL(fileURLWithPath:args[2]))) as! [String:Any]
            let fixtureEvents = fixture["events"] as! [[String:Any]]
            guard let value = fixtureEvents.first(where: { $0["step"] as? String == "stock-after" })?["result"] as? [String:Any] else {
                throw CheckError.message("Missing fixture preset")
            }
            _ = try validate(preset(value))
            report["offlinePlanAndAllPartialRestoresPassed"] = true
            if args[1].hasPrefix("--validate") {
                report["status"] = "PASS_EFFECT_PLAN_AND_PARTIAL_RESTORE"; save(); return
            }
            let devices = try midi.devices()
            try require(devices.count == 1,"Exactly one matching plug required")
            guard let id = devices[0]["source"] as? Int else { throw CheckError.message("Missing source") }
            source = id
            func snapshot(_ name: String, enabled: Bool) throws -> [Int64] {
                let result = try waitFor { midi.inspect(id,completion:$0) }; record(name,result)
                try require(result["identity"] as? String == "NAMLNK08","Exact NAMLNK08 required")
                supported = true
                guard let words = result["words"] as? [Int64], words.count == 12,
                      let listen = result["listening"] as? [String:Any],
                      let timing = result["irqTiming"] as? [String:Any],
                      let accepted = timing["accepted"] as? Int64 else { throw CheckError.message("Invalid status") }
                try require(words[0] == 0x4e4c4b31 && words[1] == 1 && words[2] == 1,
                            "Unexpected firmware schema")
                try require(words[5] == 1854512385 && words[6] == 1,"Fender generation 1 required")
                try require(words[4] == 0 && words[10] == 0 && words[9] == 1 && words[8] > 0 && words[8] < 150,
                            "Processing stopped/fault/guard: \(words)")
                try require(listen["enabled"] as? Bool == enabled && listen["settling"] as? Bool == false,
                            "Unexpected mute or settling state")
                if enabled { try require(listen["fadeComplete"] as? Bool == true,"Fade incomplete") }
                try require(timing["usable"] as? Bool == true && timing["rejected"] as? Int64 == 0 && timing["flags"] as? Int64 == 0,
                            "Unusable raw IRQ counters")
                if let previous = lastAccepted { try require(accepted > previous,"IRQ publication stopped") }
                if let previous = lastRuns { try require(words[7] > previous,"NAM processing stopped") }
                lastAccepted = accepted; lastRuns = words[7]
                report["peakTimerTicks"] = words[8]
                return words
            }
            _ = try snapshot("before-muted",enabled:false)
            let before = try waitFor { midi.stock(id,completion:$0) }; record("stock-before",before)
            let base = try preset(before), next = try validate(base)
            original = base
            let p = try plan(next)
            modified = true
            let applied = try waitFor { midi.stock(id,plan:p,completion:$0) }; record("spring-controls",applied)
            try require(applied["controlsVerified"] as? Bool == true && preset(applied) == next,
                        "Spring settings did not read back exactly")
            report["changedPresetIndices"] = (0..<128).filter { base[$0] != next[$0] }
            pause(1)
            _ = try snapshot("spring-muted-after-1-second",enabled:false)
            pause(4)
            _ = try snapshot("spring-muted-after-5-seconds",enabled:false)
            report["headphonePreparation"] = "User confirmed minimum before this effects series and was instructed to keep volume low for each step"
            let arm = try waitFor { midi.listen(id,enabled:true,completion:$0) }; record("SPRING_LISTENING_ENABLED",arm)
            try require((arm["listening"] as? [String:Any])?["enabled"] as? Bool == true,"Listening not confirmed")
            var prior = 0.0
            for seconds in [0.5,1.0,5.0,15.0,30.0] {
                pause(seconds-prior); prior = seconds
                _ = try snapshot("spring-after-\(seconds)-seconds",enabled:true)
            }
            let after = try waitFor { midi.stock(id,completion:$0) }; record("stock-after",after)
            try require(try preset(after) == next,"Preset changed during comparison")
            report["all128PreparedPresetBytesUnchanged"] = true
            report["mutedObservationSeconds"] = 5
            report["armedObservationSeconds"] = 30
            report["listeningLeftEnabled"] = true
            report["audibleFeedbackPending"] = true
            report["status"] = "PASS_NAMLNK08_FENDER_EFFECT_OBSERVATION"
        } catch {
            failed = true; report["status"] = "FAILED"; report["error"] = String(describing:error)
            if supported, let id = source {
                do {
                    let muted = try waitFor { midi.listen(id,enabled:false,completion:$0) }; record("failure-mute",muted)
                    report["failureMuteConfirmed"] = (muted["listening"] as? [String:Any])?["enabled"] as? Bool == false
                } catch { report["muteError"] = String(describing:error) }
                if modified, let before = original {
                    do {
                        let p = try plan(before)
                        let restored = try waitFor { midi.stock(id,plan:p,completion:$0) }; record("failure-restore",restored)
                        report["all128OriginalPresetBytesRestored"] = try preset(restored) == before
                    } catch { report["restoreError"] = String(describing:error) }
                }
            }
        }
        midi.disconnect(); report["finished"] = ISO8601DateFormatter().string(from:Date()); save()
        print(report["status"]!); if failed { print(report["error"]!); exit(1) }
    }
}
