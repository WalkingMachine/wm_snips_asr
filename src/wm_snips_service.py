#!/usr/bin/python2.7
import paho.mqtt.client as mqtt
import json
import random
import rospy
import os
from std_msgs.msg import String
from time import sleep, time
from threading import Thread

HOST = 'localhost'
PORT = 1883

# HOTWORD_TECTED_FORCE = b'{"siteId":"default","modelId":"sara","modelVersion":"workflow-hey_snips_subww_feedback_10seeds-2018_12_04T12_13_05_evaluated_model_0002","modelType":"universal","currentSensitivity":0.5,"detectionSignalMs":1557415912991,"endSignalMs":1557415912991}'
HOTWORD_TECTED_FORCE = b'{"siteId":"default","modelId":"sara"}'


def snips_get_rawtext(msg):
    out = ""
    m = msg.payload.decode("utf-8")
    dicti = json.loads(m)
    try:
        out = dicti["input"]
    except Exception as e:
        print("ERROR " + str(e))
    return out


class Snips_check(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.listening = False
        self.last_mqtt_message_time = time()
        self.start()

    def run(self):
        print("x")
        while(True):
            if (self.listening == False) or (time() - self.last_mqtt_message_time > 5):
                client.publish("hermes/hotword/default/detected",
                               HOTWORD_TECTED_FORCE)
                self.last_mqtt_message_time = time()
            sleep(0.5)


class Snips_Anser(Thread):
    def __init__(self):
        Thread.__init__(self)
        rospy.init_node('talker', anonymous=True)
        self.start()
        self.pub = rospy.Publisher('snips_nlu', String, queue_size=10)
        self.listen_auto = False
        self.waiting_command = None
        self.supervisor = Snips_check()

    def run(self):
        # rospy.Subscriber("snips_nlu", String, self.callback_ros)
        print("RUN")
        rospy.spin()

    def callback_ros(self, data):
        print(data.data)

    def on_connect(self, client, userdata, flags, rc):
        client.subscribe("hermes/#")
        client.subscribe('hermes/intent/denevraut:#')
        client.subscribe('hermes/tts/sayFinished')
        client.subscribe("hermes/hotword/default/detected")
        print("Connected to {0} with result code {1}".format(HOST, rc))

    def on_message(self, client, userdata, msg):
        # print("Message received on topic {0}: {1}".format(msg.topic, msg.payload))
        # if msg.topic != "hermes/audioServer/default/audioFrame":
        # print(msg.topic)
        if msg.topic != "hermes/audioServer/default/audioFrame":
            print(msg.topic)
            print(msg.payload.decode("utf-8"))
            # self.pub.publish(msg.payload.decode("utf-8"))
            # print(msg.topic)
        if msg.topic == 'hermes/intent/denevraut:how_are_you':
            self.pub.publish(snips_get_rawtext(msg))
            client.publish(
                "hermes/tts/say", '{"text": "Dont ask stupid question tabernack", "lang": "en", "siteId":"default"}')

        if msg.topic == "hermes/asr/startListening":
            self.supervisor.listening = True

        if msg.topic == "hermes/asr/stopListening":
            self.supervisor.listening = False
            # client.publish("hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)

        if msg.topic == 'hermes/tts/sayFinished':
            # client.publish("hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)
            if self.listen_auto:
                self.listen_auto = False
                # sleep(0.1)
                if self.waiting_command == "approval":
                    self.waiting_command = None
                    client.publish(
                        "hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)
                elif self.waiting_command == "stopping":
                    print("STOPPING")
                    self.waiting_command = None
                    client.disconnect()
                elif self.waiting_command == "install_1":
                    self.waiting_command = "install_2"
                    client.publish(
                        "hermes/tts/say", '{"text": "Installing...", "lang": "en", "siteId":"default"}')
                    print("Installing new snips assistant...")
                    os.system(
                        "/bin/bash /home/jimmy/Desktop/snips/scripts/snips_install-assistant")
                elif self.waiting_command == "install_2":
                    self.waiting_command = None
                    client.publish(
                        "hermes/tts/say", '{"text": "Installing done", "lang": "en", "siteId":"default"}')

        # print(msg.topic)
        if msg.topic == 'hermes/intent/denevraut:fuck_you':
            self.pub.publish(snips_get_rawtext(msg))
            print(msg.topic)
            r = random.randint(1, 3)
            if r == 1:
                client.publish(
                    "hermes/tts/say", '{"text": "oh. you are that kind of person", "lang": "en", "siteId":"default"}')
            elif r == 2:
                client.publish(
                    "hermes/tts/say", '{"text": "oh. bad admin. verry bad", "lang": "en", "siteId":"default"}')
            else:
                client.publish(
                    "hermes/tts/say", '{"text": "oh. im in pain", "lang": "en", "siteId":"default"}')

        if msg.topic == "hermes/hotword/default/detected":
            # client.publish("hermes/tts/say", '{"text": "Qua say tue veu", "lang": "en", "siteId":"default"}')
            0

        if msg.topic == "hermes/intent/denevraut:no":
            self.pub.publish(snips_get_rawtext(msg))
            m = msg.payload.decode("utf-8")
            dicti = json.loads(m)
            # k = dicti.keys()
            try:
                pp = '{"text": "Ok, you disaprouve tabernack' + \
                    ""+'", "lang": "en", "siteId":"default"}'
                # print(pp)
                client.publish("hermes/tts/say", pp)
            except Exception:
                print('+ text +')

        if msg.topic == "hermes/intent/denevraut:yes":
            self.pub.publish(snips_get_rawtext(msg))
            m = msg.payload.decode("utf-8")
            dicti = json.loads(m)
            # k = dicti.keys()
            try:
                pp = '{"text": "Ok, you approuve calisse' + \
                    ""+'", "lang": "en", "siteId":"default"}'
                if self.waiting_command == "bring_up":
                    self.waiting_command = None
                    os.system(
                        "/bin/bash /home/jimmy/sara_ws/src/sara_launch/sh_files/Sara_total_bringup.sh")

                # print(pp)
                client.publish("hermes/tts/say", pp)
            except Exception:
                print('+ text +')

        if msg.topic == "hermes/intent/denevraut:action_program":
            self.pub.publish(snips_get_rawtext(msg))
            m = msg.payload.decode("utf-8")
            dicti = json.loads(m)
            # k = dicti.keys()
            try:
                text = dicti["input"]
                slots = dicti["slots"]
                system_action = ""
                executable = ""
                executable2 = ""
                number = ""
                appoving = ".. Do you approve?"
                self.waiting_command = "approval"  # Defaut fonction

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
                    self.waiting_command = "bring_up"
                    print("Sara everyting in waiting")
                if executable2 == "snips assistant" and system_action == "stop":
                    self.waiting_command = "stopping"
                    appoving = ""
                    print("snips assistant stopping in waiting")
                if executable2 == "snips assistant" and system_action == "install":
                    appoving = ""
                    self.waiting_command = "install_1"
                    print("snips assistant install in waiting")

                # print(json.dumps(slots, indent=4, sort_keys=True))
                # print(json.dumps(dicti, indent=4, sort_keys=True))
                # print(text)
                pp = '{"text": "Applying the fucking. ' + system_action + ". on the calisse the " + \
                    executable + executable2 + number + appoving + \
                    ' tabernack", "lang": "en", "siteId":"default"}'
                client.publish("hermes/tts/say", pp)
                self.listen_auto = True
                # sleep(4)
                # print(pp)

            except Exception as e:
                print('+ text +')

        if msg.topic == "hermes/intent/denevraut:names":
            self.pub.publish(snips_get_rawtext(msg))
            m = msg.payload.decode("utf-8")
            dicti = json.loads(m)
            # k = dicti.keys()
            try:
                text = dicti["input"]
                slots = dicti["slots"]
                print(slots)
                name = ((slots[0])["value"])["value"]

                print(json.dumps(dicti, indent=4, sort_keys=True))
                print(text)
                pp = '{"text": "Is your name. ' + name + \
                    '", "lang": "en", "siteId":"default"}'
                print(pp)
                client.publish("hermes/tts/say", pp)
            except Exception:
                print('+ text +')

        if msg.topic == "hermes/intent/denevraut:take_from_place_and_bring_to_me":
            self.pub.publish(snips_get_rawtext(msg))
            m = msg.payload.decode("utf-8")
            dicti = json.loads(m)
            # k = dicti.keys()
            try:
                text = dicti["input"]
                print(json.dumps(dicti, indent=4, sort_keys=True))
                print(text)
                pp = '{"text": "did tou said.. ' + text + \
                    '", "lang": "en", "siteId":"default"}'
                print(pp)
                client.publish("hermes/tts/say", pp)
            except Exception:
                print('+ text +')
            # print(dicti)
            # for kk in k:
            #    print(kk)


if __name__ == "__main__":
    client = mqtt.Client()
    snips_anser = Snips_Anser()
    client.on_connect = snips_anser.on_connect
    client.on_message = snips_anser.on_message

    client.connect(HOST, PORT, 60)
    detectedCode = {
        "siteId": "default",
        "modelId": "sara",
        "modelVersion": "workflow-hey_snips_subww_feedback_10seeds-2018_12_04T12_13_05_evaluated_model_0002",
        "modelType": "universal",
        "currentSensitivity": 0.5,
        "detectionSignalMs": 1557415912991,
        "endSignalMs": 1557415912991
    }

    # mon osti de calisse. I\'m lestening
    client.publish(
        "hermes/tts/say", '{"text": "I\'m Listening", "lang": "en", "siteId":"default"}')
    # client.publish("hermes/hotword/default/detected", b'{"siteId":"default","modelId":"none"}')
    # client.publish("hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)
    # client.publish("hermes/tts/say", '{"text": "Qua say tue veu ", "lang": "en", "siteId":"default"}')
    # client.publish("hermes/tts/say", '{"text": "i like train", "lang": "en", "siteId":"default"}')
    # client.publish("hermes/tts/say", '{"text": "take me a beer from the fridge", "lang": "en", "siteId":"default"}')
    # client.publish("hermes/dialogueManager/startSession")
    # client.publish("hermes/tts/say", '{"text": "i\m ready to go", "lang": "en", "siteId":"default"}')
    # client.publish("hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)

    # client.publish("hermes/tts/say", '{"text": "i\'m stock. but, i\'m, stil, going!", "lang": "en", "siteId":"default"}')
    client.loop_forever()
