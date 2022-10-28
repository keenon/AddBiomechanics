# syntax=docker/dockerfile:1
FROM ubuntu:20.04
# This gets published to Docker Hub as keenon/biomechnet_base

RUN apt-get update

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
    make -j3 && \
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
RUN git clone https://github.com/keenon/opensim-core.git
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
        -DOPENSIM_WITH_CASADI=OFF \
        -DOPENSIM_WITH_TROPTER=OFF \
        -DBUILD_PYTHON_WRAPPING=OFF \
        -DBUILD_JAVA_WRAPPING=OFF \
        -DOPENSIM_DEPENDENCIES_DIR="~/opensim_dependencies_install" \
        -DWITH_BTK=ON && \
    make -j4 && \
    make install

# Test our installation
RUN cd ~/opensim_install/bin && \
    sed -i 's/sudo -k//g' ./opensim-install-command-line.sh && \
    sed -i 's/sudo //g' ./opensim-install-command-line.sh && \
    cat ./opensim-install-command-line.sh && \
    ./opensim-install-command-line.sh
RUN LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/opensim_dependencies_install/ipopt/lib" opensim-cmd