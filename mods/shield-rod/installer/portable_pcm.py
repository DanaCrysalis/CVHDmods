"""Trim and encode the original SPU render without a numerical runtime."""
from array import array
import sys
import wave


def finish_pcm(raw, path, sound_id, rate):
    values = array('h')
    values.frombytes(raw.read_bytes())
    if sys.byteorder != 'little':
        values.byteswap()
    if len(values) % 2:
        raise ValueError('Invalid stereo PCM render')
    total = len(values) // 2
    last = next((i for i in range(total-1, -1, -1)
                 if max(abs(values[i*2]), abs(values[i*2+1])) > 2), None)
    if last is None:
        raise ValueError(f'Silent original sound {sound_id:04X}')
    if last >= total - rate // 4:
        raise ValueError(f'Non-terminating original sound {sound_id:04X}')
    count = min(total, last + 1 + rate // 50)
    del values[count*2:]
    peak = max(abs(value) for value in values)
    little = array('h', values)
    if sys.byteorder != 'little':
        little.byteswap()
    with wave.open(str(path), 'wb') as output:
        output.setparams((2, 2, rate, 0, 'NONE', 'not compressed'))
        output.writeframes(little.tobytes())
    if sys.byteorder == 'little':
        values.byteswap()
    return values.tobytes(), count, peak
