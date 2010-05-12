from django import forms
from richmond.webapp.api.models import SMS

class SMSForm(forms.ModelForm):
    class Meta:
        model = SMS
    
class SMSReceiptForm(forms.Form):
    cliMsgId = forms.IntegerField()
    apiMsgId = forms.CharField(max_length=32)
    status = forms.IntegerField()
    timestamp = forms.IntegerField()
    to = forms.CharField(max_length=32)
    from_ = forms.CharField(max_length=32)
    charge = forms.CharField(max_length=32)
