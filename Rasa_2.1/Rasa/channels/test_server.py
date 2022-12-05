from sanic import Sanic, json, response
from sanic.request import Request
from sanic.response import HTTPResponse
import requests


def create_app() -> Sanic:

    bot_app = Sanic("callback_server", configure_logging=False)

    @bot_app.post("/bot")
    def print_response(request: Request) -> HTTPResponse:
        print(request.json)
        return response.json('', status=200)

    return bot_app


if __name__ == "__main__":
    app = create_app()
    port = 5068

    print(f"Starting callback server on port {port}.")
    app.run("10.252.10.240", port)
