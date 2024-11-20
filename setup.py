# E:\Projects\ournetwork\pipeline\setup.py
from setuptools import setup, find_packages

setup(
    name="modular_pipeline",
    version="0.1.6",
    description="A library for building modular pipelines in Python",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Brandyn Hamilton",
    author_email="brandynham1120@gmail.com",
    url="https://github.com/BrandynHamilton/Data-Pipeline",
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
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    include_package_data=True,
    zip_safe=False,
)
