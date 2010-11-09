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

parser = OptionParser(usage="""%prog [options] <command>

Available commands:
  start      -- Start a VM.
  stop       -- Stop a VM by killing its process.
  shutdown   -- Gracefully shutdown the VM via an ACPI event.
  restart    -- Shutdown and restart a VM.
  status     -- Print the status of a VM.
  commit     -- Run a commit operation on a VM that is running a snapshot.
""")

parser.add_option( "-d", "--dry-run",
    help="Don't actually start the VM, just print the command line that would be used.",
    action="store_true", default=False
    )

parser.add_option( "-v", "--verbose",
    help="Print the arguments passed to KVM.",
    action="store_true", default=False
    )

parser.add_option( "-t", "--timeout", type="int", default=60,
    help="restart command only: Seconds to wait for shutdown."
    )

parser.add_option( "-k", "--kill",
    help="restart command only: If timeout expires, kill the VM instead of failing.",
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

if not progargs:
    parser.print_help()
    sys.exit(1)


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

if progargs[0] == "start":
    if not vm.process.is_running:
        vm.start()
    else:
        print "VM '%s' is already running." % vm.name

elif progargs[0] == "stop":
    if vm.process.is_running:
        vm.stop()
    else:
        print "VM '%s' is not running." % vm.name

elif progargs[0] == "shutdown":
    if vm.process.is_running:
        vm.shutdown()
    else:
        print "VM '%s' is not running." % vm.name

elif progargs[0] == "commit":
    if vm.process.is_running and vm.runsnapshot:
        vm.commit()
    else:
        print "VM '%s' is not running, or not in snapshot mode." % vm.name

elif progargs[0] == "status":
    if vm.process.is_running:
        if vm.runsnapshot:
            print "VM '%s' is running in snapshot mode." % vm.name
        else:
            print "VM '%s' is running in normal mode." % vm.name
    else:
        print "VM '%s' is not running." % vm.name

elif progargs[0] == "restart":
    if vm.process.is_running:
        print "Shutting down..."
        vm.shutdown()
        if not vm.process.waitState("EXITED", maxwait=options.timeout):
            if options.kill:
                print "VM failed shutting down, killing it."
                vm.stop()
                if not vm.process.waitState("STOPPED"):
                    sys.exit("VM failed shutting down and even refused being killed!!1! Plz go fixin.")
            else:
                sys.exit("VM failed shutting down.")
        else:
            print "Shutdown complete."

    print "Starting up..."
    vm.start()
    print "VM should be booting, glhf."
