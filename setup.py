import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="atrio",
    version="0.1",
    author="Leonard Gerard",
    author_email="leonard@abundantrobotics.com",
    description="Python tools and library to communicate with trio controller",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AbundantRobotics/atrio",
    packages=setuptools.find_packages(),
    install_requires=[
        "argparse~=1.4.0",
        "argcomplete~=1.11.1",
        "crcmod~=1.7",
        "pytest~=5.4.1",
        "PyYAML~=5.3.1",
        "setuptools~=46.1.3",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'console_scripts': [
            'atrio = atrio.trio_cmd:main',
        ],
    }
)
