#
# MIT License
#
# (C) Copyright 2019-2023 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
"""
A crude dict/json/write to a file-based data store. This is a shim until a
real data store is enabled.
"""
import collections
# TODO CASMCMS-1154 Get a real data store
import os
import os.path

class DataStoreHACK(collections.abc.MutableMapping):
    """ A dictionary that reads/writes to a file """

    def __init__(self, store_file, schema_obj, key_field, *args, **kwargs):
        self.store = dict()
        self.schema = schema_obj
        self.key_field = key_field
        self.update(*args, **kwargs)
        self.store_file = store_file
        if not os.path.exists(self.store_file):
            with open(self.store_file, 'a'):
                os.utime(self.store_file, None)
            self._write()
        else:
            self._read()

    def _read(self):
        """ Read in the data """
        # Setting 'unknown="Exclude" allows downgrades by just dropping any data
        # fields that are no longer part of the current schema.
        with open(self.store_file, 'r') as data_file:
            obj_data = self.schema.loads(data_file.read(), many=True, unknown="EXCLUDE")
            self.store = {str(getattr(obj, self.key_field)): obj for obj in obj_data}

    def _write(self):
        """ Write the data to the file store """
        with open(self.store_file, 'w') as data_file:
            data_file.write(self.schema.dumps(iter(self.store.values()), many=True))

    def save(self):
        """ Save the data to disk """
        return self._write()

    def reset(self):
        """ Reset the data store to empty and write it out to disk """
        self.store = dict()
        return self._write()

    def __getitem__(self, key):
        return self.store[key]

    def __setitem__(self, key, value):
        self.store[key] = value
        self._write()

    def __delitem__(self, key):
        del self.store[key]
        self._write()

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __contains__(self, key):
        return key in self.store
