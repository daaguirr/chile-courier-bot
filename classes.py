import json
import re
import signal
import sys
import time
from dataclasses import dataclass
from typing import Union, List, Mapping

import bs4
import requests
from deepdiff import DeepDiff


# noinspection PyShadowingNames,PyUnusedLocal
def signal_handler(signal, frame):
    print("\nprogram exiting gracefully")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

JSON_Type = Union[str, int, float, bool, None, Mapping[str, 'JSON_Type'], List['JSON_Type']]


@dataclass
class RawDataScrapper:
    cod: str

    def get_data(self) -> str:
        raise NotImplementedError()


import random as rnd
from coolname import generate_slug


@dataclass
class DevDataScrapper(RawDataScrapper):
    last: str = generate_slug(4)

    def get_data(self) -> str:
        self.last = rnd.choice([self.last, generate_slug(4)])
        return self.last


class BluexRaw(RawDataScrapper):
    cod: str

    def get_data(self) -> str:
        res = requests.get(f"http://www.bluex.cl/nacional?documentos={self.cod}")
        soup = bs4.BeautifulSoup(res.content, "lxml")
        table = soup.find('table', attrs={'class': 'tableTracking'})
        row = table.find('tbody').find('tr').find_all('td')
        state = re.match(r".*Progreso(.*)", row[2].getText().strip('\n')).group(1)
        date = re.match(r".*Evento(.*)", row[3].getText().strip('\n')).group(1)
        return f"{date} {state}"


class PullmanBusCargoRaw(RawDataScrapper):
    cod: str

    def get_data(self) -> str:
        res = requests.post(
            f'http://www.pullmancargo.cl/WEB/cuentacorrientecarga/funciones/ajax2.php?op=consultaodt&odt={self.cod}')
        last = res.json()[0]
        return f"{last['FECHA']} {last['AGENCIA']} {last['estadoweb']}"


class StarkenRaw(RawDataScrapper):
    cod: str

    codes = {
        '11': lambda x, y: x + y,
        '12': lambda x, y: x - y,
        '13': lambda x, y: x * y,
    }

    def get_data(self) -> str:
        s = requests.Session()
        s.headers.update(
            {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:78.0) Gecko/20100101 Firefox/78.0'})
        res = s.get("https://www.starken.cl/personas")
        soup = bs4.BeautifulSoup(res.content, "lxml")
        form = soup.find(id='kiteknology-seguimiento-formulario-front')
        captcha_images = form.find('label', attrs={'for': 'edit-verificacion'}).find_all('img')
        src_images_captcha = [i['src'] for i in captcha_images]
        codes = [re.match('.*/(.*)\.png', s).group(1) for s in src_images_captcha]
        left, op, right = codes
        result = self.codes[op](int(left), int(right))
        from collections import OrderedDict
        request_data = OrderedDict()
        request_data['codigo'] = self.cod
        request_data['verificacion'] = ''
        request_data['op'] = 'Buscar'

        for i in form.find_all('input'):
            request_data[i['name']] = i['value']
        request_data['verificacion'] = str(int(result))
        url = "https://www.starken.cl/seguimiento?" + '&'.join([f"{k}={v}" for k, v in request_data.items()])
        res = s.get(url)
        soup_2 = bs4.BeautifulSoup(res.content, "lxml")

        result_q = soup_2.find(id='resultado-tabla-seguimiento').find('tbody').find('tr').find_all('td')
        return f"{result_q[1].getText()}"


class ChileExpressRaw(RawDataScrapper):
    cod: str

    def get_data(self) -> str:
        res = requests.post("https://www.chilexpress.cl/contingencia/Resultado", json={"FindOt": self.cod})
        soup = bs4.BeautifulSoup(res.content, "lxml")
        return soup.find(id="ListaTrackingOT").find('tr').getText(' ')
