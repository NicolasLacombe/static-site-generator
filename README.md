# static-site-generator
Python 3.6 script that can generate a static website by expanding json content into html template.
Support "Server Side Include" syntax too, so inclusion of html template into other template works too.

Optionally:
 - A continuous scan of the input directory can be spawned, and template expansion will occurs if and when anything change
 - A http.server can be started to serve the output location

### Dependencies:
[watchdog](https://pythonhosted.org/watchdog/installation.html)
