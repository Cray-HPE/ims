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

from src.server.models.recipes import V2RecipeRecordInputSchema, V2RecipeRecord
from src.server.v3.models import PATCH_OPERATIONS
from src.server.helper import ARCH_X86_64, ARCH_ARM64


class V3DeletedRecipeRecord(V2RecipeRecord):
    """ The V3DeletedRecipeRecord object """

    # pylint: disable=W0622
    def __init__(self, name, recipe_type, linux_distribution,
                 link=None, id=None, created=None, deleted=None,
                 template_dictionary=None, require_dkms=False, arch=ARCH_X86_64):
        # Supplied
        self.deleted = deleted or datetime.datetime.now()
        super().__init__(name, recipe_type=recipe_type, linux_distribution=linux_distribution,
                         link=link, id=id, created=created, template_dictionary=template_dictionary,
                         require_dkms=require_dkms, arch=arch)

    def __repr__(self):
        return '<V3DeletedRecipeRecord(id={self.id!r})>'.format(self=self)


class V3DeletedRecipeRecordInputSchema(V2RecipeRecordInputSchema):
    """ A schema specifically for defining and validating user input """

    @post_load
    def make_recipe(self, data, many, partial):
        """ Marshall an object out of the individual data components """
        return V3DeletedRecipeRecord(**data)

    class Meta:  # pylint: disable=missing-docstring
        model = V3DeletedRecipeRecord
        unknown = RAISE  # do not allow unknown fields in the schema


class V3DeletedRecipeRecordSchema(V3DeletedRecipeRecordInputSchema):
    """
    Schema for a fully-formed DeletedRecipeRecord object such as an object being
    read in from a database. Builds upon the basic input fields in
    DeletedRecipeRecordInputSchema.
    """
    id = fields.UUID(metadata={"metadata": {"description": "Unique id of the recipe"}})
    created = fields.DateTime(metadata={"metadata": {"description": "Time the recipe record was created"}})
    deleted = fields.DateTime(metadata={"metadata": {"description": "Time the recipe record was deleted"}})


class V3DeletedRecipeRecordPatchSchema(Schema):
    """
    Schema for a updating an RecipeRecord object.
    """
    operation = fields.Str(required=True,
                           metadata={"metadata": {"description": "The operation or action that should be taken on the recipe record. "
                                                  f'Supported operations are: { ", ".join(PATCH_OPERATIONS) }'}},
                           validate=OneOf(PATCH_OPERATIONS, error="Recipe type must be one of: {choices}."))
