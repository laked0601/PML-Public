from flask import Flask
from flask_wtf.csrf import CSRFProtect
from secrets import token_urlsafe
from os import path
from flask_cors import CORS
from application.flaskfilters import *

THIS_SERVER_DIR = path.dirname(path.abspath(__file__)).replace('\\', '/') + '/'
wsapp = Flask(__name__,
              template_folder=THIS_SERVER_DIR + "webpages",
              static_folder=THIS_SERVER_DIR + "static")
wsapp.secret_key = token_urlsafe(16)
csrf = CSRFProtect(wsapp)

cors = CORS(wsapp, origins=["*"])

wsapp.jinja_env.filters['format_large_number'] = format_large_number
wsapp.jinja_env.filters['rounded_percentage'] = rounded_percentage
wsapp.jinja_env.filters['accounting_format'] = accounting_format
