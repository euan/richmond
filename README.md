Richmond
========

Connecting the python-ssmi client to AMQP to allow for backends to scale more easily. 

If you're wondering about the name. Apparently Richmond has is a great city for commuters, few traffic problems. Seemed like a good name for a high-traffic message bus application.

Getting started
---------------

Make sure you have your AMQP broker running. I've only tested it with RabbitMQ, in theory, it should work with any other AMQP 0.8 spec based broker.

    $ rabbitmq-server

RabbitMQ will automatically assign a node name for you. For my network that doesn't work too well because the rest of the clients are unable to connect. If you run into the same problem, try the following:

    $ RABBITMQ_NODENAME=rabbit@localhost rabbitmq-server

Make sure you have configured your login credentials & virtual host stuff in RabbitMQ. This is the minimal stuff for this to work 'out of the box':

    $ rabbitmqctl -n rabbit@localhost add_user richmond richmond
    Creating user "richmond" ...
    ...done.
    $ rabbitmqctl -n rabbit@localhost add_vhost /richmond
    Creating vhost "richmond" ...
    ...done.
    $ rabbitmqctl -n rabbit@localhost set_permissions -p /richmond richmond \
        '.*' '.*' '.*'
    Setting permissions for user "richmond" in vhost "richmond" ...
    ...done.
 
That last line gives the user 'richmond' on virtual host 'richmond' configure, read & write access to all resources that match those three regular expressions. Which, in this case, matches all resources in the vhost.

This project uses [virtualenv][virtualenv] and [pip][pip] to to create a sandbox and manage the required libraries at the required versions. Make sure you have both installed.

Setup a virtual python environment in the directory `ve`. The `--no-site-packages` makes sure that all required dependencies are installed your the virtual environments `site-packages` directory even if they exist in Python's global `site-packages` directory.

    $ virtualenv --no-site-packages ./ve/ 

Start the environment by sourcing `activate`. This'll prepend the name of the virtual environment to your shell prompt, informing you that the prompt is still active.

        $ source ve/bin/activate

When you're done run `deactivate` to exit the virtual environment.

Install the required libraries with pip into the virtual environment. They're pulled in from both [pypi][pypi] and [GitHub][github]. Make sure you have the development package for python (python-dev or python-devel or something of that sort) installed, Twisted needs it when it's being built.

    $ pip -E ./ve/ install -r config/requirements.pip
 
Running Richmond
----------------

Richmond is implemented using a [Pub/Sub][pubsub] design using the [Competing Consumer pattern][competing consumers]. 

Richmond has two plugins for Twisted, `richmond_broker` and `richmond_worker`.

The broker connects to TruTeq's SSMI service and connects to RabbitMQ. It publishes all incoming messages over SSMI as JSON to the receive queue in RabbitMQ and it publishes all incoming messages over the send queue back to TruTeq over SSMI.

The worker reads all incoming JSON objects on the receive queue and publishes a response back to the send queue for the `richmond_worker` to publish over SSMI.

Make sure you update the configuration file in `config/richmond-broker.cfg` and start the broker:

    $ source ve/bin/activate
    (ve)$ twistd --pidfile=tmp/pids/twistd.richmond.broker.pid -n \     
        richmond_broker -c config/richmond-broker.cfg
    ...
 
Make sure you update the worker configuration in `config/richmond-worker.cfg` if the defaults aren't suitable and start a worker.

    $ source ve/bin/activate
    (ve)$ twistd --pidfile=tmp/pids/twistd.richmond.worker.1.pid -n \
        richmond_worker -w richmond.workers.ussd.EchoWorker
    ...

The worker's -w option allows you to specify a class that subclasses `richmond.workers.base.RichmondWorker`.

Remove the `-n` option to have `twistd` run in the background. The `--pidfile` option isn't necessary, `twistd` will use 'twistd.pid' by default. However, since we could have multiple brokers and workers running at the same time on the same machine it is good to be explicit since `twistd` will assume an instance is already running if 'twistd.pid' already exists.

Creating a custom worker
------------------------

We'll create a worker that responds to USSD json objects. We'll subclass the `richmond.workers.ussd.USSDWorker` which itself subclasses `richmond.workers.base.RichmondWorker`. The `USSDWorker` subclasses `RichmondWorker`'s `consume` method and maps these to the following methods:

    * new_ussd_session(msisdn, message)
    * existing_ussd_session(msisdn, message)
    * timed_out_ussd_session(msisdn, message)
    * end_ussd_session(msisdn, message)

The `USSDWorker` also provides a `reply(msisdn, message, type)` that publishes the message of the given type to the queue.

