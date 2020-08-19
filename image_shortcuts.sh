# Copyright 2020, Cray Inc. All Rights Reserved.

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