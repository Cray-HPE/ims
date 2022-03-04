#
# MIT License
#
# (C) Copyright 2020-2022 Hewlett Packard Enterprise Development LP
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
"""
Recipe API
"""

import http.client
from flask import jsonify, request, current_app
from flask_restful import Resource

from src.server.ims_exceptions import ImsArtifactValidationException, ImsSoftUndeleteArtifactException
from src.server.errors import problemify, generate_missing_input_response, generate_data_validation_failure, \
     generate_resource_not_found_response, generate_patch_conflict
from src.server.helper import validate_artifact, delete_artifact, get_log_id, \
    soft_delete_artifact, soft_undelete_artifact, ARTIFACT_LINK, verify_recipe_link_unique
from src.server.models.recipes import V2RecipeRecordInputSchema, V2RecipeRecordSchema, V2RecipeRecordPatchSchema, \
    V2RecipeRecord
from src.server.v3.models.recipes import V3DeletedRecipeRecordPatchSchema, V3DeletedRecipeRecord, \
    V3DeletedRecipeRecordSchema
from src.server.v3.models import PATCH_OPERATION_UNDELETE

recipe_user_input_schema = V2RecipeRecordInputSchema()
recipe_patch_input_schema = V2RecipeRecordPatchSchema()
deleted_recipe_patch_input_schema = V3DeletedRecipeRecordPatchSchema()
recipe_schema = V2RecipeRecordSchema()
deleted_recipe_schema = V3DeletedRecipeRecordSchema()


class V3BaseRecipeCollection(Resource):
    """
    Common base class for V3Recipes
    """

    recipes_table = 'recipes'
    deleted_recipes_table = 'deleted_recipes'


