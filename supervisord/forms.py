# -*- coding: utf-8 -*-
# kate: space-indent on; indent-width 4; replace-tabs on;

from django        import forms
from django.conf   import settings
from django.forms  import Form, ModelForm
from django.forms.models import ModelFormMetaclass
from django.utils.translation import ugettext_lazy as _

from supervisord.models import Process

class PropertyModelFormMeta( ModelFormMetaclass ):
    """ Metaclass that updates the property generated fields with the
        docstrings from their model counterparts.
    """
    def __init__( cls, name, bases, attrs ):
        ModelFormMetaclass.__init__( cls, name, bases, attrs )

        if cls._meta.model:
            model = cls._meta.model
        elif hasattr( bases[0], '_meta' ) and bases[0]._meta.model:
            # apparently, _meta has not been created yet if inherited, so use parent's (if any)
            model = bases[0]._meta.model
        else:
            model = None

        if model:
            mdlfields = model._meta.get_all_field_names()
            for fldname in cls.base_fields:
                if fldname in mdlfields:
                    continue
                prop = getattr( model, fldname )
                if prop.__doc__:
                    cls.base_fields[fldname].label = _(prop.__doc__)


class PropertyModelForm( ModelForm ):
    """ ModelForm that gets/sets fields that are not within the model's
        fields as model attributes. Necessary to get forms that manipulate
        properties.
    """

    __metaclass__ = PropertyModelFormMeta

    def __init__( self, *args, **kwargs ):
        ModelForm.__init__( self, *args, **kwargs )

        if self.instance:
            instfields = self.instance._meta.get_all_field_names()
            for fldname in self.fields:
                if fldname in instfields:
                    continue
                self.fields[fldname].initial = getattr( self.instance, fldname )

    def save( self, commit=True ):
        inst = ModelForm.save( self, commit=commit )

        if commit:
            self.save_to_model( inst )
        else:
            # Update when the model has been saved.
            from django.db.models import signals
            self._update_inst = inst
            signals.post_save.connect( self.save_listener, sender=inst.__class__ )

        return inst

    def save_listener( self, **kwargs ):
        if kwargs['instance'] is self._update_inst:
            self.save_to_model( self._update_inst )

    def save_to_model( self, inst ):
        instfields = inst._meta.get_all_field_names()

        for fldname in self.fields:
            if fldname not in instfields:
                setattr( inst, fldname, self.cleaned_data[fldname] )

class ProcessForm( PropertyModelForm ):
    command                     = forms.CharField( required=False )
    directory                   = forms.CharField( required=False )
    redirect_stderr             = forms.CharField( required=False )
    autostart                   = forms.CharField( required=False )
    stdout_logfile              = forms.CharField( required=False )
    stdout_logfile_maxbytes     = forms.CharField( required=False )
    stdout_logfile_backups      = forms.CharField( required=False )

    class Meta:
        model = Process
