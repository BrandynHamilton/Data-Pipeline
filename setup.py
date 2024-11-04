# E:\Projects\ournetwork\pipeline\setup.py
from setuptools import setup, find_packages

setup(
    name="pipeline",
    version="0.1",
    description="A library for building modular pipelines in Python",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Brandyn Hamilton",
    author_email="brandynham1120@gmail.com",
    url="https://github.com/yourusername/chart_builder",
    packages=find_packages(include=["pipeline", "pipeline.*"]),  # Automatically finds subpackages
    install_requires=[
        "pandas",
        "numpy",
        "plotly",
        "kaleido",
        "pyairtable",
        "python-dotenv",
        "google-analytics-data",
        "google-auth-oauthlib",
        "google-api-python-client"
    ],
    include_package_data=True,
    zip_safe=False,
)
