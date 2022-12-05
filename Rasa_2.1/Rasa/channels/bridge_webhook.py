import json
from typing import Text, Dict, Optional, Callable, Awaitable, Any

from sanic import Blueprint, response
from sanic.request import Request

from rasa.core.channels.channel import (
    CollectingOutputChannel,
    UserMessage,
    InputChannel,
)
from rasa.core.channels.rest import RestInput
from rasa.utils.endpoints import EndpointConfig, ClientResponseError
from sanic.response import HTTPResponse

from actions.utils import DefaultParser, FacebookParser, InputParser, Utils, ZaloParser
import requests
import traceback
import time
LOG_ORIGIN = 'BRIGDE_STATION'

class BotstationOutput(CollectingOutputChannel):
    @classmethod
    def name(cls) -> Text:
        return "NEO_Brigde_Webhook_Output"

    def __init__(self, endpoint: EndpointConfig, config) -> None:
        self.botstation_endpoint = endpoint
        self.parser: InputParser
        self.config = config
        super().__init__()

    async def _persist_message(self, message: Dict[Text, Any]) -> None:
        await super()._persist_message(message)
        bot_data=self.latest_output()
        print(f"BotstationOutput._persist_message->self.latest_output()={bot_data}")
        try:
            if 'custom' in self.latest_output():
                self.parser.append_bot_data(
                    self.latest_output()['custom']['json'])
            else:
                self.parser.append_bot_data(self.latest_output())
            
            self.parser.append_bot_name(self.config['bot_name'])
            
            bot_url=self.config['url']

            #HA Proxy Server ID
            ha_id = self.parser.response['metadata']['serverid']
            
            print(
                f"Bot.Channel({bot_url})._persist_message.latest_output={self.parser.response}")
            headers = {
                'content-type': 'application/json',
                'Cookie' : 'SERVERID=' +str(ha_id),
            }
            requests.post(self.config['url'], headers=headers,
                          json=self.parser.response, timeout=self.config['bot_station_timeout'])
            self.messages.clear()
            time.sleep(0)
        except:
            tb = traceback.format_exc()
            Utils.console_log(tb,
                              'OUTPUT_CHANNEL._persist_message')


class BotstationInput(RestInput):
    """A custom REST http input channel that responds using a callback server.

    Incoming messages are received through a REST interface. Responses
    are sent asynchronously by calling a configured external REST endpoint."""

    @classmethod
    def name(cls) -> Text:
        return "NEO_Brigde_Webhook_Input"

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        cls.config = credentials
        return cls(EndpointConfig.from_dict(credentials))

    def __init__(self, endpoint: EndpointConfig) -> None:
        self.botstation_endpoint = endpoint
        self.output_channel = self.get_output_channel()
        self.message_handler = MessageHandler(
            'BOT', self.name(), self.output_channel, self.config)

    async def _extract_metadata(self, req: Request) -> Optional[Text]:
        return req.json.get("metadata", None)

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        botstation_webhook = Blueprint(
            "NEO_Brigde_Webhook_Input_webhook", __name__)

        @botstation_webhook.route("/", methods=["GET"])
        async def health(_: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @botstation_webhook.route("/webhook", methods=["POST"])
        async def webhook(request: Request) -> HTTPResponse:
            await self.message_handler.handle_message(request.json, on_new_message)
            return response.json({
                'status': 1,
                'message': 'success'
            })

        return botstation_webhook

    def get_output_channel(self) -> BotstationOutput:
        return BotstationOutput(self.botstation_endpoint, self.config)


class MessageHandler():
    last_message: Dict[Text, Any]
    last_json_response: Dict[Text, Any]

    def __init__(self, verify: Text, input_channel: Text, output_channel: BotstationOutput, config) -> None:
        self.verify = verify
        self.output_channel = output_channel
        self.last_message = {}
        self.input_channel = input_channel
        self.config = config
        Utils.console_log('Message handler is up and running', LOG_ORIGIN)

    def log_last_message(self):
        # TODO: Implements backend message logging
        pass

    async def handle_message(self, data: Dict[Text, Any], on_new_message: Callable[[UserMessage], Awaitable[None]]):
        # Create input parser for incoming post and match parser type to input type
        self.parser = InputParser(data)
        self.parser = DefaultParser(data)

        # Save last message
        self.last_message = data
        self.log_last_message()

        # Tell parser to create a skeleton with provided info for bot's response
        self.parser.create_response()

        # Pass current parser to output channel
        self.output_channel.parser = self.parser

        # Handle message by RASA SDK
        message = UserMessage(
            text=self.parser.get_fields('message'),
            output_channel=self.output_channel,
            sender_id=self.parser.get_fields('recipient_id'),
            input_channel=self.input_channel,
            metadata=self.parser.get_fields('metadata')
        )

        await on_new_message(message)

        return
