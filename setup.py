
from os import path
from setuptools import setup, find_packages

here = path.abspath(path.dirname(__file__))


setup(
    name='kea2',
    version='0.0.1',
    description="CLI snippets & macro's",
    url='https://github.com/mfiers42/kea2',
    author='Mark Fiers',
    author_email='mark.fiers.42@gmail.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    install_requires=[
        'colorlog',
    ],
    # extras_require={
    #     'dev': ['check-manifest'],
    #     'test': ['coverage'],
    # },
    # package_data={
    #     'sample': ['package_data.dat'],
    # },

    entry_points={
        'console_scripts': [
            'k2=kea2.cli:k2',
            'k2_manage=kea2.cli:k2_manage',
        ],
    },
)
