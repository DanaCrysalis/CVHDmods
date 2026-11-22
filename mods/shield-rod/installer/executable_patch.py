"""Verified BSDIFF40 patch application using Python's standard library."""
import bz2
import hashlib
import struct


def canonical_pe(data):
    """Ignore only PE build time/checksum; every code/data byte stays verified."""
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError('Not a Windows executable')
    pe = struct.unpack_from('<I', data, 60)[0]
    if pe + 92 > len(data) or data[pe:pe+4] != b'PE\0\0':
        raise ValueError('Invalid executable header')
    out = bytearray(data)
    out[pe+8:pe+12] = bytes(4)  # COFF TimeDateStamp
    out[pe+88:pe+92] = bytes(4)  # OptionalHeader CheckSum
    return bytes(out)


def integer(data):
    if len(data) != 8:
        raise ValueError('Truncated patch integer')
    value = int.from_bytes(data, 'little')
    return -(value & 0x7fffffffffffffff) if value >> 63 else value


def apply(original, patch, expected_size, expected_sha):
    if patch[:8] != b'BSDIFF40' or len(patch) < 32:
        raise ValueError('Invalid executable patch')
    ctrl_size, diff_size, size = (integer(patch[i:i+8]) for i in (8, 16, 24))
    if size != expected_size or size < 0 or size > 128 * 1024 * 1024 or min(ctrl_size, diff_size) < 0:
        raise ValueError('Invalid executable patch dimensions')
    split = 32 + ctrl_size
    end = split + diff_size
    if end > len(patch):
        raise ValueError('Truncated executable patch')
    control = bz2.decompress(patch[32:split])
    differences = bz2.decompress(patch[split:end])
    extra = bz2.decompress(patch[end:])
    output = bytearray(size)
    old_pos = new_pos = ctrl_pos = diff_pos = extra_pos = 0
    while new_pos < size:
        if ctrl_pos + 24 > len(control):
            raise ValueError('Truncated patch instructions')
        add, copy, seek = (integer(control[i:i+8]) for i in range(ctrl_pos, ctrl_pos+24, 8))
        ctrl_pos += 24
        if min(add, copy) < 0 or new_pos + add + copy > size or diff_pos + add > len(differences) or extra_pos + copy > len(extra):
            raise ValueError('Invalid patch instruction')
        output[new_pos:new_pos+add] = differences[diff_pos:diff_pos+add]
        first, last = max(0, -old_pos), min(add, len(original)-old_pos)
        if last > first:
            output[new_pos+first:new_pos+last] = bytes((a+b) & 255 for a, b in zip(
                differences[diff_pos+first:diff_pos+last], original[old_pos+first:old_pos+last]))
        new_pos += add
        old_pos += add
        diff_pos += add
        output[new_pos:new_pos+copy] = extra[extra_pos:extra_pos+copy]
        new_pos += copy
        extra_pos += copy
        old_pos += seek
    if ctrl_pos != len(control) or diff_pos != len(differences) or extra_pos != len(extra):
        raise ValueError('Unused executable patch data')
    if hashlib.sha256(output).hexdigest() != expected_sha:
        raise ValueError('Patched executable failed SHA-256 verification')
    return bytes(output)
