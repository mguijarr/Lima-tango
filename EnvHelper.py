############################################################################
# This file is part of LImA, a Library for Image Acquisition
#
# Copyright (C) : 2009-2011
# European Synchrotron Radiation Facility
# BP 220, Grenoble 38043
# FRANCE
#
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
############################################################################

import os, tempfile, re, imp
from subprocess import Popen, PIPE

FindCoreVerHelperPy = """
import os, sys, PyTango

class LimaCCDs(PyTango.Device_4Impl):
    def __init__(self, *args) :
        PyTango.Device_4Impl.__init__(self,*args)
        self.get_device_properties(self.get_device_class())
        print 'LimaCameraType=%s' % self.LimaCameraType
        sys.exit(0)

class LimaCCDsClass(PyTango.DeviceClass):
    device_property_list = {
        'LimaCameraType':
        	[PyTango.DevString, "Camera Plugin name",[]],
        'NbProcessingThread':
        	[PyTango.DevString, "Number of thread for processing", [2]],
        'AccThresholdCallbackMoedule':
        	[PyTango.DevString, "Plugin name file which manage threshold",
                 []],
    }

tango_util = PyTango.Util(sys.argv)
tango_util.add_TgClass(LimaCCDsClass, LimaCCDs, 'LimaCCDs')
tango_util_inst = PyTango.Util.instance()
tango_util_inst.server_init()
tango_util_inst.server_run()
"""

ModDepend = ['Core', 'Espia']
Debug = 0
LimaDir = None

def setup_lima_env(argv):
    if not check_args(argv):
        return
    if check_link_strict_version() != 'FULL':
        return
    tdir = tempfile.gettempdir()
    sname = os.path.basename(argv[0])
    pname = sname.split('.py')[0] + '.py'
    aux_py_name = os.path.join(tdir, pname)
    aux_py = open(aux_py_name, 'wt')
    aux_py.write(FindCoreVerHelperPy)
    aux_py.close()
    args = ['python', aux_py_name] + argv[1:]
    pobj = Popen(args, stdout=PIPE, stderr=PIPE)
    output = {}
    for l in pobj.stdout.readlines():
        key, val = l.strip().split('=')
        output[key] = val
    del aux_py
    os.unlink(aux_py_name)
    print_debug('Got from TANGO database: %s' % output)
    cdir = os.path.join(os.path.dirname(__file__), 'camera')
    cfile_name = os.path.join(cdir, output['LimaCameraType'] + '.py')
    cfile = open(cfile_name, 'rt')
    pre_str = '^[ \t]*from[ ]+Lima[ ]+import[ ]+(?P<plugin>[A-Za-z0-9_]+)'
    pre_obj = re.compile(pre_str)
    vers = {}
    for l in cfile.readlines():
        m = pre_obj.match(l)
        if not m:
            continue
        pname = m.group('plugin')
        print_debug('Found %s import in %s' % (pname, cfile_name))
        if pname not in ['Core']:
            setup_env(pname)
    for k, v in os.environ.items():
        if 'LIMA_' in k and '_VERSION' in k:
            print_debug('Env: %s=%s' % (k, v))

def check_args(argv):
    global Debug
    for arg in argv:
        if arg.startswith('-v'):
            try:
                Debug = max(0, int(arg[2:]) - 1)
            except:
                pass
    return 1

def check_link_strict_version():
    cmd = 'from Lima import Core; '
    cmd += 'import os; print os.environ["LIMA_LINK_STRICT_VERSION"]'
    args = ['python', '-c', cmd]
    pobj = Popen(args, stdout=PIPE)
    strict_link = pobj.stdout.readline().strip()
    print_debug('LIMA_LINK_STRICT_VERSION=%s' % strict_link)
    return strict_link.upper()

def setup_env(mod):
    pvers = find_dep_vers(mod)
    all_vers = list(pvers.keys())
    all_vers.sort(version_cmp)
    env_var_name = 'LIMA_%s_VERSION' % mod.upper()
    if env_var_name in os.environ:
        ver = os.environ[env_var_name]
        if ver[0] != 'v':
            ver = 'v' + ver
        if ver not in all_vers:
            print 'Warning: could not find %s=%s' % (env_var_name, ver)
            return
    else:
        ver = all_vers[-1]
        os.environ[env_var_name] = ver[1:]
    deps = pvers[ver]
    for dname, dver in deps.items():
        env_var_name = 'LIMA_%s_VERSION' % dname.upper()
        os.environ[env_var_name] = dver
        if dname != 'Core':
            setup_env(dname)
    
def find_dep_vers(mod):
    vers = {}
    vre_str = 'v[0-9]+\.[0-9]+\.[0-9]+'
    vre_obj = re.compile(vre_str)
    pdir = os.path.join(check_lima_dir(), mod)
    for vdir in os.listdir(pdir):
        if vre_obj.match(vdir):
            for dep in ModDepend:
                vname = os.path.join(pdir, vdir, '%s_VERSION' % dep.upper())
                if os.path.exists(vname):
                    vfile = open(vname, 'rt')
                    ver = vfile.readline().strip()
                    if vdir not in vers:
                        vers[vdir] = {}
                    vers[vdir][dep] = ver
    print_debug('%s vers=%s' % (mod, vers))
    return vers
                           
def check_lima_dir():
    global LimaDir
    if LimaDir is not None:
        return LimaDir
    args = ['python', '-c', 'from Lima import Core; print Core.__file__']
    pobj = Popen(args, stdout=PIPE)
    core_init_dir = pobj.stdout.readline().strip()
    core_dir = os.path.dirname(core_init_dir)
    LimaDir = os.path.dirname(core_dir)
    return LimaDir

def version_code(s):
    return map(int, s.strip('v').split('.'))

def version_cmp(x, y):
    return cmp(version_code(x), version_code(y))

def print_debug(msg):
    if Debug:
        print msg