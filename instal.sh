#!/bin/bash

# Installe les dépendances
sudo apt-get update
sudo apt-get install -y dirmngr apt-transport- --allow-unauthenticated

# Ajoute le ppa de snips
sudo bash -c  'echo "deb https://debian.snips.ai/stretch stable main" > /etc/apt/sources.list.d/snips.list'
sudo apt-key adv --keyserver pgp.mit.edu --recv-keys F727C778CCB0A455
sudo apt-get update

# Installe snips
sudo apt-get install -y snips-platform-voice --allow-unauthenticated
sudo apt-get install -y snips-platform-demo --allow-unauthenticated
sudo apt-get install -y snips-tts --allow-unauthenticated
sudo apt-get install -y snips-watch --allow-unauthenticated
sudo apt-get install -y snips-template snips-skill-server --allow-unauthenticated

# Désactive les services
sudo systemctl disable snips-*
sudo rm system/multi-user.target.wants/snips-*
