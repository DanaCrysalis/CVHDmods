"""STFS data-package writer/reader shared from hod_musicpack.py."""
import hashlib,struct
from pathlib import Path
TITLE_ID=0x58410A7A
STFS_BLOCK = 0x1000
STFS_HEADER = 0x971A
STFS_L0, STFS_L1 = 0xAA, 0xAA * 0xAA
STFS_END = 0xFFFFFF


def _fat_datetime(t=None):
    import time
    t = time.localtime(t)
    date = ((t.tm_year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
    clock = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
    return date, clock


def _stfs_layout(n):
    """Physical block (after the header) of every data block and hash table."""
    data, l0, l1, l2 = [], [], [], None
    pos = 0
    for b in range(n):
        if b % STFS_L0 == 0:
            if b and b % STFS_L1 == 0:
                if l2 is None:
                    l2, pos = pos, pos + 1
                l1.append(pos)
                pos += 1
            elif b == STFS_L0:
                l1.append(pos)
                pos += 1
            l0.append(pos)
            pos += 1
        data.append(pos)
        pos += 1
    if n == 0:
        l0.append(0)
        pos = 1
    return data, l0, l1, l2, pos


def write_stfs(src, out, display_name, package):
    """Pack folder `src` into one LIVE package at `out` (file name = content id)."""
    src = Path(src)
    entries = []  # (name, is_dir, parent index, path)
    index = {src: 0xFFFF}
    queue = [src]
    while queue:  # directories first, breadth first, then files (as official packs)
        d = queue.pop(0)
        for p in sorted(x for x in d.iterdir() if x.is_dir()):
            index[p] = len(entries)
            entries.append((p.name, True, index[d], p))
            queue.append(p)
    for d in list(index):
        for p in sorted(x for x in d.iterdir() if x.is_file()):
            entries.append((p.name, False, index[d], p))
    for name, *_ in entries:
        assert len(name) <= 40 and name.isascii(), f'file name not allowed in a package: {name}'

    table_blocks = max(1, -(-len(entries) // 64))
    blocks = [None] * table_blocks
    chains = [(0, table_blocks)]
    raw_entries = []
    date, clock = _fat_datetime()
    for name, is_dir, parent, p in entries:
        if is_dir:
            start = count = size = 0
        else:
            data = p.read_bytes()
            size, count, start = len(data), -(-len(data) // STFS_BLOCK), len(blocks)
            for i in range(count):
                blocks.append(data[i * STFS_BLOCK:(i + 1) * STFS_BLOCK].ljust(STFS_BLOCK, b'\0'))
            if count:
                chains.append((start, count))
        e = bytearray(0x40)
        e[:len(name)] = name.encode()
        e[0x28] = len(name) | (0x80 if is_dir else 0)
        e[0x29:0x2C] = count.to_bytes(3, 'little')
        e[0x2C:0x2F] = count.to_bytes(3, 'little')
        e[0x2F:0x32] = start.to_bytes(3, 'little')
        struct.pack_into('>HIHHHH', e, 0x32, parent, size, date, clock, date, clock)
        raw_entries.append(bytes(e))
    table = b''.join(raw_entries).ljust(table_blocks * STFS_BLOCK, b'\0')
    for i in range(table_blocks):
        blocks[i] = table[i * STFS_BLOCK:(i + 1) * STFS_BLOCK]

    n = len(blocks)
    nxt = [STFS_END] * n
    for start, count in chains:
        for i in range(start, start + count - 1):
            nxt[i] = i + 1
    data_pos, l0_pos, l1_pos, l2_pos, total = _stfs_layout(n)
    body = bytearray(total * STFS_BLOCK)
    for i, blk in enumerate(blocks):
        body[data_pos[i] * STFS_BLOCK:(data_pos[i] + 1) * STFS_BLOCK] = blk

    def table_block(hashes_infos):
        t = bytearray(STFS_BLOCK)
        for k, (h, info) in enumerate(hashes_infos):
            t[k * 0x18:k * 0x18 + 0x14] = h
            struct.pack_into('>I', t, k * 0x18 + 0x14, info)
        return bytes(t)

    l0_tables = []
    for g, pos in enumerate(l0_pos):
        rng = range(g * STFS_L0, min(n, (g + 1) * STFS_L0))
        t = table_block([(hashlib.sha1(blocks[i]).digest(), 0x80000000 | nxt[i]) for i in rng])
        body[pos * STFS_BLOCK:(pos + 1) * STFS_BLOCK] = t
        l0_tables.append(t)
    top = l0_tables[0]
    l1_tables = []
    for k, pos in enumerate(l1_pos):
        rng = l0_tables[k * STFS_L0:(k + 1) * STFS_L0]
        t = table_block([(hashlib.sha1(x).digest(), 0) for x in rng])
        body[pos * STFS_BLOCK:(pos + 1) * STFS_BLOCK] = t
        l1_tables.append(t)
    if l1_tables:
        top = l1_tables[0]
    if l2_pos is not None:
        top = table_block([(hashlib.sha1(x).digest(), 0) for x in l1_tables])
        body[l2_pos * STFS_BLOCK:(l2_pos + 1) * STFS_BLOCK] = top

    h = bytearray(-(-STFS_HEADER // STFS_BLOCK) * STFS_BLOCK)
    h[0:4] = b'LIVE'
    struct.pack_into('>QII', h, 0x22C, 0xFFFFFFFFFFFFFFFF, 1, 1)   # licensed to everyone
    struct.pack_into('>I', h, 0x340, STFS_HEADER)
    struct.pack_into('>II', h, 0x344, 2, 2)                          # marketplace content, metadata v2
    struct.pack_into('>Q', h, 0x34C, total * STFS_BLOCK)
    struct.pack_into('>I', h, 0x360, TITLE_ID)
    vd = bytearray(0x24)
    vd[0], vd[1], vd[2] = 0x24, 0, 1                                  # read-only format
    vd[3:5] = table_blocks.to_bytes(2, 'little')
    vd[5:8] = (0).to_bytes(3, 'little')
    vd[8:0x1C] = hashlib.sha1(top).digest()
    struct.pack_into('>II', vd, 0x1C, n, 0)
    h[0x379:0x379 + 0x24] = vd
    name = display_name.encode('utf-16-be')[:0xFE]
    for lang in range(9):                                             # every language slot
        h[0x411 + lang * 0x100:0x411 + lang * 0x100 + len(name)] = name
    title = 'Castlevania Harmony of Despair'.encode('utf-16-be')
    h[0x1691:0x1691 + len(title)] = title
    h[0x1711] = 0xC0
    h[0x32C:0x340] = hashlib.sha1(bytes(h[0x344:STFS_HEADER])).digest()
    out = Path(out)
    out.write_bytes(bytes(h) + bytes(body))
    return out


def read_stfs(path, verify=True):
    """Files of a LIVE/PIRS package as {path: bytes}; checks every hash if asked."""
    b = Path(path).read_bytes()
    assert b[:4] in (b'LIVE', b'PIRS', b'CON '), 'not an Xbox 360 package'
    hs = int.from_bytes(b[0x340:0x344], 'big')
    base = -(-hs // STFS_BLOCK)
    vd = b[0x379:0x379 + 0x24]
    ft_blocks = int.from_bytes(vd[3:5], 'little')
    ft_start = int.from_bytes(vd[5:8], 'little')
    n = int.from_bytes(vd[0x1C:0x20], 'big')
    data_pos, l0_pos, l1_pos, l2_pos, _ = _stfs_layout(n)

    def blk(phys):
        o = (base + phys) * STFS_BLOCK
        return b[o:o + STFS_BLOCK]

    def entry(logical):
        t = blk(l0_pos[logical // STFS_L0])
        k = logical % STFS_L0
        return t[k * 0x18:k * 0x18 + 0x14], int.from_bytes(t[k * 0x18 + 0x15:k * 0x18 + 0x18], 'big')

    if verify:
        for i in range(n):
            assert entry(i)[0] == hashlib.sha1(blk(data_pos[i])).digest(), f'block {i} hash'
        for k, pos in enumerate(l1_pos):
            t = blk(pos)
            for j, p0 in enumerate(l0_pos[k * STFS_L0:(k + 1) * STFS_L0]):
                assert t[j * 0x18:j * 0x18 + 0x14] == hashlib.sha1(blk(p0)).digest(), 'level-1 hash'
        top = blk(l2_pos) if l2_pos is not None else blk(l1_pos[0]) if l1_pos else blk(l0_pos[0])
        assert hashlib.sha1(top).digest() == vd[8:0x1C], 'top hash'

    def chain(start, count):
        out, cur = [], start
        for i in range(count):
            out.append(cur)
            if i + 1 < count:
                cur = entry(cur)[1]
        return out

    raw = b''.join(blk(data_pos[i]) for i in chain(ft_start, ft_blocks))
    entries = []
    for k in range(len(raw) // 0x40):
        e = raw[k * 0x40:(k + 1) * 0x40]
        if not e[0x28] & 0x3F:
            break
        entries.append((e[:e[0x28] & 0x3F].decode('ascii'), bool(e[0x28] & 0x80),
                        int.from_bytes(e[0x2F:0x32], 'little'), int.from_bytes(e[0x29:0x2C], 'little'),
                        int.from_bytes(e[0x32:0x34], 'big'), int.from_bytes(e[0x34:0x38], 'big')))

    def full(i):
        name, _, _, _, parent, _ = entries[i]
        return name if parent == 0xFFFF else full(parent) + '/' + name

    files = {}
    for i, (name, is_dir, start, count, parent, size) in enumerate(entries):
        if not is_dir:
            files[full(i)] = b''.join(blk(data_pos[x]) for x in chain(start, count))[:size] if count else b''
    return files

