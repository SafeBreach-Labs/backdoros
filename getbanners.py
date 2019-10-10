#!/usr/bin/env python2.7
#
# Copyright (c) 2019, SafeBreach
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#  1. Redistributions of source code must retain the above
# copyright notice, this list of conditions and the following
# disclaimer.
#
#  2. Redistributions in binary form must reproduce the
# above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with
# the distribution.
#
#  3. Neither the name of the copyright holder
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS
# AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
# GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import socket
import sys
import os

####################
# Global Variables #
####################

__version__ = "0.1.0"
__author__ = "Itzik Kotler"
__copyright__ = "Copyright 2019, SafeBreach"

#############
# Functions #
#############


# Based on https://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-filename
def slugify(input):
    return "".join(x for x in input if x.isalnum())


def main(argc, argv):

    if (argc < 2):
        print "MISSING IP/HOSTNAME"
        return -1

    socket.setdefaulttimeout(5)

    target = socket.gethostbyname(argv[1])

    fd = open(slugify(argv[1]) + '.txt', 'w+t')

    for port_num in xrange(0, 1024):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        print "Trying %d/tcp ..." % (port_num)

        if (s.connect_ex((target, port_num)) == 0):

            try:
                data = s.recv(1024)
            except socket.timeout:
                data = "<TIMEOUT>"

            fd.write("%d: %s\n" % (port_num, data))

        s.close()

    fd.close()


###############
# Entry Point #
###############

if __name__ == '__main__':
    main(len(sys.argv), sys.argv)
