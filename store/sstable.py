__all__ = ['SSTable']

import os
import sys
import mmap
import time
import struct

from .index import Index
from .offset import Offset

class SSTable(object):
    def __init__(self, table, t=None):
        self.table = table
        if not t: t = '%.4f' % time.time()
        self.t = t
        self.opened = False

        # offset
        offset = Offset(self, t)
        self.offset = offset

        # index
        index = Index(self, t, ())
        self.index = index

        # indexes
        self.indexes = {}

        # for n in 

        self.f = None
        self.mm = None

    def __repr__(self):
         return '<%s db: %r, table: %r, t: %r>' % (
            self.__class__.__name__,
            self.table.db.db_name,
            self.table.table_name,
            self.t,
        )

    def __enter__(self):
        '''
        Used only on data writing to file.
        '''
        self.f = open(self.get_path(), 'wb')
        self.offset.f = open(self.offset.get_path(), 'wb')
        self.index.f = open(self.index.get_path(), 'wb')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        '''
        Used only on data writing to file.
        '''
        self.index.f.close()
        self.offset.f.close()
        self.f.close()
        return False
    
    def __add__(self, other):
        # FIXME:
        pass

    def get_path(self):
        filename = 'sstable-%s.data' % self.t
        path = os.path.join(self.table.get_path(), filename)
        return path

    def is_opened(self):
        return self.opened

    def open(self):
        '''
        Used only on data reading from file.
        '''
        self.f = open(self.get_path(), 'r+b')
        self.mm = mmap.mmap(self.f.fileno(), 0)
        self.offset.open()
        self.index.open()
        self.opened = True

    def close(self):
        '''
        Used only on data reading from file.
        '''
        self.index.close()
        self.offset.close()
        self.mm.close()
        self.f.close()
        self.opened = False

    def w_open(self):
        '''
        Open file for writing.
        '''
        self.f = open(self.get_path(), 'wb')
        self.offset.w_open()
        self.index.w_open()

    def w_close(self):
        '''
        Close file for writing.
        '''
        self.index.w_close()
        self.offset.w_close()
        self.f.close()

    def add_rows(self, rows):
        for row in rows:
            self._add_row(row)

    def _add_row(self, row):
        # sstable
        row_blob = SSTable._get_row_packed(self.table, row)
        sstable_pos = self.f.tell()
        self.f.write(row_blob)

        # offset
        sstable_pos_blob = Offset._get_sstable_pos_packed(
            self, sstable_pos)
        self.offset.f.write(sstable_pos_blob)

        # index
        key_blob = Index._get_key_packed(self, row, sstable_pos)
        self.index.f.write(key_blob)

    @classmethod
    def _get_row_packed(cls, table, row):
        row_blob_items = []

        for c, t in table.schema:
            v = row.get(c, None)
            b = t._get_column_packed(v)
            row_blob_items.append(b)

        _row_blob = b''.join(row_blob_items)
        row_blob = struct.pack(b'!Q', len(_row_blob)) + _row_blob
        return row_blob

    @classmethod
    def _get_row_unpacked(cls, table, mm, pos):
        row_blob_len, = struct.unpack_from('!Q', mm, pos)
        row = {}
        p = pos + 8

        for c, t in table.schema:
            v, p = t._get_column_unpacked(mm, p)
            row[c] = v

        return row

    def get(self, key):
        offset_pos, sstable_pos = self.index._get_sstable_pos(key)
        row = SSTable._get_row_unpacked(self.table, self.mm, sstable_pos)
        return row, offset_pos, sstable_pos

    def get_lt(self, key):
        offset_pos, sstable_pos = self.index._get_lt_sstable_pos(key)
        row = SSTable._get_row_unpacked(self.table, self.mm, sstable_pos)
        return row, offset_pos, sstable_pos

    def get_le(self, key):
        offset_pos, sstable_pos = self.index._get_le_sstable_pos(key)
        row = SSTable._get_row_unpacked(self.table, self.mm, sstable_pos)
        return row, offset_pos, sstable_pos

    def get_gt(self, key):
        offset_pos, sstable_pos = self.index._get_gt_sstable_pos(key)
        row = SSTable._get_row_unpacked(self.table, self.mm, sstable_pos)
        return row, offset_pos, sstable_pos

    def get_ge(self, key):
        offset_pos, sstable_pos = self.index._get_ge_sstable_pos(key)
        row = SSTable._get_row_unpacked(self.table, self.mm, sstable_pos)
        return row, offset_pos, sstable_pos
