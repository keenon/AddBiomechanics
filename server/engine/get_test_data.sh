#!/bin/bash

TARGET=Camargo2021_Formatted_No_Arm/AB24_split3

aws s3 cp s3://biomechanics-uploads161949-dev/protected/us-west-2:e013a4d2-683d-48b9-bfe5-83a0305caf87/data/$TARGET ./test_data/${TARGET}_original --recursive