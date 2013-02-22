Prince XML WSGI server
======================

Configuration using Nginx and uWSGI
-----------------------------------

Start a ``uwsgi`` daemon process in the program directory (here
running ``http`` user)::

  uwsgi -s /var/run/princexml.sock -w app --uid http

(See included nginx.conf.sample for server configuration).

Dynamic processing of included content
--------------------------------------

For processing of included content via the <iframe> element in a
Javascript-enabled web browser (i.e. to support dynamic HTML
documents), the server uses the Python Webkit GTK bindings to invoke a
"webkit" web browser and downloads each of the linked resources.

This is an optional feature and depends on the `pywebkitgtk
<http://code.google.com/p/pywebkitgtk/>`_ package.


Testing
-------

Using ``curl``::

  $ curl --data-binary @package.tar http://host

The provided tarball must contain an ``index.html`` file along with
any required images and/or stylesheets.

Succesful output (status code 200) will contain the URL for the
generated document. Note: It may not be available right away.

