#!/bin/bash

amplify env checkout prod
yarn build
aws s3 cp build s3://app.addbiomechanics.org --recursive
aws cloudfront create-invalidation \
    --distribution-id E1360KJ6G6R8KO \
    --paths "/*"