#!/usr/bin/python2.7 
# -*- coding: utf-8 -*-
#   Global import
import paho.mqtt.client as mqtt
import json
import random
import rospy
import os
from std_msgs.msg import String
from time import sleep, time
from threading import Thread
#   Local import
from snips_services import Snips_Services_Start
from snips_tests import Snips_Action_Tests

#   MQTT constantes
MQTT_HOST               = 'localhost'
MQTT_PORT               = 1883
MQTT_ENABLE_LISTENING   = b'{"siteId":"default","modelId":""}'
MQTT_ALL_INTENT         = 'hermes/intent/'
MQTT_SNIPS_END_SESSION  = "hermes/dialogueManager/endSession"
#   Ros Messages
ROS_MESSAGE_I_TTS               = "/wm_snips_asr/tts"
ROS_MESSAGE_I_ACTIVE_LISTENING  = "/wm_snips_asr/enable_listening"
ROS_MESSAGE_O_ASR_TEXT          = "/wm_snips_asr/asr_brut_text"
#   Modes
MQTT_SUBSCRIBE_ALL = True
MODE_HELP_LISTENING = False #force a écouter a tout prix
SNIPS_AUTO_LISTEN  = False  # Non fonctionnel
MODE_TESTS         = False
MODE_TESTER        = True

def snips_get_speach_text(msg):
    #   Retourne le texte brut comme le ARS as compris
    out = ""
    sessionID = ""
    m = msg.payload.decode("utf-8")
    dicti = json.loads(m)
    try:
        out         = dicti["input"]
        sessionID   = dicti["sessionId"]
    except Exception as e:
        print("[ERROR][snips_get_speach_text] " + str(e))
    return out, sessionID


class Snips_MQTT_Supervisor(Thread):
    """ Thread de suppervision: s'assurer que snips est toujours en train d'ecouter """
    def __init__(self, mqtt_client):
        Thread.__init__(self)
        self.mqtt_client = mqtt_client
        # Mode ecoute sur demmande
        self.listen_on_demand_flag = False
        self.is_listening_flag = False
        # Mode ecoute continus
        self.listening = False
        self.last_mqtt_message_time = time()
        # Autres
        self.watchdog_time = 1
        self.start()

    def run(self):
        print("[Snips_Supervisor] run")
        while(True):
            # Mode d'ecoute continus
            if (self.listening is True) and (time() - self.last_mqtt_message_time > 5.0) and MODE_HELP_LISTENING:
                print("Force listening")
                if SNIPS_AUTO_LISTEN:
                    self.mqtt_client.publish("hermes/hotword/default/detected", MQTT_ENABLE_LISTENING)
                self.last_mqtt_message_time = time()
            # Mode d'ecoute sur demmande
            if self.listen_on_demand_flag:
                # On vas redemander le demarage de l'ecoute de snips tant qu'il n'ecoute pas
                if self.is_listening_flag:
                    self.listen_on_demand_flag = False
                    self.is_listening_flag = False
                else:
                    self.mqtt_client.publish("hermes/hotword/default/detected", MQTT_ENABLE_LISTENING)
            sleep(self.watchdog_time)


