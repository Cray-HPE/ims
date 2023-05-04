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
Image Models
"""

import datetime
import uuid

from marshmallow import Schema, fields, post_load, RAISE
from marshmallow.validate import Length, OneOf

from src.server.models import ArtifactLink
from src.server.helper import PLATFORM_X86_64, PLATFORM_ARM64

class V2ImageRecord:
    """ The ImageRecord object """

    # pylint: disable=W0622
    def __init__(self, name, link=None, id=None, created=None, platform=PLATFORM_X86_64):
        # Supplied
        self.name = name
        self.link = link
        
        # v2.1
        self.platform = platform

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
    platform = fields.Str(required=False, default = PLATFORM_X86_64, description="Architecture of the image",
                          validate=OneOf([PLATFORM_ARM64,PLATFORM_X86_64]), load_default=True, dump_default=True)

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
    link = fields.Nested(ArtifactLink, required=False, allow_none=False,
                         description="the location of the image manifest")
    platform = fields.Str(required=False, description="Architecture of the recipe", default=PLATFORM_X86_64,
                          validate=OneOf([PLATFORM_ARM64,PLATFORM_X86_64]), load_default=True, dump_default=True)

