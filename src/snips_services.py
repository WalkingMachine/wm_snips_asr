#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
############################################################
#   -Classe de gestion des services non python snips.ai
#   -Snips.ai comprend plusieurs services connectée par MQTT
#   -pour l'utilisation minimale, 6 services doivent être activés
#       snips-audio-server  #gestion des entrées sorties audio
#       snips-asr           #algoritme de traitement de la voie
#       snips-hotword       #détection du mot clée "hey snips"  #Optionnel
#       snips-nlu           #Semble convertire la sortie du asr en texte
#       snips-dialogue      #Semble gérer toute sortie de nlu
#       snips-injection     #Sert a insérer des mot inconnue dans le model
#   -Comprend aussis un service de TTS
#       snips-tts
#
#   -La classe ici présente gere l'exécution des services snips.ai
#    et s'assure de leur bonne fermeture lorsque le programme meurt
############################################################

#   Global import
import subprocess
import sys
from threading import Thread
from time import sleep
import signal
import atexit
import os
try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty  # python 2.x


def _print(text, printOn):
    # Impression désactivable
    if printOn:
        print(text)


class _Snips_Service():
    """ Activer un seul service snips.ai """
    def __init__(self, command, name, printOn):
        self.name = name
        self.pOn = printOn

        _print("[I[" + str(command) + "] init", self.pOn)
        self.sp = subprocess.Popen(
            command,
            bufsize=64,
            shell=True,
            close_fds=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        self.run_stderr_alive = True
        t_err = Thread(target=self.run_stderr, args=(self.sp.stderr, None))
        t_err.daemon = True
        t_err.start()
        self.run_stdout_alive = True
        t_out = Thread(target=self.run_stdout, args=(self.sp.stdout, None))
        t_out.daemon = True
        t_out.start()

    def terminate(self):
        """ Ne fonctionne pas, pas au point """
        self.run_stderr_alive = False
        self.run_stdout_alive = False
        try:
            0
            # os.killpg(os.getpgid(self.sp.pid), signal.SIGTERM) #Trop radicale
            # self.sp.kill()                                     #Ne marche pas
            # try:
            #    self.sp.wait()
            #    if(self.sp.poll() is not None):
            #        for n in range(0, 10):
            #            self.sp.kill()
            #            self.sp.wait()
            #            _print("[E[" + self.name + "] " + "Process not Dead !!!", self.pOn)
            #            sleep(0.5)
            #    else:
            #        _print("[I[" + self.name + "] " + "Process terminated", self.pOn)
            # except Exception:
            #    _print("[E[" + self.name + "] " + "Failing wait or someting when killing", self.pOn)
        except Exception:
            _print("[E[" + self.name + "] " + "Failing killing process, probably not active", self.pOn)

    def run_stderr(self, out, _):
        while(self.run_stderr_alive):
            line = out.readline()[:-1]
            if len(line) > 0:
                _print("[E[" + self.name + "] " + line, self.pOn)

    def run_stdout(self, out, _):
        while(self.run_stdout_alive):
            line = out.readline()[:-1]
            if len(line) > 0:
                _print("[I[" + self.name + "] " + line, self.pOn)


class Snips_Services_Start(Thread):
    """ Demarer tout les services snips et gérer leur fermeture """
    def __init__(self, printOn=False):
        Thread.__init__(self)
        self.pOn = printOn
        self.daemon = True
        self.alive = True
        self.services = []
        self.start()
        atexit.register(self.sysexit_callback)
        # signal.signal(signal.SIGINT, self.exit_gracefully)  #Fonctionne
        # signal.signal(signal.SIGTERM, self.exit_gracefully) #Fonctionne
        if printOn is False:
            print("[i[Snips_Services_Start] No output")

    def exit_gracefully(self, signum, frame):
        _print("[E[Snips_Services_Start] KILL DETECTED KILLING ALL PROCESS", self.pOn)
        self.stop()

    def sysexit_callback(self):
        _print("[E[Snips_Services_Start] sys.exit() detected KILLING ALL PROCESS", self.pOn)
        self.stop()

    def stop(self):
        self.alive = False
        os.killpg(os.getpgid(os.getpid()), signal.SIGTERM)  # Sufisent et le plus efficace pour que le process meurt
        self._stop_services()

    def run(self):
        self._start_services()
        while(self.alive):
            sleep(1)

    def _start_services(self):
        self.services.append(_Snips_Service("snips-audio-server"   , "audio", printOn=self.pOn))
        self.services.append(_Snips_Service("snips-asr"            , "asr  ", printOn=self.pOn))
        self.services.append(_Snips_Service("snips-tts"            , "tts  ", printOn=self.pOn))
        # self.services.append(_Snips_Service("snips-hotword"        , "hotwd", printOn=self.pOn))
        self.services.append(_Snips_Service("snips-dialogue"       , "dialo", printOn=self.pOn))
        self.services.append(_Snips_Service("snips-nlu"            , "nlu  ", printOn=self.pOn))
        self.services.append(_Snips_Service("snips-injection"      , "injec", printOn=self.pOn))

    def _stop_services(self):
        for service in self.services:
            service.terminate()

    def _close_os_snips_process(self):
        # PAS ENCORE UTILISE, INSTABLE
        try:
            retcode = subprocess.Popen(
                ["pgrep snips-"],
                close_fds=True,
                bufsize=64,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

            pids = retcode.stdout.read().splitlines()
            _print(pids, self.pOn)
            for pid in pids:
                _print("[I[Snips_Services_Start] Killing process: " + str(pid), self.pOn)
                retcode = subprocess.call(["pkill", pid])
        except Exception as e:
            _print("[E[Snips_Services_Start]" + str(e), self.pOn)


if __name__ == "__main__":
    s = Snips_Services_Start(False)
    sleep(2)
    s.stop()     # Oubligatoire, si non les process snips ne meurt pas, ce stop est radicale
    sys.exit(1)  # Ne tue pas les process corectement
