# -*- coding: utf-8 -*-
# kate: space-indent on; indent-width 4; replace-tabs on;

import uuid
from os.path import dirname, abspath, join

from django.db        import models
from django.db.models import signals

from supervisord.models import Supervisor, Process

class Bridge(models.Model):
    name        = models.CharField(max_length=10,  unique=True)
    commonname  = models.CharField(max_length=250, blank=True)
    ip4address  = models.CharField(max_length=15,  blank=True)
    ip6address  = models.CharField(max_length=39,  blank=True)
    netmask     = models.CharField(max_length=15,  blank=True)
    needifaces  = models.CharField(max_length=250, blank=True, help_text="Fail if one of the listed interfaces is not in the bridge. Checked after addifaces are applied.")
    failifaces  = models.CharField(max_length=250, blank=True, help_text="Fail if one of the listed interfaces *is* in the bridge.")
    addifaces   = models.CharField(max_length=250, blank=True, help_text="After starting the bridge, add the listed interfaces to it.")
    dnsmasq     = models.CharField(max_length=10,  default="off", choices=(
                      ("off",  "No DNSMASQ Daemon running"),
                      ("dns",  "Provide DNS only (no DHCP)"),
                      ("dhcp", "Provide DNS and DHCP")
                      ))
    process     = models.ForeignKey(Process,       blank=True, null=True)

    def __unicode__(self):
        return "%s (%s)" % ( self.commonname, self.name)

    def save(self, *args, **kwargs):
        if self.process is None:
            svd = Supervisor.objects.all()[0]
            process = Process(supervisor=svd, name=self.name)
        else:
            process = self.process

        kvmdir = dirname(abspath(__file__))
        process.command                 = "%s -n %s -v" % ( join(kvmdir, "bridgemon.py"), self.name )
        process.directory               = "/guests"
        process.autostart               = "false"
        process.redirect_stderr         = "true"
        process.stdout_logfile          = join( "/var/log/guests", ("bridge_%s.log" % self.name) )
        process.stdout_logfile_maxbytes = "50MB"
        process.stdout_logfile_backups  = "10"
        process.save()

        if self.process is None:
            self.process = process

        return models.Model.save(self, *args, **kwargs)

    # Deletion handler
    def post_delete( self ):
        """ Delete the according process. """
        self.process.delete()

    @staticmethod
    def post_delete_listener( **kwargs ):
        kwargs['instance'].post_delete()

    def start(self):
        return self.process.start()

    def stop(self):
        if not self.idle:
            raise SystemError("Cannot stop bridge, there are VMs using it.")
        return self.process.stop()

    @property
    def idle(self):
        return not max(( vm.process.is_running for vm in self.virtualmachine_set.all()))


