from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent

long_description = (this_directory / "README.md").read_text(encoding="utf-8")
 
classifiers=[
    'Development Status :: 4 - Beta',
    'Intended Audience :: Science/Research',
    'Topic :: Scientific/Engineering :: Hydrology',
    'Operating System :: OS Independent',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3'
]
 
setup(
  name='hidroana',
  version='0.0.5',
  description='Download and process hydrological data from ANA (Brazil)',
  long_description=long_description,
  long_description_content_type='text/markdown',
  url='',  
  author='Grenda Menezes',
  author_email='grenda.menezes@gmail.com',
  license='MIT', 
  classifiers=classifiers,
  keywords='hydrology ana brazil rainfall streamflow', 
  packages=find_packages(),
  install_requires=[
        'pandas',
        'tqdm',
        'zeep',
        'geopandas'
    ],
  python_requires='>=3.8',

)
