"""
Image Models
Copyright 2018-2020 Hewlett Packard Enterprise Development LP
"""

import datetime
import uuid

from marshmallow import Schema, fields, post_load, RAISE
from marshmallow.validate import Length

from src.server.models import ArtifactLink


class V2ImageRecord:
    """ The ImageRecord object """

    # pylint: disable=W0622
    def __init__(self, name, link=None, id=None, created=None):
        # Supplied
        self.name = name
        self.link = link

        # derived
        self.id = id or uuid.uuid4()
        self.created = created or datetime.datetime.now()

    def __repr__(self):
        return '<V2ImageRecord(id={self.id!r})>'.format(self=self)


class V2ImageRecordInputSchema(Schema):
    """ A schema specifically for defining and validating user input """
    name = fields.Str(required=True, description="the name of the image",
                      validate=Length(min=1, error="name field must not be blank"))
    link = fields.Nested(ArtifactLink, required=False, allow_none=True,
                         description="the location of the image manifest")

    @post_load
    def make_image(self, data):
        """ Marshall an object out of the individual data components """
        return V2ImageRecord(**data)

    class Meta:  # pylint: disable=missing-docstring
        model = V2ImageRecord
        unknown = RAISE  # do not allow unknown fields in the schema


class V2ImageRecordSchema(V2ImageRecordInputSchema):
    """
    Schema for a fully-formed ImageRecord object such as an object being
    read in from a database. Builds upon the basic input fields in
    ImageRecordInputSchema.
    """
    id = fields.UUID(description="the unique id of the image")
    created = fields.DateTime(description="the time the image record was created")


class V2ImageRecordPatchSchema(Schema):
    """
    Schema for a updating an ImageRecord object.
    """
    link = fields.Nested(ArtifactLink, required=True, allow_none=False,
                         description="the location of the image manifest")
