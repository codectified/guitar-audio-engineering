// Joins the Spark GO's separate USB input and output into one Core Audio device ("Spark GO (rig)"), so the rig
// can open it like a Scarlett: one device, one clock, small buffers. Run: swift spark_aggregate.swift [--remove]
import CoreAudio
import Foundation

let aggregateUID = "com.guitarrig.sparkgo.aggregate"

func prop<T>(_ id: AudioObjectID, _ selector: AudioObjectPropertySelector,
             _ scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal, _ empty: T) -> T {
    var addr = AudioObjectPropertyAddress(mSelector: selector, mScope: scope, mElement: kAudioObjectPropertyElementMain)
    var value = empty
    var size = UInt32(MemoryLayout<T>.size)
    AudioObjectGetPropertyData(id, &addr, 0, nil, &size, &value)
    return value
}

func devices() -> [AudioObjectID] {
    var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDevices,
                                          mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size)
    var ids = [AudioObjectID](repeating: 0, count: Int(size) / MemoryLayout<AudioObjectID>.size)
    AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &ids)
    return ids
}

func name(_ id: AudioObjectID) -> String {
    prop(id, kAudioObjectPropertyName, kAudioObjectPropertyScopeGlobal, "" as CFString) as String
}

func uid(_ id: AudioObjectID) -> String {
    prop(id, kAudioDevicePropertyDeviceUID, kAudioObjectPropertyScopeGlobal, "" as CFString) as String
}

func channels(_ id: AudioObjectID, _ scope: AudioObjectPropertyScope) -> Int {
    var addr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyStreamConfiguration,
                                          mScope: scope, mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(id, &addr, 0, nil, &size) == noErr, size > 0 else { return 0 }
    let list = UnsafeMutableRawPointer.allocate(byteCount: Int(size), alignment: 16)
    defer { list.deallocate() }
    AudioObjectGetPropertyData(id, &addr, 0, nil, &size, list)
    let buffers = UnsafeMutableAudioBufferListPointer(list.assumingMemoryBound(to: AudioBufferList.self))
    return buffers.reduce(0) { $0 + Int($1.mNumberChannels) }
}

// Remove an existing one first, so re-running rebuilds it with the Spark's current device IDs
for id in devices() where uid(id) == aggregateUID {
    let status = AudioHardwareDestroyAggregateDevice(id)
    print(status == noErr ? "Removed the old Spark GO (rig) device." : "Couldn't remove the old device (\(status)).")
}
if CommandLine.arguments.contains("--remove") { exit(0) }

let spark = devices().filter { name($0).contains("Spark") && uid($0) != aggregateUID }
guard let input = spark.first(where: { channels($0, kAudioObjectPropertyScopeInput) > 0 }),
      let output = spark.first(where: { channels($0, kAudioObjectPropertyScopeOutput) > 0 }) else {
    print("Spark GO not found: switch it on and plug in the USB cable.")
    exit(1)
}

let description: [String: Any] = [
    kAudioAggregateDeviceNameKey: "Spark GO (rig)",
    kAudioAggregateDeviceUIDKey: aggregateUID,
    kAudioAggregateDeviceIsPrivateKey: 0,  // public, so PortAudio (the rig) can see it
    kAudioAggregateDeviceMainSubDeviceKey: uid(output),  // clock from the output side
    kAudioAggregateDeviceSubDeviceListKey: [
        [kAudioSubDeviceUIDKey: uid(output)],
        [kAudioSubDeviceUIDKey: uid(input), kAudioSubDeviceDriftCompensationKey: 1],
    ],
]
var aggregate: AudioObjectID = 0
let status = AudioHardwareCreateAggregateDevice(description as CFDictionary, &aggregate)
print(status == noErr ? "Created Spark GO (rig): \(uid(input)) in + \(uid(output)) out."
                      : "Couldn't create the aggregate device (\(status)).")
exit(status == noErr ? 0 : 1)
