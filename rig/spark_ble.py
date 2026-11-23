"""Talk to a Positive Grid Spark GO over Bluetooth LE, the way its phone app does, so the rig can turn the
amp's own guitar sound and effects down and the Spark just plays the rig.

Protocol from lucanenni/spark-go-utils (PROTOCOL.md, MIT), reverse-engineered and tested on real Spark GOs.
Keep writes few and slow: streaming ~60 commands/s has locked a Spark GO up.

    python spark_ble.py status            # find it, show the active patch and its pedals
    python spark_ble.py guitar 0          # Spark's own guitar volume, 0.0-1.0 (doesn't touch USB/music)
    python spark_ble.py bypass            # switch off every pedal in the active patch (live only, not saved)
    python spark_ble.py clean             # rig mode: pedals off, amp low gain + flat EQ (live only)
    python spark_ble.py param amp 4 0     # one knob on one pedal (live only)
    python spark_ble.py restore           # reload the active patch: undoes bypass and knob changes
"""
import asyncio
import struct
import sys

from bleak import BleakClient, BleakScanner

SERVICE = "0000ffc0-0000-1000-8000-00805f9b34fb"
WRITE = "0000ffc1-0000-1000-8000-00805f9b34fb"
NOTIFY = "0000ffc2-0000-1000-8000-00805f9b34fb"
SLOTS = ["gate", "comp/wah", "drive", "amp", "mod/eq", "delay", "reverb"]
GAP_S = 0.15  # between commands: well under the rate that has locked a Spark GO up


def pack7(data8):
    """8-bit -> 7-bit, SysEx style: per 7 bytes, one byte of top bits, then the bytes masked to 7 bits."""
    out = bytearray()
    for i in range(0, len(data8), 7):
        group = data8[i:i + 7]
        out.append(sum(1 << j for j, b in enumerate(group) if b & 0x80))
        out += bytes(b & 0x7F for b in group)
    return bytes(out)


def unpack7(data7):
    out, i = bytearray(), 0
    while i < len(data7):
        top, group = data7[i], data7[i + 1:i + 8]
        out += bytes(b | (0x80 if top & (1 << j) else 0) for j, b in enumerate(group))
        i += 1 + len(group)
    return bytes(out)


def message(seq, cmd, sub, data8=b"", raw=None):
    """[16-byte header with total length][F0 01 seq checksum cmd sub packed-data F7]."""
    body = raw if raw is not None else pack7(data8)
    checksum = 0
    for b in body:
        checksum ^= b
    inner = bytes([0xF0, 0x01, seq & 0xFF, checksum, cmd, sub]) + body + b"\xF7"
    return bytes([0x01, 0xFE, 0x00, 0x00, 0x53, 0xFE, 16 + len(inner)]) + bytes(9) + inner


def read_string(data, pos):
    b = data[pos]
    if b == 0xD9:
        return data[pos + 2:pos + 2 + data[pos + 1]].decode("ascii", "replace"), pos + 2 + data[pos + 1]
    if 0xA0 <= b <= 0xBF:
        return data[pos + 1:pos + 1 + b - 0xA0].decode("ascii", "replace"), pos + 1 + b - 0xA0
    n = data[pos + 1] - 0xA0  # effect-state echo: raw length byte, then a fixstr byte
    return data[pos + 2:pos + 2 + n].decode("ascii", "replace"), pos + 2 + n


def parse_preset(data):
    pos = 2
    _uuid, pos = read_string(data, pos)
    name, pos = read_string(data, pos)
    for _ in range(3):  # version, description, icon
        _, pos = read_string(data, pos)
    pos += 5  # BPM float
    count, pos = data[pos] - 0x90, pos + 1  # always 7 slots
    pedals = []
    for _ in range(count):
        pedal, pos = read_string(data, pos)
        on = data[pos] == 0xC3
        n_params = data[pos + 1] - 0x90
        pos += 2
        params = []
        for _ in range(n_params):  # each: id, 0x91, 0xCA + 4-byte big-endian float
            params.append(struct.unpack(">f", data[pos + 3:pos + 7])[0])
            pos += 7
        pedals.append((pedal, on, params))
    return {"name": name, "pedals": pedals}


