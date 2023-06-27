from setuptools import setup, find_packages

setup(
    name='addbiomechanics',
    version='0.1',
    author='Keenon Werling',
    author_email='keenon@stanford.edu',
    description='A command line interface to conveniently upload bulk data to AddBiomechanics for parallel processing on the cluster',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'addb=addbiomechanics.addb:main',
        ],
    },
    include_package_data=True,
    package_data={
        'addbiomechanics': ['data/**'],
    },
    install_requires=[
        'boto3'
    ]
)
