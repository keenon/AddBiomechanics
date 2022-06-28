#!/bin/bash

amplify env checkout dev
yarn build
aws s3 cp build s3://dev.addbiomechanics.org --recursive
aws cloudfront create-invalidation \
    --distribution-id E3E4XU2LCU9D2 \
    --paths "/*"