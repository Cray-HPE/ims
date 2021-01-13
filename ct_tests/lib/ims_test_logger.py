#!/usr/bin/env python3
# Copyright 2020 Cray Inc. All Rights Reserved.

"""
Test logging and output functions
"""
 
import datetime
import logging
import sys

logfile_path_base = "/opt/cray/tests/ims-build"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

verbose_output = False

#
# Test logging / output functions
#

def info(msg):
    logger.info(msg)
    print(msg)

def section(sname):
    divstr="#"*80
    print("")
    print(divstr)
    info(sname)
    print(datetime.datetime.now())
    print(divstr)
    print("")

def subtest(sname):
    section("Subtest: %s" % sname)

def debug(msg):
    logger.debug(msg)
    if verbose_output:
        print(msg)

def warn(msg, prefix=True):
    logger.warn(msg)
    if prefix:
        print("WARNING: %s" % msg)
    else:
        print(msg)

def error(msg, prefix=True):
    logger.error(msg)
    if prefix:
        sys.stderr.write("ERROR: %s\n" % msg)
    else:
        sys.stderr.write("%s\n" % msg)

def init_logger(logfile_suffix, verbose=False):
    global verbose_output
    verbose_output = verbose
    logfile_path = "%s-%s.log" % (logfile_path_base, logfile_suffix)
    logfile_handler = logging.FileHandler(filename=logfile_path)
    logger.addHandler(logfile_handler)
    logfile_formatter = logging.Formatter(fmt="#LOG#|%(asctime)s.%(msecs)03d|%(levelname)s|%(message)s",datefmt="%Y-%m-%d_%H:%M:%S")
    logfile_handler.setFormatter(logfile_formatter)
    print("Logging to: %s" % logfile_path)
    if verbose_output:
        print("Verbose output enabled")
