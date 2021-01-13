"""
Copyright 2018-2020 Hewlett Packard Enterprise Development LP
"""

from marshmallow import Schema, fields
from marshmallow.validate import OneOf, Length

ARTIFACT_LINK_TYPE_S3 = 's3'
ARTIFACT_LINK_TYPES = (
    ARTIFACT_LINK_TYPE_S3,
)


class ArtifactLink(Schema):
    """ A schema specifically for validating artifact links """
    path = fields.Str(required=True, description="URL or path to the artifact",
                      validate=Length(min=1, error="name field must not be blank"))
    etag = fields.Str(required=False, default="", description="Artifact entity tag")
    type = fields.Str(required=True, allow_none=False,
                      description="The type of artifact link",
                      validate=OneOf(ARTIFACT_LINK_TYPES, error="Type must be one of: {choices}."))
