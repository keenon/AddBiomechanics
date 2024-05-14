#!/bin/bash

docker build -t keenon/biomechnet_dev -f Dockerfile.dev --platform linux/amd64 .
docker push keenon/biomechnet_dev