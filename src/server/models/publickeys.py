"""
Public Key Models
Copyright 2018-2020 Hewlett Packard Enterprise Development LP
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
