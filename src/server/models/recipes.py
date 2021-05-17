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
"""
Recipe Models
"""

import datetime
import uuid

from marshmallow import Schema, fields, post_load, RAISE
from marshmallow.validate import OneOf, Length
from src.server.models import ArtifactLink

RECIPE_TYPE_KIWI_NG = 'kiwi-ng'
RECIPE_TYPE_PACKER = 'packer'

LINUX_DISTRIBUTION_SLES12 = 'sles12'
LINUX_DISTRIBUTION_SLES15 = 'sles15'
LINUX_DISTRIBUTION_CENTOS = 'centos7'

RECIPE_TYPES = (RECIPE_TYPE_KIWI_NG, RECIPE_TYPE_PACKER)
LINUX_DISTRIBUTIONS = (LINUX_DISTRIBUTION_SLES12, LINUX_DISTRIBUTION_SLES15, LINUX_DISTRIBUTION_CENTOS)


class V2RecipeRecord:
    """ The RecipeRecord object """

    # pylint: disable=W0622
    def __init__(self, name, recipe_type, linux_distribution, link=None, id=None, created=None):
        # Supplied
        self.name = name
        self.link = link
        self.recipe_type = recipe_type
        self.linux_distribution = linux_distribution

        # derived
        self.id = id or uuid.uuid4()
        self.created = created or datetime.datetime.now()

    def __repr__(self):
        return '<V2RecipeRecord(id={self.id!r})>'.format(self=self)


class V2RecipeRecordInputSchema(Schema):
    """ A schema specifically for defining and validating user input """
    name = fields.Str(required=True, description="the name of the recipe",
                      validate=Length(min=1, error="name field must not be blank"))
    link = fields.Nested(ArtifactLink, required=False, allow_none=True,
                         description="the location of the recipe archive")
    recipe_type = fields.Str(required=True,
                             description="The type of recipe, currently '%s' is the only valid value"
                                         % RECIPE_TYPE_KIWI_NG,
                             validate=OneOf(RECIPE_TYPES, error="Recipe type must be one of: {choices}."))
    linux_distribution = fields.Str(required=True,
                                    description="The linux distributiobn of the recipe, either '%s' or '%s' or '%s'"
                                                % (LINUX_DISTRIBUTION_SLES12, LINUX_DISTRIBUTION_SLES15,
                                                   LINUX_DISTRIBUTION_CENTOS),
                                    validate=OneOf(LINUX_DISTRIBUTIONS, error="Recipe type must be one of: {choices}."))

    @post_load
    def make_recipe(self, data):
        """ Marshall an object out of the individual data components """
        return V2RecipeRecord(**data)

    class Meta:  # pylint: disable=missing-docstring
        model = V2RecipeRecord
        unknown = RAISE  # do not allow unknown fields in the schema


class V2RecipeRecordSchema(V2RecipeRecordInputSchema):
    """
    Schema for a fully-formed RecipeRecord object such as an object being
    read in from a database. Builds upon the basic input fields in
    RecipeRecordInputSchema.
    """
    id = fields.UUID(description="the unique id of the recipe")
    created = fields.DateTime(description="the time the recipe record was created")


class V2RecipeRecordPatchSchema(Schema):
    """
    Schema for a updating a RecipeRecord object.
    """
    link = fields.Nested(ArtifactLink, required=True, allow_none=False,
                         description="the location of the recipe archive")
