#!/home/ubuntu/ucap/ucap_venv/bin/python
from flask import Flask
app = Flask(__name__)

import ucap.api
import ucap.web_routes