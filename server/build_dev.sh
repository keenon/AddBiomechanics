#!/bin/bash

docker build -t keenon/biomechnet_dev -f Dockerfile.dev .
docker push keenon/biomechnet_dev