import re
import signal
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Union, List, Mapping
import random as rnd
from coolname import generate_slug

import bs4
import requests


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

    def get_data(self) -> str:
        s = requests.Session()
        s.headers.update(
            {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:78.0) Gecko/20100101 Firefox/78.0'})
        s.get("https://www.starken.cl/seguimiento")
        res = s.get(f"https://gateway.starken.cl/tracking/orden-flete-dte/of/{self.cod}")
        data = res.json()
        updated_at = datetime.strptime(data["updated_at"], '%Y-%m-%dT%H:%M:%S.%fZ')

        return f"{data['status']} {updated_at.strftime('%Y-%m-%d %H:%M')}"


class ChileExpressRaw(RawDataScrapper):
    cod: str

    def get_data(self) -> str:
        res = requests.post("https://www.chilexpress.cl/contingencia/Resultado", json={"FindOt": self.cod})
        soup = bs4.BeautifulSoup(res.content, "lxml")
        return soup.find(id="ListaTrackingOT").find('tr').getText(' ')
