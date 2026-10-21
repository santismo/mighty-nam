import Foundation
import CoreMIDI

// Shared with the Mac command-line check. This class never opens an audio
// stream. Each write requires a fresh, explicitly supported firmware identity.
public final class NamMidi {
    private var client: MIDIClientRef = 0
    private var input: MIDIPortRef = 0
    private var output: MIDIPortRef = 0
    private var source: MIDIEndpointRef = 0
    private var destination: MIDIEndpointRef = 0
    private var buffer: [UInt8] = []
    private var version = ""
    private var values: [UInt32] = []
    private var page = -1
    private var pendingFx: [UInt8]?
    private var pendingTuner: [UInt8]?
    private var pendingPreset: [UInt8]?
    private var pendingModel: [UInt8]?
    private var pendingStock: NamStockWire.Plan?
    private var pendingListen: Bool?
    private var pendingBuffer: Int?
    private var listenSnapshot: [String:Any] = [:]
    private var stockRead = false
    private var stockBefore: [UInt8] = []
    private var stockReadAttempts = 0
    private var snapshotAttempts = 0
    private var pageCount = 62
    private var sent = 0
    private var generation = 0
    private var callback: ((Result<[String:Any], Error>) -> Void)?
    private var timer: DispatchWorkItem?
    enum Failure: Error { case message(String) }
    public init() {}
    private func name(_ endpoint: MIDIEndpointRef) -> String {
        var value: Unmanaged<CFString>?
        guard MIDIObjectGetStringProperty(endpoint, kMIDIPropertyDisplayName, &value) == noErr,
              let value = value else { return "" }
        return value.takeRetainedValue() as String
    }
    private func setup() throws {
        if client != 0 { return }
        guard MIDIClientCreateWithBlock("NAM Plug control" as CFString, &client, nil) == noErr else { throw Failure.message("MIDI is unavailable") }
        guard MIDIOutputPortCreate(client, "Status requests" as CFString, &output) == noErr else { throw Failure.message("MIDI output unavailable") }
        let status = MIDIInputPortCreateWithBlock(client, "Status replies" as CFString, &input) { [weak self] list, _ in
            let chunks = Self.packetChunks(list)
            DispatchQueue.main.async { [weak self] in
                for chunk in chunks { self?.receive(chunk) }
            }
        }
        guard status == noErr else { throw Failure.message("MIDI input unavailable") }
    }
    // CoreMIDI packets have variable-length storage beyond the declared
    // 256-byte tuple. Taking a pointer to list.pointee.packet copies that
    // fixed-size Swift value and loses the tail of larger replies. Walk the
    // original callback allocation, then own the bytes before dispatching.
    static func packetChunks(_ list: UnsafePointer<MIDIPacketList>) -> [[UInt8]] {
        var chunks: [[UInt8]] = []
        var packet = UnsafeRawPointer(list)
            .advanced(by: MemoryLayout<MIDIPacketList>.offset(of: \.packet)!)
            .assumingMemoryBound(to: MIDIPacket.self)
        for _ in 0..<list.pointee.numPackets {
            let n = Int(packet.pointee.length)
            let data = UnsafeRawPointer(packet)
                .advanced(by: MemoryLayout<MIDIPacket>.offset(of: \.data)!)
                .assumingMemoryBound(to: UInt8.self)
            chunks.append(Array(UnsafeBufferPointer(start: data, count: n)))
            packet = UnsafePointer(MIDIPacketNext(packet))
        }
        return chunks
    }
    public func devices() throws -> [[String:Any]] {
        try setup()
        var result: [[String:Any]] = []
        for i in 0..<MIDIGetNumberOfSources() {
            let endpoint = MIDIGetSource(i), label = name(endpoint)
            let normalized = label.uppercased().filter { $0.isLetter || $0.isNumber }
            guard normalized.contains("MIGHTYPLUGPRO") else { continue }
            var entity: MIDIEntityRef = 0
            guard MIDIEndpointGetEntity(endpoint, &entity) == noErr, entity != 0 else { continue }
            let matches = (0..<MIDIGetNumberOfDestinations()).map { MIDIGetDestination($0) }.filter {
                var other: MIDIEntityRef = 0
                return MIDIEndpointGetEntity($0, &other) == noErr && other == entity
            }
            if matches.count == 1 { result.append(["source":Int(endpoint),"destination":Int(matches[0]),"name":label]) }
        }
        return result
    }
    public func exchange(_ id: Int, request: [UInt8], completion: @escaping (Result<[String:Any],Error>)->Void) {
        guard NamLinkWire.request(request) != nil else { completion(.failure(Failure.message("Invalid model frame"))); return }
        start(id, model: request, completion: completion)
    }
    public func preset(_ id: Int, request: [UInt8], completion: @escaping (Result<[String:Any],Error>)->Void) {
        guard NamPresetWire.request(request) != nil else { completion(.failure(Failure.message("Invalid preset request"))); return }
        start(id, model:nil, preset:request, completion:completion)
    }
    public func fx(_ id: Int, request: [UInt8], completion: @escaping (Result<[String:Any],Error>) -> Void) {
        guard NamFxWire.validRequest(request) else { completion(.failure(Failure.message("Invalid FX request"))); return }
        start(id,model:nil,fx:request,completion:completion)
    }
    public func tuner(_ id: Int, operation: Int, page: Int, nonce: Int, completion: @escaping (Result<[String:Any],Error>)->Void) {
        guard let request = NamTunerWire.request(operation:operation,page:page,nonce:nonce) else {
            completion(.failure(Failure.message("Invalid tuner request"))); return
        }
        start(id, model:nil, tuner:request, completion:completion)
    }
    public func inspect(_ id: Int, completion: @escaping (Result<[String:Any],Error>)->Void) {
        start(id, model: nil, completion: completion)
    }
    public func stock(_ id: Int, plan: NamStockWire.Plan? = nil, completion: @escaping (Result<[String:Any],Error>)->Void) {
        start(id, model:nil, stock:plan, readStock:true, completion:completion)
    }
    public func listen(_ id: Int, enabled: Bool, completion: @escaping (Result<[String:Any],Error>)->Void) {
        start(id, model:nil, listen:enabled, completion:completion)
    }
    public func outputBuffer(_ id: Int, samples: Int, completion: @escaping (Result<[String:Any],Error>)->Void) {
        guard NamOutputBuffer.choices.contains(samples) else { completion(.failure(Failure.message("Unsupported output buffer"))); return }
        start(id,model:nil,outputBuffer:samples,completion:completion)
    }
    private func start(_ id: Int, model: [UInt8]?, fx: [UInt8]? = nil, tuner: [UInt8]? = nil, preset: [UInt8]? = nil, stock: NamStockWire.Plan? = nil, readStock: Bool = false, listen: Bool? = nil, outputBuffer: Int? = nil, completion: @escaping (Result<[String:Any],Error>)->Void) {
        guard callback == nil else { completion(.failure(Failure.message("A plug operation is already in progress"))); return }
        do {
            guard let entry = try devices().first(where: { $0["source"] as? Int == id }),
                  let dest = entry["destination"] as? Int else { throw Failure.message("Plug disconnected. Refresh devices.") }
            detach()
            source = MIDIEndpointRef(id); destination = MIDIEndpointRef(dest)
            guard MIDIPortConnectSource(input, source, nil) == noErr else { throw Failure.message("Could not connect MIDI input") }
            callback = completion; pendingFx = fx; pendingTuner = tuner; pendingPreset = preset; pendingModel = model; pendingStock = stock; stockRead = readStock
            pendingListen = listen; listenSnapshot = [:]
            pendingBuffer = outputBuffer
            stockBefore = []; stockReadAttempts = 0; version = ""; values = []; page = -1; sent = 0
            snapshotAttempts = 0
            request([0xf0,0x43,0x58,0,0xf7])
        } catch { detach(); completion(.failure(error)) }
    }
    public func disconnect() {
        if callback != nil { finish(.failure(Failure.message("Disconnected"))) }
        else { detach() }
    }
    private func detach() {
        timer?.cancel(); timer = nil; generation += 1
        if source != 0 && input != 0 { MIDIPortDisconnectSource(input, source) }
        source = 0; destination = 0; buffer = []
    }
    private func finish(_ result: Result<[String:Any],Error>) {
        let done = callback; callback = nil; pendingFx = nil; pendingTuner = nil; pendingPreset = nil; pendingModel = nil; pendingStock = nil; pendingListen = nil; pendingBuffer = nil; stockRead = false; detach(); done?(result)
    }
    private func request(_ bytes: [UInt8]) {
        timer?.cancel(); generation += 1; let ticket = generation
        buffer = []
        // MIDIPacketList's inline storage is too small for a full model frame.
        guard bytes.count <= 330 else { finish(.failure(Failure.message("Model frame too large"))); return }
        let storage = UnsafeMutableRawPointer.allocate(byteCount: 4096, alignment: MemoryLayout<MIDIPacketList>.alignment)
        defer { storage.deallocate() }
        let list = storage.bindMemory(to: MIDIPacketList.self, capacity: 1)
        let first = MIDIPacketListInit(list)
        let status: OSStatus = bytes.withUnsafeBufferPointer { data in
            guard let base = data.baseAddress else { return -1 }
            let added = MIDIPacketListAdd(list,4096,first,0,data.count,base)
            guard UInt(bitPattern: added) != 0 else { return -1 }
            return MIDISend(output,destination,list)
        }
        sent += 1
        guard status == noErr else { finish(.failure(Failure.message("Plug disconnected during the read"))); return }
        let timeout = DispatchWorkItem { [weak self] in
            guard let self = self, self.generation == ticket, self.callback != nil else { return }
            self.finish(.failure(Failure.message("The plug did not reply. Check its connection and normal operating mode.")))
        }
        timer = timeout; DispatchQueue.main.asyncAfter(deadline: .now()+(pendingPreset != nil ? 10 : (pendingModel == nil ? 3 : 0.75)), execute: timeout)
    }
    private func receive(_ bytes: [UInt8]) {
        for byte in bytes {
            guard callback != nil else { return }
            if byte >= 0xf8 { continue }
            if byte == 0xf0 { buffer = [byte]; continue }
            if buffer.isEmpty { continue }
            if byte == 0xf7 { buffer.append(byte); let message = buffer; buffer=[]; accept(message); continue }
            if byte >= 0x80 || buffer.count >= 330 { buffer=[]; continue }
            buffer.append(byte)
        }
    }
    private func accept(_ message: [UInt8]) {
        if page == -1 {
            guard message.count == 45, Array(message[0..<4]) == [0xf0,0x43,0x58,0x10],
                  Array(message[36..<44]) == Array("PLUGPRO\0".utf8) else { return }
            version = String(bytes: message[4..<12], encoding: .ascii) ?? ""
            if let fx = pendingFx {
                guard version == "NAMLNK13" else { finish(.failure(Failure.message("Exact NAMLNK13 required"))); return }
                page = -11; request(fx); return
            }
            if let tuner = pendingTuner {
                guard ["NAMLNK12", "NAMLNK13"].contains(version) else {
                    finish(.failure(Failure.message("The tuner requires NAMLNK12. No tuner command was sent."))); return
                }
                page = -10; request(tuner); return
            }
            if pendingBuffer != nil && !["NAMLNK09","NAMLNK10","NAMLNK11","NAMLNK12","NAMLNK13"].contains(version) {
                finish(.failure(Failure.message("Adjustable output buffering requires NAMLNK09. No setting was sent."))); return
            }
            if pendingListen != nil && !NamListening.supports(version) {
                finish(.failure(Failure.message("Listening requires NAMLNK07 or NAMLNK08. No listening command sent."))); return
            }
            if let raw = pendingPreset {
                guard ["NAMLNK10","NAMLNK11","NAMLNK12","NAMLNK13"].contains(version), let wire = NamPresetWire.request(raw) else {
                    finish(.failure(Failure.message("Onboard presets require NAMLNK10. Nothing was saved to the plug."))); return
                }
                page = -9; request(wire); return
            }
            if stockRead {
                guard NamLinkWire.supportsModels(version), pendingStock?.allowed(on:version) != false else {
                    finish(.failure(Failure.message("These controls require the matching silent link firmware. No controls sent."))); return
                }
                page = -3; request(NamStockWire.read); return
            }
            if let raw = pendingModel {
                guard NamLinkWire.supportsModels(version), let wire = NamLinkWire.request(raw) else {
                    finish(.failure(Failure.message("Model transfer requires supported silent link firmware. No model commands sent."))); return
                }
                page = -2; request(wire); return
            }
            guard version == "NAMA2I01" || NamLinkWire.supportsModels(version) else {
                finish(.success(["identity":version,"compatible":false,"modelTransfer":false,"requests":sent,"words":[],"audioStreamOpened":false])); return
            }
            pageCount = ["NAMLNK10","NAMLNK11","NAMLNK12","NAMLNK13"].contains(version) ? 26 : (version == "NAMLNK09" ? 25 : (NamListening.supports(version) ? 24 : (version == "NAMLNK06" ? 23 : (NamLinkWire.supportsModels(version) ? 12 : 62))))
            page = 0
        } else if page == -11 {
            guard let pending=pendingFx, let result=NamFxWire.reply(message,to:pending) else {return}
            finish(.success(result));return
        } else if page == -10 {
            guard let pending = pendingTuner, let raw = NamTunerWire.reply(message,to:pending) else { return }
            finish(.success(["frame":raw])); return
        } else if page == -9 {
            guard let pending=pendingPreset,let raw=NamPresetWire.reply(message,to:pending) else { return }
            finish(.success(["frame":raw]));return
        } else if page == -7 || page == -8 {
            let expectedPage: UInt8 = page == -7 ? 24 : 23
            guard message.count == 15, Array(message[0..<9]) == [0xf0,0x43,0x58,0x70,4,2,1,expectedPage,0], message[13] < 16 else { return }
            var value: UInt32 = 0
            for i in 0..<5 { value |= UInt32(message[9+i]) << (7*i) }
            if page == -7 {
                guard let decoded = NamOutputBuffer.decode(value), decoded["samples"] as? Int == pendingBuffer else {
                    finish(.failure(Failure.message("The output buffer setting was not confirmed."))); return
                }
                listenSnapshot["audioBuffer"] = decoded
                page = -8; request([0xf0,0x43,0x58,0x70,4,2,0x4e,0x50,23,0xf7]); return
            }
            guard let state = NamListening.decode(value), state["enabled"] as? Bool == false else {
                finish(.failure(Failure.message("The plug did not confirm mute after changing its buffer."))); return
            }
            listenSnapshot["listening"] = state
            finish(.success(listenSnapshot)); return
        } else if page == -6 {
            guard message.count == 15, Array(message[0..<9]) == [0xf0,0x43,0x58,0x70,4,2,1,23,0],
                  message[13] < 16 else { return }
            var value: UInt32 = 0
            for i in 0..<5 { value |= UInt32(message[9+i]) << (7*i) }
            guard let listening = NamListening.decode(value),
                  listening["enabled"] as? Bool == pendingListen else {
                finish(.failure(Failure.message("The plug did not confirm listening. Check its status."))); return
            }
            listenSnapshot["listening"] = listening
            finish(.success(listenSnapshot)); return
        } else if page == -3 {
            guard let preset = NamStockWire.preset(message) else { return }
            guard let plan = pendingStock else {
                finish(.success(["identity":version,"preset":preset.map(Int.init),"audioStreamOpened":false])); return
            }
            guard let commands = plan.messages(before:preset) else {
                finish(.failure(Failure.message("Invalid control snapshot"))); return
            }
            stockBefore = preset
            page = -4
            request(commands)
            let ticket = generation
            // MIDI CC ingress queues updates. Allow the stock foreground service
            // to apply them before sending order and reading back the whole state.
            DispatchQueue.main.asyncAfter(deadline:.now()+0.08) { [weak self] in
                guard let self = self, self.generation == ticket, self.callback != nil else { return }
                if plan.cabinetBypassed != nil {
                    self.page = -5
                    self.request(NamStockWire.read)
                } else {
                    self.request(plan.orderMessage)
                }
            }
            return
        } else if page == -4 {
            guard let plan = pendingStock, message == plan.orderReply else { return }
            page = -5; request(NamStockWire.read); return
        } else if page == -5 {
            guard let plan = pendingStock, let preset = NamStockWire.preset(message) else { return }
            if !plan.matches(preset, before:stockBefore) ||
                (plan.namEnabled != nil && (preset[3] & 63) != (stockBefore[3] & 63)) {
                stockReadAttempts += 1
                guard stockReadAttempts < 4 else {
                    finish(.failure(Failure.message("Some effect controls were not confirmed. Refresh the plug before trying again."))); return
                }
                let ticket = generation
                DispatchQueue.main.asyncAfter(deadline:.now()+0.04) { [weak self] in
                    guard let self = self, self.generation == ticket, self.callback != nil else { return }
                    self.request(NamStockWire.read)
                }
                return
            }
            finish(.success(["identity":version,"preset":preset.map(Int.init),
                             "before":stockBefore.map(Int.init),"controlsVerified":true,
                             "stockChain":NamLinkWire.supportsStockChain(version),"persistentSave":false,"audioStreamOpened":false])); return
        } else if page == -2 {
            guard let pending = pendingModel, let raw = NamLinkWire.reply(message,to:pending) else { return }
            finish(.success(["frame":raw])); return
        } else {
            guard message.count == 15, Array(message[0..<6]) == [0xf0,0x43,0x58,0x70,4,2], message[6] == 1,
                  message[7] == page, message[13] < 16 else { return }
            if message[8] != 0 {
                if ["NAMLNK06","NAMLNK07","NAMLNK08","NAMLNK09","NAMLNK10","NAMLNK11","NAMLNK12","NAMLNK13"].contains(version) && page == 12 && message[8] == 2 && snapshotAttempts < 2 {
                    snapshotAttempts += 1
                    request([0xf0,0x43,0x58,0x70,4,2,0x4e,0x50,12,0xf7]); return
                }
                finish(.failure(Failure.message("The plug could not provide a stable diagnostic snapshot. Read its status again."))); return
            }
            var value: UInt32 = 0
            for i in 0..<5 { value |= UInt32(message[9+i]) << (7*i) }
            values.append(value); page += 1
        }
        if page == pageCount {
            let linked = NamLinkWire.supportsModels(version)
            guard values[0] == (linked ? 0x4e4c4b31 : 0x4d504232) && values[1] == (linked ? 1 : 3) && values[2] == 1 else { finish(.failure(Failure.message("Unexpected diagnostic schema"))); return }
            var result: [String:Any] = ["identity":version,"compatible":true,"modelTransfer":linked,
                             "stockChain":NamLinkWire.supportsStockChain(version),"requests":sent,
                             "words":(linked ? Array(values.prefix(12)) : values).map{Int64($0)},"audioStreamOpened":false]
            if ["NAMLNK06","NAMLNK07","NAMLNK08","NAMLNK09","NAMLNK10","NAMLNK11","NAMLNK12","NAMLNK13"].contains(version) {
                guard let timing = NamIrqTiming.decode(Array(values[12..<23])) else {
                    finish(.failure(Failure.message("Unexpected timing snapshot. No hardware timing conclusion is available."))); return
                }
                result["irqTiming"] = timing
            }
            if NamListening.supports(version) {
                guard let listening = NamListening.decode(values[23]) else {
                    finish(.failure(Failure.message("Unexpected listening state."))); return
                }
                result["listeningSupported"] = true; result["listening"] = listening
            }
            if ["NAMLNK09","NAMLNK10","NAMLNK11","NAMLNK12","NAMLNK13"].contains(version) {
                guard let decoded = NamOutputBuffer.decode(values[24]) else {
                    finish(.failure(Failure.message("Unexpected output buffer status."))); return
                }
                result["audioBuffer"] = decoded
            }
            if ["NAMLNK10","NAMLNK11","NAMLNK12","NAMLNK13"].contains(version) {
                let bank=values[25],active=bank & 255,mask=(bank >> 8) & 255
                guard bank >> 24 == 1,bank & 0x00ff0000 == 0,(active < 7 || active == 255),mask < 128 else {
                    finish(.failure(Failure.message("Unexpected preset bank status"))); return
                }
                result["presetBank"]=["active":Int(active),"mask":Int(mask),"slots":7]
            }
            if let samples = pendingBuffer {
                guard let command = NamOutputBuffer.command(identity:version,samples:samples) else {
                    finish(.failure(Failure.message("Unsupported output buffer setting."))); return
                }
                listenSnapshot=result; page = -7; request(command); return
            }
            if let enabled = pendingListen {
                guard let command = NamListening.arm(identity:version,enabled:enabled),
                      !enabled || (values[4] == 0 && values[5] != 0 && values[9] == 1) else {
                    finish(.failure(Failure.message("Load a model and clear any processing fault before listening."))); return
                }
                listenSnapshot = result; page = -6; request(command); return
            }
            finish(.success(result))
        } else { request([0xf0,0x43,0x58,0x70,4,2,0x4e,0x50,UInt8(page),0xf7]) }
    }
    deinit {
        timer?.cancel()
        if source != 0 && input != 0 { MIDIPortDisconnectSource(input,source) }
        if input != 0 { MIDIPortDispose(input) }; if output != 0 { MIDIPortDispose(output) }; if client != 0 { MIDIClientDispose(client) }
    }
}
