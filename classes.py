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
from requests.structures import CaseInsensitiveDict


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
        url = "https://www.blue.cl/wp-admin/admin-ajax.php"

        headers = CaseInsensitiveDict()
        headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:95.0) Gecko/20100101 Firefox/95.0"
        headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
        headers["Accept-Language"] = "es-CL,es;q=0.8,en-US;q=0.5,en;q=0.3"
        headers["Accept-Encoding"] = "gzip, deflate, br"
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Origin"] = "https://www.blue.cl"
        headers["DNT"] = "1"
        headers["Connection"] = "keep-alive"
        headers["Referer"] = f"https://www.blue.cl/seguimiento/?n_seguimiento={self.cod}"
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "cors"
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["Sec-GPC"] = "1"
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        headers["TE"] = "trailers"

        data = f"action=getTrackingInfo&n_seguimiento={self.cod}"

        response = requests.post(url, headers=headers, data=data)
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
        s.get(f"https://centrodeayuda.chilexpress.cl/seguimiento/{self.cod}")
        res = s.get(
            f"https://services.wschilexpress.com/agendadigital/api/v3/Tracking/GetTracking?gls_Consulta={self.cod}")
        data = res.json()
        last = data['ListTracking'][0]
        try:
            updated_at = datetime.fromisoformat(last["fec_track"])
        except ValueError:
            updated_at = datetime.strptime(last["fec_track"], '%Y-%m-%dT%H:%M:%S.%f')

        return f"{last['gls_tracking']} {updated_at.strftime('%Y-%m-%d %H:%M')}"


class UPSRaw(RawDataScrapper):
    def get_data(self) -> str:
        import requests

        s = requests.Session()
        s.get("https://www.ups.com/track?loc=es_CL&requester=ST/")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:92.0) Gecko/20100101 Firefox/92.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'es-CL,es;q=0.8,en-US;q=0.5,en;q=0.3',
            'Referer': 'https://www.ups.com/track?loc=es_CL&requester=ST/',
            'X-XSRF-TOKEN': s.cookies.get("X-XSRF-TOKEN-ST"),
            'Origin': 'https://www.ups.com',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-GPC': '1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        }

        data = {"Locale": "es_CL", "TrackingNumber": [self.cod]}

        response = s.post('https://www.ups.com/track/api/Track/GetStatus?loc=es_CL', headers=headers, json=data)
        result = response.json()
        return result['trackDetails'][-1]['packageStatus']
