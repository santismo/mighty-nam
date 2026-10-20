import Foundation
import CoreMIDI

// Actual CoreMIDI allocation/layout regression: include preset replies larger
// than MIDIPacket.data and subsequent packets at their variable-sized offsets.
@main struct MidiPacketTests {
 static func main() {
  var checked=0
  for sizes in [[15],[65],[256],[257],[326],[330],[15,326,65],[326,330,15],[330,1,326,65]] {
   let storage=UnsafeMutableRawPointer.allocate(byteCount:4096,alignment:MemoryLayout<MIDIPacketList>.alignment)
   storage.initializeMemory(as:UInt8.self,repeating:0xa5,count:4096)
   let list=storage.bindMemory(to:MIDIPacketList.self,capacity:1)
   var last=MIDIPacketListInit(list)
   let expected=sizes.enumerated().map { index,count in (0..<count).map { UInt8(($0*31+index*17)%256) } }
   for (i,bytes) in expected.enumerated() {
    last=bytes.withUnsafeBufferPointer { MIDIPacketListAdd(list,4096,last,MIDITimeStamp(i+1),$0.count,$0.baseAddress!) }
    precondition(UInt(bitPattern:last) != 0)
   }
   let copied=NamMidi.packetChunks(UnsafePointer(list))
   precondition(copied==expected,"Variable packet data differs for \(sizes)")
   storage.deallocate()
   precondition(copied==expected,"Copied packets must outlive the callback")
   checked+=1
  }
  print("PASS: \(checked) CoreMIDI variable-packet cases")
 }
}
