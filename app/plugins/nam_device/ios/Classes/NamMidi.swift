import Foundation
import CoreMIDI

// Shared with the Mac command-line check. This class never opens an audio
// stream and has no arbitrary packet sender, model writer, reset or updater.
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
        guard MIDIClientCreateWithBlock("mighty-nam control" as CFString, &client, nil) == noErr else { throw Failure.message("MIDI is unavailable") }
        guard MIDIOutputPortCreate(client, "Status requests" as CFString, &output) == noErr else { throw Failure.message("MIDI output unavailable") }
        let status = MIDIInputPortCreateWithBlock(client, "Status replies" as CFString, &input) { [weak self] list, _ in
            var chunks: [[UInt8]] = []
            withUnsafePointer(to: list.pointee.packet) { first in
                var packet = first
                for _ in 0..<list.pointee.numPackets {
                    let n = Int(packet.pointee.length)
                    let data = UnsafeRawPointer(packet).advanced(by: MemoryLayout<MIDIPacket>.offset(of: \.data)!).assumingMemoryBound(to: UInt8.self)
                    chunks.append(Array(UnsafeBufferPointer(start: data, count: n)))
                    packet = UnsafePointer(MIDIPacketNext(packet))
                }
            }
            DispatchQueue.main.async { [weak self] in
                for chunk in chunks { self?.receive(chunk) }
            }
        }
        guard status == noErr else { throw Failure.message("MIDI input unavailable") }
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
    public func inspect(_ id: Int, completion: @escaping (Result<[String:Any],Error>)->Void) {
        guard callback == nil else { completion(.failure(Failure.message("A read is already in progress"))); return }
        do {
            guard let entry = try devices().first(where: { $0["source"] as? Int == id }),
                  let dest = entry["destination"] as? Int else { throw Failure.message("Plug disconnected. Refresh devices.") }
            detach()
            source = MIDIEndpointRef(id); destination = MIDIEndpointRef(dest)
            guard MIDIPortConnectSource(input, source, nil) == noErr else { throw Failure.message("Could not connect MIDI input") }
            callback = completion; version = ""; values = []; page = -1; sent = 0
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
        let done = callback; callback = nil; detach(); done?(result)
    }
    private func request(_ bytes: [UInt8]) {
        timer?.cancel(); generation += 1; let ticket = generation
        buffer = []
        var list = MIDIPacketList()
        let status: OSStatus = withUnsafeMutablePointer(to: &list) { pointer in
            let first = MIDIPacketListInit(pointer)
            return bytes.withUnsafeBufferPointer { data in
                guard data.count == 5 || data.count == 10 else { return -1 }
                _ = MIDIPacketListAdd(pointer, MemoryLayout<MIDIPacketList>.size, first, 0, data.count, data.baseAddress!)
                return MIDISend(output, destination, pointer)
            }
        }
        sent += 1
        guard status == noErr else { finish(.failure(Failure.message("Plug disconnected during the read"))); return }
        let timeout = DispatchWorkItem { [weak self] in
            guard let self = self, self.generation == ticket, self.callback != nil else { return }
            self.finish(.failure(Failure.message("The plug did not reply. Check its connection and normal operating mode.")))
        }
        timer = timeout; DispatchQueue.main.asyncAfter(deadline: .now()+3, execute: timeout)
    }
    private func receive(_ bytes: [UInt8]) {
        for byte in bytes {
            guard callback != nil else { return }
            if byte >= 0xf8 { continue }
            if byte == 0xf0 { buffer = [byte]; continue }
            if buffer.isEmpty { continue }
            if byte == 0xf7 { buffer.append(byte); let message = buffer; buffer=[]; accept(message); continue }
            if byte >= 0x80 || buffer.count >= 64 { buffer=[]; continue }
            buffer.append(byte)
        }
    }
    private func accept(_ message: [UInt8]) {
        if page == -1 {
            guard message.count == 45, Array(message[0..<4]) == [0xf0,0x43,0x58,0x10],
                  Array(message[36..<44]) == Array("PLUGPRO\0".utf8) else { return }
            version = String(bytes: message[4..<12], encoding: .ascii) ?? ""
            guard version == "NAMA2I01" else {
                finish(.success(["identity":version,"compatible":false,"requests":sent,"words":[],"audioStreamOpened":false])); return
            }
            page = 0
        } else {
            guard message.count == 15, Array(message[0..<6]) == [0xf0,0x43,0x58,0x70,4,2], message[6] == 1,
                  message[7] == page, message[8] == 0, message[13] < 16 else { return }
            var value: UInt32 = 0
            for i in 0..<5 { value |= UInt32(message[9+i]) << (7*i) }
            values.append(value); page += 1
        }
        if page == 62 {
            guard values[0] == 0x4d504232 && values[1] == 3 && values[2] == 1 else { finish(.failure(Failure.message("Unexpected diagnostic schema"))); return }
            finish(.success(["identity":version,"compatible":true,"requests":sent,"words":values.map{Int64($0)},"audioStreamOpened":false]))
        } else { request([0xf0,0x43,0x58,0x70,4,2,0x4e,0x50,UInt8(page),0xf7]) }
    }
    deinit {
        timer?.cancel()
        if source != 0 && input != 0 { MIDIPortDisconnectSource(input,source) }
        if input != 0 { MIDIPortDispose(input) }; if output != 0 { MIDIPortDispose(output) }; if client != 0 { MIDIClientDispose(client) }
    }
}
