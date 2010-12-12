# -*- coding: utf-8 -*-
# kate: space-indent on; indent-width 4; replace-tabs on;

import xmlrpclib
import os
from os.path import join
from functools import partial
from time import time, sleep
from ConfigParser import ConfigParser

from django.db        import models
from django.db.models import signals


def mk_config_property( field, doc="", get_coerce=None, get_none=None, set_coerce=unicode, set_none='' ):
    """ Create a property for the given config field. """

    def get_field( self ):
        return self.getconf( field )

    def set_field( self, value ):
        return self.setconf( field, value )

    return property( get_field, set_field, doc=doc )


class Supervisor(models.Model):
    address     = models.CharField(max_length=250)
    username    = models.CharField(max_length=250, blank=True)
    password    = models.CharField(max_length=250, blank=True)
    confdir     = models.CharField(max_length=250)

    Fault       = xmlrpclib.Fault

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)

        self._xmlrpc = None

    def get_xmlrpc(self):
        if self._xmlrpc is None:
            self._xmlrpc = xmlrpclib.Server("http://%s:%s@%s" % ( self.username, self.password, self.address ))
        return self._xmlrpc

    xmlrpc = property(get_xmlrpc)

    def __unicode__(self):
        return "Supervisor at %s" % self.address

    def getState(self):
        return self.xmlrpc.supervisor.getState()

    @property
    def is_running(self):
        return self.getState()['statename'] == 'RUNNING'

class Process(models.Model):
    supervisor  = models.ForeignKey(Supervisor)
    name        = models.CharField(max_length=250)

    command                 = mk_config_property( "command", "The command to run" )
    directory               = mk_config_property( "directory", "The command's workdir" )
    redirect_stderr         = mk_config_property( "redirect_stderr", "Whether or not to redirect STDERR to STDOUT" )
    autostart               = mk_config_property( "autostart" )
    stdout_logfile          = mk_config_property( "stdout_logfile", "Where to log STDOUT to" )
    stdout_logfile_maxbytes = mk_config_property( "stdout_logfile_maxbytes", "The max size of the logfile" )
    stdout_logfile_backups  = mk_config_property( "stdout_logfile_backups", "How many backups to keep" )

    Fault = xmlrpclib.Fault

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)

        self._conf = ConfigParser()
        if self.id is not None and self.name:
            self._conf.read(self.confpath)

    @property
    def confpath(self):
        return join(self.supervisor.confdir, self.name + ".conf")

    def getconf(self, option):
        return self._conf.get( ("program:" + self.name), option )

    def setconf(self, option, value):
        if not self._conf.has_section("program:" + self.name):
            self._conf.add_section("program:" + self.name)
        return self._conf.set( ("program:" + self.name), option, value )

    def __unicode__(self):
        return "%s on Supervisor at %s" % (self.name, self.supervisor.address)

    def save(self, *args, **kwargs):
        adding = (self.id is None)
        ret = models.Model.save(self, *args, **kwargs)

        fd = open(self.confpath, "w")
        try:
            self._conf.write(fd)
        finally:
            fd.close()

        self.supervisor.xmlrpc.supervisor.reloadConfig()
        if adding:
            self.supervisor.xmlrpc.supervisor.addProcessGroup(self.name)

        return ret

    # Deletion handler
    def pre_delete( self ):
        """ Delete this process from Supervisord. """
        if self.is_running:
            self.stop()
        self.supervisor.xmlrpc.supervisor.removeProcessGroup(self.name)
        os.unlink(self.confpath)
        self.supervisor.xmlrpc.supervisor.reloadConfig()

    @staticmethod
    def pre_delete_listener( **kwargs ):
        kwargs['instance'].pre_delete()

    def start(self):
        return self.supervisor.xmlrpc.supervisor.startProcess(self.name)

    def stop(self):
        return self.supervisor.xmlrpc.supervisor.stopProcess(self.name)

    def sendStdin(self, data):
        return self.supervisor.xmlrpc.supervisor.sendProcessStdin(self.name, data)

    def getInfo(self):
        return self.supervisor.xmlrpc.supervisor.getProcessInfo(self.name)

    info = property(getInfo)

    def waitState(self, state="RUNNING", interval=0.5, maxwait=10):
        start = int(time())
        while self.info["statename"] != state:
            if (int(time()) - start) >= maxwait:
                return False
            sleep(interval)
        return True

    @property
    def is_running(self):
        return self.info['statename'] == 'RUNNING'


signals.pre_delete.connect( Process.pre_delete_listener, sender=Process )
