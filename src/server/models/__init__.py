# Copyright 2018-2021 Hewlett Packard Enterprise Development LP
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

from marshmallow import Schema, fields
from marshmallow.validate import OneOf, Length

from src.server.helper import ARTIFACT_LINK_TYPES


class ArtifactLink(Schema):
    """ A schema specifically for validating artifact links """
    path = fields.Str(required=True, description="URL or path to the artifact",
                      validate=Length(min=1, error="name field must not be blank"))
    etag = fields.Str(required=False, default="", description="Artifact entity tag")
    type = fields.Str(required=True, allow_none=False,
                      description="The type of artifact link",
                      validate=OneOf(ARTIFACT_LINK_TYPES, error="Type must be one of: {choices}."))
