import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="Helper Library",
    version="0.0.1",
    author="Arturo Minor",
    author_email="arbahena@amazon.com",
    description="Helper classes",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    install_requires=[
        'boto3',
        'urllib3'
    ]
)
