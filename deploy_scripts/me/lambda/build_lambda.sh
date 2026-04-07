#!/usr/bin/env bash

PROJECT_DIR='../../../holoscope'

if [ -d build ]; then
  rm -rf build
fi

# Recreate build directory
mkdir -p build/function/ build/layer/

# Copy source files
echo "Copy source files"
cp -p ../../../config.toml build/function/config.toml
cp -p ../../../run.py build/function/


# Pack python libraries
echo "Pack python libraries"
uv pip install -r ../../../requirements.txt --target ./build/layer/python/ --python-platform x86_64-manylinux2014 --python-version 3.13 --only-binary :all:
cp -r $PROJECT_DIR ./build/layer/python/

# Remove pycache in build directory
find build -type f | grep -E "(__pycache__|\.pyc|\.pyo|\.npz$)" | xargs rm
