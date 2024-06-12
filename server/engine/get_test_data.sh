#!/bin/bash

TARGET=Moore2015_Formatted_With_Arm/subject10

aws s3 cp s3://biomechanics-uploads161949-dev/protected/us-west-2:e013a4d2-683d-48b9-bfe5-83a0305caf87/data/$TARGET ./test_data/${TARGET}_original --recursive