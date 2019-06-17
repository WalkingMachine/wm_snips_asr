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
#   Local import
from snips_services import Snips_Services_Start

#   Constantes
HOTWORD_TECTED_FORCE = b'{"siteId":"default","modelId":""}'
ALL_INTENT = 'hermes/intent/'
MQTT_HOST = 'localhost'
MQTT_PORT = 1883
ROS_MESSAGE_I_ACTIVE_LISTENING = "/wm_snips_asr/enable_listening"
ROS_MESSAGE_O_ASR_TEXT = "/wm_snips_asr/asr_brut_text"
MQTT_SNIPS_END_SESSION = "hermes/dialogueManager/endSession" 
#   Modes
MQTT_SUBSCRIBE_ALL = True
SNIPS_AUTO_LISTEN = False
TEST_FEATURES = False


def snips_get_speach_text(msg):
    #   Retourne le texte brut comme le ARS as compris
    out = ""
    m = msg.payload.decode("utf-8")
    dicti = json.loads(m)
    try:
        out = dicti["input"]
    except Exception as e:
        print("[ERROR][snips_get_speach_text] " + str(e))
    return out


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
        print("[Snips_Supervisor] run")
        while(True):
            # Mode d'ecoute continus
            if (self.listening is False) or (time() - self.last_mqtt_message_time > 5):
                if SNIPS_AUTO_LISTEN:
                    client.publish("hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)
                self.last_mqtt_message_time = time()
            # Mode d'ecoute sur demmande
            if self.listen_on_demand_flag:
                # On vas redemander le demarage de l'ecoute de snips tant qu'il n'ecoute pas
                if self.is_listening_flag:
                    self.listen_on_demand_flag = False
                    self.is_listening_flag = False
                else:
                    client.publish("hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)
            sleep(self.watchdog_time)


class Snips_Anser(Thread):
    """ Initialisation et callback MQTT des services snips """
    def __init__(self):
        Thread.__init__(self)
        rospy.init_node('wm_snips_service', anonymous=True)
        rospy.Subscriber(ROS_MESSAGE_I_ACTIVE_LISTENING, String, lambda message: self.callback_ros_on_message(message, ROS_MESSAGE_I_ACTIVE_LISTENING))
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
        print("[MQTT]: rospy.spin()")
        rospy.spin()

    def callback_ros_on_message(self, message, topic):
        print("[RosSubscriper]" + message.data)
        if topic == ROS_MESSAGE_I_ACTIVE_LISTENING:
            # Activer le mecanisme qui s'assure que Snips se met en mode ecoute
            self.supervisor.listen_on_demand_flag = True
            # Demander a snips le mode ecoute, peut ne pas marcher du premier coup
            client.publish("hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)

    def on_connect(self, client, userdata, flags, rc):
        if MQTT_SUBSCRIBE_ALL:
            client.subscribe("hermes/#")
        client.subscribe('hermes/intent/#')
        client.subscribe('hermes/tts/sayFinished')
        client.subscribe("hermes/hotword/default/detected")
        # client.subscribe("hermes/asr/startListening")
        # client.subscribe("hermes/asr/stopListening")
        client.subscribe("hermes/dialogueManager/sessionStarted")
        client.subscribe("hermes/dialogueManager/sessionEnded")
        print("Connected to {0} with result code {1}".format(MQTT_HOST, rc))

    def on_message(self, client, userdata, msg):
        """ On MQTT message : callback """

        if MQTT_SUBSCRIBE_ALL and msg.topic != "hermes/audioServer/default/audioFrame":
            print(msg.topic)
            print(msg.payload.decode("utf-8"))

        if msg.topic.find(ALL_INTENT) == 0:
            dict_in = json.loads(msg.payload.decode("utf-8"))
            sessionID = dict_in["sessionId"]
            brutText = snips_get_speach_text(msg)
            print("[ROS Publish]" + str(brutText))
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
            # Snips envoit un stop au debut de l'ecoute et a la fin, il faut filtrer le bon stop
            # if self.listening_start_time - self.hotword_detect_time > 1.0:
            if (self.understand_at_time < self.listening_start_time):  # N'as rien entendus
                print("Rien entendus !")
                client.publish("hermes/tts/say", '{"text": "I didnt ear anything", "lang": "en", "siteId":"default"}')

            # Tests mode continus
            self.supervisor.listening = False

        if msg.topic == "hermes/hotword/default/detected":
            # client.publish("hermes/tts/say", '{"text": "Qua say tue veu", "lang": "en", "siteId":"default"}')
            self.hotword_detect_time = time()

        # Fiew local test on specific texts
        if TEST_FEATURES:
            if MQTT_SUBSCRIBE_ALL and msg.topic != "hermes/audioServer/default/audioFrame":
                print(msg.topic)
                print(msg.payload.decode("utf-8"))

            if msg.topic == 'hermes/tts/sayFinished':
                # client.publish("hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)
                if self.auto_listen_flag:
                    self.auto_listen_flag = False
                    # sleep(0.1)
                    if self.waiting_command_flag == "approval":
                        self.waiting_command_flag = None
                        client.publish("hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)
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
                
            if msg.topic == 'hermes/intent/denevraut:how_are_you':
                self.pub.publish(snips_get_speach_text(msg))
                client.publish("hermes/tts/say", '{"text": "Dont ask stupid question tabernack", "lang": "en", "siteId":"default"}')

            if msg.topic == 'hermes/intent/denevraut:fuck_you':
                self.pub.publish(snips_get_speach_text(msg))
                print(msg.topic)
                r = random.randint(1, 3)
                if r == 1:
                    client.publish("hermes/tts/say", '{"text": "oh. you are that kind of person", "lang": "en", "siteId":"default"}')
                elif r == 2:
                    client.publish("hermes/tts/say", '{"text": "oh. bad admin. verry bad", "lang": "en", "siteId":"default"}')
                else:
                    client.publish("hermes/tts/say", '{"text": "oh. im in pain", "lang": "en", "siteId":"default"}')

            if msg.topic == "hermes/intent/denevraut:no":
                self.pub.publish(snips_get_speach_text(msg))
                m = msg.payload.decode("utf-8")
                dicti = json.loads(m)
                try:
                    pp = '{"text": "Ok, you disaprouve' + \
                        "" + '", "lang": "en", "siteId":"default"}'
                    client.publish("hermes/tts/say", pp)
                except Exception:
                    print('+ text +')

            if msg.topic == "hermes/intent/denevraut:yes":
                self.pub.publish(snips_get_speach_text(msg))
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
                self.pub.publish(snips_get_speach_text(msg))
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
                    pp = '{"text": "Applying the fucking. ' + system_action + ". on the calisse the " + \
                        executable + executable2 + number + appoving + \
                        ' tabernack", "lang": "en", "siteId":"default"}'
                    client.publish("hermes/tts/say", pp)
                    self.auto_listen_flag = True
                except Exception as e:
                    print('+ text +')

            if msg.topic == "hermes/intent/denevraut:names":
                self.pub.publish(snips_get_speach_text(msg))
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
                self.pub.publish(snips_get_speach_text(msg))
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


if __name__ == "__main__":
    snips = Snips_Services_Start()

    client = mqtt.Client()
    snips_anser = Snips_Anser()
    client.on_connect = snips_anser.on_connect
    client.on_message = snips_anser.on_message
    connected = client.connect(MQTT_HOST, MQTT_PORT, 60)  # connected if 0

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
    #client.publish("hermes/hotword/default/detected", HOTWORD_TECTED_FORCE)
    client.publish("hermes/tts/say", '{"text": "' + hello + '", "lang": "en", "siteId":"default"}')
    print("[MQTT]: loop_forever()")
    client.loop_forever()
    snips.stop()    # OUBLIGATOIRE ! Les process snips reste ouvert si non!
