import sqlite3
from contextlib import contextmanager
from globals import THIS_SERVER_DIR


@contextmanager
def sql_connection():
    c = sqlite3.connect(THIS_SERVER_DIR + "data/main.db")
    yield c
    c.close()
