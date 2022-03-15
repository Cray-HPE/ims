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
#
HOST=http://127.0.0.1:5000

alias ims-images='curl -s $HOST/images | json_pp'

_post_image_data () {
curl -X POST -H 'Content-Type: application/json' \
       -d "$1" \
       $HOST/images | \
       python -m json.tool
}

ims-create-image () {
export POST_DATA=$(cat <<EOF
{ "name": "test",
  "link": {
    "path": "s3://my_bucket/path/to/image/manifest.json",
    "etag": "foo",
    "type": "s3"
  }
}
EOF
)
_post_image_data $POST_DATA
}


ims-create-image-link-null () {
export POST_DATA=$(cat <<EOF
{ "name": "test",
  "link": null
}
EOF
)
_post_image_data $POST_DATA
}

ims-create-image-no-link () {
export POST_DATA=$(cat <<EOF
{ "name": "test" }
EOF
)
_post_image_data $POST_DATA
}

ims-patch-image () {
export POST_DATA=$(cat <<EOF
{   "link": {
    "path": "s3://my_bucket/path/to/image/manifest.json",
    "etag": "foo",
    "type": "s3"
  }
}
EOF
)
curl -X PATCH -H 'Content-Type: application/json' \
       -d "$POST_DATA" \
       $HOST/images/$1 | \
       python -m json.tool
}


ims-create-image-no-etag () {
export POST_DATA=$(cat <<EOF
{ "name": "test",
  "link": {
    "path": "s3://my_bucket/path/to/image/manifest.json",
    "type": "s3"
  }
}
EOF
)
_post_image_data $POST_DATA
}

ims-create-image-http-type () {
export POST_DATA=$(cat <<EOF
{ "name": "test",
  "link": {
    "path": "s3://my_bucket/path/to/image/manifest.json",
    "etag": "foo",
    "type": "http"
  }
}
EOF
)
_post_image_data $POST_DATA
}

ims-create-image-no-type () {
export POST_DATA=$(cat <<EOF
{ "name": "test",
  "link": {
    "path": "s3://my_bucket/path/to/image/manifest.json",
    "etag": "foo"
  }
}
EOF
)
_post_image_data $POST_DATA
}

ims-create-image-no-name () {
export POST_DATA=$(cat <<EOF
{ "link": {
    "path": "s3://my_bucket/path/to/image/manifest.json",
    "etag": "foo",
    "type": "s3"
  }
}
EOF
)
_post_image_data $POST_DATA
}

ims-delete-image () {
curl -X DELETE $HOST/images/$1
}

ims-get-image () {
curl -X GET $HOST/images/$1 | python -m json.tool
}