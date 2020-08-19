# Copyright 2019, Cray Inc. All Rights Reserved.
# A crude dict/json/write to a file-based data store. This is a shim until a
# real data store is enabled.

import collections
# TODO CASMCMS-1154 Get a real data store
import os
import os.path


class DataStoreHACK(collections.MutableMapping):
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
        with open(self.store_file, 'r') as data_file:
            obj_data = self.schema.loads(data_file.read(), many=True)
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
