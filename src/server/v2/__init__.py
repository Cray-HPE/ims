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
v2 API definition, consolidated into its own blueprint.
"""
import json

import httpproblem
from flask import Blueprint
from flask_restful import Api

from src.server.v2.resources.images import V2ImageResource, V2ImageCollection
from src.server.v2.resources.jobs import V2JobResource, V2JobCollection
from src.server.v2.resources.public_keys import V2PublicKeyResource, V2PublicKeyCollection
from src.server.v2.resources.recipes import V2RecipeResource, V2RecipeCollection


app_errors = {
    # Custom 405 error format to conform to RFC 7807
    'MethodNotAllowed': json.loads(
        httpproblem.problem_http_response(405, detail='The method is not allowed for the requested URL.')['body']
    )
}

apiv2_blueprint = Blueprint('api_v2', __name__)
apiv2 = Api(apiv2_blueprint, catch_all_404s=False, errors=app_errors)

# Routes

for uri_prefix, endpoint_prefix in [('', 'root'), ('/v2', 'v2')]:
    apiv2.add_resource(V2PublicKeyResource,
                       '/'.join([uri_prefix, 'public-keys/<public_key_id>']),
                       endpoint='_'.join([endpoint_prefix, 'public_key_resource']))
    apiv2.add_resource(V2PublicKeyCollection,
                       '/'.join([uri_prefix, 'public-keys']),
                       endpoint='_'.join([endpoint_prefix, 'public_keys_collection']))

    apiv2.add_resource(V2RecipeResource,
                       '/'.join([uri_prefix, 'recipes/<recipe_id>']),
                       endpoint='_'.join([endpoint_prefix, 'recipe_resource']))
    apiv2.add_resource(V2RecipeCollection,
                       '/'.join([uri_prefix, 'recipes']),
                       endpoint='_'.join([endpoint_prefix, 'recipe_collection']))

    apiv2.add_resource(V2ImageResource,
                       '/'.join([uri_prefix, 'images/<image_id>']),
                       endpoint='_'.join([endpoint_prefix, 'image_resource']))
    apiv2.add_resource(V2ImageCollection,
                       '/'.join([uri_prefix, 'images']),
                       endpoint='_'.join([endpoint_prefix, 'image_collection']))

    apiv2.add_resource(V2JobResource,
                       '/'.join([uri_prefix, 'jobs/<job_id>']),
                       endpoint='_'.join([endpoint_prefix, 'job_resource']))
    apiv2.add_resource(V2JobCollection,
                       '/'.join([uri_prefix, 'jobs']),
                       endpoint='_'.join([endpoint_prefix, 'job_collection']))
