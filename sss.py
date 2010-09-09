import sqlite3
from helpers import *

class Db:
    def __init__(self, filename, schema):
        self.filename = filename
        self.db = sqlite3.connect(self.filename)
        self.select = self.run
        self.commit = self.db.commit
        self.rollback = self.db.rollback

        try:
            sv = self.selectcell('select version from Schema')
        except sqlite3.OperationalError:
            sv = None
        try:
            if not sv:
                self.run('create table Schema (version)')
                self.run('insert into Schema values (null)')
            for v,func in schema:
                if v > sv:
                    log('Updating to schema v%d\n' % v)
                    func(self)
                    self.run('update Schema set version=?', v)
                    self.commit()
        except:
            try:
                # EXTREMELY DISAPPOINTING: the python sqlite3 module
                # *always* calls commit() right before executing a
                # "create table" statement.  So our transaction will always
                # be half done and rolling back at this point won't actually
                # work.  Horrible.  sqlite3 (eg. the command line) is fine,
                # but not python-sqlite3.
                #
                # But in the hopes that this retarded behaviour might be fixed
                # someday, let's put the rollback here anyway.
                self.rollback()
            except:
                pass
            raise
        assert(self.selectcell('select version from Schema') == v)
        self.commit()

    def run(self, st, *args):
        #log('%r %r\n' % (st, args))
        return self.db.execute(st, args)

    def selectcell(self, st, *args):
        for row in self.run(st, *args):
            return row[0]

    def selectrow(self, st, *args):
        for row in self.run(st, *args):
            return row

    def selectcol(self, st, *args):
        for row in self.run(st, *args):
            yield row[0]
