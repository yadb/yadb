__all__ = ['Column']

import struct

from .expr import Expr

class Column(object):
    def __init__(self, name=None, type=None, size=None):
        self.name = name
        self.type = type
        self.size = size

    def __repr__(self):
        return '<%s name: %r, type: %r, size: %s>' % (
            self.__class__.__name__,
            self.name,
            self.type,
            self.size,
        )

    def __eq__(self, other):
        return Expr(self, '==', other)

    def __ne__(self, other):
        return Expr(self, '!=', other)

    def __lt__(self, other):
        return Expr(self, '<', other)

    def __le__(self, other):
        return Expr(self, '<=', other)

    def __gt__(self, other):
        return Expr(self, '>', other)

    def __ge__(self, other):
        return Expr(self, '>=', other)

    def __iter__(self):
        '''
        Used for conversion to dict in Schema.
        '''
        d = {
            'name': self.name,
            'type': self.type,
            'size': self.size,
        }

        for k, v in d.items():
            yield k, v

    def _get_struct_format(self, value=None):
        if self.type == 'bool':
            fmt = b'!BBB'
        elif self.type == 'int':
            fmt = b'!BBq'
        elif self.type == 'float':
            fmt = b'!BBd'
        elif self.type == 'str':
            if value is None:
                fmt = b'!BBQ%is' % self.size
            else:
                fmt = b'!BBQ%is' % len(value)
        else:
            raise Exception('unsupported column type')

        return fmt

    def _get_column_size(self, value):
        fmt = self._get_struct_format(value)
        size = struct.calcsize(fmt)
        return size

    def _get_column_packed(self, value=None):
        fmt = self._get_struct_format(value)
        is_null = 1 if value is None else 0

        if self.type == 'str':
            # FIXME: use self.size if required
            b = struct.pack(fmt, 0, is_null, len(value), value)
        else:
            b = struct.pack(fmt, 0, is_null, value)

        return b

    def _get_column_unpacked(self, mm, pos):
        status, is_null = struct.unpack_from('!BB', mm, pos)
        pos += 2

        if self.type == 'bool':
            value, = struct.unpack_from('!B', mm, pos)
            value = bool(value)
            pos += 1
        elif self.type == 'int':
            value, = struct.unpack_from('!q', mm, pos)
            pos += 8
        elif self.type == 'float':
            value, = struct.unpack_from('!d', mm, pos)
            pos += 8
        elif self.type == 'str':
            str_len, = struct.unpack_from('!Q', mm, pos)
            pos += 8
            value = mm[pos:pos + str_len]
            pos += str_len
        else:
            raise Exception('unsupported column type')

        return value, pos
