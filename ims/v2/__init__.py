"""
v2 API definition, consolidated into its own blueprint.
Copyright 2018, 2019, Cray Inc. All Rights Reserved.
"""
import json

import httpproblem
from flask import Blueprint
from flask_restful import Api

from ims.v2.resources.images import V2ImageResource, V2ImageCollection
from ims.v2.resources.jobs import V2JobResource, V2JobCollection
from ims.v2.resources.public_keys import V2PublicKeyResource, V2PublicKeyCollection
from ims.v2.resources.recipes import V2RecipeResource, V2RecipeCollection

API_VERSION = 1

app_errors = {
    # Custom 405 error format to conform to RFC 7807
    'MethodNotAllowed': json.loads(
        httpproblem.problem_http_response(405, detail='The method is not allowed for the requested URL.')['body']
    )
}

apiv2_blueprint = Blueprint('api_v2', __name__)
apiv2 = Api(apiv2_blueprint, catch_all_404s=False, errors=app_errors)

# Routes

apiv2.add_resource(V2PublicKeyResource,
                   '/public-keys/<public_key_id>',
                   endpoint='public_key_resource')
apiv2.add_resource(V2PublicKeyCollection,
                   '/public-keys',
                   endpoint='public_keys_collection')

apiv2.add_resource(V2RecipeResource,
                   '/recipes/<recipe_id>',
                   endpoint='recipe_resource')
apiv2.add_resource(V2RecipeCollection,
                   '/recipes',
                   endpoint='recipe_collection')

apiv2.add_resource(V2ImageResource,
                   '/images/<image_id>',
                   endpoint='image_resource')
apiv2.add_resource(V2ImageCollection,
                   '/images',
                   endpoint='image_collection')

apiv2.add_resource(V2JobResource,
                   '/jobs/<job_id>',
                   endpoint='job_resource')
apiv2.add_resource(V2JobCollection,
                   '/jobs',
                   endpoint='job_collection')
