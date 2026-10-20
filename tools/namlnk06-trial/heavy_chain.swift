import Foundation

// Silent NAMLNK06 only. Uses production volatile effect controls; no model
// writes, audio APIs, routing, persistent saves, reset or firmware update API.
struct Trial {
    let name: String
    let changes: [Int:Int]
    let seconds: Double
    var order: [Int]? = nil
    var nam: Bool = true
}

@main struct HeavyChain {
    static let crc: UInt32 = 3399832575 // Previously verified Marshall Lite.
    static let parameters = NamStockWire.groups.flatMap { Array($0.0) }
    static let heads = NamStockWire.heads.keys.sorted()
    static let order = [5,1,2,3,9,4,6,7,8]
    static let alternateOrder = [5,3,1,2,4,9,8,6,7]
    static let highDrive = Dictionary(uniqueKeysWithValues: zip(17...22,[95,85,100,90,85,100]))
    static let highMod = Dictionary(uniqueKeysWithValues: zip(47...52,[95,100,90,85,100,90]))
    static let highDelay = Dictionary(uniqueKeysWithValues: zip(53...60,[100,95,85,100,90,95,100,85]))
    static let highReverb = Dictionary(uniqueKeysWithValues: zip(61...64,[85,100,95,90]))
    static let heavyTypes = [1:3,2:13,4:2,5:1,6:5,7:3,8:5,9:10]
    static func merge(_ parts: [[Int:Int]]) -> [Int:Int] {
        parts.reduce(into: [:]) { result, part in result.merge(part) { _, new in new } }
    }
    static func trials(_ original: [UInt8]) -> [Trial] {
        let enabled = Dictionary(uniqueKeysWithValues: heads.map { ($0,Int(original[$0]) & 63) })
        let heavy = merge([heavyTypes,highDrive,highMod,highDelay,highReverb])
        var list = [
            Trial(name:"all-current-effects-enabled",changes:enabled,seconds:3),
            Trial(name:"high-drive-parameters",changes:highDrive,seconds:3),
            Trial(name:"long-modulation-delay",changes:merge([[7:3],highDelay]),seconds:5),
            Trial(name:"high-detune-modulation",changes:merge([[6:5],highMod]),seconds:3),
            Trial(name:"long-shimmer-reverb",changes:merge([[8:5],highReverb]),seconds:15),
            Trial(name:"heavy-full-chain",changes:heavy,seconds:30,order:order),
        ]
        for i in 0..<13 {
            let types = [1:1+i%3,2:1+i,4:1+i%2,5:1,6:1+i,7:1+i%5,8:1+i%6,9:[1,10,19][i%3]]
            list.append(Trial(name:"active-algorithm-switch-\(i+1)",changes:merge([types,highDrive,highMod,highDelay,highReverb]),
                              seconds:4,order:i%2 == 0 ? order : alternateOrder))
        }
        let lastTypes = [1:1,2:13,4:1,6:13,9:1]
        list.append(Trial(name:"dry-bypass-through-suspension",changes:lastTypes.mapValues { $0 | 64 },seconds:1))
        list.append(Trial(name:"change-types-while-bypassed",changes:[1:67,2:66,6:69,7:5,8:5,9:74],seconds:1))
        list.append(Trial(name:"resume-dry-effects",changes:[1:3,2:2,4:1,6:5,9:10],seconds:5))
        for i in 0..<6 {
            list.append(Trial(name:"NAM-toggle-\(i+1)",changes:[:],seconds:0.5,nam:i%2 != 0))
        }
        list.append(Trial(name:"heavy-reordered-chain",changes:heavy,seconds:10,order:alternateOrder))
        list.append(Trial(name:"wet-effects-bypassed",changes:[7:67,8:69],seconds:10))
        list.append(Trial(name:"wet-effects-resumed",changes:[7:3,8:5],seconds:10))
        list.append(Trial(name:"heavy-full-chain-final",changes:heavy,seconds:30,order:order))
        return list
    }
    static func preset(_ stock: [String:Any]) throws -> [UInt8] {
        guard let values = stock["preset"] as? [Int], values.count == 128,
              values.allSatisfy({ (0...127).contains($0) }) else {
            throw CheckError.message("Malformed 128-byte preset")
        }
        return values.map(UInt8.init)
    }
    static func changed(_ old: [UInt8], _ trial: Trial) throws -> [UInt8] {
        var next = old
        for (cc,value) in trial.changes {
            guard let at = NamStockWire.presetIndex(cc), (0...127).contains(value) else {
                throw CheckError.message("Invalid requested effect control")
            }
            next[at] = UInt8(value)
        }
        if let order = trial.order {
            try require(order.count == 9 && Set(order) == Set(1...9),"Invalid chain order")
            next.replaceSubrange(90..<99,with:order.map(UInt8.init))
        }
        next[3] = (next[3] & 63) | (trial.nam ? 0 : 64)
        return next
    }
    static func plan(_ target: [UInt8], before: [UInt8]? = nil) throws -> NamStockWire.Plan {
        // Always include required heads; parameters only when changed. Restoration
        // omits `before`, so every allowed parameter is sent even after partial failure.
        let changedParameters = parameters.filter {
            before == nil || before![NamStockWire.presetIndex($0)!] != target[NamStockWire.presetIndex($0)!]
        }
        let controls = (heads + changedParameters).map { [$0,Int(target[NamStockWire.presetIndex($0)!])] }
        guard let p = NamStockWire.Plan(controls:controls,order:target[90..<99].map(Int.init),
                                       namEnabled:(target[3] & 64) == 0) else {
            throw CheckError.message("Preset cannot form a bounded restorable plan")
        }
        return p
    }
    static func validate(_ original: [UInt8]) throws -> [[String:Any]] {
        _ = try plan(original)
        var current = original
        var rows: [[String:Any]] = []
        for trial in trials(original) {
            let next = try changed(current,trial)
            let p = try plan(next,before:current)
            var predicted = current
            for (at,value) in p.expected { predicted[at] = value }
            predicted[3] = (predicted[3] & 63) | (trial.nam ? 0 : 64)
            try require(predicted == next && p.matches(next),"Plan prediction mismatch")
            // Verify the full restore also works after an arbitrary partial write.
            for prefix in [0,1,4,p.expected.count] {
                var partial = current
                for (at,value) in p.expected.sorted(by:{$0.key < $1.key}).prefix(prefix) { partial[at] = value }
                partial[3] = next[3]
                let restore = try plan(original)
                for (at,value) in restore.expected { partial[at] = value }
                partial[3] = original[3]
                try require(partial == original,"Partial-write restoration failed")
            }
            rows.append(["name":trial.name,"seconds":trial.seconds,
                         "changes":trial.changes.keys.sorted().map { [$0,trial.changes[$0]!] },
                         "order":next[90..<99].map(Int.init),"NAMEnabled":trial.nam])
            current = next
        }
        return rows
    }
    static func main() {
        let args = CommandLine.arguments
        guard args.count == 4, ["--validate","--run"].contains(args[1]) else {
            print("Usage: heavy-chain --validate|--run FIXTURE_REPORT REPORT"); exit(2)
        }
        var report: [String:Any] = [
            "started":ISO8601DateFormatter().string(from:Date()),"status":"PREPARING",
            "audioStreamOpened":false,"macAudioSettingsChanged":false,"teamsSettingsChanged":false,
            "firmwareFlashCommands":false,"resetCommands":false,"persistentSave":false,
            "modelUpload":false,"mode":args[1],"counterCalibrated":false,
            "wholeISRDeadlineProven":false,"audibleOutputTested":false,
            "inputScope":"Existing plug input; no controlled strumming or generated host waveform.",
            "parameterSource":"NAMLNK06 offline heavy-switching settings; compressor/EQ/gate/cab parameters preserved."
        ]
        var events: [[String:Any]] = []
        var completed: [String] = []
        var original: [UInt8]?
        var modified = false
        var failed = false
        var source: Int?
        var previousAccepted: Int64?
        var initialGeneration: UInt32 = 0
        var midi: NamMidi?
        func save() {
            report["events"] = events; report["completedCases"] = completed
            do {
                try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys])
                    .write(to:URL(fileURLWithPath:args[3]),options:.atomic)
            } catch { print("Cannot save evidence: \(error)"); exit(2) }
        }
        func event(_ step: String, _ value: [String:Any]) {
            events.append(["step":step,"time":ISO8601DateFormatter().string(from:Date()),"result":value])
            save(); print(step); fflush(stdout)
        }
        func snapshot(_ name: String, healthy: Bool = true) throws -> [UInt32] {
            let value = try waitFor { midi!.inspect(source!,completion:$0) }
            event(name,value)
            let w = try statusWords(value)
            guard let timing = value["irqTiming"] as? [String:Any],
                  timing["usable"] as? Bool == true, timing["rejected"] as? Int64 == 0,
                  timing["flags"] as? Int64 == 0, let accepted = timing["accepted"] as? Int64 else {
                throw CheckError.message("Missing or rejected IRQ timing")
            }
            if let previous = previousAccepted { try require(accepted > previous,"IRQ counter stalled") }
            previousAccepted = accepted
            if healthy {
                try require(w[4] == 0 && w[10] == 0 && w[9] == 1 && w[8] > 0 && w[8] < 150,
                            "Processing fault/stopped/guard: fault=\(w[4]), running=\(w[9]), peak=\(w[8])")
                try require(w[5] == crc && w[6] == initialGeneration,"Marshall model changed")
                let sample = Float(bitPattern:w[11])
                try require(sample.isFinite && abs(sample) <= 0.875,"Last output sample exceeded ceiling")
            }
            return w
        }
        do {
            let fixture = try JSONSerialization.jsonObject(with:Data(contentsOf:URL(fileURLWithPath:args[2]))) as! [String:Any]
            let fixtureEvents = fixture["events"] as! [[String:Any]]
            let stock = fixtureEvents.first { $0["step"] as? String == "stock-after-reload" }!["result"] as! [String:Any]
            report["plannedCases"] = try validate(preset(stock))
            if args[1] == "--validate" {
                report["status"] = "PASS_HEAVY_CHAIN_PLANS_AND_PARTIAL_RESTORE"; save(); return
            }
            midi = NamMidi()
            let devices = try midi!.devices()
            try require(devices.count == 1,"Require exactly one plug")
            source = devices[0]["source"] as? Int
            try require(source != nil,"Missing MIDI source")
            let initial = try snapshot("initial",healthy:false)
            initialGeneration = initial[6]
            try require(initial[5] == crc && initialGeneration > 0,"Expected already-loaded Marshall Lite")
            _ = try snapshot("initial-health")
            let saved = try waitFor { midi!.stock(source!,completion:$0) }
            event("original-stock",saved)
            let backup = try preset(saved)
            report["plannedCases"] = try validate(backup)
            original = backup
            var current = backup
            for trial in trials(backup) {
                report["activeCase"] = trial.name; save()
                let next = try changed(current,trial)
                let p = try plan(next,before:current)
                modified = true
                let result = try waitFor { midi!.stock(source!,plan:p,completion:$0) }
                event(trial.name+"-controls",result)
                try require(result["identity"] as? String == "NAMLNK06" &&
                            result["controlsVerified"] as? Bool == true &&
                            result["stockChain"] as? Bool == true,"Controls not confirmed")
                try require(try preset(result) == next,"Unexpected preset bytes changed")
                current = next
                var last = try snapshot(trial.name+"-start")
                let deadline = Date(timeIntervalSinceNow:trial.seconds)
                var poll = 0
                while Date() < deadline {
                    pause(min(1,max(0,deadline.timeIntervalSinceNow))); poll += 1
                    let w = try snapshot(trial.name+"-poll-\(poll)")
                    try require(w[3] &- last[3] > 0 && w[7] &- last[7] > 0,"Processing stopped advancing")
                    last = w
                }
                completed.append(trial.name); save()
            }
            report["status"] = "PASS_NAMLNK06_PHYSICAL_HEAVY_SETTINGS_SWITCHING"
        } catch {
            failed = true
            report["status"] = "FAILED"
            report["error"] = String(describing:error)
            event("failure",["error":String(describing:error)])
        }
        if modified, let original = original, let id = source {
            do {
                let restore = try plan(original)
                let result = try waitFor { midi!.stock(id,plan:restore,completion:$0) }
                event("restore-original-controls",result)
                try require(result["controlsVerified"] as? Bool == true,"Restore not confirmed")
                try require(try preset(result) == original,"Original 128-byte preset was not restored")
                report["all128OriginalPresetBytesRestored"] = true
                _ = try snapshot("final-status",healthy:!failed)
                if !failed {
                    pause(3)
                    _ = try snapshot("restored-settings-after-3-seconds")
                }
            } catch {
                report["restoreError"] = String(describing:error)
                failed = true; report["status"] = "FAILED"
            }
        }
        midi?.disconnect()
        report["finished"] = ISO8601DateFormatter().string(from:Date())
        save(); print(report["status"]!)
        if failed { exit(1) }
    }
}
