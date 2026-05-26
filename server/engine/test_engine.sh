#!/bin/bash
set -e

TEST_NAME="opencap_test"

CURR_DIR=`pwd`
echo $CURR_DIR
rm -rf $CURR_DIR/tests/data/${TEST_NAME}
cp -r $CURR_DIR/tests/data/${TEST_NAME}_original $CURR_DIR/tests/data/${TEST_NAME}
echo $CURR_DIR
python src/engine.py $CURR_DIR/tests/data/${TEST_NAME}

# Print the last return value
echo $?

# gdb -ex r --args python src/engine.py $CURR_DIR/tests/data/${TEST_NAME}
# sudo lldb -f python3 -- src/engine.py $CURR_DIR/test_data/grf_test