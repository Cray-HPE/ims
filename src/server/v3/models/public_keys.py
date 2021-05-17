# Copyright 2020-2021 Hewlett Packard Enterprise Development LP
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

import datetime

from marshmallow import Schema, fields, RAISE, post_load
from marshmallow.validate import OneOf

from src.server.models.publickeys import V2PublicKeyRecord, V2PublicKeyRecordInputSchema
from src.server.v3.models import PATCH_OPERATIONS


class V3DeletedPublicKeyRecord(V2PublicKeyRecord):
    """ The V3DeletedPublicKeyRecord object """

    # pylint: disable=W0622
    def __init__(self, name, public_key, id=None, created=None, deleted=None):
        # Supplied
        self.deleted = deleted or datetime.datetime.now()
        super().__init__(name, public_key=public_key, id=id, created=created)

    def __repr__(self):
        return '<V3DeletedPublicKeyRecord(id={self.id!r})>'.format(self=self)


class V3DeletedPublicKeyRecordInputSchema(V2PublicKeyRecordInputSchema):
    """ A schema specifically for defining and validating user input """

    @post_load
    def make_public_key(self, data):
        """ Marshall an object out of the individual data components """
        return V3DeletedPublicKeyRecord(**data)

    class Meta:  # pylint: disable=missing-docstring
        model = V3DeletedPublicKeyRecord
        unknown = RAISE  # do not allow unknown fields in the schema


class V3DeletedPublicKeyRecordSchema(V3DeletedPublicKeyRecordInputSchema):
    """
    Schema for a fully-formed DeletedRecipeRecord object such as an object being
    read in from a database. Builds upon the basic input fields in
    DeletedRecipeRecordInputSchema.
    """
    id = fields.UUID(description="the unique id of the public_key")
    created = fields.DateTime(description="the time the public_key record was created")
    deleted = fields.DateTime(description="the time the public_key record was deleted")


class V3DeletedPublicKeyRecordPatchSchema(Schema):
    """
    Schema for a updating an PublicKey object.
    """
    operation = fields.Str(required=True,
                           description='The operation or action that should be taken on the recipe record. '
                                       f'Supported operations are: { ", ".join(PATCH_OPERATIONS) }',
                           validate=OneOf(PATCH_OPERATIONS, error="Recipe type must be one of: {choices}."))
