# https://core.telegram.org/bots/api
# Created by Joshua Sonnet
# (c) 2020 under GLP-3.0

import gc
import json
import time


class TelegramBot:

    def __init__(self, token, modem):
        # Takes the GSM modem as a Sim800L lib object
        self.modem = modem

        self.url = 'https://api.telegram.org/bot' + token

        # This creates the custom keyboard (-> see pic in report)
        self.kbd = {
            'keyboard': [["log get", "log clear"], ["replay", "injection", "busoff", "reply"],
                         ["filter", "filter clear"],
                         ["ota", "help", "exit"]],
            'resize_keyboard': True,
            'one_time_keyboard': False}

        # This specifies the update call
        self.upd = {
            'offset': 0,
            'limit': 1,
            'timeout': 30,
            'allowed_updates': ['message']}

    def send(self, chat_id, text):
        # data object for API
        data = {'chat_id': chat_id, 'text': text}
        try:
            # add keyboard
            data['reply_markup'] = json.dumps(self.kbd)
            # Send POST request with modem
            resp = self.modem.http_request(url=self.url + '/sendMessage', mode='POST', data=json.dumps(data),
                                           content_type='application/json')
            return resp.status_code
        except:
            pass
        finally:
            gc.collect()

    # TODO test
    def sendFile(self, chat_id, file):
        # data object for API (now with file)
        data = {'chat_id': chat_id, 'document': file}
        try:
            pass
            # Upload file as multipart/form-data
            # requests.post(url+"/sendDocument", {'chat_id':'ID'}, files={'document':('file.name',open('file','rb'))})
            resp = self.modem.http_request(url=self.url + '/sendMessage', mode='POST', data=json.dumps(data),
                                           content_type='multipart/form-data')
            return resp.status_code
        except:
            pass
        finally:
            gc.collect()

    def update(self):
        result = []
        try:
            resp = self.modem.http_request(url=self.url + '/getUpdates', mode='POST', data=json.dumps(self.upd),
                                           content_type='application/json')
            # jo = requests.post(self.url + '/getUpdates', json=self.upd).json()
            # TODO testing
            jo = json.loads(resp.text)
        except:
            return None
        finally:
            gc.collect()
        if 'result' in jo:
            for item in jo['result']:
                if 'text' in item['message']:
                    if 'username' not in item['message']['chat']:
                        item['message']['chat']['username'] = 'notset'
                    result.append((item['message']['chat']['id'],
                                   item['message']['chat']['username'],
                                   item['message']['text']))
        if len(result) > 0:
            self.upd['offset'] = jo['result'][-1]['update_id'] + 1

        return result

    # Check for new messages, call handler if new one found
    def listen(self, handler):
        messages = self.update()
        if messages:
            handler(messages)
        time.sleep(2)
        gc.collect()
