__all__ = ['Table']

import os
import sys
from collections import OrderedDict

from .column import Column
from .schema import Schema
from .memtable import MemTable
from .sstable import SSTable
from .query import Query
from .deferred import Deferred

class Table(object):
    MEMTABLE_LIMIT_N_ITEMS = 10000

    def __init__(self, db, table_name):
        self.store = db.store
        self.db = db
        self.table_name = table_name

        # load schema
        schema = Schema(self)
        schema.load()
        self.schema = schema

        # memtable
        self.memtable = MemTable(self)

        # sstables
        self.sstables = []
        dirname = os.path.join(self.store.data_path, self.db.db_name, self.table.table_name)

        for filename in os.listdir(dirname):
            if not filename.startswith('commitlog'):
                continue

            s = filename.index('commitlog-') + len('commitlog-')
            e = filename.index('.sstable')
            t = filename[s:e]

            # sstable
            sst = SSTable(self, t)
            sst.open()
            self.sstables.append(sst)

        print self.sstables

    def __getattr__(self, attr):
        c = getattr(self.schema, attr)
        return c

    def close(self):
        for sst in self.sstables:
            sst.close()

    @classmethod
    def create(cls, db, table_name, _type_fields):
        # sort type_fields
        type_fields = OrderedDict()

        for c, t in sorted(_type_fields.items(), key=lambda n: n[0]):
            if c == 'primary_key':
                continue

            if t == 'bool':
                coltype = Column(c, t, 1)
            elif t == 'int':
                coltype = Column(c, t, 8)
            elif t == 'float':
                coltype = Column(c, t, 8)
            elif t.startswith('str'):
                if '[' in t:
                    size = int(t[t.index('[') + 1:t.index(']')])
                else:
                    size = None

                coltype = Column(c, t, size)
            else:
                raise Exception('unsupported column type')

            type_fields[c] = coltype

        # add primary_key at the end of dict
        column_names = _type_fields.get('primary_key', [])

        for column_name in column_names:
            coltype = type_fields[column_name]

            if coltype.type == 'str' and coltype.size is None:
                raise Exception(
                    'Primary key\'s column with type'
                    '"str" must have fixed size'
                )

        type_fields['primary_key'] = column_names

        # create table dir inside of database dir
        dirpath = os.path.join(db.store.data_path, db.db_name, table_name)
        
        try:
            os.makedirs(dirpath)
        except OSError as e:
            pass

        # create schema
        schema = Schema.create(db, table_name, type_fields)

        # table
        table = Table(db, table_name)
        return table

    @property
    def query(self):
        q = Query(self.db.store)
        return q

    def commit_if_required(self):
        if len(self.memtable) >= self.MEMTABLE_LIMIT_N_ITEMS:
            self.commit()
        # pass

    def commit(self):
        # get sorted rows
        rows = self.memtable.get_sorted_rows()
        
        # create new sstable
        sst = SSTable.create(self, rows)
        sst.open()
        self.sstables.append(sst)

        # clear memtable
        # self.memtable = MemTable(self)
        self.memtable.clear()

    def insert(self, **row):
        # tx
        tx = self.store.get_current_transaction()
        tx.log((self.db, self.table, self.commit_insert, (), row))

    def commit_insert(self, **row):
        # compare against schema
        for k, v in row.items():
            if k not in self.schema.type_fields:
                raise Exception('filed %r is not defined in schema for table %r' % (k, self.table_name))

        # set default columns
        for k, v in self.schema.type_fields.items():
            if k == 'primary_key':
                continue

            if k not in row:
                row[k] = None

        # build key
        key = tuple(row[k] for k in self.schema.type_fields['primary_key'])

        # insert key
        self.memtable[key] = row

        # commit if required
        self.commit_if_required()

    def get(self, *args):
        # deferred
        d = Deferred()

        # tx
        tx = self.store.get_current_transaction()
        tx.log((self.db, self.table, self.commit_get, (d,) + args, {}))

        return d
    
    def commit_get(self, d, *args):
        key = tuple(args)

        try:
            v = self.memtable[key]
        except KeyError as e:
            for sst in reversed(self.sstables):
                try:
                    v = sst.get(key)
                    break
                except KeyError as e:
                    pass
            else:
                raise KeyError

        d.set(v)
