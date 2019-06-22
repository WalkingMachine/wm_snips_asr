#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#   Global import
import paho.mqtt.client as mqtt
import json
import random
import rospy
import os
from std_msgs.msg import String, Empty
from time import sleep, time
from threading import Thread
#   Local import
from snips_services import Snips_Services_Start

#   MQTT constantes
MQTT_HOST               = 'localhost'
MQTT_PORT               = 1883
MQTT_ENABLE_LISTENING   = b'{"siteId":"default","modelId":""}'
MQTT_ALL_INTENT         = 'hermes/intent/'
MQTT_SNIPS_END_SESSION  = "hermes/dialogueManager/endSession"
#   Ros Messages
ROS_MESSAGE_I_ACTIVE_LISTENING  = "/wm_snips_asr/enable_listening"
ROS_MESSAGE_O_ASR_TEXT          = "/wm_snips_asr/asr_brut_text"
#   Modes
MQTT_SUBSCRIBE_ALL = False
SNIPS_AUTO_LISTEN  = False  # Non fonctionnel
TEST_FEATURES      = False


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
        rospy.loginfo("[ERROR][snips_get_speach_text] " + str(e))
    return out, sessionID


class Snips_MQTT_Supervisor(Thread):
    """ Thread de suppervision: s'assurer que snips est toujours en train d'ecouter """
    def __init__(self):
        Thread.__init__(self)
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
        rospy.loginfo("[Snips_Supervisor] run")
        while not rospy.is_shutdown():
            # Mode d'ecoute continus
            if (self.listening is False) or (time() - self.last_mqtt_message_time > 5):
                if SNIPS_AUTO_LISTEN:
                    client.publish("hermes/hotword/default/detected", MQTT_ENABLE_LISTENING)
                self.last_mqtt_message_time = time()
            # Mode d'ecoute sur demmande
            if self.listen_on_demand_flag:
                # On vas redemander le demarage de l'ecoute de snips tant qu'il n'ecoute pas
                if self.is_listening_flag:
                    self.listen_on_demand_flag = False
                    self.is_listening_flag = False
                else:
                    client.publish("hermes/hotword/default/detected", MQTT_ENABLE_LISTENING)
            sleep(self.watchdog_time)


class Snips_Anser(Thread):
    """ Initialisation et callback MQTT des services snips """
    def __init__(self):
        Thread.__init__(self)
        rospy.init_node('wm_snips_service')
        rospy.Subscriber(ROS_MESSAGE_I_ACTIVE_LISTENING, Empty, self.callback_ros_on_message)
        self.pub = rospy.Publisher(ROS_MESSAGE_O_ASR_TEXT, String, queue_size=10)
        self.start()
        #   Supervisor of the snips MQTT
        self.supervisor = Snips_MQTT_Supervisor()
        #   Variable de supervision: savoir si snips as entendus quoi que ce soit
        self.listening_start_time = 0
        self.hotword_detect_time = 0
        self.understand_at_time = 0
        #   Flags
        self.auto_listen_flag = False
        self.waiting_command_flag = None

    def run(self):
        rospy.loginfo("[MQTT]: rospy.spin()")
        rospy.spin()

    def callback_ros_on_message(self, message):
        # Activer le mecanisme qui s'assure que Snips se met en mode ecoute
        self.supervisor.listen_on_demand_flag = True
        # Demander a snips le mode ecoute, peut ne pas marcher du premier coup
        client.publish("hermes/hotword/default/detected", MQTT_ENABLE_LISTENING)

    def on_connect(self, client, userdata, flags, rc):
        if MQTT_SUBSCRIBE_ALL:
            client.subscribe("hermes/#")
        client.subscribe('hermes/intent/#')
        client.subscribe('hermes/tts/sayFinished')
        client.subscribe("hermes/hotword/default/detected")
        client.subscribe("hermes/dialogueManager/sessionStarted")
        client.subscribe("hermes/dialogueManager/sessionEnded")
        rospy.loginfo("Connected to {0} with result code {1}".format(MQTT_HOST, rc))

    def on_message(self, client, userdata, msg):
        """ On MQTT message : callback """

        if MQTT_SUBSCRIBE_ALL and msg.topic != "hermes/audioServer/default/audioFrame":
            rospy.loginfo(msg.topic)
            rospy.loginfo(msg.payload.decode("utf-8"))

        if msg.topic.find(MQTT_ALL_INTENT) == 0:
            brutText, sessionID = snips_get_speach_text(msg)
            rospy.loginfo("[ROS Publish]" + str(brutText))
            self.pub.publish(brutText)
            self.understand_at_time = time()
            client.publish(MQTT_SNIPS_END_SESSION, '{"sessionId":"' + sessionID + '"}')

        if msg.topic == "hermes/dialogueManager/sessionStarted":
            self.supervisor.is_listening_flag = True
            self.listening_start_time = time()
            # Tests mode continus
            self.supervisor.listening = True

        if msg.topic == "hermes/dialogueManager/sessionEnded":
            # Verrifier si snips as entendus quelque chose
            if (self.understand_at_time < self.listening_start_time):
                rospy.loginfo("[MQTT] Snips: rien entendus")
                client.publish("hermes/tts/say", '{"text": "I didnt ear anything", "lang": "en", "siteId":"default"}')
            # Tests mode continus
            self.supervisor.listening = False

        if msg.topic == "hermes/hotword/default/detected":
            self.hotword_detect_time = time()


#   Main code, not a tests
if __name__ == "__main__":
    try:
        snips = Snips_Services_Start()

        client = mqtt.Client()
        snips_anser = Snips_Anser()
        client.on_connect = snips_anser.on_connect
        client.on_message = snips_anser.on_message
        connected = client.connect(MQTT_HOST, MQTT_PORT, 60)  # connected if 0



        hello = "I\'m Listening"
        client.publish("hermes/tts/say", '{"text": "' + hello + '", "lang": "en", "siteId":"default"}')
        rospy.loginfo("[MQTT]: loop_forever()")
        while not rospy.is_shutdown():
            client.loop()
    except rospy.ROSInterruptException:
        rospy.loginfo("Killing snips")
        snips.stop()    # OUBLIGATOIRE ! Les process snips reste ouvert si non!
        pass
