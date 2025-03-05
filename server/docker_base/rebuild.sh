#!/bin/bash

docker build -t keenon/biomechnet_base --platform linux/amd64 .
docker push keenon/biomechnet_base