"""Small integer raster operations used by the disc converter; no image codecs."""
from array import array
import sys

uint16 = 'uint16'


class Flat:
    def __init__(self, values):
        self.values = list(values)

    def reshape(self, height, width):
        if height < 0:
            height = len(self.values) // width
        if height * width != len(self.values):
            raise ValueError('Raster dimensions do not match its data')
        return Grid([self.values[i*width:(i+1)*width] for i in range(height)])

    def tolist(self):
        return self.values


class Grid:
    def __init__(self, rows):
        self.rows = [list(row) for row in rows]
        self.shape = (len(self.rows), len(self.rows[0]) if self.rows else 0)
        if any(len(row) != self.shape[1] for row in self.rows):
            raise ValueError('Ragged raster')

    def __getitem__(self, key):
        y, x = key
        if isinstance(y, int) and isinstance(x, int):
            return self.rows[y][x]
        if not isinstance(y, slice) or not isinstance(x, slice):
            raise TypeError('Expected a pixel or rectangular slice')
        return Grid([row[x] for row in self.rows[y]])

    def __setitem__(self, key, value):
        y, x = key
        if isinstance(y, int) and isinstance(x, int):
            self.rows[y][x] = value
            return
        ys = range(*y.indices(self.shape[0]))
        xs = range(*x.indices(self.shape[1]))
        if not isinstance(value, Grid) or value.shape != (len(ys), len(xs)):
            raise ValueError('Raster slice assignment dimensions differ')
        for dest, source in zip(ys, value.rows):
            self.rows[dest][x] = source

    def flatten(self):
        return Flat(v for row in self.rows for v in row)


def zeros(shape, dtype=None):
    height, width = shape
    return Grid([[0] * width for _ in range(height)])


def frombuffer(data, dtype):
    if dtype in ('<u2', 'uint16'):
        values = array('H')
        values.frombytes(data)
        if sys.byteorder != 'little':
            values.byteswap()
        return Flat(values)
    if dtype == 'uint8':
        return Flat(data)
    raise ValueError(f'Unsupported raster sample type: {dtype}')


def concatenate(grids, axis=0):
    if axis == 0:
        return Grid(row for grid in grids for row in grid.rows)
    if axis == 1:
        if len({g.shape[0] for g in grids}) != 1:
            raise ValueError('Raster heights differ')
        return Grid([v for g in grids for v in g.rows[y]] for y in range(grids[0].shape[0]))
    raise ValueError('Unsupported raster axis')


def repeat(grid, count, axis):
    if axis != 1:
        raise ValueError('Only horizontal pixel repetition is used')
    return Grid([v for value in row for v in [value] * count] for row in grid.rows)


def nibbles(grid):
    return Grid([(value >> bit) & 15 for value in row for bit in (0, 4, 8, 12)] for row in grid.rows)
