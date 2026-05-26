#!/bin/bash

docker build -t keenon/biomechnet_dev -f Dockerfile.dev --platform linux/amd64 .
