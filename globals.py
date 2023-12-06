from flask import redirect
from os import path

MAX_UNSIGNED_INT = 4_294_967_295
THIS_SERVER_DIR = path.dirname(path.abspath(__file__)).replace('\\', '/') + '/'
THIS_SERVER_URL = "http://127.0.0.1:5000"
DEMO = False
BASE_ENDPOINT = ""
