all:
	python3 setup.py sdist bdist_wheel

init:
	pip install -r requirements.txt

check:
	python3 -m unittest discover -s tests -p '*_test.py'

test: check

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf biomechanics_net.egg-info/