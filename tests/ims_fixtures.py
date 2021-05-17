# Copyright 2018-2019, 2021 Hewlett Packard Enterprise Development LP
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# (MIT License)
"""
Test Fixtures
"""
import os.path

from fixtures import Fixture, TempDir


class DataStoreFixture(Fixture):
    """ Test Fixture for preparing an empty data store """

    def __init__(self, datastore):
        super(DataStoreFixture, self).__init__()
        self.datastore = datastore

    def _setUp(self):
        """ Mock a DataStoreHACK instance with initial data if requested """
        self.store_dir = self.useFixture(TempDir()).path
        data_file = os.path.join(self.store_dir, 'data.json')
        self.datastore.store_file = data_file
        self.datastore.reset()


class _GenericDataFixture(Fixture):
    schema = None
    datastore = None
    id_field = None

    def __init__(self, initial_data=None):
        super(_GenericDataFixture, self).__init__()
        self._initial_data = initial_data

    def _setUp(self):
        """ Create an Marshmallow data object instance with test data """
        self.useFixture(DataStoreFixture(self.datastore))
        if self._initial_data:
            if isinstance(self._initial_data, dict):
                input_data = self.schema().load(self._initial_data)
                self.datastore.store = {self._initial_data[self.id_field]: input_data}
                self.datastore.save()
            elif isinstance(self._initial_data, list):
                data = {}
                for record in self._initial_data:
                    input_data = self.schema().load(record)
                    data[record[self.id_field]] = input_data
                self.datastore.store = data
                self.datastore.save()
        self.addCleanup(self.datastore.reset)
