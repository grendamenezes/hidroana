from setuptools import setup, find_packages
 
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
  version='0.0.1',
  description='Download and process hydrological data from ANA (Brazil)',
  long_description = open('README.txt').read() + '\n\n' + open('CHANGELOG.txt').read(),
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
        'zeep'
    ],
  python_requires='>=3.8',

)