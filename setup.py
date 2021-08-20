import pathlib
from setuptools import setup, find_packages

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="biomechanicsnet",
    version="0.0.1",
    description="An aggregated dataset of biomechanics data",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/keenon/BiomechanicsNet",
    author="Keenon Werling",
    author_email="keenonwerling@gmail.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    packages=find_packages(exclude=("tests",)),
    include_package_data=True,
    install_requires=["nimblephysics", "numpy"],
    entry_points={
        "console_scripts": [
            "realpython=reader.__main__:main",
        ]
    },
)
