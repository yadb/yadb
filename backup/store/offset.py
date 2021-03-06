__all__ = ['Offset']

import os
import sys
import mmap
import struct

class Offset(object):
    '''
    Offset is class that finds out position of row at given index
    '''

    def __init__(self, sstable, t, path=None):
        self.sstable = sstable
        self.t = t
        self.mm = None
        self.f = None

    def __getitem__(self, i):
        return self._read_sstable_pos(i)

    def get_path(self):
        filename = 'offset-%s.data' % self.t
        path = os.path.join(self.sstable.table.get_path(), filename)
        return path

    def open(self):
        '''
        Open file for reading.
        '''
        self.f = open(self.get_path(), 'r+b')
        self.mm = mmap.mmap(self.f.fileno(), 0)

    def close(self):
        '''
        Open file for reading.
        '''
        self.mm.close()
        self.f.close()

    def w_open(self):
        '''
        Open file for writing.
        '''
        self.f = open(self.get_path(), 'wb')

    def w_close(self):
        '''
        Close file for writing.
        '''
        self.f.close()

    def _read_sstable_pos(self, i):
        offset_pos = i * 8
        sstable_pos, = struct.unpack_from('!Q', self.mm, offset_pos)
        return sstable_pos

    def _write_sstable_pos(self, sstable_pos):
        pos_blob = struct.pack('!Q', sstable_pos)
        self.f.write(pos_blob)