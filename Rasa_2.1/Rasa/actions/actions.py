from typing import Text, Dict, Any, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import json


class ActionReplyFlowerKnowledge(Action):
    def name(self) -> Text:
        return "action_reply_flower_knowledge"

    def run(self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        try:
            ranking = tracker.latest_message.get('intent_ranking', [])
            print(ranking)
            knowledge_type = tracker.get_intent_of_latest_message()
            KNOWLEDGE = ['info', 'body', 'leaf', 'root', 'color', 'climate', 'weather', 'price', 'season', 'grow',
                         'care', 'fengshui', 'buy', 'like', 'bodyLike', 'leafLike', 'rootLike', 'fertilizer', 'uses',
                         'meaningful']
            knowledge_type = knowledge_type.split("_")
            knowledge_type = knowledge_type[len(knowledge_type) - 1]
            index = KNOWLEDGE.index(knowledge_type)
            flower = tracker.get_slot('flower').lower()
            f = open('./actions/fact.json', encoding='utf-8')
            data = json.load(f)
            f.close()
            print(flower, index)
            dispatcher.utter_message(data[flower].split('\n')[index])
        except:
            pass
        return []
