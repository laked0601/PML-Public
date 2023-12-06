from webserver_app import wsapp
from globals import BASE_ENDPOINT, THIS_SERVER_DIR
from application import portfolios
from application import reports
import errors
from flask import redirect, send_file


@wsapp.route(BASE_ENDPOINT + "/")
def site_index():
    return redirect(BASE_ENDPOINT + "/portfolios.html")


@wsapp.route(BASE_ENDPOINT + "/download-site")
def download_site():
    return send_file(THIS_SERVER_DIR + "pml.zip")


if __name__ == "__main__":
    wsapp.run()



