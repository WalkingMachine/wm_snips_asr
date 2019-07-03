#!/usr/bin/python2.7
#   Global import
import paho.mqtt.client as mqtt
import json
import random
import rospy
import os
from std_msgs.msg import String
from time import sleep, time
from threading import Thread
MQTT_ENABLE_LISTENING   = b'{"siteId":"default","modelId":""}'


class Snips_Action_Tests():
    def __init__(self):
        self.auto_listen_flag = False
        self.auto_listen_flag = False
        self.waiting_command_flag = None

    def execute(self, msg, client):
        if msg.topic == 'hermes/tts/sayFinished':
            # client.publish("hermes/hotword/default/detected", MQTT_ENABLE_LISTENING)
            if self.auto_listen_flag:
                self.auto_listen_flag = False
                self.auto_callback(client)

        if msg.topic == 'hermes/intent/denevraut:how_are_you':
            print("ddd")
            client.publish("hermes/tts/say", '{"text": "Dont ask stupid question tabernack", "lang": "en", "siteId":"default"}')

        if msg.topic == 'hermes/intent/denevraut:fuck_you':
            print(msg.topic)
            r = random.randint(1, 3)
            if r == 1:
                client.publish("hermes/tts/say", '{"text": "oh. you are that kind of person", "lang": "en", "siteId":"default"}')
            elif r == 2:
                client.publish("hermes/tts/say", '{"text": "oh. bad admin. verry bad", "lang": "en", "siteId":"default"}')
            else:
                client.publish("hermes/tts/say", '{"text": "oh. im in pain", "lang": "en", "siteId":"default"}')

        if msg.topic == "hermes/intent/denevraut:no":
            m = msg.payload.decode("utf-8")
            dicti = json.loads(m)
            try:
                pp = '{"text": "Ok, you disaprouve' + \
                    "" + '", "lang": "en", "siteId":"default"}'
                client.publish("hermes/tts/say", pp)
            except Exception:
                print('+ text +')

        if msg.topic == "hermes/intent/denevraut:yes":
            m = msg.payload.decode("utf-8")
            dicti = json.loads(m)
            try:
                pp = '{"text": "Ok, you approuve' + \
                    "" + '", "lang": "en", "siteId":"default"}'
                if self.waiting_command_flag == "bring_up":
                    self.waiting_command_flag = None
                    os.system("/bin/bash /home/jimmy/sara_ws/src/sara_launch/sh_files/Sara_total_bringup.sh")
                client.publish("hermes/tts/say", pp)
            except Exception:
                print('+ text +')

        if msg.topic == "hermes/intent/denevraut:action_program":
            self.action_program(msg, client)

        if msg.topic == "hermes/intent/denevraut:names":
            m = msg.payload.decode("utf-8")
            dicti = json.loads(m)
            try:
                text = dicti["input"]
                slots = dicti["slots"]
                print(slots)
                name = ((slots[0])["value"])["value"]

                print(json.dumps(dicti, indent=4, sort_keys=True))
                print(text)
                pp = '{"text": "Hi ' + name + \
                    '", "lang": "en", "siteId":"default"}'
                print(pp)
                client.publish("hermes/tts/say", pp)
            except Exception:
                print('+ text +')

        if msg.topic == "hermes/intent/denevraut:take_from_place_and_bring_to_me":
            m = msg.payload.decode("utf-8")
            dicti = json.loads(m)
            try:
                text = dicti["input"]
                print(json.dumps(dicti, indent=4, sort_keys=True))
                print(text)
                pp = '{"text": "did tou said.. ' + text + \
                    '", "lang": "en", "siteId":"default"}'
                print(pp)
                client.publish("hermes/tts/say", pp)
            except Exception:
                print('[ERROR] take_from_place_and_bring_to_me')

    def action_program(self, msg, client):
        m = msg.payload.decode("utf-8")
        dicti = json.loads(m)
        try:
            text = dicti["input"]
            slots = dicti["slots"]
            system_action = ""
            executable = ""
            executable2 = ""
            number = ""
            appoving = ".. Do you approve?"
            self.waiting_command_flag = "approval"  # Defaut fonction

            for slot in slots:
                if slot["entity"] == "system_action":
                    system_action = (slot["value"])["value"]
                elif slot["entity"] == "executable":
                    executable = (slot["value"])["value"]
                elif slot["entity"] == "snips/number":
                    number = str(int((slot["value"])["value"]))
                elif slot["entity"] == "service_name":
                    executable2 = (slot["value"])["value"]

            if executable2 == "sara everything":
                self.waiting_command_flag = "bring_up"
                print("Sara everyting in waiting")
            if executable2 == "snips assistant" and system_action == "stop":
                self.waiting_command_flag = "stopping"
                appoving = ""
                print("snips assistant stopping in waiting")
            if executable2 == "snips assistant" and system_action == "install":
                appoving = ""
                self.waiting_command_flag = "install_1"
                print("snips assistant install in waiting")
            # print(json.dumps(slots, indent=4, sort_keys=True))
            # print(json.dumps(dicti, indent=4, sort_keys=True))
            pp = '{"text": "Applying the. ' + system_action + ". on the " + \
                executable + executable2 + number + appoving + \
                '", "lang": "en", "siteId":"default"}'
            client.publish("hermes/tts/say", pp)
            self.auto_listen_flag = True
        except Exception as e:
            print("ERROR" + str(e))

    def auto_callback(self, client):
        if self.waiting_command_flag == "approval":
            self.waiting_command_flag = None
            client.publish("hermes/hotword/default/detected", MQTT_ENABLE_LISTENING)
        elif self.waiting_command_flag == "stopping":
            print("STOPPING")
            self.waiting_command_flag = None
            client.disconnect()
        elif self.waiting_command_flag == "install_1":
            self.waiting_command_flag = "install_2"
            client.publish("hermes/tts/say", '{"text": "Installing...", "lang": "en", "siteId":"default"}')
            print("Installing new snips assistant...")
            os.system("/bin/bash /home/jimmy/Desktop/snips/scripts/snips_install-assistant")
        elif self.waiting_command_flag == "install_2":
            self.waiting_command_flag = None
            client.publish("hermes/tts/say", '{"text": "Installing done", "lang": "en", "siteId":"default"}')