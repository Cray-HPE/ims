#
# MIT License
#
# (C) Copyright 2019-2022 Hewlett Packard Enterprise Development LP
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
from datetime import datetime

# TODO CASMCMS-1154 Get a real data store
import json
import logging
import os
import os.path

logger = logging.getLogger(__name__)


class DataStoreHACK(collections.MutableMapping):
    """A dictionary that reads/writes to a file"""

    MAX_RECOVERY_RETRIES: int = 3

    def __init__(self, store_file, schema_obj, key_field, *args, **kwargs):
        self.store = dict()
        self.schema = schema_obj
        self.key_field = key_field
        self.update(*args, **kwargs)
        self.store_file = store_file
        self.current_retries = 0
        if not os.path.exists(self.store_file):
            with open(self.store_file, "a"):
                os.utime(self.store_file, None)
            self._write()
        else:
            self._read()

    def _read(self):
        """Reads in store file"""
        try:
            logger.info(f"Starting read of {self.store_file}")
            with open(self.store_file, "r") as data_file:
                obj_data = self.schema.loads(data_file.read(), many=True)
                self.store = {
                    str(getattr(obj, self.key_field)): obj for obj in obj_data
                }
        except BaseException as error:
            logger.error(
                f"Unable to read {self.store_file} data, file may be empty or corrupted",
                exc_info=error,
            )
            self._save_corrupted_file()
            self._recover_file_read()

    def _write(self):
        """Write the data to the file store"""
        try:
            with open(self.store_file, "w") as data_file:
                data_file.write(self.schema.dumps(iter(self.store.values()), many=True))
        except BaseException as error:
            logger.error(f"Unable to write to file {self.store_file}", exc_info=error)
            raise error

    def _save_corrupted_file(self):
        """
        Saves the file with a timestamp prefix for manual debugging
        """
        path: list[str] = self.store_file.split(os.sep)
        path[0]: str = os.sep
        file_name: str = path[-1]
        timestamp: str = datetime.now().strftime("%Y%m%d-%H%M%S")
        timestamp_prefix_name: str = timestamp + "_" + file_name
        path[-1]: str = timestamp_prefix_name

        new_path: str = os.path.join(*path)
        os.rename(self.store_file, new_path)
        logger.info(
            f"Saving corrupted data file {file_name} as {timestamp_prefix_name}"
        )

    def _recover_file_read(self):
        """
        Creates a valid empty JSON file if _read() throws an exception due to corruption
        or recovery has failed too many times.
        """
        logger.info(f"Starting recreation of {self.store_file} with empty JSON")
        try:
            with open(self.store_file, "w") as f:
                f.write(json.dumps([]))
                logger.info(f"Recreated {self.store_file} with empty JSON")
        except BaseException as error:
            logger.error(f"Failed recreation of corrupted file {self.store_file}")
            raise error

        if self.current_retries < self.MAX_RECOVERY_RETRIES:
            self.current_retries += 1
            self._read()

    def save(self):
        """Save the data to disk"""
        return self._write()

    def reset(self):
        """Reset the data store to empty and write it out to disk"""
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
