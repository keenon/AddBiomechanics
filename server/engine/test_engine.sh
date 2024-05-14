#!/bin/bash
set -e

#TEST_NAME="sprinter"
TEST_NAME="AB24_split3_tiny"
#TEST_NAME="falisse2017_small"

CURR_DIR=`pwd`
echo $CURR_DIR
rm -rf $CURR_DIR/test_data/${TEST_NAME}
cp -r $CURR_DIR/test_data/${TEST_NAME}_original $CURR_DIR/test_data/${TEST_NAME}
echo $CURR_DIR
python3 src/engine.py $CURR_DIR/test_data/${TEST_NAME}

# Print the last return value
echo $?

# gdb -ex r --args python3 src/engine.py $CURR_DIR/test_data/${TEST_NAME}
# sudo lldb -f python3 -- src/engine.py $CURR_DIR/test_data/grf_test