class VirtualMachine(models.Model):
    name        = models.CharField(max_length=50,  unique=True)
    process     = models.ForeignKey(Process,       blank=True, null=True, unique=True)
    description = models.TextField(blank=True)
    macaddress  = models.CharField(max_length=17,  blank=True, unique=True)
    ip4address  = models.CharField(max_length=15,  blank=True)
    ip6address  = models.CharField(max_length=39,  blank=True)
    bridge      = models.ForeignKey(Bridge,        blank=True, null=True)
    uuid        = models.CharField(max_length=50,  blank=True)
    cpus        = models.IntegerField(default=2)
    memory      = models.IntegerField(default=512)
    diskpath    = models.CharField(max_length=250, blank=True, default="hda.qcow2")
    diskformat  = models.CharField(max_length=20,  default="qcow2")
    disksize    = models.CharField(max_length=10,  default="10G", help_text="only used when creating the image")
    cdrompath   = models.CharField(max_length=250, blank=True)
    vncport     = models.IntegerField(default=-1,  unique=True)
    keymap      = models.CharField(max_length=10,  default="de")
    runsnapshot = models.BooleanField(default=False, blank=True)
    emumachine  = models.CharField(max_length=50,  blank=True, default="pc")
    paravirt    = models.BooleanField(default=True, blank=True)

    def __unicode__(self):
        return self.name

    def get_kvm_args(self):
        """ Return KVM arguments to start this VM. """
        args = ["-enable-kvm", "-monitor", "stdio", "-rtc", "base=utc", "-nodefaults", "-vga", "cirrus"]

        if self.emumachine:
            args.extend(["-M", self.emumachine])

        args.extend(["-name", self.name.encode("utf-8")])
        args.extend(["-uuid", self.uuid.encode("utf-8")])
        args.extend(["-smp", str(self.cpus)])
        args.extend(["-m", str(self.memory)])

        if self.cdrompath:
            args.extend(["-boot", "order=dc,once=d"])
            args.extend(["-cdrom", self.cdrompath.encode("utf-8")])
        else:
            args.extend(["-boot", "order=c"])

        if self.diskpath:
            diskpath = self.diskpath.encode("utf-8")
        else:
            diskpath = "/guests/%s/hda.%s" % (self.name.encode("utf-8"), self.diskformat.encode("utf-8"))

        if self.paravirt:
            args.extend(["-drive", "file=%s,if=virtio,id=drive-disk0,boot=on,format=%s" % (diskpath, self.diskformat)])
        else:
            args.extend(["-drive", "file=%s,if=none,id=drive-disk0,boot=on,format=%s" % (diskpath, self.diskformat)])
            args.extend(["-device", "ide-drive,bus=ide.0,unit=0,drive=drive-disk0,id=ide0-0-0"])

        kvmdir = dirname(abspath(__file__))

        args.extend(["-net", "nic,vlan=0,macaddr=%s,model=%s" % (
            self.macaddress.encode("utf-8"),
            {True: 'virtio', False: 'rtl8139'}[self.paravirt]
            )])
        args.extend(["-net", "tap,vlan=0,script=%s" % join(kvmdir, "netconf.py")])

        if self.vncport is not None:
            args.extend(["-usbdevice", "tablet"])
            if self.bridge:
                vncip = self.bridge.ip4address
            else:
                vncip = "127.0.0.1"
            args.extend(["-vnc", "%s:%d" % (vncip, self.vncport)])
            args.extend(["-k", self.keymap.encode("utf-8")])

        if self.runsnapshot:
            args.extend(["-snapshot"])

        return args

    def save(self, *args, **kwargs):
        if self.process is None:
            svd = Supervisor.objects.all()[0]
            process = Process(supervisor=svd, name=self.name)
        else:
            process = self.process

        if self.vncport == -1:
            self.vncport = max( [ rec['vncport'] for rec in VirtualMachine.objects.values('vncport') ] ) + 1

        kvmdir = dirname(abspath(__file__))
        process.command                 = "%s -n %s -v" % ( join(kvmdir, "monitord.py"), self.name )
        process.directory               = join( "/guests" )
        process.autostart               = "false"
        process.redirect_stderr         = "true"
        process.stdout_logfile          = join( "/var/log/guests", ("machine_%s.log" % self.name) )
        process.stdout_logfile_maxbytes = "50MB"
        process.stdout_logfile_backups  = "10"
        process.save()

        if self.process is None:
            self.process = process

        if not self.uuid:
            uu = uuid.uuid4()
            self.uuid = str(uu)

        if not self.macaddress:
            from random import choice
            def x():
                return str(choice("0123456789ABCDEF"))
            while(True):
                tryaddr = ["52:54:00"]
                for i in range(3):
                    tryaddr.append(x() + x())
                tryaddr = ':'.join(tryaddr)
                if VirtualMachine.objects.filter(macaddress=tryaddr).count() == 0:
                    self.macaddress = tryaddr
                    break

        return models.Model.save(self, *args, **kwargs)

    # Deletion handler
    def post_delete( self ):
        """ Delete the according process. """
        self.process.delete()

    @staticmethod
    def post_delete_listener( **kwargs ):
        kwargs['instance'].post_delete()

    def start(self):
        if self.bridge is not None and not self.bridge.process.is_running:
            self.bridge.start()
            if not self.bridge.process.waitState("RUNNING"):
                raise SystemError("Failed to bring up bridge '%s' for VM '%s'" % (self.bridge.name, self.name))
        return self.process.start()

    def stop(self):
        return self.process.stop()

    def shutdown(self):
        if self.process.is_running:
            return self.process.sendStdin("system_powerdown\n")
        return None

    def commit(self):
        if not self.runsnapshot:
            raise SystemError("Cannot commit when not running in snapshot mode")
        return self.process.sendStdin("commit drive-disk0\n")


class Snapshot(models.Model):
    vm          = models.ForeignKey(VirtualMachine)
    tag         = models.CharField(max_length=250)

    class Meta:
        unique_together = ("vm", "tag")

    def __unicode__(self):
        return "%s: %s" % ( self.vm.name, self.tag)

    def save(self, *args, **kwargs):
        if self.id is not None:
            return

        if self.vm.process.sendStdin("savevm %s\n" % self.tag.encode("utf-8")):
            return models.Model.save(self, *args, **kwargs)
        else:
            raise SystemError("Could not dispatch savevm command")

    def load(self):
        if not self.id:
            raise SystemError("Cannot load a snapshot that has not yet been created")
        return self.vm.process.sendStdin("loadvm %s\n" % self.tag.encode("utf-8"))


signals.post_delete.connect( Bridge.post_delete_listener,         sender=Bridge         )
signals.post_delete.connect( VirtualMachine.post_delete_listener, sender=VirtualMachine )
