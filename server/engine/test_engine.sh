#!/bin/bash
set -e

#TEST_NAME="sprinter"
#TEST_NAME="Moore2015"
#TEST_NAME="Moore2015_trimmed"
TEST_NAME="AB06_split5"
#TEST_NAME="falisse2017_small"
#TEST_NAME="Moore2015_trimmed"

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