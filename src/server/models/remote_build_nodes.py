#
# MIT License
#
# (C) Copyright 2023-2024 Hewlett Packard Enterprise Development LP
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
Remote Build Nodes
"""

import socket
from flask import current_app as app

from marshmallow import Schema, fields, post_load, RAISE
from marshmallow.validate import Length, OneOf

from fabric import Connection
from paramiko.ssh_exception import (SSHException, NoValidConnectionsError, 
                                    AuthenticationException, BadHostKeyException)
from invoke.exceptions import UnexpectedExit, Failure

from src.server.helper import ARCH_ARM64, ARCH_X86_64

class V3RemoteBuildNodeRecord:
    """ The RemoteBuildNodeRecord object """

    # pylint: disable=W0622
    def __init__(self, xname):
        # Supplied
        self.xname = xname

    def __repr__(self):
        return '<V3RemoteBuildNodeRecord(xname={self.xname!r})>'.format(self=self)

    def getStatus(self) -> (str, int): #(arch, current jobs)
        """
        Utility function to verify that a node is set up and available for remote
        builds. If the node can not be contacted or is not set up for running IMS
        jobs, this will return (None,None)
        
        Returns:
            Archetecture of the node if it can be determined
            Number of jobs currently running on the node

        """

        # start with status Invalid
        arch = None
        numJobs = None

        # connect to the remote node
        connect_kwargs = {"key_filename": "/app/id_ecdsa"}
        c = Connection(self.xname, user="root", connect_kwargs=connect_kwargs)

        # validate the connection
        try: 
            c.open()
        except (BadHostKeyException, AuthenticationException, NoValidConnectionsError,
                SSHException, socket.error) as error:
            app.logger.error(f"Unable to connect to node: {self.xname}, Error: {error}")
            return arch, numJobs

        # make sure the above connection gets closed on exit
        try:
            # get arch of the system
            try:
                # query node for arch
                result = c.run("uname -i", hide=True)

                # check result
                if result.exited != 0:
                    app.logger.error(f"Unable to determine archecture of node: {self.xname}, Error: {result.stdout} {result.stderr}")
                    return arch, numJobs

                # see if we can pull out a known arch type
                if "aarch64" in result.stdout:
                    arch = ARCH_ARM64
                elif "x86" in result.stdout:
                    arch = ARCH_X86_64
                else:
                    app.logger.error(f"Unable to determine archecture of node: {self.xname}, Error: {result.stdout}")
                    return arch, numJobs
            except (UnexpectedExit, Failure) as error:
                app.logger.error(f"Unable to determine archecture of node: {self.xname}, Error: {error}")
                return arch, numJobs

            # insure it has podman installed
            try:
                # query node for arch
                result = c.run("which podman", hide=True)

                # check result
                if result.exited != 0:
                    app.logger.error(f"Unable to determine if podman is installed on node: {self.xname}, Error: {result.stdout} {result.stderr}")
                    return None,None

                # see if we can pull out a known arch type
                if "/usr/bin/podman" not in result.stdout:
                    app.logger.error(f"Podman not installed on node: {self.xname}, Error: {result.stdout}")
                    return
            except (UnexpectedExit, Failure) as error:
                app.logger.error(f"Unable determine if tools are installed on node: {self.xname}, Error: {error}")
                return None,None

            # Every running IMS job will create a working directory '/tmp/ims_(IMS_JOB_ID)'.
            # Count the number of these directories to find the number of running jobs on
            # the node - they are cleaned up when the job is complete on the node.
            # execute: "ls -d1 /tmp/* | grep /tmp/ims_ | wc -l"
            try:
                result = c.run("ls -d1 /tmp/* | grep /tmp/ims_ | wc -l", hide=True)
                if result.exited != 0:
                    # let this go through and schedule a job on the node
                    app.logger.error(f"Unable to determine number of jobs on node: {self.xname}, Error: {result.stdout} {result.stderr}")
                    numJobs = 0
                else:
                    numJobs = int(result.stdout)
            except (UnexpectedExit, Failure) as error:
                # Just log this, but allow the job to run
                app.logger.error(f"Unable determine number of running jobs on node: {self.xname}, Error: {error}")
                numJobs = 0
        finally:
            # close tha active connection
            c.close()

        return arch, numJobs


class V3RemoteBuildNodeRecordInputSchema(Schema):
    """ A schema specifically for defining and validating user input """
    xname = fields.Str(required=True, metadata={"metadata": {"description": "XName of the remote build node"}},
                      validate=Length(min=1, error="name field must not be blank"))

    @post_load
    def make_remote_build_node(self, data, many, partial):
        """ Marshall an object out of the individual data components """
        return V3RemoteBuildNodeRecord(**data)

    class Meta:  # pylint: disable=missing-docstring
        model = V3RemoteBuildNodeRecord
        unknown = RAISE  # do not allow unknown fields in the schema


class V3RemoteBuildNodeRecordSchema(V3RemoteBuildNodeRecordInputSchema):
    """
    Schema for a fully-formed RemoteBuildNode object such as an object being
    read in from a database. Builds upon the basic input fields in
    RemoteBuildNodeInputSchema.
    """