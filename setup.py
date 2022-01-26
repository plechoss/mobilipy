from setuptools import setup, find_packages

VERSION = '0.1.9' 
DESCRIPTION = 'A mobility analysis package developed at the Swiss Data Science Center'

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Setting up
setup(
       # the name must match the folder name 'sdscmob'
        name="mobilipy", 
        version=VERSION,
        author="Michal Pleskowicz",
        author_email="<michal.pleskowicz@gmail.com>",
        description=DESCRIPTION,
        long_description=long_description,
        long_description_content_type='text/markdown',
        packages=find_packages(),
        install_requires=[], # add any additional packages that 
        # needs to be installed along with your package. Eg: 'caer'
        
        keywords=['python', 'mobility', 'gps', 'trips', 'first package'],
        classifiers= [
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Education",
            "Programming Language :: Python :: 3",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: Microsoft :: Windows",
        ]
)