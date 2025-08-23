from threading import Thread

from bottle import route, run


@route("/")
def home():
    return "I'm alive"


def run_server():
    run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=run_server)
    t.start()
