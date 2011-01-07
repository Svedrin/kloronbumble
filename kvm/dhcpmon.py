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

from kvm.models import VirtualMachine

action, macaddr, ipaddr = sys.argv[1:4]
macaddr = macaddr.upper()

try:
    vm = VirtualMachine.objects.get(macaddress=macaddr)
except VirtualMachine.DoesNotExist:
    print "No VM found with MAC Address", macaddr
else:
    if action == "del":
        vm.ip4address = ""
    else:
        vm.ip4address = ipaddr
    vm.save()
