from ublox_gps import MicropyGPS
from telegram import TelegramBot
from pyb import UART
from pyb import CAN
from SIM800L import Modem
import utime
from pyb import RTC
import pyb
import machine

import os

GPS_LOG_TIME = 5000  # 5s
SHUTOFF_TIME = 30000  # 30s of no CAN activity

VERSION = 0.1
PATH = '' # FIXME /sd/

# Logs input to can.log
# args will be seperated by komma and printed each time a new line
def log(*args, file='can.log'):
    with open(PATH + file, 'a') as f:
        print(','.join(args), file=f)
    os.sync()


# Override is working | TODO test modem working? -> definitly response.content (see implementation!)
def ota():
    url = 'https://raw.githubusercontent.com/jsonnet/CANLogger/master/version?token=ABOA4NLENQYN3IFQMFUI77S6N6OZW'
    response = modem.http_request(url, 'GET')
    
    # If a newer version is available
    if float(response.content) > VERSION:
        url = 'https://raw.githubusercontent.com/jsonnet/CANLogger/master/code/main.py'
        response = modem.http_request(url, 'GET')
        # Override existing main file and reboot
        with open(PATH + 'main.py', 'w') as f:
            print(response.content, file=f)
            # Force buffer write and restart
            os.sync()
            machine.soft_reset()

def setup():
    # FIXME convert to class
    global gps, rtc, can, can2, gps_uart, sim_uart, interrupt, modem
    
    # GPS init
    gps_uart = UART(1, 9600)  # init with given baudrate
    gps_uart.init(9600, bits=8, parity=None, stop=1, read_buf_len=512//2)  # init with given parameters
    gps = MicropyGPS()

    # CAN init (500 MHz)
    can = CAN(1, CAN.NORMAL, prescaler=4, sjw=1, bs1=16, bs2=4, auto_restart=True)
    can2 = CAN(2, CAN.NORMAL, prescaler=4, sjw=1, bs1=14, bs2=6)
    #can.setfilter(0, CAN.MASK32, 0, (0x0, 0x0))
    can.setfilter(0, CAN.LIST16, 0, (23, 24, 25, 26))

    # SIM800L init
    sim_uart = UART(4, 9600, timeout=1000)
    modem = Modem(sim_uart)
    modem.initialize()
    
    modem.connect(apn=modem.scan_networks()[0][0])  # FIXME check apn or set static

    # Clock init #TODO set correct time and connect battery
    rtc = RTC()

    # Interrupt Flag init
    interrupt = False
    pyb.ExtInt('X5', pyb.ExtInt.IRQ_FALLING, pyb.Pin.PULL_UP, incoming_call)

    # Software Update
    ota()
    
    # Telegram Bot
    telegram = api.TelegramBot('API-KEY')


# Callback function for incoming call to initiate attack mode
def incoming_call(_):
    global interrupt
    # TODO modem hangup (already implemented cmd in modem!)
    # TODO possibly send SMS as conformation?
    # TODO light up some LEDs
    interrupt = True

# FIXME needs a lot of work
def handle():
    global interrupt
    modem.connect(apn=modem.scan_networks())  # FIXME check apn
    url = 'uni'  # FIXME add correct Website
    response = modem.http_request(url, 'GET')

    # FIXME Add other commands

    url = 'Upload'  # FIXME add correct Website
    with open(PATH + 'can.log', 'r') as f:
        data = f.read()  # Okay, will print \n explicitly!
    response = modem.http_request(url, 'POST', data, 'application/text')
    if response.status_code == 200:
        os.remove(PATH + 'can.log')

    # TODO only with EXIT command
    interrupt = False


# PoC for Telegram
def message_handler(messages):
    for message in messages:
        if message[2] == '/start':
            telegram.send(message[0], 'CAN Logger in attack mode, ready for you!')
        else:
            # do something switch case for all commands
            
            telegram.send(message[0], 'Okay!')
    #gc.collect()

telegram.listen(message_handler)



def loop():
    gps_time = utime.ticks_ms()

    while True:
        ## Logging mode ##
    
        # Only log gps once a second
        if utime.ticks_ms() - gps_time >= GPS_LOG_TIME:
            gps_time = utime.ticks_ms()
            
            gps.updateall(gps_uart.read())
            log(rtc.datetime(), gps.latitude_string(), gps.longitude_string(), gps.speed_string())

        # Log new incoming can messages
        #can2.send(b'1234', 23, timeout=10000) ## FIXME debug
        log(rtc.datetime(), str(can.recv(0)))
        
        ## Attack mode ##
        while interrupt:
            handle()


setup()
loop()
