from setuptools import setup
import setuptools

setup(
    name='TAC',
    long_description='file: README.md',
    long_description_content_type="text/markdown",
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Operating System :: OS Independent",
    ],
    project_urls={
        'Homepage': 'https://github.com/JeremieGince/TPAutoCorrect',
        'Source': 'https://github.com/JeremieGince/TPAutoCorrect',
        'Documentation': 'https://JeremieGince.github.io/TPAutoCorrect',
    },
)


# build library
#  setup.py sdist bdist_wheel
# With pyproject.toml
# python -m pip install --upgrade build
# python -m build

# publish on PyPI
#   twine check dist/*
#   twine upload --repository-url https://test.pypi.org/legacy/ dist/*
#   twine upload dist/*

