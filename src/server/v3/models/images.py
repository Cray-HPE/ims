"""
Copyright 2020 Hewlett Packard Enterprise Development LP
"""
import datetime

from marshmallow import Schema, fields, post_load, RAISE
from marshmallow.validate import OneOf

from src.server.models.images import V2ImageRecord, V2ImageRecordInputSchema
from src.server.v3.models import PATCH_OPERATIONS


class V3DeletedImageRecord(V2ImageRecord):
    """ The ImageRecord object """

    # pylint: disable=W0622
    def __init__(self, name, link=None, id=None, created=None, deleted=None):
        # Supplied
        self.deleted = deleted or datetime.datetime.now()
        super().__init__(name, link=link, id=id, created=created)

    def __repr__(self):
        return '<V3DeletedImageRecord(id={self.id!r})>'.format(self=self)


class V3DeletedImageRecordInputSchema(V2ImageRecordInputSchema):
    """ A schema specifically for defining and validating user input """

    @post_load
    def make_image(self, data):
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
    id = fields.UUID(description="the unique id of the image")
    created = fields.DateTime(description="the time the image record was created")
    deleted = fields.DateTime(description="the time the image record was deleted")


class V3DeletedImageRecordPatchSchema(Schema):
    """
    Schema for a updating an ImageRecord object.
    """
    operation = fields.Str(required=True,
                           description='The operation or action that should be taken on the image record. '
                                       f'Supported operations are: { ", ".join(PATCH_OPERATIONS) }',
                           validate=OneOf(PATCH_OPERATIONS, error="Recipe type must be one of: {choices}."))
