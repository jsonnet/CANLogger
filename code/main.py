from libs.ublox_gps import MicropyGPS
from libs.telegram import TelegramBot
from pyb import UART
from pyb import CAN
from pyb import LED
from libs.SIM800L import Modem
import utime
from pyb import RTC
import pyb
import machine

import os

GPS_LOG_TIME = 5000  # 5s
SHUTOFF_TIME = 30000  # 30s of no CAN activity
TOKEN = "REDACTED"


VERSION = 0.1
PATH = ''  # FIXME /sd/

# This will hold CAN IDs to be filtered for in the can log
can_filter = []

# Logs input to can.log
# args will be seperated by komma and printed each time a new line
def log(*args, file='can.log'):
    with open(PATH + file, 'a') as f:
        print(','.join(args), file=f)
    os.sync()


# Override is working | TODO test modem working?
def ota():
    url = 'https://raw.githubusercontent.com/jsonnet/CANLogger/master/version'
    response = modem.http_request(url, 'GET')

    # TODO resp content could now be changed to text
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
    global gps, rtc, can, can2, gps_uart, sim_uart, interrupt, modem, telegram
    
    # GPS init
    gps_uart = UART(1, 9600)  # init with given baudrate
    gps_uart.init(9600, bits=8, parity=None, stop=1, read_buf_len=512//2)  # init with given parameters
    gps = MicropyGPS()

    # CAN init (500 MHz)
    can = CAN(1, CAN.NORMAL)
    can2 = CAN(2, CAN.NORMAL)
    can.init(CAN.NORMAL, prescaler=4, sjw=1, bs1=16, bs2=4, auto_restart=True)
    can2.init(CAN.NORMAL, prescaler=4, sjw=1, bs1=14, bs2=6, auto_restart=True)
    can.setfilter(0, CAN.MASK32, 0, (0,0))
    #can.setfilter(0, CAN.LIST16, 0, (23, 24, 25, 26))

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
    telegram = TelegramBot(token=TOKEN, modem=modem)


# Callback function for incoming call to initiate attack mode
def incoming_call(_):
    global interrupt
    # Hangup call
    modem.hangup()

    # TODO possibly send SMS as conformation? or telegram but user must be known?!

    # light up red and yellow to indicate attack mode
    LED(2).on()
    LED(4).on()

    interrupt = True


# PoC for Telegram
def message_handler(messages):
    global interrupt
    # TODO maybe check if user is permitted?
    for message in messages:
        if message[2] == '/start':
            telegram.send(message[0], 'CAN Logger in attack mode, ready for you!')
        else:
            if message['text'] == "log":
                params = message['text'].split(" ")[1:]
                # get
                if params[0] == 'get':
                    with open(PATH + 'can.log', 'r') as f:
                        data = f.read()  # Okay, will print \n explicitly!
                    telegram.send(message[0], data)
                    os.remove(PATH + 'can.log')

                # clear
                elif params[0] == 'clear':
                    os.remove(PATH + 'can.log')

            elif message['text'] == "Replay":
                params = message['text'].split(" ")[1:]
                # split for params in msg
                pass
            elif message['text'] == "ingestion":
                params = message['text'].split(" ")[1:]
                # split for params in msg
                pass
            elif message['text'] == "filter":  # CAN Log Filter by ID
                params = message['text'].split(" ")[1:]
                # add
                if params[0] == 'add':
                    for id in params[1:]:
                        can_filter.append(id)
                # remove
                elif params[0] == 'remove':
                    for id in params[1:]:
                        can_filter.remove(id)
                # clear
                elif params[0] == 'clear':
                    can_filter.clear()

            elif message['text'] == "exit":
                LED(2).off()
                LED(4).off()
                LED(3).on()
                interrupt = False

            telegram.send(message[0], 'Executed!')


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
        #can2.send(b'1234', 23, timeout=10000)  ## FIXME debug
        can_id, can_rtr, can_fmi, can_Data = can.recv(0)

        # Filter for CAN Log
        if not can_filter or can_id in can_filter:
            log(rtc.datetime(), str(can_id), str(can_Data))

        ## Attack mode ##
        while interrupt:
            telegram.listen(message_handler)


setup()
loop()
