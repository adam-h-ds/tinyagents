from setuptools import setup

setup(
    name='tinyagents',
    version='0.1.0',
    description='A tiny, lightweight and unintrusive library for orchestrating agentic applications.',
    author='Adam Hedib (adam-h-ds)',
    license='MIT',
    long_description="A tiny, lightweight and unintrusive library for orchestrating agentic applications.",
    long_description_content_type='text/markdown',
    classifiers=[
        "Programming Language :: Python :: 3"
    ],
    python_requires='>=3.10',
    packages = ['tinyagents'],
    extras_require={
        'dev': [
            "pytest",
            "black"
        ],
        "google": [
            "google-generativeai",
            "google-cloud-aiplatform"
        ]
    },
    include_package_data=True
)