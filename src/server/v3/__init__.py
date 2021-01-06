"""
v3 API definition, consolidated into its own blueprint.
Copyright 2020 Hewlett Packard Enterprise Development LP
"""
import json

import httpproblem
from flask import Blueprint
from flask_restful import Api

from src.server.v3.resources.images import \
    V3ImageResource, V3ImageCollection, \
    V3DeletedImageResource, V3DeletedImageCollection
from src.server.v3.resources.jobs import V3JobResource, V3JobCollection
from src.server.v3.resources.public_keys import \
    V3PublicKeyResource, V3PublicKeyCollection, \
    V3DeletedPublicKeyResource, V3DeletedPublicKeyCollection
from src.server.v3.resources.recipes import \
    V3RecipeResource, V3RecipeCollection, \
    V3DeletedRecipeResource, V3DeletedRecipeCollection

app_errors = {
    # Custom 405 error format to conform to RFC 7807
    'MethodNotAllowed': json.loads(
        httpproblem.problem_http_response(405, detail='The method is not allowed for the requested URL.')['body']
    )
}

apiv3_blueprint = Blueprint('api_v3', __name__)
apiv3 = Api(apiv3_blueprint, catch_all_404s=False, errors=app_errors)

# Routes
for uri_prefix, endpoint_prefix in [('/v3', 'v3')]:
    apiv3.add_resource(V3PublicKeyResource,
                       '/'.join([uri_prefix, 'public-keys/<public_key_id>']),
                       endpoint='_'.join([endpoint_prefix, 'public_key_resource']))
    apiv3.add_resource(V3PublicKeyCollection,
                       '/'.join([uri_prefix, 'public-keys']),
                       endpoint='_'.join([endpoint_prefix, 'public_keys_collection']))

    apiv3.add_resource(V3DeletedPublicKeyResource,
                       '/'.join([uri_prefix, 'deleted/public-keys/<deleted_public_key_id>']),
                       endpoint='_'.join([endpoint_prefix, 'deleted_public_key_resource']))
    apiv3.add_resource(V3DeletedPublicKeyCollection,
                       '/'.join([uri_prefix, 'deleted/public-keys']),
                       endpoint='_'.join([endpoint_prefix, 'deleted_public_keys_collection']))

    apiv3.add_resource(V3RecipeResource,
                       '/'.join([uri_prefix, 'recipes/<recipe_id>']),
                       endpoint='_'.join([endpoint_prefix, 'recipe_resource']))
    apiv3.add_resource(V3RecipeCollection,
                       '/'.join([uri_prefix, 'recipes']),
                       endpoint='_'.join([endpoint_prefix, 'recipe_collection']))

    apiv3.add_resource(V3DeletedRecipeResource,
                       '/'.join([uri_prefix, 'deleted/recipes/<deleted_recipe_id>']),
                       endpoint='_'.join([endpoint_prefix, 'deleted_recipe_resource']))
    apiv3.add_resource(V3DeletedRecipeCollection,
                       '/'.join([uri_prefix, 'deleted/recipes']),
                       endpoint='_'.join([endpoint_prefix, 'deleted_recipe_collection']))

    apiv3.add_resource(V3ImageResource,
                       '/'.join([uri_prefix, 'images/<image_id>']),
                       endpoint='_'.join([endpoint_prefix, 'image_resource']))
    apiv3.add_resource(V3ImageCollection,
                       '/'.join([uri_prefix, 'images']),
                       endpoint='_'.join([endpoint_prefix, 'image_collection']))

    apiv3.add_resource(V3DeletedImageResource,
                       '/'.join([uri_prefix, 'deleted/images/<deleted_image_id>']),
                       endpoint='_'.join([endpoint_prefix, 'deleted_image_resource']))
    apiv3.add_resource(V3DeletedImageCollection,
                       '/'.join([uri_prefix, 'deleted/images']),
                       endpoint='_'.join([endpoint_prefix, 'deleted_image_collection']))

    apiv3.add_resource(V3JobResource,
                       '/'.join([uri_prefix, 'jobs/<job_id>']),
                       endpoint='_'.join([endpoint_prefix, 'job_resource']))
    apiv3.add_resource(V3JobCollection,
                       '/'.join([uri_prefix, 'jobs']),
                       endpoint='_'.join([endpoint_prefix, 'job_collection']))
