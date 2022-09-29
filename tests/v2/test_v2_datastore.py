#
# MIT License
#
# (C) Copyright 2019, 2021-2022 Hewlett Packard Enterprise Development LP
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
#

import datetime
import os
import tempfile

from unittest import TestCase, mock
from json import JSONDecodeError
from mock import MagicMock

from src.server import DataStoreHACK


class TestV2DataStore(TestCase):
    """
    Tests the DataStoreHack init code.
    """

    def setUp(self) -> None:
        # Create temp directory for file testing
        self.temp_file = tempfile.NamedTemporaryFile()

    def tearDown(self) -> None:
        self.temp_file.close()

    def test_file_not_found(self):
        mock_schema = MagicMock()

        with self.assertRaises(FileNotFoundError):
            DataStoreHACK("/bad/path", mock_schema, "fake_key")

    @mock.patch("src.server.datetime", wraps=datetime.datetime)
    @mock.patch("os.rename")
    def test_file_found_decode_error(self, mock_rename, mock_datetime):
        # setup mocks
        expected_datetime: datetime.datetime = datetime.datetime(
            2022, 9, 27, 11, 22, 31, 123456
        )
        mock_schema = MagicMock()
        mock_schema.loads.side_effect = [
            JSONDecodeError("bad json", self.temp_file.name, 0),
            [],
        ]
        mock_datetime.now.return_value = expected_datetime

        with mock.patch("builtins.open", mock.mock_open()) as mock_file:
            DataStoreHACK(self.temp_file.name, mock_schema, "id")
            mock_file.assert_called_with(self.temp_file.name, "r")

            # test if file was renamed with correct timestamps
            expected_renamed_prefix: str = expected_datetime.strftime("%Y%m%d-%H%M%S")
            args, _ = mock_rename.call_args
            new_filepath: str = args[1]
            renamed_file_prefix = new_filepath.split(os.sep)[-1].split("_")[0]
            self.assertEqual(renamed_file_prefix, expected_renamed_prefix)

            # test if the file was written to with clean data
            write_handle: MagicMock = mock_file()
            write_handle.write.assert_called_once_with("[]")
