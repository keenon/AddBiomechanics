#!/bin/bash
set -e

# Generate a unique device name for this Docker container
echo "$(date '+%s')" > date.txt
echo "Device$(cat date.txt)" > device_name.txt
echo "DevicePolicy$(cat date.txt)" > policy_name.txt
aws iot create-thing --thing-name $(cat device_name.txt)
# Get/Create the certs
mkdir -p ~/certs
curl -o ~/certs/Amazon-root-CA-1.pem https://www.amazontrust.com/repository/AmazonRootCA1.pem 
aws iot create-keys-and-certificate \
    --set-as-active \
    --certificate-pem-outfile "~/certs/device.pem.crt" \
    --public-key-outfile "~/certs/public.pem.key" \
    --private-key-outfile "~/certs/private.pem.key" > cert.json
echo $(cat cert.json | jq -r '.certificateArn') > certArn.txt
cat certArn.txt
aws iot attach-thing-principal \
    --thing-name "$(cat device_name.txt)" \
    --principal "$(cat certArn.txt)"
aws iot create-policy \
    --policy-name "$(cat policy_name.txt)" \
    --policy-document "file://${pwd}/../policy.json"
aws iot attach-policy \
    --policy-name "$(cat policy_name.txt)" \
    --target "$(cat certArn.txt)"