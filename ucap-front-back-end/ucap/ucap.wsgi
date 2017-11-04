activate_this = '/home/ubuntu/ucap/ucap_venv/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, '/var/www/ucap-backend/')

from ucap import app as application