class Snips_Anser(Thread):
    """ Initialisation et callback MQTT des services snips """
    def __init__(self, mqtt_client):
        Thread.__init__(self)
        self.mqtt_client = mqtt_client
        rospy.init_node('wm_snips_service', anonymous=True)
        rospy.Subscriber(ROS_MESSAGE_I_ACTIVE_LISTENING, String, lambda message: self.callback_ros_on_message(message, ROS_MESSAGE_I_ACTIVE_LISTENING))
        rospy.Subscriber(ROS_MESSAGE_I_TTS             , String, lambda message: self.callback_ros_on_message(message, ROS_MESSAGE_I_TTS))
        self.pub = rospy.Publisher(ROS_MESSAGE_O_ASR_TEXT, String, queue_size=10)
        self.start()
        #   Supervisor of the snips MQTT
        self.supervisor = Snips_MQTT_Supervisor(self.mqtt_client)
        #   Variable de supervision: savoir si snips as entendus quoi que ce soit
        self.listening_start_time = 0
        self.hotword_detect_time = 0
        self.understand_at_time = 0
        # Classe de tests
        self.tests = Snips_Action_Tests()

    def run(self):
        print("[MQTT]: rospy.spin()")
        rospy.spin()

    def callback_ros_on_message(self, message, topic):
        print("[RosSubscriper]" + message.data)
        if topic == ROS_MESSAGE_I_ACTIVE_LISTENING:
            print("[LISTENING]: ")
            # Activer le mecanisme qui s'assure que Snips se met en mode ecoute
            self.supervisor.listen_on_demand_flag = True
            # Demander a snips le mode ecoute, peut ne pas marcher du premier coup
            self.mqtt_client.publish("hermes/hotword/default/detected", MQTT_ENABLE_LISTENING)
        elif topic == ROS_MESSAGE_I_TTS:
            print("[TTS]: " + str(message))
            self.mqtt_client.publish("hermes/tts/say", '{"text": "' + str(message.data) + '", "lang": "en", "siteId":"default"}')

    def on_connect(self, mqtt_client, userdata, flags, rc):
        if MQTT_SUBSCRIBE_ALL:
            mqtt_client.subscribe("hermes/#")
        mqtt_client.subscribe('hermes/intent/#')
        mqtt_client.subscribe('hermes/tts/sayFinished')
        mqtt_client.subscribe("hermes/hotword/default/detected")
        mqtt_client.subscribe("hermes/dialogueManager/sessionStarted")
        mqtt_client.subscribe("hermes/dialogueManager/sessionEnded")
        print("Connected to {0} with result code {1}".format(MQTT_HOST, rc))

    def on_message(self, mqtt_client, userdata, msg):
        """ On MQTT message : callback """
        if MQTT_SUBSCRIBE_ALL and msg.topic != "hermes/audioServer/default/audioFrame":
            print(msg.topic)
            # print(msg.payload.decode("utf-8"))

        if MODE_TESTS:
            self.tests.execute(msg, mqtt_client)

        if msg.topic.find(MQTT_ALL_INTENT) == 0:
            brutText, sessionID = snips_get_speach_text(msg)
            print("[ROS Publish]" + str(brutText))
            self.pub.publish(brutText)
            self.understand_at_time = time()
            mqtt_client.publish(MQTT_SNIPS_END_SESSION, '{"sessionId":"' + sessionID + '"}')

        if msg.topic == "hermes/dialogueManager/sessionStarted":
            self.supervisor.is_listening_flag = True
            self.listening_start_time = time()
            # Tests mode continus
            self.supervisor.listening = True

        if msg.topic == "hermes/dialogueManager/sessionEnded":
            self.pub.publish("sessionEnded")
            # Verrifier si snips as entendus quelque chose
            if (self.understand_at_time < self.listening_start_time) and MODE_HELP_LISTENING:
                print("[MQTT] Snips: rien entendus")
                mqtt_client.publish("hermes/tts/say", '{"text": "I didnt ear anything", "lang": "en", "siteId":"default"}')
            # Tests mode continus
            self.supervisor.listening = False

        if msg.topic == "hermes/hotword/default/detected":
            self.hotword_detect_time = time()

        if msg.topic == 'hermes/tts/sayFinished' and MODE_TESTER:
            self.pub.publish("sayFinished")


class wm_snips_service():
    def __init__(self):
        snips = Snips_Services_Start()
        mqtt_client = mqtt.Client()
        snips_anser = Snips_Anser(mqtt_client)
        mqtt_client.on_connect = snips_anser.on_connect
        mqtt_client.on_message = snips_anser.on_message
        connected = mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)  # connected if 0

        messages = [
            "I\'m Listening",
            "Sara here",
            "Hi",
            "i like train",
            "mon osti de calisse",
            "Qua say tue veu tway",
            "i\'m stock, but i\'m stil going!",
            "you are not alone anymore",
            "stop messing up with me",
            "be carful with me"]
        hello = messages[random.randint(0, len(messages) - 1)]
        #hello = "I\'m Listening"
        mqtt_client.publish("hermes/tts/say", '{"text": "' + hello + '", "lang": "en", "siteId":"default"}')
        print("[MQTT]: loop_forever()")
        mqtt_client.loop_forever()
        snips.stop()    # OUBLIGATOIRE ! Les process snips reste ouvert si non!


if __name__ == "__main__":
    wm_snips_service()
