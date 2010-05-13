from django.conf.urls.defaults import *
from piston.resource import Resource
from piston.authentication import HttpBasicAuthentication
from richmond.webapp.api import handlers
from richmond.webapp.api import views

ad = {'authentication': HttpBasicAuthentication(realm="Richmond")}
conversation_resource = Resource(handler=handlers.ConversationHandler, **ad)
sms_receipt_resource = Resource(handler=handlers.SMSReceiptHandler, **ad)
sms_send_resource = Resource(handler=handlers.SendSMSHandler, **ad)
sms_receive_resource = Resource(handler=handlers.ReceiveSMSHandler, **ad)

urlpatterns = patterns('',
    (r'^conversation\.yaml$', conversation_resource, {
        'emitter_format': 'yaml'
    }, 'conversation'),
    (r'^sms/receipt\.html$', sms_receipt_resource, {}, 'sms-receipt'),
    (r'^sms/send\.html$', sms_send_resource, {}, 'sms-send'),
    (r'^sms/receive\.html$', sms_receive_resource, {}, 'sms-receive'),
    (r'^callback\.html$', views.example_sms_callback, {}, 'sms-example-callback'),
)
