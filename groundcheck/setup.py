"""Setup configuration for GroundCheck library."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="groundcheck",
    version="0.1.0",
    author="CRT Project Contributors",
    description="Verify that LLM outputs are grounded in retrieved context",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/blockhead22/AI_round2",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        # Minimal dependencies - no ML libraries required
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
        "neural": [
            "transformers>=4.30.0",
            "torch>=2.0.0",
            "sentence-transformers>=2.2.0",
        ],
        "all": [
            "transformers>=4.30.0",
            "torch>=2.0.0",
            "sentence-transformers>=2.2.0",
        ],
    },
)
