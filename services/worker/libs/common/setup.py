from setuptools import setup, find_packages

setup(
    name="eia-common",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.10.0",
        "pydantic-settings>=2.7.0",
        "sqlalchemy>=2.0.36",
        "structlog>=24.4.0",
    ],
)
