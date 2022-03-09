#
# MIT License
#
# (C) Copyright 2018-2022 Hewlett Packard Enterprise Development LP
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
Public Key Models
"""

import datetime
import uuid

from marshmallow import Schema, fields, post_load, RAISE
from marshmallow.validate import Length


class V2PublicKeyRecord:
    """ The PublicKeyRecord object """

    # pylint: disable=W0622
    def __init__(self, name, public_key, id=None, created=None):
        # Supplied
        self.name = name
        self.public_key = public_key

        # derived
        self.id = id or uuid.uuid4()
        self.created = created or datetime.datetime.now()

    def __repr__(self):
        return '<V2PublicKeyRecord(id={self.id!r})>'.format(self=self)


class V2PublicKeyRecordInputSchema(Schema):
    """ A schema specifically for defining and validating user input """
    name = fields.Str(required=True, description="A name to identify the public key",
                      validate=Length(min=1, error="name field must not be blank"))
    public_key = fields.Str(required=True, description="The raw public key file contents",
                            validate=Length(min=1, error="public_key field must not be blank"))

    @post_load
    def make_public_key(self, data):
        """ Marshall an object out of the individual data components """
        return V2PublicKeyRecord(**data)

    class Meta:  # pylint: disable=missing-docstring
        model = V2PublicKeyRecord
        unknown = RAISE  # do not allow unknown fields in the schema


class V2PublicKeyRecordSchema(V2PublicKeyRecordInputSchema):
    """
    Schema for a fully-formed PublicKeyRecord object such as an object being
    read in from a database. Builds upon the basic input fields in
    PublicKeyRecordInputSchema.
    """
    id = fields.UUID(description="the unique id of the public key")
    created = fields.DateTime(description="the time the public key9 record was created")
