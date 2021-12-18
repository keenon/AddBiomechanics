# syntax=docker/dockerfile:1
FROM ubuntu:20.04

#########################################################
# Set up access to AWS (most of this work sets up IOT)
#########################################################

# Install basic tools
RUN apt-get update && apt-get upgrade
RUN apt-get install -y curl unzip jq
# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install
COPY .aws /root/.aws
# Check that AWS is working
RUN aws iot describe-endpoint --endpoint-type iot:Data-ATS
# Generate a unique device name for this Docker container
RUN echo "$(date '+%s')" > date.txt
RUN echo "Device$(cat date.txt)" > device_name.txt
RUN echo "DevicePolicy$(cat date.txt)" > policy_name.txt
RUN aws iot create-thing --thing-name $(cat device_name.txt)
# Get/Create the certs
RUN mkdir /root/certs
RUN curl -o /root/certs/Amazon-root-CA-1.pem https://www.amazontrust.com/repository/AmazonRootCA1.pem 
RUN aws iot create-keys-and-certificate \
    --set-as-active \
    --certificate-pem-outfile "/root/certs/device.pem.crt" \
    --public-key-outfile "/root/certs/public.pem.key" \
    --private-key-outfile "/root/certs/private.pem.key" > cert.json
RUN echo $(cat cert.json | jq -r '.certificateArn') > certArn.txt
RUN cat certArn.txt
RUN aws iot attach-thing-principal \
    --thing-name "$(cat device_name.txt)" \
    --principal "$(cat certArn.txt)"
COPY ./policy.json /root/policy.json
RUN aws iot create-policy \
    --policy-name "$(cat policy_name.txt)" \
    --policy-document "file://root/policy.json"
RUN aws iot attach-policy \
    --policy-name "$(cat policy_name.txt)" \
    --target "$(cat certArn.txt)"

#########################################################
# Set up the server app
#########################################################

# Install Python 3
RUN apt-get install -y python3 python3-pip
COPY ./app /app
RUN pip3 install -r /app/requirements.txt
CMD python3 /app/simpleserver.py

# Install zip
RUN apt-get install -y zip