# syntax=docker/dockerfile:1
FROM ubuntu:20.04
# This gets published to Docker Hub as keenon/biomechnet_base

RUN apt-get update && apt-get install -y build-essential

# Install Python 3
RUN apt-get install -y python3 python3-pip python3-dev python3-numpy python3-setuptools

# Install NumPy
RUN pip install numpy==1.20.2

# Install zip
RUN apt-get install -y zip

# Install Git
RUN apt-get install -y git

# Install curl
RUN apt-get install -y curl

# Install CMake
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y cmake

# Install blas
RUN apt-get install -y libopenblas-dev liblapack-dev

# Install wget
RUN apt-get install -y wget

# Install pkgconf
RUN apt-get install -y pkgconf

# Install fortran
RUN apt-get install -y gfortran

# Install autoconf and libtool
RUN apt-get install -y autoconf libtool

# Install PCRE2
RUN apt-get install -y libpcre2-dev

# Install yacc
RUN apt-get install -y byacc

# Install SWIG
RUN wget -nc -q --show-progress https://github.com/swig/swig/archive/refs/tags/v4.1.1.tar.gz && \
    tar -xzf v4.1.1.tar.gz && \
    cd swig-4.1.1 && \
    ./autogen.sh && \
    ./configure --prefix=$HOME/swig --disable-ccache && \
    make -j8 && \
    make install && \
    cd .. && \
    rm -rf swig-4.1.1 v4.1.1.tar.gz

# Install OpenSim dependencies
RUN git clone https://github.com/opensim-org/opensim-core.git
RUN mkdir opensim_dependencies_build && \
    cd opensim_dependencies_build && \
    cmake ../opensim-core/dependencies \
        -DCMAKE_INSTALL_PREFIX="~/opensim_dependencies_install" \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DOPENSIM_WITH_CASADI=ON \
        -DOPENSIM_WITH_TROPTER=OFF && \
    make -j4

# Install OpenSim
RUN mkdir opensim_build && \
    cd opensim_build && \
    cmake ../opensim-core \
        -DCMAKE_INSTALL_PREFIX="~/opensim_install" \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DOPENSIM_WITH_CASADI=ON \
        -DOPENSIM_WITH_TROPTER=OFF \
        -DBUILD_PYTHON_WRAPPING=ON \
        -DBUILD_JAVA_WRAPPING=OFF \
        -DOPENSIM_DEPENDENCIES_DIR="~/opensim_dependencies_install" \
        -DOPENSIM_INSTALL_UNIX_FHS=OFF \
        -DSWIG_DIR="~/swig/share/swig" \
        -DSWIG_EXECUTABLE="~/swig/bin/swig" \
        -DWITH_BTK=ON && \
    make -j4 && \
    make install

# Install OpenSim Python interface
RUN cd ~/opensim_install/sdk/Python && \
    python3 setup.py install
ENV LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:/root/opensim_dependencies_install/simbody/lib"

# Test our installation
RUN cd ~/opensim_install/bin && \
    sed -i 's/sudo -k//g' ./opensim-install-command-line.sh && \
    sed -i 's/sudo //g' ./opensim-install-command-line.sh && \
    cat ./opensim-install-command-line.sh && \
    ./opensim-install-command-line.sh
RUN LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/opensim_dependencies_install/ipopt/lib" opensim-cmd