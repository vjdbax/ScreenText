#!/usr/bin/env python3
"""
Setup script for ScreenText Helper
"""

import os
import sys
from setuptools import setup, find_packages

# Чтение README
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

# Чтение requirements
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name="ScreenText Helper",
    version="1.0.0",
    author="ScreenText Helper Team",
    author_email="support@screentext-helper.com",
    description="Windows приложение для захвата области экрана, распознавания текста и перевода",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/screentext-helper",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Desktop Environment",
        "Topic :: Text Processing :: Linguistic",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-qt>=4.2.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-qt>=4.2.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "screentext-helper=run:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.png", "*.ico", "*.json"],
    },
    zip_safe=False,
    keywords="screen capture ocr text recognition translation windows utility",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/screentext-helper/issues",
        "Source": "https://github.com/yourusername/screentext-helper",
        "Documentation": "https://github.com/yourusername/screentext-helper/wiki",
    },
)