from ublox_gps import MicropyGPS
from pyb import UART
from pyb import CAN
from SIM800L import Modem
import time  # FIXME to utime
from pyb import RTC
import pyb
import machine

import os

VERSION = 0.1


def log(*args):
    with open('can.log', 'a') as f:
        print(','.join(str(args)), file=f)

    os.sync()


def ota():
    modem.connect(apn=modem.scan_networks())  # FIXME check apn
    url = 'ota'  # FIXME add correct Website
    response = modem.http_request(url, 'GET')
    if float(response.content) > VERSION:
        url = 'update'  # FIXME add correct Website
        response = modem.http_request(url, 'GET')
        with open('/sd/main.py', 'w') as f:
            f.write(response.content)
            machine.soft_reset()

def setup():
    global gps, rtc, can, uart, sim_uart, interrupt, modem
    # GPS init
    uart = UART(1, 9600)  # init with given baudrate
    uart.init(9600, bits=8, parity=None, stop=1)  # init with given parameters

    # GPS Lib init
    gps = MicropyGPS()

    # CAN init 500 MHz
    can = CAN(1, CAN.LOOPBACK, extframe=False, prescaler=8, sjw=1, bs1=14, bs2=6)
    #can.setfilter(0, CAN.MASK32, 0, (0x0, 0x0))
    can.setfilter(0, CAN.LIST16, 0, (23, 24, 25, 26))

    # SIM800L Lib init
    sim_uart = UART(4, 9600, timeout=1000)

    # Create new modem object on the right Pins
    modem = Modem()

    # Initialize the modem
    #modem.initialize()

    # Clock init
    rtc = RTC()

    # Interrupt Flag init
    interrupt = False
    x5 = pyb.Pin.board.X5
    x5.irq(trigger=pyb.Pin.IRQ_RISING, handler=incoming_call)

    # Software Update
    #ota()


def incoming_call():
    global interrupt
    interrupt = True


def handle():
    global interrupt
    modem.connect(apn=modem.scan_networks())  # FIXME check apn
    url = 'uni'  # FIXME add correct Website
    response = modem.http_request(url, 'GET')

    # FIXME Add other commands

    url = 'Upload'  # FIXME add correct Website
    with open('/sd/can.log', 'r') as f:
        data = f.read()  # FIXME readlines
    response = modem.http_request(url, 'POST', data, 'application/text')
    if response.status_code == 200:
        os.remove('/sd/can.log')

    interrupt = False


def loop():
    gps_time = time.time()
    # can_time = time.time()

    while True:
        if time.time() - gps_time >= 1000:
            gps.updateall(uart.read())
            log((rtc.datetime(), gps.latitude, gps.longitude, gps.speed))

        can.send(b'1234', 23, timeout=10000)
        log((rtc.datetime(), can.recv(0)))
        print("logged!")

        if interrupt:
            handle()


setup()
loop()