Here's [working example][foobarworker]:
 
    from richmond.workers.ussd import USSDWorker, SessionType
    from twisted.python import log
 
    class FooBarWorker(USSDWorker):
 
        def new_ussd_session(self, msisdn, message):
            """Respond to new sessions"""
            self.reply(msisdn, "foo?", SessionType.existing)
 
        def existing_ussd_session(self, msisdn, message):
            """Respond to returning sessions"""
            if message == "bar" or message == "0": # sorry android is silly
                # replying with type `SessionType.end` ends the session
                self.reply(msisdn, "Clever. Bye!", SessionType.end)
            else:
                # replying with type `SessionType.existing` keeps the session
                # open and prompts the user for input
                self.reply(msisdn, "Say bar ...", SessionType.existing)
	        
        def timed_out_ussd_session(self, msisdn, message):
            """These timed out unfortunately"""
            log.msg("%s timed out" % msisdn)
	        
        def end_ussd_session(self, msisdn, message):
            """These ended the session themselves"""
            log.msg("%s ended session" % msisdn)
	    

Start the worker:

    $ source ve/bin/activate
    (ve)$ twistd --pidfile=tmp/pids/twistd.richmond.worker.2.pid -n \
        richmond_worker -w richmond.workers.example.FooBarWorker
    ...


Running the Webapp / API
------------------------

The webapp is a regular Django application. Before you start make sure the `DATABASE` settings in `src/richmond/webapp/settings.py` are up to date. `Richmond` is being developed with `PostgreSQL` as the default backend for the Django ORM but this isn't a requirement.

For development start it within the virtual environment:

    $ source ve/bin/activate
    (ve)$ python setup.py develop
    (ve)$ ./manage.py syncdb
    (ve)$ ./manage.py runserver
    ...
 
When running in production start it with the `twistd` plugin `richmond_webapp`
 
    $ source ve/bin/activate
    (ve)$ twistd --pidfile=tmp/pids/richmond.webapp.pid -n richmond_webapp

Run the tests for the webapp API with `./manage.py` as well:

    $ source ve/bin/activate
    (ve)$ ./manage.py test api

Scheduling SMS for delivery via the API
---------------------------------------

The API is HTTP with concepts borrowed from REST. All URLs have a rate limit of 60 hits per 60 seconds and require HTTP Basic Authentication.

**Sending SMSs**

    $ curl -u 'username:password' -X POST \
    >   http://localhost:8000/api/v1/sms/send.json \
    >   -d 'to_msisdn=27123456789' \
    >   -d 'from_msisdn=27123456789' \
    >   -d 'message=hello world'
    [
        {
            "delivered_at": "2010-05-13 11:34:34", 
            "id": 5, 
            "from_msisdn": "27123456789", 
            "to_msisdn": "27123456789", 
            "delivery_status": 0, 
            "message": "hello world"
        }
    ]

**Sending Batched SMSs**

Sending multiple SMSs is as simple as sending a simple SMS. Just specify multiple values for `to_msisdn`.

    $ curl -u 'username:password' -X POST \
    >   http://localhost:8000/api/v1/sms/send.json \
    >   -d 'to_msisdn=27123456780' \
    >   -d 'to_msisdn=27123456781' \
    >   -d 'to_msisdn=27123456782' \
    >   -d 'from_msisdn=27123456789' \
    >   -d 'message=hello world'
    [
        {
            "delivered_at": "2010-05-13 11:32:22", 
            "id": 2, 
            "from_msisdn": "27123456789", 
            "to_msisdn": "27123456780", 
            "delivery_status": 0, 
            "message": "hello world"
        }, 
        {
            "delivered_at": "2010-05-13 11:32:22", 
            "id": 3, 
            "from_msisdn": "27123456789", 
            "to_msisdn": "27123456781", 
            "delivery_status": 0, 
            "message": "hello world"
        }, 
        {
            "delivered_at": "2010-05-13 11:32:22", 
            "id": 4, 
            "from_msisdn": "27123456789", 
            "to_msisdn": "27123456782", 
            "delivery_status": 0, 
            "message": "hello world"
        }
    ]

**Sending Personalized SMSs**

Personalized SMSs can be sent by specifying a template and the accompanying variables.

All template variables should be prefixed with 'template_'. In the template you can refer to the values without their prefix.

    $ curl -u 'username:password' -X POST \
    > http://localhost:8000/api/v1/sms/template_send.json \
    > -d 'to_msisdn=27123456789' \
    > -d 'to_msisdn=27123456789' \
    > -d 'to_msisdn=27123456789' \
    > -d 'from_msisdn=27123456789' \
    > -d 'template_name=Simon' \
    > -d 'template_surname=de Haan' \
    > -d 'template_name=Jack' \
    > -d 'template_surname=Jill' \
    > -d 'template_name=Foo' \
    > -d 'template_surname=Bar' \
    > -d 'template=Hello {{name}} {{surname}}'
    [
        {
            "delivered_at": "2010-05-14 04:42:09", 
            "id": 6, 
            "from_msisdn": "27123456789", 
            "to_msisdn": "27123456789", 
            "delivery_status": 0, 
            "message": "Hello Foo Bar"
        }, 
        {
            "delivered_at": "2010-05-14 04:42:09", 
            "id": 7, 
            "from_msisdn": "27123456789", 
            "to_msisdn": "27123456789", 
            "delivery_status": 0, 
            "message": "Hello Jack Jill"
        }, 
        {
            "delivered_at": "2010-05-14 04:42:09", 
            "id": 8, 
            "from_msisdn": "27123456789", 
            "to_msisdn": "27123456789", 
            "delivery_status": 0, 
            "message": "Hello Simon de Haan"
        }
    ]

