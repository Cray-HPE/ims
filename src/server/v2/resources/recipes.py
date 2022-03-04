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
"""
Recipe API
"""

import http.client
from flask import jsonify, request, current_app
from flask_restful import Resource

from src.server.ims_exceptions import ImsArtifactValidationException
from src.server.errors import problemify, generate_missing_input_response, generate_data_validation_failure, \
     generate_resource_not_found_response, generate_patch_conflict
from src.server.helper import validate_artifact, delete_artifact, get_log_id, ARTIFACT_LINK, verify_recipe_link_unique
from src.server.models.recipes import V2RecipeRecordInputSchema, V2RecipeRecordSchema, V2RecipeRecordPatchSchema

recipe_user_input_schema = V2RecipeRecordInputSchema()
recipe_patch_input_schema = V2RecipeRecordPatchSchema()
recipe_schema = V2RecipeRecordSchema()


class V2RecipeCollection(Resource):
    """
    Class representing the operations that can be taken on a collection of recipes
    """

    def get(self):
        """ retrieve a list/collection of recipes """
        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v2.GET", log_id)
        return_json = recipe_schema.dump(iter(current_app.data["recipes"].values()), many=True)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def post(self):
        """ Add a new recipe to the IMS Service.

        A new recipe is created from values that are passed in via the request body. If the recipe already
        exists, then a 400 is returned. If the recipe is created successfully then a 201 is returned.

        """

        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v2.POST", log_id)

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
                current_app.logger.info("Link value being set is not unique")
                return problem

            try:
                validate_artifact(new_recipe.link)
            except ImsArtifactValidationException as exc:
                return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))

        # Save to datastore
        current_app.data['recipes'][str(new_recipe.id)] = new_recipe

        return_json = recipe_schema.dump(new_recipe)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return return_json, 201

    def delete(self):
        """ Delete all recipes. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v2.DELETE", log_id)

        try:
            if request.args.get("cascade", 'True').lower() in ['true', 'yes', 't', '1']:
                for recipe_id, recipe_record in current_app.data['recipes'].items():
                    if recipe_record.link:
                        current_app.logger.info("%s Deleting artifact for recipe_id: %s", log_id, recipe_id)
                        try:
                            delete_artifact(recipe_record.link)
                        except Exception as exc:  # pylint: disable=broad-except
                            current_app.logger.warning("%s Could not delete artifact %s for recipe_id=%s",
                                                       log_id, recipe_record.link, recipe_id, exc_info=exc)
                    else:
                        current_app.logger.debug("%s No artifact to delete for recipe_id: %s", log_id, recipe_id)
            del current_app.data['recipes']
            current_app.data['recipes'] = {}
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting recipes. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204


class V2RecipeResource(Resource):
    """
    Endpoint for the recipes/{recipe_id} resource.
    """

    def get(self, recipe_id):
        """ Retrieve a recipe. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v2.GET %s", log_id, recipe_id)
        if recipe_id not in current_app.data["recipes"]:
            current_app.logger.info("%s no IMS recipe matches recipe_id=%s", log_id, recipe_id)
            return generate_resource_not_found_response()

        return_json = recipe_schema.dump(current_app.data['recipes'][recipe_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, recipe_id):
        """ Delete a recipe. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v2.DELETE %s", log_id, recipe_id)

        try:
            if request.args.get("cascade", 'True').lower() in ['true', 'yes', 't', '1']:
                recipe = current_app.data['recipes'][recipe_id]
                if recipe.link:
                    current_app.logger.info("%s Deleting artifact", log_id)
                    try:
                        delete_artifact(recipe.link)
                    except Exception as exc:  # pylint: disable=broad-except
                        current_app.logger.warning("%s Could not delete artifact %s",
                                                   log_id, recipe.link, exc_info=exc)
                else:
                    current_app.logger.debug("%s No artifact to delete", log_id)
            del current_app.data['recipes'][recipe_id]
        except KeyError:
            current_app.logger.info("%s no IMS recipe matches recipe_id=%s", log_id, recipe_id)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self, recipe_id):
        """ Update an existing recipe record """
        log_id = get_log_id()
        current_app.logger.info("%s ++ recipes.v2.PATCH %s", log_id, recipe_id)

        if recipe_id not in current_app.data["recipes"]:
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

        recipe = current_app.data["recipes"][recipe_id]
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
                        current_app.logger.info("Link value being set is not unique")
                        return problem

                    try:
                        validate_artifact(value)
                    except ImsArtifactValidationException as exc:
                        return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))
            else:
                current_app.logger.info("%s Not able to patch record field {} with value {}", log_id, key, value)
                return generate_data_validation_failure(errors=[])

            setattr(recipe, key, value)
        current_app.data['recipes'][recipe_id] = recipe

        return_json = recipe_schema.dump(current_app.data['recipes'][recipe_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)
