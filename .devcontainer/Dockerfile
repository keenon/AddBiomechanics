# syntax=docker/dockerfile:1
FROM ubuntu:20.04

#########################################################
# Set up access to AWS (most of this work sets up IOT)
#########################################################

# Install basic tools
RUN apt-get update && apt-get upgrade
RUN apt-get install -y curl unzip jq
# Install AWS CLI
RUN ARCH=`uname -m` && \
    echo "$ARCH" && \
    if [ "$ARCH" = "x86_64" ]; then \
        curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
        unzip awscliv2.zip && \
        ./aws/install; \
    elif [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then \
        curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip" && \
        unzip awscliv2.zip && \
        ./aws/install; \
    else exit; \
    fi
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

# Install zip
RUN apt-get install -y zip

# Install Git
RUN apt-get install -y git

# Install curl
RUN apt-get install -y curl

# Install python
RUN apt-get install -y python3 python3-pip

# Install CMake
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y cmake

# Install blas
RUN apt-get install -y libblas-dev liblapack-dev

# Install wget
RUN apt-get install -y wget

# Install pkgconf
RUN apt-get install -y pkgconf

# Install fortran
RUN apt-get install -y gfortran-10

# Install autoconf and libtool
RUN apt-get install -y autoconf libtool

# Install MUMPS -- there's a race condition in these build files apparently, so you 
# may need to retry this command several times.
RUN git clone https://github.com/coin-or-tools/ThirdParty-Mumps.git && \
    cd ThirdParty-Mumps && \
    ./get.Mumps && \
    FC=$(which gfortran-10) ./configure && \
    make -j14 && \
    make install && \
    cd .. && \
    rm -rf ThirdParty-Mumps

# Install IPOPT
RUN git clone https://github.com/coin-or/Ipopt.git && \
    cd Ipopt && \
    ./configure --with-mumps && \
    make -j14 && \
    make install && \
    cd .. && \
    rm -rf Ipopt && \
    ln -s /usr/local/include/coin-or /usr/local/include/coin

# Install CASADI
RUN git clone https://github.com/casadi/casadi.git && \
    cd casadi && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make -j8 && \
    make install && \
    cd ../.. && \
    rm -rf casadi

# Install autoconf and libtool
RUN apt-get install -y autoconf libtool libadolc2

# Install OpenSim dependencies
RUN git clone https://github.com/opensim-org/opensim-core.git
RUN mkdir opensim_dependencies_build && \
    cd opensim_dependencies_build && \
    cmake ../opensim-core/dependencies \
        -DCMAKE_INSTALL_PREFIX="~/opensim_dependencies_install" \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DSUPERBUILD_casadi=OFF \
        -DSUPERBUILD_ipopt=OFF && \
    make -j8

# Install OpenSim
RUN mkdir opensim_build && \
    cd opensim_build && \
    cmake ../opensim-core \
        -DCMAKE_INSTALL_PREFIX="~/opensim_install" \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DBUILD_PYTHON_WRAPPING=OFF \
        -DBUILD_JAVA_WRAPPING=OFF \
        -DOPENSIM_DEPENDENCIES_DIR="~/opensim_dependencies_install" \
        -DWITH_BTK=ON && \
    make -j3 && \
    make install

# Test our installation
RUN cd ~/opensim_install/bin && \
    sed -i 's/sudo -k//g' ./opensim-install-command-line.sh && \
    sed -i 's/sudo //g' ./opensim-install-command-line.sh && \
    cat ./opensim-install-command-line.sh && \
    ./opensim-install-command-line.sh
RUN LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/opensim_dependencies_install/ipopt/lib" opensim-cmd

# Devcontainer specific

RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash
RUN apt-get install -y nodejs
RUN npm install -g yarn

EXPOSE 80
EXPOSE 8080
EXPOSE 3000
EXPOSE 9000