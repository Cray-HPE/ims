#
# MIT License
#
# (C) Copyright 2020-2023 Hewlett Packard Enterprise Development LP
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
import datetime

from marshmallow import Schema, fields, post_load, RAISE
from marshmallow.validate import OneOf

from src.server.models.images import V2ImageRecord, V2ImageRecordInputSchema
from src.server.v3.models import PATCH_OPERATIONS


class V3DeletedImageRecord(V2ImageRecord):
    """ The ImageRecord object """

    # pylint: disable=W0622
    def __init__(self, name, link=None, id=None, created=None, deleted=None, arch="x86_64", metadata=None):
        # Supplied
        self.deleted = deleted or datetime.datetime.now()
        super().__init__(name, link=link, id=id, created=created, arch=arch, metadata=metadata)

    def __repr__(self):
        return '<V3DeletedImageRecord(id={self.id!r})>'.format(self=self)


class V3DeletedImageRecordInputSchema(V2ImageRecordInputSchema):
    """ A schema specifically for defining and validating user input """

    @post_load
    def make_image(self, data, many, partial):
        """ Marshall an object out of the individual data components """
        return V3DeletedImageRecord(**data)

    class Meta:  # pylint: disable=missing-docstring
        model = V3DeletedImageRecord
        unknown = RAISE  # do not allow unknown fields in the schema


class V3DeletedImageRecordSchema(V3DeletedImageRecordInputSchema):
    """
    Schema for a fully-formed ImageRecord object such as an object being
    read in from a database. Builds upon the basic input fields in
    ImageRecordInputSchema.
    """
    id = fields.UUID(metadata={"metadata": {"description": "Unique id of the image"}})
    created = fields.DateTime(metadata={"metadata": {"description": "Time the image record was created"}})
    deleted = fields.DateTime(metadata={"metadata": {"description": "Time the image record was deleted"}})


class V3DeletedImageRecordPatchSchema(Schema):
    """
    Schema for updating an ImageRecord object.
    """
    operation = fields.Str(required=True,
                           metadata={"metadata": {"description": "The operation or action that should be taken on the image record. "
                                                   f'Supported operations are: { ", ".join(PATCH_OPERATIONS) }'}},
                           validate=OneOf(PATCH_OPERATIONS, error="Recipe type must be one of: {choices}."))
