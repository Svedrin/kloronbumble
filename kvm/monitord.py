#!/usr/bin/env python
# -*- coding: utf-8 -*-
# kate: space-indent on; indent-width 4; replace-tabs on;

import os, sys
from os.path  import join, dirname, abspath, exists
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

parser.add_option( "-i", "--id",
    help="Start a VM given by ID."
    )

parser.add_option( "-n", "--name",
    help="Start a VM given by name."
    )

options, progargs = parser.parse_args()

if bool(options.id) == bool(options.name):
    sys.exit("You need to specify exactly one of -i or -n.")


import subprocess
from kvm.models import VirtualMachine

if options.id:
    vm = VirtualMachine.objects.get(id=options.id)
elif options.name:
    vm = VirtualMachine.objects.get(name=options.name)

if options.dry_run:
    print ' '.join( ["/usr/bin/kvm"] + vm.get_kvm_args() )
    sys.exit(256)


if not vm.diskpath or not exists(vm.diskpath):
    # create image
    diskpath = "/guests/%s/hda.%s" % (vm.name.encode("utf-8"), vm.diskformat.encode("utf-8"))
    if options.verbose:
        print "Creating %s image at '%s'..." % ( vm.diskformat, diskpath );
    proc = subprocess.Popen(
        ["qemu-img", "create", "-f", vm.diskformat, "-o", "size=10G,preallocation=metadata", diskpath],
        stdin  = sys.stdin,
        stdout = sys.stdout,
        stderr = sys.stderr
        )
    proc.wait()

    if options.verbose:
        print "Done."
    vm.diskpath = diskpath
    vm.save()


if options.verbose:
    print "Invoking KVM..."
    print ' '.join( ["/usr/bin/kvm"] + vm.get_kvm_args() )

proc = subprocess.Popen(
    ["/usr/bin/kvm"] + vm.get_kvm_args(),
    stdin  = sys.stdin,
    stdout = sys.stdout,
    stderr = sys.stderr
    )
proc.wait()
