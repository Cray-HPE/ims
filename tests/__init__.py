"""
Copyright 2018, 2019, Cray Inc. All Rights Reserved.
"""
import os.path

import sys

# Add the source directory to the path for convenience when running tests
# from individual files
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
