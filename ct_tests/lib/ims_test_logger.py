# Copyright 2020-2021 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# (MIT License)

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
