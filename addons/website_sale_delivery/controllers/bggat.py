"""
    Copy this file and rename it bggat.py
    Fill your app_id and app_secret from your banggood account
"""

import json
import requests

from requests.structures import CaseInsensitiveDict

class GAT:
    def get_access_token():
        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"
        url = "https://api.banggood.com/getAccessToken?app_id=APP_ID&app_secret=APP_SECRET"
        response = requests.get(url, headers=headers)
        response = json.loads(response.text)
        
        print("get_access_token() " + str(response), file=open('PATH', 'a'))
        
        access_token_file = open('/PATH/addons/website_sale_delivery/controllers/.access_token', 'w', encoding='utf-8')
        access_token_file.write(response["access_token"])

        return response["access_token"]