class V3RecipeCollection(V3BaseRecipeCollection):
    """
    Class representing the operations that can be taken on a collection of recipes
    """

    def get(self):
        """ retrieve a list/collection of recipes """
        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v3.GET", log_id)
        return_json = recipe_schema.dump(iter(current_app.data[self.recipes_table].values()), many=True)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def post(self):
        """ Add a new recipe to the IMS Service.

        A new recipe is created from values that are passed in via the request body. If the recipe already
        exists, then a 400 is returned. If the recipe is created successfully then a 201 is returned.

        """

        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v3.POST", log_id)

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No post data accompanied the POST request.", log_id)
            return generate_missing_input_response()

        current_app.logger.info("%s json_data = %s", log_id, json_data)

        # Validate input
        errors = recipe_user_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the post data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        new_recipe = recipe_schema.load(json_data)

        if new_recipe.link:
            problem = verify_recipe_link_unique(new_recipe.link)
            if problem:
                current_app.logger.info("Link value being set is not unique.")
                return problem

            try:
                validate_artifact(new_recipe.link)
            except ImsArtifactValidationException as exc:
                current_app.logger.info(f"The artifact {new_recipe.link} is not in S3")
                current_app.logger.info(str(exc))
                return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))

        # Save to datastore
        current_app.data[self.recipes_table][str(new_recipe.id)] = new_recipe

        return_json = recipe_schema.dump(new_recipe)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return return_json, 201

    def delete(self):
        """ Delete all recipes. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v3.DELETE", log_id)

        try:
            recipes_to_delete = []
            for recipe_id, recipe in current_app.data[self.recipes_table].items():

                # TODO ADD RECIPE FILTER OPTIONS

                deleted_recipe = V3DeletedRecipeRecord(name=recipe.name, recipe_type=recipe.recipe_type,
                                                       linux_distribution=recipe.linux_distribution,
                                                       id=recipe.id, created=recipe.created, link=recipe.link)
                if deleted_recipe.link:
                    try:
                        deleted_recipe.link = soft_delete_artifact(recipe.link)
                    except ImsArtifactValidationException as exc:
                        current_app.logger.info(f"The artifact {recipe.link} is not in S3 and "
                                                f"was not soft-deleted. Ignoring.")
                        current_app.logger.info(str(exc))
                    except Exception as exc:  # pylint: disable=broad-except
                        current_app.logger.warning("%s Could not soft-delete artifact %s for recipe_id=%s",
                                                   log_id, recipe.link, recipe_id, exc_info=exc)

                current_app.data[self.deleted_recipes_table][recipe_id] = deleted_recipe
                recipes_to_delete.append(recipe_id)

            for recipe_id in recipes_to_delete:
                del current_app.data[self.recipes_table][recipe_id]
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting recipes. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204


class V3RecipeResource(V3BaseRecipeCollection):
    """
    Endpoint for the recipes/{recipe_id} resource.
    """

    def get(self, recipe_id):
        """ Retrieve a recipe. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v3.GET %s", log_id, recipe_id)
        if recipe_id not in current_app.data[self.recipes_table]:
            current_app.logger.info("%s no IMS recipe matches recipe_id=%s", log_id, recipe_id)
            return generate_resource_not_found_response()

        return_json = recipe_schema.dump(current_app.data[self.recipes_table][recipe_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, recipe_id):
        """ Delete an image. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v3.DELETE %s", log_id, recipe_id)

        try:
            recipe = current_app.data[self.recipes_table][recipe_id]
            deleted_recipe = V3DeletedRecipeRecord(name=recipe.name, recipe_type=recipe.recipe_type,
                                                   linux_distribution=recipe.linux_distribution,
                                                   id=recipe.id, created=recipe.created, link=recipe.link)
            if deleted_recipe.link:
                try:
                    deleted_recipe.link = soft_delete_artifact(recipe.link)
                except ImsArtifactValidationException as exc:
                    current_app.logger.info(f"The artifact {recipe.link} is not in S3 and "
                                            f"was not soft-deleted. Ignoring.")
                    current_app.logger.info(str(exc))
                except Exception as exc:  # pylint: disable=broad-except
                    current_app.logger.warning("%s Could not soft-delete artifact %s for recipe_id=%s",
                                               log_id, recipe.link, recipe_id, exc_info=exc)

            current_app.data[self.deleted_recipes_table][recipe_id] = deleted_recipe
            del current_app.data[self.recipes_table][recipe_id]
        except KeyError:
            current_app.logger.info("%s no IMS recipe record matches recipe_id=%s", log_id, recipe_id)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self, recipe_id):
        """ Update an existing recipe record """
        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v3.PATCH %s", log_id, recipe_id)

        if recipe_id not in current_app.data[self.recipes_table]:
            current_app.logger.info("%s no IMS recipe record matches recipe_id=%s", log_id, recipe_id)
            return generate_resource_not_found_response()

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No patch data accompanied the PATCH request.", log_id)
            return generate_missing_input_response()

        # Validate input
        errors = recipe_patch_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the PATCH data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        recipe = current_app.data[self.recipes_table][recipe_id]
        for key, value in list(json_data.items()):
            if key == ARTIFACT_LINK:
                if recipe.link and dict(recipe.link) == value:
                    # The stored link value matches what is trying to be patched.
                    # In this case, for idempotency reasons, do not return failure.
                    pass
                elif recipe.link and dict(recipe.link) != value:
                    current_app.logger.info("%s recipe record cannot be patched since it already has link info", log_id)
                    return generate_patch_conflict()
                else:
                    problem = verify_recipe_link_unique(value)
                    if problem:
                        current_app.logger.info("Link value being set is not unique.")
                        return problem

                    try:
                        validate_artifact(value)
                    except ImsArtifactValidationException as exc:
                        return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))
            else:
                current_app.logger.info("%s Not able to patch record field {} with value {}", log_id, key, value)
                return generate_data_validation_failure(errors=[])

            setattr(recipe, key, value)
        current_app.data[self.recipes_table][recipe_id] = recipe

        return_json = recipe_schema.dump(current_app.data[self.recipes_table][recipe_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)


class V3DeletedRecipeCollection(V3BaseRecipeCollection):
    """
    Class representing the operations that can be taken on a collection of recipes
    """

    def get(self):
        """ Retrieve a list/collection of all deleted recipes """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_recipes.v3.GET", log_id)
        return_json = deleted_recipe_schema.dump(iter(current_app.data[self.deleted_recipes_table].values()), many=True)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self):
        """ Permanently delete all deleted recipes. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_recipes.v3.DELETE", log_id)

        try:
            recipes_to_delete = []
            for deleted_recipe_id, deleted_recipe in current_app.data[self.deleted_recipes_table].items():

                # TODO ADD PUBLIC_KEY FILTER OPTIONS

                if deleted_recipe.link:
                    current_app.logger.info("%s Deleting artifact for deleted_recipe_id: %s", log_id, deleted_recipe_id)
                    try:
                        delete_artifact(deleted_recipe.link)
                    except Exception as exc:  # pylint: disable=broad-except
                        current_app.logger.warning("%s Could not delete artifact %s for deleted_recipe_id=%s",
                                                   log_id, deleted_recipe.link, deleted_recipe_id, exc_info=exc)
                else:
                    current_app.logger.debug("%s No artifact to delete for deleted_recipe_id: %s",
                                             log_id, deleted_recipe_id)

                recipes_to_delete.append(deleted_recipe_id)

            for deleted_recipe_id in recipes_to_delete:
                del current_app.data[self.deleted_recipes_table][deleted_recipe_id]
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting recipes. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self):
        """ Undelete all deleted recipes. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_recipes.v3.PATCH", log_id)

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No patch data accompanied the PATCH request.", log_id)
            return generate_missing_input_response()

        # Validate input
        errors = deleted_recipe_patch_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the PATCH data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        try:  # pylint: disable=too-many-nested-blocks
            recipes_to_undelete = []
            for deleted_recipe_id, deleted_recipe in current_app.data[self.deleted_recipes_table].items():

                # TODO ADD PUBLIC_KEY FILTER OPTIONS

                recipe = V2RecipeRecord(name=deleted_recipe.name, recipe_type=deleted_recipe.recipe_type,
                                        linux_distribution=deleted_recipe.linux_distribution,
                                        id=deleted_recipe.id, created=deleted_recipe.created,
                                        link=deleted_recipe.link)
                for key, value in list(json_data.items()):
                    if key == "operation":
                        if value == PATCH_OPERATION_UNDELETE:
                            try:
                                if recipe.link:
                                    recipe.link = soft_undelete_artifact(recipe.link)

                                current_app.data[self.recipes_table][deleted_recipe_id] = recipe
                                recipes_to_undelete.append(deleted_recipe_id)
                            except ImsArtifactValidationException as exc:
                                return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))
                        else:
                            current_app.logger.info("%s Unsupported patch operation value %s.", log_id, value)
                            return generate_data_validation_failure(errors=[])
                    else:
                        current_app.logger.info('%s Unsupported patch request key="%s" value="%s"', log_id, key, value)
                        return generate_data_validation_failure(errors=[])

            for deleted_recipe_id in recipes_to_undelete:
                del current_app.data[self.deleted_recipes_table][deleted_recipe_id]
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered undeleting recipes. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204


class V3DeletedRecipeResource(V3BaseRecipeCollection):
    """
    Endpoint for the recipes/{deleted_recipe_id} resource.
    """

    def get(self, deleted_recipe_id):
        """ Retrieve a deleted recipe. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_recipes.v3.GET %s", log_id, deleted_recipe_id)
        if deleted_recipe_id not in current_app.data[self.deleted_recipes_table]:
            current_app.logger.info("%s no IMS recipe matches deleted_recipe_id=%s", log_id, deleted_recipe_id)
            return generate_resource_not_found_response()

        return_json = deleted_recipe_schema.dump(current_app.data[self.deleted_recipes_table][deleted_recipe_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, deleted_recipe_id):
        """ Permanently delete a recipe. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_recipes.v3.DELETE %s", log_id, deleted_recipe_id)

        try:
            deleted_recipe = current_app.data[self.deleted_recipes_table][deleted_recipe_id]
            if deleted_recipe.link:
                current_app.logger.info("%s Deleting artifact for deleted_recipe_id: %s", log_id, deleted_recipe_id)
                try:
                    delete_artifact(deleted_recipe.link)
                except Exception as exc:  # pylint: disable=broad-except
                    current_app.logger.warning("%s Could not delete artifact %s for deleted_recipe_id=%s",
                                               log_id, deleted_recipe.link, deleted_recipe_id, exc_info=exc)
            else:
                current_app.logger.debug("%s No artifact to delete for deleted_recipe_id: %s",
                                         log_id, deleted_recipe_id)
            del current_app.data[self.deleted_recipes_table][deleted_recipe_id]
        except KeyError:
            current_app.logger.info("%s no IMS image record matches image_id=%s", log_id, deleted_recipe_id)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self, deleted_recipe_id):
        """ Undelete a deleted recipe record """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_recipes.v3.PATCH %s", log_id, deleted_recipe_id)

        if deleted_recipe_id not in current_app.data[self.deleted_recipes_table]:
            current_app.logger.info("%s no IMS recipe record matches deleted_recipe_id=%s", log_id, deleted_recipe_id)
            return generate_resource_not_found_response()

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No patch data accompanied the PATCH request.", log_id)
            return generate_missing_input_response()

        # Validate input
        errors = deleted_recipe_patch_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the PATCH data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        deleted_recipe = current_app.data[self.deleted_recipes_table][deleted_recipe_id]
        recipe = V2RecipeRecord(name=deleted_recipe.name, recipe_type=deleted_recipe.recipe_type,
                                linux_distribution=deleted_recipe.linux_distribution,
                                id=deleted_recipe.id, created=deleted_recipe.created,
                                link=deleted_recipe.link)
        for key, value in list(json_data.items()):
            if key == "operation":
                if value == PATCH_OPERATION_UNDELETE:
                    if recipe.link:
                        try:
                            recipe.link = soft_undelete_artifact(recipe.link)
                        except ImsSoftUndeleteArtifactException:
                            pass
                        except ImsArtifactValidationException as exc:
                            return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))

                    current_app.data[self.recipes_table][deleted_recipe_id] = recipe
                    del current_app.data[self.deleted_recipes_table][deleted_recipe_id]
                else:
                    current_app.logger.info("%s Unsupported patch operation value %s.", log_id, value)
                    return generate_data_validation_failure(errors=[])
            else:
                current_app.logger.info('%s Unsupported patch request key="%s" value="%s"', log_id, key, value)
                return generate_data_validation_failure(errors=[])

        return None, 204
