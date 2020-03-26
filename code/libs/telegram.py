import gc
import json
import time


class TelegramBot:

    def __init__(self, token, modem):
        self.modem = modem

        self.url = 'https://api.telegram.org/bot' + token

        self.kbd = {
            'keyboard': [["log get", "log clear"], ["replay", "injection", "busoff"], ["filter", "filter clear"],
                         ["ota", "help", "exit"]],
            'resize_keyboard': True,
            'one_time_keyboard': True}

        self.upd = {
            'offset': 0,
            'limit': 1,
            'timeout': 30,
            'allowed_updates': ['message']}

    def send(self, chat_id, text, keyboard=None):
        data = {'chat_id': chat_id, 'text': text}
        if keyboard:
            self.kbd['keyboard'] = keyboard
            data['reply_markup'] = json.dumps(self.kbd)
        try:
            # TODO test
            resp = self.modem.http_request(url=self.url + '/sendMessage', mode='POST', data=data,
                                           content_type='application/json')
            return resp.status_code
        except:
            pass
        finally:
            gc.collect()

    # TODO WIP
    def sendFile(self, chat_id, file, keyboard=None):
        data = {'chat_id': chat_id, 'document': file}
        if keyboard:
            self.kbd['keyboard'] = keyboard
            data['reply_markup'] = json.dumps(self.kbd)
        try:
            pass
            # Upload file as multipart/form-data
            # requests.post(self.url + '/sendDocument', json=data)
            # https://api.telegram.org/file/bot<token>/<file_path> ???
            # FIXME implement
        except:
            pass
        finally:
            gc.collect()

    def update(self):
        result = []
        try:
            resp = self.modem.http_request(url=self.url + '/getUpdates', mode='POST', data=self.upd,
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

    def listen(self, handler):
        # while True:
        messages = self.update()
        if messages:
            handler(messages)
        time.sleep(2)
        # gc.collect()
