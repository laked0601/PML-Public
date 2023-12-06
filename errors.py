from webserver_app import wsapp
from flask import send_from_directory, jsonify, redirect
from globals import BASE_ENDPOINT

# Serve static files from the "static" directory
@wsapp.route(BASE_ENDPOINT + '/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


@wsapp.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad Request', "message": getattr(error, "description")}), 400


def not_found():
    return redirect(BASE_ENDPOINT + "/static/404.html")
