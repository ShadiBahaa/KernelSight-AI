#!/usr/bin/env python3
"""Setup script for KernelSight AI CLI"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="kernelsight",
    version="0.1.0",
    description="Autonomous SRE Agent - eBPF-based system monitoring with AI-powered remediation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="KernelSight AI Team",
    author_email="kernelsight@example.com",
    url="https://github.com/kernelsight/kernelsight-ai",
    
    # Package configuration
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    py_modules=["kernelsight"],
    
    # Dependencies
    install_requires=[
        "rich>=13.0.0",
        "google-genai>=1.55.0",
    ],
    
    # Optional dependencies
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ],
    },
    
    # CLI scripts
    entry_points={
        "console_scripts": [
            "kernelsight=kernelsight:main",
        ],
    },
    
    # Metadata
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    
    python_requires=">=3.8",
    
    # Include additional files
    include_package_data=True,
    zip_safe=False,
)
