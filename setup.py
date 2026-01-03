from setuptools import setup, find_packages

setup(
    name="sse",
    version="0.1.0",
    description="Semantic String Engine v0: local semantic compression for text with explicit ambiguity and contradiction preservation.",
    author="AI Assistant",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "scikit-learn",
        "sentence-transformers",
        "jsonschema",
    ],
    entry_points={
        "console_scripts": [
            "sse=sse.cli:main",
        ],
    },
    python_requires=">=3.8",
)
