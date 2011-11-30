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

def invoke(args):
    if options.dry_run or options.verbose:
        print " ".join(args)
    if not options.dry_run:
        from signal import signal, SIGTERM, SIG_DFL

        proc = subprocess.Popen(args,
            stdin  = sys.stdin,
            stdout = sys.stdout,
            stderr = sys.stderr
            )

        def fwdsigterm(signum, frame):
            proc.send_signal(SIGTERM)
            signal(SIGTERM, fwdsigterm)

        signal(SIGTERM, fwdsigterm)
        proc.wait()
        signal(SIGTERM, SIG_DFL)

if options.id:
    vm = VirtualMachine.objects.get(id=options.id)
elif options.name:
    vm = VirtualMachine.objects.get(name=options.name)

wd = join("/guests", vm.name)
if not exists(wd):
    os.mkdir(wd)

os.chdir(wd)

if not vm.diskpath or not exists(vm.diskpath):
    # create image
    diskpath = "/guests/%s/hda.%s" % (vm.name.encode("utf-8"), vm.diskformat.encode("utf-8"))
    if options.verbose:
        print "Creating %s image at '%s'..." % ( vm.diskformat, diskpath );
    invoke(["qemu-img", "create", "-f", vm.diskformat, "-o", ("size=%s,preallocation=metadata" % vm.disksize), diskpath])

    if options.verbose:
        print "Done."
    vm.diskpath = diskpath
    vm.save()


invoke(["/usr/bin/kvm"] + vm.get_kvm_args())
