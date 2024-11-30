#!/usr/bin/python3

import RPi.GPIO as GPIO
from dht11 import DHT11
import time
import datetime

# initialize GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# read data using pin 26
sensor = DHT11(signal_pin=26)

try:
    while True:
        result = sensor.read()
        if result.is_valid():
            print(f"{datetime.datetime.now()} - Temperature: {result.temperature}, Humidity: {result.humidity}")
        else:
            print(f"{datetime.datetime.now()} - Invalid data: {result}")
        time.sleep(2)

except KeyboardInterrupt:
    GPIO.cleanup()