# -*- coding: utf-8 -*-
# Copyright (C) 2018 Greenbone Networks GmbH
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import configparser
import getpass
import logging
import os.path
import sys

from gmp.helper import get_version
from gmp.gmp import (SSHConnection,
                     TLSConnection,
                     UnixSocketConnection)

__version__ = get_version()

logger = logging.getLogger(__name__)

help_text = """
    gvm-cli {version} (C) 2017 Greenbone Networks GmbH

    This program is a command line tool to access services via
    GMP (Greenbone Management Protocol).

    Examples:

    gvm-cli socket --xml "<get_version/>"
    gvm-cli socket --xml "<commands><authenticate><credentials><username>myuser</username><password>mypass</password></credentials></authenticate><get_tasks/></commands>"
    gvm-cli socket --gmp-username foo --gmp-password foo < myfile.gmp

    Further Information about GMP see here:
    http://docs.greenbone.net/index.html#api_documentation
    Note: "GMP" was formerly known as "OMP".

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
    """.format(version=__version__)


def main():

    parser = argparse.ArgumentParser(
        prog='gvm-cli',
        description=help_text,
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
        epilog="""
usage: gvm-cli [-h] [--version] [connection_type] ...
   or: gvm-cli connection_type --help""")

    subparsers = parser.add_subparsers(metavar='[connection_type]')
    subparsers.required = True
    subparsers.dest = 'connection_type'

    parser.add_argument(
        '-h', '--help', action='help',
        help='Show this help message and exit.')

    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        '-c', '--config', nargs='?', const='~/.config/gvm-tools.conf',
        help='Configuration file path. Default: ~/.config/gvm-tools.conf')
    args, remaining_args = parent_parser.parse_known_args()

    defaults = {
        'gmp_username': '',
        'gmp_password': ''
    }

    # Retrieve data from config file
    if args.config:
        try:
            config = configparser.SafeConfigParser()
            path = os.path.expanduser(args.config)
            config.read(path)
            defaults = dict(config.items('Auth'))
        except Exception as e:
            print(str(e))

    parent_parser.set_defaults(**defaults)

    parent_parser.add_argument(
        '--timeout', required=False, default=60, type=int,
        help='Wait <seconds> for response or if value -1, then wait '
             'continuously. Default: 60')
    parent_parser.add_argument(
        '--log', nargs='?', dest='loglevel', const='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Activates logging. Default level: INFO.')
    parent_parser.add_argument('--gmp-username', help='GMP username.')
    parent_parser.add_argument('--gmp-password', help='GMP password.')
    parent_parser.add_argument('-X', '--xml', help='The XML request to send.')
    parent_parser.add_argument('-r', '--raw', help='Return raw XML.',
                               action='store_true', default=False)
    parent_parser.add_argument('infile', nargs='?', type=open,
                               default=sys.stdin)
    parser_ssh = subparsers.add_parser(
        'ssh', help='Use SSH connection for gmp service.',
        parents=[parent_parser])
    parser_ssh.add_argument('--hostname', required=True,
                            help='Hostname or IP-Address.')
    parser_ssh.add_argument('--port', required=False,
                            default=22, help='Port. Default: 22.')
    parser_ssh.add_argument('--ssh-user', default='gmp',
                            help='SSH Username. Default: gmp.')

    parser_tls = subparsers.add_parser(
        'tls', help='Use TLS secured connection for gmp service.',
        parents=[parent_parser])
    parser_tls.add_argument('--hostname', required=True,
                            help='Hostname or IP-Address.')
    parser_tls.add_argument('--port', required=False,
                            default=9390, help='Port. Default: 9390.')
    parser_tls.add_argument('--certfile', required=False, default=None,
                            help='Path to the certificate file.')
    parser_tls.add_argument('--keyfile', required=False, default=None,
                            help='Path to key certificate file.')
    parser_tls.add_argument('--cafile', required=False, default=None,
                            help='Path to CA certificate file.')

    parser_socket = subparsers.add_parser(
        'socket', help='Use UNIX-Socket connection for gmp service.',
        parents=[parent_parser])
    parser_socket.add_argument(
        '--sockpath', nargs='?', default='/usr/local/var/run/gvmd.sock',
        help='UNIX-Socket path. Default: /usr/local/var/run/gvmd.sock.')

    parser.add_argument(
        '-V', '--version', action='version',
        version='%(prog)s {version}'.format(version=__version__),
        help='Show program\'s version number and exit')

    args = parser.parse_args(remaining_args)

    # Sets the logging
    if args.loglevel is not None:
        level = logging.getLevelName(args.loglevel)
        logging.basicConfig(filename='gvm-cli.log', level=level)

    # If timeout value is -1, then the socket has no timeout for this session
    if args.timeout == -1:
        args.timeout = None

    xml = ''

    if args.xml is not None:
        xml = args.xml
    else:
        # If this returns False, then some data are in sys.stdin
        if not args.infile.isatty():
            try:
                xml = args.infile.read()
            except (EOFError, BlockingIOError) as e:
                print(e)

    # If no command was given, program asks for one
    if len(xml) == 0:
        xml = input()

    # Remove all newlines if the commands come from file
    xml = xml.replace('\n', '').replace('\r', '')

    # Ask for password if none are given
    if args.gmp_username and not args.gmp_password:
        args.gmp_password = getpass.getpass('Enter password for ' +
                                            args.gmp_username + ': ')

    # Open the right connection. SSH at last for default
    try:
        if 'socket' in args.connection_type:
            gvm = UnixSocketConnection(sockpath=args.sockpath,
                                       raw_response=args.raw,
                                       timeout=args.timeout)
        elif 'tls' in args.connection_type:
            gvm = TLSConnection(hostname=args.hostname, port=args.port,
                                certfile=args.certfile,
                                keyfile=args.keyfile,
                                cafile=args.cafile,
                                raw_response=args.raw, timeout=args.timeout)
        else:
            gvm = SSHConnection(
                hostname=args.hostname, port=args.port, timeout=args.timeout,
                raw_response=args.raw, ssh_user=args.ssh_user, ssh_password='')
    except Exception as e:
        print(e)
        sys.exit(1)

    if args.gmp_username:
        gvm.authenticate(args.gmp_username, args.gmp_password)

    gvm.send(xml)

    result = gvm.read()
    print(result)
    gvm.close()

    sys.exit(0)


if __name__ == '__main__':
    main()
