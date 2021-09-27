import json
import random as rnd
import signal
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Union, List, Mapping

import bs4
import requests
from coolname import generate_slug


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
        length = rnd.randint(4, 8)
        self.last = rnd.choice([self.last, generate_slug(length)])
        return self.last


class BluexRaw(RawDataScrapper):
    cod: str

    def get_data(self) -> str:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:87.0) Gecko/20100101 Firefox/87.0',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'es-CL,es;q=0.8,en-US;q=0.5,en;q=0.3',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://www.bluex.cl',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Referer': 'https://www.bluex.cl/seguimiento/?n_seguimiento=6899442620',
            'Sec-GPC': '1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
            'TE': 'Trailers',
        }

        data = {
            'action': 'getTrackingInfo',
            'n_seguimiento': self.cod
        }

        response = requests.post('https://www.bluex.cl/wp-admin/admin-ajax.php', headers=headers, data=data)

        response_data = response.json()["data"]
        data_raw = json.loads(response_data[0])

        last_data = data_raw['s1']['listaDocumentos'][0]['ultimoPinchazo']
        date = datetime.strptime(last_data["fecha"], '%Y%m%d%H%M%S').isoformat()

        return f"{date} {last_data['nombreTipo']}"


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
        s = requests.Session()
        s.headers.update(
            {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:78.0) Gecko/20100101 Firefox/78.0',
             'Ocp-Apim-Subscription-Key': "7b878d2423f349e3b8bbb9b3607d4215"
             })
        s.get("https://centrodeayuda.chilexpress.cl/seguimiento/712437989605")
        res = s.get(
            "https://services.wschilexpress.com/agendadigital/api/v3/Tracking/GetTracking?gls_Consulta=712437989605")
        data = res.json()
        last = data['ListTracking'][0]

        updated_at = datetime.fromisoformat(last["fec_track"])

        return f"{last['gls_tracking']} {updated_at.strftime('%Y-%m-%d %H:%M')}"
