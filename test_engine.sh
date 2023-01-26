#!/bin/bash

TEST_NAME="kirsten_bug" # "opencap_test"

CURR_DIR=`pwd`
echo $CURR_DIR
rm -rf $CURR_DIR/test_data/${TEST_NAME}
cp -r $CURR_DIR/test_data/${TEST_NAME}_original $CURR_DIR/test_data/${TEST_NAME}
pushd server
echo $CURR_DIR
python3 engine/engine.py $CURR_DIR/test_data/${TEST_NAME}
# gdb -ex r --args python3 engine/engine.py $CURR_DIR/test_data/grf_test
# sudo lldb -f python3 -- engine/engine.py $CURR_DIR/test_data/grf_test