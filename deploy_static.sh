#!/bin/bash

aws s3 cp static s3://addbiomechanics.org --recursive
aws cloudfront create-invalidation \
    --distribution-id ELBJ4YIAMC8PY \
    --paths "/*"