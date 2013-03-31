#!/usr/bin/env python
# -*- coding: utf-8 -*-
# kate: space-indent on; indent-width 4; replace-tabs on;

import os, sys
from os.path  import join, dirname, abspath, exists, basename
from optparse import OptionParser

PROJECT_ROOT = None

# Path auto-detection
if not PROJECT_ROOT or not exists( PROJECT_ROOT ):
    PROJECT_ROOT = dirname(dirname(abspath(__file__)))

# environment variables
sys.path.append( PROJECT_ROOT )
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

parser = OptionParser()

parser.add_option( "-d", "--dry-run",
    help="Don't actually start the VM, just print the command line that would be used.",
    action="store_true", default=False
    )

parser.add_option( "-v", "--verbose",
    help="Print the arguments passed to KVM.",
    action="store_true", default=False
    )

options, progargs = parser.parse_args()


# cwd = /guests/mumbledjango_demo → mumbledjango_demo
vmname = basename(os.getcwd())

import subprocess
from kvm.models import VirtualMachine

vm = VirtualMachine.objects.get(name=vmname)

def invoke(args):
    if options.dry_run:
        print " ".join(args)
    else:
        proc = subprocess.Popen(args,
            stdin  = sys.stdin,
            stdout = sys.stdout,
            stderr = sys.stderr
            )
        proc.wait()



if vm.bridge is not None:
    invoke(["ifconfig", progargs[0], "up"])
    invoke(["brctl", "addif", vm.bridge.name, progargs[0]])

else:
    invoke(["/sbin/ifconfig", progargs[0], "up"])
    invoke(["/sbin/route", "add", "-host", vm.ip4address, "dev", progargs[0]])
    if vm.ip6address:
        invoke(["ip", "address", "add", vm.ip6address, "dev", progargs[0]])
