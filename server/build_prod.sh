#!/bin/bash

docker build -t keenon/biomechnet_prod -f Dockerfile.prod .
docker push keenon/biomechnet_prod