Checking the status of sent SMSs
--------------------------------

Once an SMS has been scheduled for sending you can check it's status via the API. There are 3 options of retrieving previously sent SMSs.

**Retrieving one specific SMS**

    $ curl -u 'username:password' -X GET \
    > http://localhost:8000/api/v1/sms/status/1.json \
    {
        "delivered_at": null, 
        "created_at": "2010-05-14 16:31:01", 
        "updated_at": "2010-05-14 16:31:01", 
        "delivery_status_display": "Pending locally", 
        "from_msisdn": "27123456789", 
        "id": 1, 
        "to_msisdn": "27123456789", 
        "message": "testing api", 
        "delivery_status": 0
    }

**Retrieving SMSs sent since a specific date**

    $ curl -u 'username:password' -X GET \
    > http://localhost:8000/api/v1/sms/status.json?since=2009-01-01
    [
        {
            "delivered_at": null, 
            "created_at": "2010-05-14 16:31:01", 
            "updated_at": "2010-05-14 16:31:01", 
            "delivery_status_display": "Pending locally", 
            "from_msisdn": "27123456789", 
            "id": 51, 
            "to_msisdn": "27123456789", 
            "message": "testing api", 
            "delivery_status": 0
        }, 
        ...
        ...
        ...
    ]

**Retrieving SMSs by specifying their IDs**

    $ curl -u 'username:password' -X GET \
    > "http://localhost:8000/api/v1/sms/status.json?id=3&id=4"
    [
        {
            "delivered_at": null, 
            "created_at": "2010-05-14 16:31:01", 
            "updated_at": "2010-05-14 16:31:01", 
            "delivery_status_display": "Pending locally", 
            "from_msisdn": "27123456789", 
            "id": 4, 
            "to_msisdn": "27123456789", 
            "message": "testing api", 
            "delivery_status": 0
        }, 
        {
            "delivered_at": null, 
            "created_at": "2010-05-14 16:31:01", 
            "updated_at": "2010-05-14 16:31:01", 
            "delivery_status_display": "Pending locally", 
            "from_msisdn": "27123456789", 
            "id": 3, 
            "to_msisdn": "27123456789", 
            "message": "testing api", 
            "delivery_status": 0
        }
    ]
    
Specifying Callbacks
--------------------

There are two types of callbacks defined. These are `sms_received` and `sms_receipt`. Each trigger an HTTP POST to the given URLs.

    $ curl -u 'username:password' -X PUT \
    > http://localhost:8000/api/v1/account/callbacks.json \
    > -d 'sms_received=http://localhost/sms/received/callback' \
    > -d 'sms_receipt=http://localhost/sms/receipt/callback'
    [
        {
            "url": "http://localhost/sms/received/callback", 
            "created_at": "2010-05-14 16:50:13", 
            "name": "sms_received", 
            "updated_at": "2010-05-14 16:50:13"
        }, 
        {
            "url": "http://localhost/sms/receipt/callback", 
            "created_at": "2010-05-14 16:50:13", 
            "name": "sms_receipt", 
            "updated_at": "2010-05-14 16:50:13"
        }
    ]

The next time an SMS is received or a SMS receipt is delivered, Richmond will post the data to the URLs specified.

Webapp Workers
--------------

Richmond uses [Celery][celery], the distributed task queue. The main Django process only registers when an SMS is received,sent or when a delivery report is received. The real work is done by the Celery workers.

Start the Celery worker via `manage.py`:

    (ve)$ ./manage.py celeryd
    
For a complete listing of the command line options available, use the help command:

    (ve)$ ./manage.py help celeryd


[virtualenv]: http://pypi.python.org/pypi/virtualenv
[pip]: http://pypi.python.org/pypi/pip
[pypi]: http://pypi.python.org/pypi/
[GitHub]: http://www.github.com/
[pubsub]: http://en.wikipedia.org/wiki/Publish/subscribe
[competing consumers]: http://www.eaipatterns.com/CompetingConsumers.html
[foobarworker]: http://github.com/smn/richmond/blob/master/richmond/workers/example.py
[celery]: http://ask.github.com/celery