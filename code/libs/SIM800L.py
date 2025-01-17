# Source https://github.com/pythings/Drivers/blob/master/SIM800L.py
# Originally by sarusso
# Modified by Joshua Sonnet 2020

import gc
import json
import time


def convert_to_string(buf):
    try:
        tt = buf.decode('utf-8').strip()
        return tt
    except UnicodeError:
        tmp = bytearray(buf)
        for i in range(len(tmp)):
            if tmp[i] > 127:
                tmp[i] = ord('#')
        return bytes(tmp).decode('utf-8').strip()


class GenericATError(Exception):
    pass


class Response(object):

    def __init__(self, content, status_code=200):
        self.status_code = int(status_code)
        self.encoding = "utf-8"
        self._cached = content
        self.status = status_code

    def close(self):
        self._cached = None

    @property
    def content(self):
        return self._cached

    @property
    def text(self):
        return str(self.content, self.encoding)

    def json(self):
        import ujson
        return ujson.loads(self.content)


class Modem(object):

    def __init__(self, uart):

        self.initialized = False
        self.modem_info = None

        self.uart = uart

    # ----------------------
    #  Modem initializer
    # ----------------------
    def initialize(self):
        # Test AT commands
        retries = 0
        while True:
            try:
                self.modem_info = self.execute_at_command('modeminfo')
                self.execute_at_command('wakeup')
                self.execute_at_command('dumpdata', 'AT+CMEE=0')
            except:
                retries += 1
                if retries < 3:
                    # logger.debug('Error in getting modem info, retrying.. (#{})'.format(retries))
                    time.sleep(3)
                else:
                    raise
            else:
                break

        # logger.debug('Ok, modem "{}" is ready and accepting commands'.format(self.modem_info))

        # Set initialized flag and support vars
        self.initialized = True

    # ----------------------
    # Execute AT commands
    # ----------------------
    def execute_at_command(self, command, data=None, clean_output=True):

        # Commands dictionary. Not the best approach ever, but works nicely.
        commands = {
            'modeminfo': {'string': 'ATI', 'timeout': 3, 'end': 'OK'},
            'fwrevision': {'string': 'AT+CGMR', 'timeout': 3, 'end': 'OK'},
            'battery': {'string': 'AT+CBC', 'timeout': 3, 'end': 'OK'},
            'scan': {'string': 'AT+COPS=?', 'timeout': 60, 'end': 'OK'},
            'network': {'string': 'AT+COPS?', 'timeout': 3, 'end': 'OK'},
            'signal': {'string': 'AT+CSQ', 'timeout': 3, 'end': 'OK'},
            'checkreg': {'string': 'AT+CREG?', 'timeout': 3, 'end': None},
            'setapn': {'string': 'AT+SAPBR=3,1,"APN","{}"'.format(data), 'timeout': 3, 'end': 'OK'},
            'initgprs': {'string': 'AT+SAPBR=3,1,"Contype","GPRS"', 'timeout': 3, 'end': 'OK'},
            # Appeared on hologram net here or below
            'opengprs': {'string': 'AT+SAPBR=1,1', 'timeout': 3, 'end': 'OK'},
            'getbear': {'string': 'AT+SAPBR=2,1', 'timeout': 3, 'end': 'OK'},
            'inithttp': {'string': 'AT+HTTPINIT', 'timeout': 3, 'end': 'OK'},
            'sethttp': {'string': 'AT+HTTPPARA="CID",1', 'timeout': 3, 'end': 'OK'},
            'enablessl': {'string': 'AT+HTTPSSL=1', 'timeout': 3, 'end': 'OK'},
            'disablessl': {'string': 'AT+HTTPSSL=0', 'timeout': 3, 'end': 'OK'},
            'initurl': {'string': 'AT+HTTPPARA="URL","{}"'.format(data), 'timeout': 3, 'end': 'OK'},
            'doget': {'string': 'AT+HTTPACTION=0', 'timeout': 3, 'end': '+HTTPACTION'},
            'setcontent': {'string': 'AT+HTTPPARA="CONTENT","{}"'.format(data), 'timeout': 3, 'end': 'OK'},
            'postlen': {'string': 'AT+HTTPDATA={},5000'.format(data), 'timeout': 3, 'end': 'DOWNLOAD'},
            # "data" is data_lenght in this context, while 5000 is the timeout
            'dumpdata': {'string': data, 'timeout': 3, 'end': 'OK'},
            'dopost': {'string': 'AT+HTTPACTION=1', 'timeout': 3, 'end': '+HTTPACTION'},
            'getdata': {'string': 'AT+HTTPREAD', 'timeout': 3, 'end': 'OK'},
            'closehttp': {'string': 'AT+HTTPTERM', 'timeout': 3, 'end': 'OK'},
            'closebear': {'string': 'AT+SAPBR=0,1', 'timeout': 3, 'end': 'OK'},

            # CUSTOM CMDs
            'hangup': {'string': 'ATH', 'timeout': 3, 'end': 'OK'},
            'sleepmode': {'string': 'AT+CSCLK=1', 'timeout': 3, 'end': 'OK'},
            'wakeup': {'string': 'AT+CSCLK=0', 'timeout': 3, 'end': 'OK'}
            # DTR high, module can enter sleep mode. DTR changes to low level, module quit sleep mode.
        }

        # References:
        # https://github.com/olablt/micropython-sim800/blob/4d181f0c5d678143801d191fdd8a60996211ef03/app_sim.py
        # https://arduino.stackexchange.com/questions/23878/what-is-the-proper-way-to-send-data-through-http-using-sim908
        # https://stackoverflow.com/questions/35781962/post-api-rest-with-at-commands-sim800
        # https://arduino.stackexchange.com/questions/34901/http-post-request-in-json-format-using-sim900-module (full post example)

        # Sanity checks
        if command not in commands:
            raise Exception('Unknown command "{}"'.format(command))

        # Clear backlog of uart
        while self.uart.any():
            self.uart.readchar()

        # Support vars
        command_string = commands[command]['string']
        excpected_end = commands[command]['end']
        timeout = commands[command]['timeout']

        # Fix for adding carriage return to dict (json post request)
        if type(command_string) is dict:
            command_string = json.dumps(command_string)

        # Add carriage return to send command
        command_string_for_at = "{}\r\n".format(command_string)
        # Execute the AT command
        self.uart.write(command_string_for_at)

        # Support vars
        pre_end = True
        output = ''
        empty_reads = 0

        _ = self.uart.readline()  # discard linefeed etc

        while True:

            line = self.uart.readline()
            if not line:
                time.sleep(1)
                empty_reads += 1
                if empty_reads > timeout:
                    raise Exception('Timeout for command "{}" (timeout={})'.format(command, timeout))
            else:
                # Convert line to string
                line_str = convert_to_string(line)

                # Do we have an error?
                if line_str == 'ERROR':
                    raise GenericATError('Got generic AT error')

                # If we had a pre-end, do we have the expected end?
                if line_str == excpected_end:
                    break
                if pre_end and line_str.startswith('{}'.format(excpected_end)):
                    output += line_str
                    break

                # Do we have a pre-end?
                if line_str == '':
                    pre_end = True
                else:
                    pre_end = False

                # Save this line unless in particular conditions
                if command == 'getdata' and line_str.startswith('+HTTPREAD:'):
                    pass
                else:
                    output += line_str

        # Remove the command string from the output
        output = output.replace(command_string + '\r\r\n', '')

        # ..and remove the last \r\n added by the AT protocol
        if output.endswith('\r\n'):
            output = output[:-2]

        # Also, clean output if needed
        if clean_output:
            output = output.replace('\r', '')
            output = output.replace('\n\n', '')
            if output.startswith('\n'):
                output = output[1:]
            if output.endswith('\n'):
                output = output[:-1]

        # logger.debug('Returning "{}"'.format(output.encode('utf8')))

        # Return
        try:
            return output
        finally:
            gc.collect()

    # ----------------------
    #  Function commands
    # ----------------------

    def hangup(self):
        output = self.execute_at_command('hangup')
        return output

    def get_info(self):
        output = self.execute_at_command('modeminfo')
        return output

    def battery_status(self):
        output = self.execute_at_command('battery')
        return output

    def scan_networks(self):
        networks = []
        output = self.execute_at_command('scan')
        pieces = output.split('(', 1)[1].split(')')
        for piece in pieces:
            piece = piece.replace(',(', '')
            subpieces = piece.split(',')
            if len(subpieces) != 4:
                continue
            networks.append({'name': json.loads(subpieces[1]), 'shortname': json.loads(subpieces[2]),
                             'id': json.loads(subpieces[3])})
        return networks

    def get_current_network(self):
        output = self.execute_at_command('network')
        network = output.split(',')[-1]
        if network.startswith('"'):
            network = network[1:]
        if network.endswith('"'):
            network = network[:-1]
        # If after filtering we did not filter anything: there was no network
        if network.startswith('+COPS'):
            return None
        return network

    def get_signal_strength(self):
        # See more at https://m2msupport.net/m2msupport/atcsq-signal-quality/
        output = self.execute_at_command('signal')
        signal = int(output.split(':')[1].split(',')[0])
        signal_ratio = float(signal) / float(30)  # 30 is the maximum value (2 is the minimum)
        return signal_ratio

    def get_ip_addr(self):
        output = self.execute_at_command('getbear')
        output = output.split('+')[-1]  # Remove potential leftovers in the buffer before the "+SAPBR:" response
        pieces = output.split(',')
        if len(pieces) != 3:
            raise Exception('Cannot parse "{}" to get an IP address'.format(output))
        ip_addr = pieces[2].replace('"', '')
        if len(ip_addr.split('.')) != 4:
            raise Exception('Cannot parse "{}" to get an IP address'.format(output))
        if ip_addr == '0.0.0.0':
            return None
        return ip_addr

    def connect(self, apn):
        if not self.initialized:
            raise Exception('Modem is not initialized, cannot connect')

        # Are we already connected?
        if self.get_ip_addr():
            # logger.debug('Modem is already connected, not reconnecting.')
            return

        # Closing bearer if left opened from a previous connect gone wrong:
        # logger.debug('Trying to close the bearer in case it was left open somehow..')
        try:
            self.execute_at_command('closebear')
        except GenericATError:
            pass

        # First, init gprs
        # logger.debug('Connect step #1 (initgprs)')
        self.execute_at_command('initgprs')

        # Second, set the APN
        if apn:
            # logger.debug('Connect step #2 (setapn)')
            self.execute_at_command('setapn', apn)

        # Then, open the GPRS connection.
        # logger.debug('Connect step #3 (opengprs)')
        self.execute_at_command('opengprs')

        # Ok, now wait until we get a valid IP address
        retries = 0
        max_retries = 5
        while True:
            retries += 1
            ip_addr = self.get_ip_addr()
            if not ip_addr:
                retries += 1
                if retries > max_retries:
                    raise Exception('Cannot connect modem as could not get a valid IP address')
                # logger.debug('No valid IP address yet, retrying... (#')
                time.sleep(1)
            else:
                break

    def disconnect(self):

        # Close bearer
        try:
            self.execute_at_command('closebear')
        except GenericATError:
            pass

        # Check that we are actually disconnected
        ip_addr = self.get_ip_addr()
        if ip_addr:
            raise Exception('Error, we should be disconnected but we still have an IP address ({})'.format(ip_addr))

    def http_request(self, url, mode='GET', data=None, content_type='application/json'):

        # Protocol check.
        assert url.startswith('http'), 'Unable to handle communication protocol for URL "{}"'.format(url)

        # Are we  connected?
        if not self.get_ip_addr():
            raise Exception('Error, modem is not connected')

        # Close the http context if left open somehow
        # logger.debug('Close the http context if left open somehow...')
        try:
            self.execute_at_command('closehttp')
        except GenericATError:
            pass

        # First, init and set http
        # logger.debug('Http request step #1.1 (inithttp)')
        self.execute_at_command('inithttp')
        # logger.debug('Http request step #1.2 (sethttp)')
        self.execute_at_command('sethttp')

        # Do we have to enable ssl as well?
        ssl_available = self.modem_info >= 'SIM800 R14.00'
        if ssl_available:
            if url.startswith('https://'):
                # logger.debug('Http request step #1.3 (enablessl)')
                self.execute_at_command('enablessl')
            elif url.startswith('http://'):
                # logger.debug('Http request step #1.3 (disablessl)')
                self.execute_at_command('disablessl')
        else:
            if url.startswith('https://'):
                raise NotImplementedError("SSL is only supported by firmware revisions >= R14.00")

        # Second, init and execute the request
        # logger.debug('Http request step #2.1 (initurl)')
        self.execute_at_command('initurl', data=url)

        if mode == 'GET':

            # logger.debug('Http request step #2.2 (doget)')
            output = self.execute_at_command('doget')
            response_status_code = int(output.split(',')[1])
            # logger.debug('Response status code: "{}"'.format(response_status_code))

        elif mode == 'POST':

            # logger.debug('Http request step #2.2 (setcontent)')
            self.execute_at_command('setcontent', content_type)

            # logger.debug('Http request step #2.3 (postlen)')
            self.execute_at_command('postlen', len(data))

            # logger.debug('Http request step #2.4 (dumpdata)')
            self.execute_at_command('dumpdata', data)

            # logger.debug('Http request step #2.5 (dopost)')
            output = self.execute_at_command('dopost')
            response_status_code = int(output.split(',')[1])
            # logger.debug('Response status code: "{}"'.format(response_status_code))


        else:
            raise Exception('Unknown mode "{}'.format(mode))

        # Third, get data
        # logger.debug('Http request step #4 (getdata)')
        response_content = self.execute_at_command('getdata', clean_output=False)

        # logger.debug(response_content)

        # Then, close the http context
        # logger.debug('Http request step #4 (closehttp)')
        self.execute_at_command('closehttp')

        return Response(status_code=response_status_code, content=response_content)
