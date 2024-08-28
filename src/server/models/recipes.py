#
# MIT License
#
# (C) Copyright 2018-2024 Hewlett Packard Enterprise Development LP
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
Recipe Models
"""

import datetime
import uuid

from marshmallow import Schema, fields, post_load, RAISE
from marshmallow.validate import OneOf, Length
from src.server.models import ArtifactLink
from src.server.helper import ARCH_X86_64, ARCH_ARM64

RECIPE_TYPE_KIWI_NG = 'kiwi-ng'
RECIPE_TYPE_PACKER = 'packer'

LINUX_DISTRIBUTION_SLES12 = 'sles12'
LINUX_DISTRIBUTION_SLES15 = 'sles15'
LINUX_DISTRIBUTION_CENTOS = 'centos7'

RECIPE_TYPES = (RECIPE_TYPE_KIWI_NG, RECIPE_TYPE_PACKER)
LINUX_DISTRIBUTIONS = (LINUX_DISTRIBUTION_SLES12, LINUX_DISTRIBUTION_SLES15, LINUX_DISTRIBUTION_CENTOS)


class RecipeKeyValuePair(Schema):
    """ A schema specifically for defining and validating user input of SSH Containers """
    key = fields.String(metadata={"metadata": {"description": "Template Key"}}, required=True)
    value = fields.String(metadata={"metadata": {"description": "Template Value"}}, required=True)


class V2RecipeRecord:
    """ The RecipeRecord object """

    # pylint: disable=W0622
    def __init__(self, name, recipe_type, linux_distribution, link=None, id=None, created=None,
                 template_dictionary=None, require_dkms=True, arch=ARCH_X86_64):
        # Supplied
        self.name = name
        self.link = link
        self.recipe_type = recipe_type
        self.linux_distribution = linux_distribution
        self.template_dictionary = template_dictionary
        self.require_dkms = require_dkms
        self.arch = arch

        # derived
        self.id = id or uuid.uuid4()
        self.created = created or datetime.datetime.now()

    def __repr__(self):
        return '<V2RecipeRecord(id={self.id!r})>'.format(self=self)


class V2RecipeRecordInputSchema(Schema):
    """ A schema specifically for defining and validating user input """
    # v2.0
    name = fields.Str(required=True, validate=Length(min=1, error="name field must not be blank"),
                      metadata={"metadata": {"description": "Name of the recipe"}})
    link = fields.Nested(ArtifactLink, required=False, allow_none=True,
                         metadata={"metadata": {"description": "Location of the recipe archive"}})
    recipe_type = fields.Str(required=True, validate=OneOf(RECIPE_TYPES, error="Recipe type must be one of: {choices}."),
                            metadata={"metadata": {"description": f"The type of recipe, currently '{RECIPE_TYPE_KIWI_NG}' is the only valid value"}})
    linux_distribution = fields.Str(required=True,metadata={"metadata": {"description": f"The linux distribution of the recipe, either "
                                    f"'{LINUX_DISTRIBUTION_SLES12}' or '{LINUX_DISTRIBUTION_SLES15}' or '{LINUX_DISTRIBUTION_CENTOS}'"}},
                                    validate=OneOf(LINUX_DISTRIBUTIONS, error="Recipe type must be one of: {choices}."))

    # v2.1
    template_dictionary = fields.List(fields.Nested(RecipeKeyValuePair()), required=False, allow_none=True)

    # v2.2
    require_dkms = fields.Boolean(load_default=True, dump_default=True,
                                  metadata={"metadata": {"description": "Recipe requires the use of dkms"}})
    arch = fields.Str(required=False, metadata={"metadata": {"description": "Architecture of the recipe"}},
                          validate=OneOf([ARCH_ARM64,ARCH_X86_64]), load_default=ARCH_X86_64, dump_default=ARCH_X86_64)

    @post_load
    def make_recipe(self, data, many, partial):
        """ Marshall an object out of the individual data components """
        data['template_dictionary'] = data.get('template_dictionary', [])
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
    id = fields.UUID(metadata={"metadata": {"description": "Unique id of the recipe"}})
    created = fields.DateTime(metadata={"metadata": {"description": "Time the recipe record was created"}})


class V2RecipeRecordPatchSchema(Schema):
    """
    Schema for a updating a RecipeRecord object.
    """
    link = fields.Nested(ArtifactLink, required=False, allow_none=False,
                         metadata={"metadata": {"description": "Location of the recipe archive"}})
    arch = fields.Str(required=False, validate=OneOf([ARCH_ARM64,ARCH_X86_64]),
                      load_default=ARCH_X86_64, dump_default=ARCH_X86_64,
                      metadata={"metadata": {"description": "Architecture of the recipe"}})
    require_dkms = fields.Boolean(required=False, load_default=True, dump_default=True,
                                  metadata={"metadata": {"description": "Recipe requires the use of dkms"}})
    template_dictionary = fields.List(fields.Nested(RecipeKeyValuePair()), required=False, allow_none=True)
