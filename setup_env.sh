#!/bin/bash

# Upgrade pip
python3 -m pip install --upgrade pip

# Install pytest
pip install pytest

# (Optional but recommended) install project in editable mode
pip install -e .