class Spark:
    def __init__(self, client):
        self.client = client
        self.seq = 0x20  # the reference client starts every connection here
        self.rx = bytearray()
        self.preset_parts = bytearray()
        self.events = asyncio.Queue()

    @classmethod
    async def connect(cls, timeout=8.0):
        device = await BleakScanner.find_device_by_filter(
            lambda d, adv: SERVICE in (adv.service_uuids or []) or "spark" in (d.name or adv.local_name or "").lower(),
            timeout=timeout)
        if device is None:
            raise RuntimeError("No Spark found over Bluetooth (is it on, and is the phone app disconnected?)")
        client = BleakClient(device)
        await client.connect(timeout=15.0)
        spark = cls(client)
        await client.start_notify(NOTIFY, spark._on_notify)
        await asyncio.sleep(0.3)
        return spark

    async def close(self):
        await self.client.disconnect()

    def _on_notify(self, _sender, data):
        self.rx += data
        while (end := self.rx.find(b"\xF7")) != -1:
            chunk, self.rx = bytes(self.rx[:end + 1]), self.rx[end + 1:]
            start = chunk.find(b"\xF0\x01")
            if start == -1 or len(chunk) - start < 7:
                continue
            chunk = chunk[start:]
            cmd, sub, data8 = chunk[4], chunk[5], unpack7(chunk[6:-1])
            if cmd in (0x01, 0x03) and sub == 0x01 and len(data8) >= 3:  # preset dump, many chunks
                self.preset_parts += data8[3:]
                if data8[1] >= data8[0] - 1:
                    self.events.put_nowait(("preset", parse_preset(bytes(self.preset_parts))))
                    self.preset_parts = bytearray()
            elif cmd == 0x03 and sub == 0x10:
                self.events.put_nowait(("active", data8[1]))
            elif cmd == 0x03 and sub == 0x15:
                name, pos = read_string(data8, 0)
                self.events.put_nowait(("effect", (name, data8[pos] == 0xC3)))

    async def send(self, msg_bytes):
        await self.client.write_gatt_char(WRITE, msg_bytes, response=False)
        self.seq = (self.seq + 1) & 0xFF
        await asyncio.sleep(GAP_S)

    async def wait_for(self, kind, timeout=3.0):
        deadline = asyncio.get_running_loop().time() + timeout
        while (left := deadline - asyncio.get_running_loop().time()) > 0:
            try:
                got, value = await asyncio.wait_for(self.events.get(), left)
            except asyncio.TimeoutError:
                break
            if got == kind:
                return value
        raise TimeoutError(f"the Spark didn't answer ({kind})")

    async def active_patch(self):
        await self.send(message(self.seq, 0x02, 0x10, raw=bytes(37)))
        return await self.wait_for("active")

    async def read_patch(self, n):
        self.preset_parts = bytearray()
        await self.send(message(self.seq, 0x02, 0x01, raw=bytes([0x00, 0x00, n]) + bytes(34)))
        return await self.wait_for("preset", timeout=5.0)

    async def load_patch(self, n):
        # not packed like the others: the patch number doubles as the checksum byte
        inner = bytes([0xF0, 0x01, self.seq, n, 0x01, 0x38, 0x00, 0x00, n, 0xF7])
        await self.send(bytes([0x01, 0xFE, 0x00, 0x00, 0x53, 0xFE, 16 + len(inner)]) + bytes(9) + inner)

    async def set_effect(self, name, on):
        data8 = bytes([len(name), len(name) + 0xA0]) + name.encode("ascii") + bytes([0xC3 if on else 0xC2, 0x00])
        await self.send(message(self.seq, 0x01, 0x15, data8))

    async def set_param(self, pedal, index, value):
        """One knob on one pedal (live only). Never stream these: ~60/s has locked a Spark GO up."""
        data8 = bytes([len(pedal), len(pedal) + 0xA0]) + pedal.encode("ascii") + bytes([index]) \
            + b"\xCA" + struct.pack(">f", float(value))
        await self.send(message(self.seq, 0x01, 0x04, data8))

    async def set_guitar_volume(self, value):
        await self.send(message(self.seq, 0x01, 0x33, bytes([0]) + b"\xCA" + struct.pack(">f", float(value))))


async def main(argv):
    action = argv[0] if argv else "status"
    spark = await Spark.connect()
    try:
        n = await spark.active_patch()
        patch = await spark.read_patch(n)
        print(f"Patch {n + 1}: {patch['name']}")
        for slot, (pedal, on, params) in zip(SLOTS, patch["pedals"]):
            print(f"  {slot:<9} {pedal:<22} {'ON ' if on else 'off'}  " + " ".join(f"{v:.2f}" for v in params))
        if action == "guitar":
            await spark.set_guitar_volume(float(argv[1]))
            print(f"Guitar volume -> {float(argv[1]):.2f}")
        elif action == "bypass":
            for slot, (pedal, on, _) in zip(SLOTS, patch["pedals"]):
                if on and slot != "amp":
                    await spark.set_effect(pedal, False)
                    print(f"  {slot} off")
        elif action == "clean":  # rig mode: every pedal off, amp at low gain with a flat EQ
            for slot, (pedal, on, params) in zip(SLOTS, patch["pedals"]):
                if slot == "amp":
                    for knob, value in enumerate([0.4, 0.5, 0.5, 0.5][:len(params) - 1]):  # leave the master
                        await spark.set_param(pedal, knob, value)
                    print(f"  amp {pedal}: gain 0.40, EQ flat, master {params[-1]:.2f}")
                elif on:
                    await spark.set_effect(pedal, False)
                    print(f"  {slot} off")
        elif action == "param":  # param <slot name> <knob index> <0.0-1.0>
            pedal = patch["pedals"][SLOTS.index(argv[1])][0]
            await spark.set_param(pedal, int(argv[2]), float(argv[3]))
            print(f"{pedal} knob {argv[2]} -> {float(argv[3]):.2f}")
        elif action == "restore":
            await spark.load_patch(n)
            print(f"Reloaded patch {n + 1}")
    finally:
        await spark.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
