from setuptools import setup
import lupyne

setup(
    name='lupyne',
    version=lupyne.__version__,
    description='Pythonic search engine based on PyLucene, including a standalone server based on CherryPy.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Aric Coady',
    author_email='aric.coady@gmail.com',
    url='https://github.com/coady/lupyne',
    project_urls={
        'Documentation': 'https://lupyne.surge.sh',
    },
    license='Apache Software License',
    packages=['lupyne', 'lupyne.engine'],
    install_requires=['six'],
    extras_require={'server': ['cherrypy>=11', 'clients>=0.2']},
    python_requires='>=2.7',
    tests_require=['pytest-cov'],
    classifiers=[
        'Development Status :: 6 - Mature',
        'Framework :: CherryPy',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: Indexing',
    ],
)
