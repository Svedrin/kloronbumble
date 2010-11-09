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

parser.add_option( "-s", "--shutdown",
    help="Shutdown the bridge even if it has been active before bridgemon has been started.",
    action="store_true", default=False
    )

parser.add_option( "-d", "--dry-run",
    help="Don't actually start the bridge, just print the command line that would be used.",
    action="store_true", default=False
    )

parser.add_option( "-v", "--verbose",
    help="Print the arguments passed to KVM.",
    action="store_true", default=False
    )

parser.add_option( "-i", "--id",
    help="Start a bridge given by ID."
    )

parser.add_option( "-n", "--name",
    help="Start a bridge given by name."
    )

options, progargs = parser.parse_args()

if bool(options.id) == bool(options.name):
    sys.exit("You need to specify exactly one of -i or -n.")


import subprocess
from time import sleep

from kvm.models import Bridge

if options.id:
    br = Bridge.objects.get(id=options.id)
elif options.name:
    br = Bridge.objects.get(name=options.name)


def invoke(args):
    if options.dry_run or options.verbose:
        print " ".join(args)
    if not options.dry_run:
        from signal import signal, SIGTERM, SIGINT, SIG_DFL

        proc = subprocess.Popen(args,
            stdin  = sys.stdin,
            stdout = sys.stdout,
            stderr = sys.stderr
            )

        def fwdsigterm(signum, frame):
            proc.send_signal(SIGTERM)
            signal(SIGTERM, fwdsigterm)

        signal(SIGTERM, fwdsigterm)
        signal(SIGINT, fwdsigterm)
        proc.wait()
        signal(SIGTERM, SIG_DFL)
        signal(SIGINT, SIG_DFL)


if not exists(join( "/sys/class/net", br.name )):
    invoke(["brctl", "addbr", br.name])
    invoke(["ifconfig", br.name, br.ip4address, "netmask", br.netmask])
    selfstarted = True
else:
    selfstarted = False

if br.addifaces:
    for iface in br.needifaces.split(','):
        ifname = iface.strip()
        if not exists(join( "/sys/class/net", br.name, "brif", ifname )):
            invoke(["brctl", "addif", br.name, ifname])

if br.needifaces:
    for iface in br.needifaces.split(','):
        if not exists(join( "/sys/class/net", br.name, "brif", iface.strip() )):
            sys.exit("Required interface '%s' missing from bridge '%s'" % (iface.strip(), br.name))

if br.failifaces:
    for iface in br.failifaces.split(','):
        if exists(join( "/sys/class/net", br.name, "brif", iface.strip() )):
            sys.exit("Blacklisted interface '%s' is in bridge '%s'" % (iface.strip(), br.name))



if br.dnsmasq != "off":
    args = ["dnsmasq", "--strict-order", "--bind-interfaces", "--keep-in-foreground",
            "--conf-file=", "--except-interface", "lo", "--listen-address", br.ip4address,
            "--interface", br.name.encode("utf-8")]

    if br.dnsmasq == "dns":
        args.append("--no-dhcp-interface=%s" % br.name.encode("utf-8"))
    else:
        # calc range
        ipparts = br.ip4address.split('.')
        lowip   = '.'.join( ipparts[:3] + ['100'] )
        highip  = '.'.join( ipparts[:3] + ['250'] )
        args.append("--dhcp-range=interface:%s,%s,%s" % (br.name, lowip, highip))

    invoke(args)

elif not options.dry_run:
    # Wait for SIGINT or SIGTERM
    try:
        from signal import signal, SIGTERM
        def sigtermtoexc(signal, frame):
            raise KeyboardInterrupt

        signal(SIGTERM, sigtermtoexc)

        while(True):
            sleep(999999)

    except KeyboardInterrupt:
        pass

else:
    print "I'd run a main loop now"

if (exists(join( "/sys/class/net", br.name )) or options.dry_run) and (selfstarted or options.shutdown):
    invoke(["ifconfig", br.name, "down"])
    invoke(["brctl", "delbr", br.name])
