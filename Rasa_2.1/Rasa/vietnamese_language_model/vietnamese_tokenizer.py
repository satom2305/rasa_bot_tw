from __future__ import annotations
from pickletools import read_int4
import json
from typing import Any, Dict, List, Optional, Text
from rasa.nlu.tokenizers.tokenizer import Token, Tokenizer
from rasa.shared.nlu.training_data.message import Message

from rasa.shared.nlu.training_data.training_data import TrainingData
from rasa.nlu.constants import TOKENS_NAMES, MESSAGE_ATTRIBUTES
from rasa.engine.graph import ExecutionContext
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage

import os
from pyvi import ViTokenizer
#from vncorenlp import VnCoreNLP
import string

#used embedded VncoreNLP

import logging
import os
import socket
import subprocess
import time
from urllib.parse import urlparse

import requests
from requests.exceptions import RequestException


class MyVnCoreNLP(object):
    def __init__(self, address='http://127.0.0.1:8888', timeout=10, annotators='wseg,pos,ner,parse',
                 max_heap_size='-Xmx2g', quiet=True):

        # Add logger
        self.logger = logging.getLogger(__name__)
        # Default URL
        self.url = address
        self.timeout = timeout

        # Default process
        self.process = None

        if address.startswith('http'):
            o = urlparse(address)
            print(f"urlparse({address})={o}")
            self.url = '%s://%s' % (o.scheme, o.netloc)
            self.logger.info('Using an existing server: %s' % self.url)
        else:
            self.logger.info('Bad server url: %s' % self.url)
            raise RuntimeError('Bad server url.')
            return None
        # Waiting until the server is available
        attempts = 0
        while attempts < 100 and not self.is_alive():
            if self.process and self.process.poll():
                raise RuntimeError('The server has stopped working.')
            self.logger.info('Waiting until the server is available...')
            attempts += 1
            time.sleep(2)
        # Store the annotators getting from the server
        self.annotators = set(self.__get_annotators() + ['lang'])
        self.logger.info('The server is now available on: %s' % self.url)

    def close(self):
        # Stop the server and clean up
        if self.process:
            self.logger.info(__class__.__name__ + ': cleaning up...')
            self.logger.info(__class__.__name__ + ': done.')

    def is_alive(self):
        # Check if the server is alive
        try:
            response = requests.get(self.url, timeout=self.timeout)
            return response.ok
        except RequestException:
            pass
        return False

    def __get_annotators(self):
        # Get list of annotators from the server
        response = requests.get(self.url + '/annotators', timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def annotate(self, text, annotators=None):
        if isinstance(annotators, str):
            assert self.annotators.issuperset(annotators.split(
                ',')), 'Please ensure that the annotators "%s" are being used on the server.' % annotators
        data = {
            'text': text.encode('UTF-8'),
            'props': annotators
        }
        response = requests.post(self.url + '/handle', data=data, timeout=self.timeout)
        response.raise_for_status()
        response = response.json()
        assert response['status'], response['error']
        del response['status']
        return response

    def tokenize(self, text):
        sentences = self.annotate(text, annotators='wseg')['sentences']
        return [[w['form'] for w in s] for s in sentences]

    def pos_tag(self, text):
        sentences = self.annotate(text, annotators='wseg,pos')['sentences']
        return [[(w['form'], w['posTag']) for w in s] for s in sentences]

    def ner(self, text):
        sentences = self.annotate(text, annotators='wseg,pos,ner')['sentences']
        return [[(w['form'], w['nerLabel']) for w in s] for s in sentences]

    def dep_parse(self, text):
        sentences = self.annotate(text, annotators='wseg,pos,ner,parse')['sentences']
        # dep, governor, dependent
        return [[(w['depLabel'], w['head'], w['index']) for w in s] for s in sentences]

    def detect_language(self, text):
        return self.annotate(text, annotators='lang')['language']



@DefaultV1Recipe.register(
    DefaultV1Recipe.ComponentType.MESSAGE_TOKENIZER, is_trainable=False
)
class VietnameseTokenizer(Tokenizer):

    @staticmethod
    def get_default_config() -> Dict[Text, Any]:
        """Returns the component's default config."""
        return {
            # This *must* be added due to the parent class.
            "intent_tokenization_flag": False,
            # This *must* be added due to the parent class.
            "intent_split_symbol": "_",
            # This is the spaCy language setting.
            "case_sensitive": True,
            "pretrain_path": './vietnamese_language_model/',
            "corenlp_server_url": "http://127.0.0.1:8888",
        }

    def __init__(self, component_config: Dict[Text, Any]) -> None:
        super().__init__(component_config)
        self.corenlp_server_url=component_config.get('corenlp_server_url')
        self.pretrain_path=component_config.get('pretrain_path')
        if component_config.get('tokenizer') == 'vncorenlp':
            self.tokenizer = 'vncorenlp'
            self.rdrsegmenter = MyVnCoreNLP(address=self.corenlp_server_url, annotators="wseg", max_heap_size='-Xmx500m')
        else:
            self.tokenizer = 'pyvi'
        #now loading replace_list
        replace_list=self.pretrain_path+"replace_list.json"
        self.replace_list = json.load(open(replace_list, encoding='utf-8'))
        self.keys = self.replace_list.keys()
    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> VietnameseTokenizer:
        return cls(config)

    def tokenize(self, message: Message, attribute: Text) -> List[Token]:
        text = message.get(attribute)
        text = text.replace('Ã²a', 'oÃ ').replace('Ã³a', 'oÃ¡').replace('á»a', 'oáº£').replace('Ãµa', 'oÃ£').replace('á»a', 'oáº¡').replace('Ã²e', 'oÃ¨').replace('Ã³e', 'oÃ©').replace('á»e', 'oáº»').replace('Ãµe', 'oáº½').replace('á»e', 'oáº¹').replace('Ã¹y', 'uá»³').replace('Ãºy', 'uÃ½').replace('á»§y', 'uá»·').replace('Å©y', 'uá»¹').replace('á»¥y', 'uá»µ')
        text = text.lower()
        if (self.tokenizer == 'vncorenlp')|(self.tokenizer == 'PhobertTokenizer'):
            sentences = self.rdrsegmenter.tokenize(text)
            try:
                for sentence in sentences:
                    words = sentence
                    for i in range(len(words)):
                        if words[i] not in self.keys:
                            continue
                        words[i] = self.replace_list[words[i]]
                    text = ' '.join(words)
            except:
                words = []
                text = ' '
        else:
            words = ViTokenizer.tokenize(text).split()
            for i in range(len(words)):
                    if words[i] not in self.keys:
                        continue
                    words[i] = self.replace_list[words[i]]
            text = ' '.join(words)
        for k, v in self.replace_list.items():
            text = text.replace(k, v)
        words = text.split(' ')
        return self._convert_words_to_tokens(words, text)
