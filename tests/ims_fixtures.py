"""
Test Fixtures
Copyright 2018, 2019, Cray Inc. All Rights Reserved.
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
