"""
Copyright 2020 Hewlett Packard Enterprise Development LP
"""
import datetime

from marshmallow import Schema, fields, post_load, RAISE
from marshmallow.validate import OneOf

from src.server.models.recipes import V2RecipeRecordInputSchema, V2RecipeRecord
from src.server.v3.models import PATCH_OPERATIONS


class V3DeletedRecipeRecord(V2RecipeRecord):
    """ The V3DeletedRecipeRecord object """

    # pylint: disable=W0622
    def __init__(self, name, recipe_type, linux_distribution, link=None, id=None, created=None, deleted=None):
        # Supplied
        self.deleted = deleted or datetime.datetime.now()
        super().__init__(name, recipe_type=recipe_type, linux_distribution=linux_distribution,
                         link=link, id=id, created=created)

    def __repr__(self):
        return '<V3DeletedRecipeRecord(id={self.id!r})>'.format(self=self)


class V3DeletedRecipeRecordInputSchema(V2RecipeRecordInputSchema):
    """ A schema specifically for defining and validating user input """

    @post_load
    def make_recipe(self, data):
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
    id = fields.UUID(description="the unique id of the recipe")
    created = fields.DateTime(description="the time the recipe record was created")
    deleted = fields.DateTime(description="the time the recipe record was deleted")


class V3DeletedRecipeRecordPatchSchema(Schema):
    """
    Schema for a updating an RecipeRecord object.
    """
    operation = fields.Str(required=True,
                           description='The operation or action that should be taken on the recipe record. '
                                       f'Supported operations are: { ", ".join(PATCH_OPERATIONS) }',
                           validate=OneOf(PATCH_OPERATIONS, error="Recipe type must be one of: {choices}."))
