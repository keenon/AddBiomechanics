

Install Python 3.9:
1. Using BREW on macos, make sure python 3.9 is installed 
    brew install python@3.9

    you can see a list of brew installed pythons by looking for checkmarks by names of packages after running 'brew search python'

2. Confirm that you installed python3.9 by running
    brew info python@3.9

3. It'll give you a path to where it lives now, like /opt/homebrew/bin/python3.9
    Note that which python3 will return /opt/homebrew/bin/python3, and python3 --version will be Python 3.11.5 (NOT 3.9). This is OK

Setting up Virtual Environment:
1. Create a new virtual environment BASED OFF OF PYTHON 3.9
    virtualenv -p /path/to/specific/pythonX.Y <new_env_name>
    virtualenv -p /opt/homebrew/bin/python3.9 cvpr

2. Activate the new virtual environment:
    source cvpr/bin/activate

3. Test to see that it's pointed to the right python version:
    python3 --version
    Python 3.9.18
