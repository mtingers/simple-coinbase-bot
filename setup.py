from distutils.core import setup
import setuptools

setup(
    name='SimpleCoinbaseBot',
    version='1.4.0',
    author='Matth Ingersoll',
    author_email='matth@mtingers.com',
    packages=['simplecoinbasebot',],
    license='BSD 2-Clause License',
    long_description=open('README.md').read(),
    url='https://github.com/mtingers/simple-coinbase-bot',
    install_requires=[
        'filelock>=3.0.12',
        'cbpro>=1.1.4',
    ],
    entry_points={
        'console_scripts': [
            'simplebot=simplecoinbasebot.simplebot:main',
            'simpletop=simplecoinbasebot.top:main',
            'persistbot=simplecoinbasebot.run:main',
        ],
    },
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)


