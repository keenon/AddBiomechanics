# syntax=docker/dockerfile:1
FROM keenon/biomechnet_base

#########################################################
# Set up access to AWS (most of this work sets up IOT)
#########################################################

# Install basic tools
RUN apt-get update
RUN apt-get install -y curl unzip jq
# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip -o awscliv2.zip && \
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

# Devcontainer specific

RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash
RUN apt-get install -y nodejs
RUN npm install -g yarn

EXPOSE 80
EXPOSE 8080
EXPOSE 3000
EXPOSE 9000