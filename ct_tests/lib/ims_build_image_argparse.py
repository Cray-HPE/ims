#
# MIT License
#
# (C) Copyright 2020-2022 Hewlett Packard Enterprise Development LP
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
"""
Parses command line arguments for IMS image build test
"""
 
import argparse

def nonblank(argname, argvalue):
    if not argvalue:
        raise argparse.ArgumentTypeError("%s name may not be blank" % argname)
    return argvalue

def valid_recipe_name(s):
    return nonblank("Recipe", s)

def valid_initrd_name(s):
    return nonblank("Initrd", s)

def valid_kernel_name(s):
    return nonblank("Kernel", s)

def valid_api_cli(s):
    if s.lower() not in { 'api', 'cli' }:
        raise argparse.ArgumentTypeError('Must specify "api" or "cli"')
    return s.lower()

parser = argparse.ArgumentParser(
    description="Use the IMS API to test building an image using the specified recipe.")
parser.add_argument("-i", dest="initrd", type=valid_initrd_name, 
    help="Name of initrd file to specify for build job (by default none is specified)",
    metavar="initrd_file_name")
parser.add_argument("-k", dest="kernel", type=valid_kernel_name, 
    help="Name of kernel file to specify for build job (by default none is specified)", 
    metavar="kernel_file_name")
parser.add_argument("-v", dest="verbose", action="store_const", const=True, 
    help="Enables verbose output (default: disabled)")
parser.add_argument("api_or_cli", type=valid_api_cli, metavar="api_or_cli", 
    help="Specify api to use the IMS API, or cli to use the IMS CLI")
parser.add_argument("recipe", type=valid_recipe_name, metavar="recipe_name", 
    help="Name of IMS recipe to use for build")

def parse_args():
    args = parser.parse_args()
    test_parameters = dict()
    test_parameters['use_api'] = (args.api_or_cli == 'api')
    if args.initrd:
        test_parameters['initrd_name'] = args.initrd
    else:
        test_parameters['initrd_name'] = None
    if args.kernel:
        test_parameters['kernel_name'] = args.kernel
    else:
        test_parameters['kernel_name'] = args.kernel
    if args.verbose:
        test_parameters['verbose'] = args.verbose
    else:
        test_parameters['verbose'] = False
    test_parameters['recipe_name'] = args.recipe
    return test_parameters
