#!/bin/bash

docker build -t keenon/biomechnet_prod -f Dockerfile.prod  --platform linux/amd64 .
docker push keenon/biomechnet_prod