"""Hit Google Civic API to get congressional districts"""

import os

import requests

import re


def get_congressional_dist_by_addr(df):
    """
    Get Contressional District from Google Maps

    Keyword Args:
      df: DataFrame with business information to request congressional districts
    """

    url = 'https://www.googleapis.com/civicinfo/v2/representatives'

    for i in range(len(df)):
        # Each call needs the API key and the address to search
        address = df.loc[i]['full_address']
        params = { 'key': os.environ['GOOGLE_STATIC_MAPS_API'], 'address': address }

        resp = requests.get(url=url, params=params)

        try:
            """
            Convert return set to JSON and get the divisions dict, which
            contains country/state/cd as one of the values.
            """

            results = resp.json()
            divisions = results['divisions']
            if divisions is not None:
                keys = divisions.keys()
                for key in keys:
                    # Regex match on ocd-division/country:us/state:(two letters)/cd:(digits)
                    res = re.search('ocd-division/country:us/state:(\w\w)/cd:([0-9]+)', key)
                    if res:
                        st = res.group(1)
                        dist = res.group(2)
                        dist_txt = st + '-' + dist
                        df.loc[i, 'civic_dist'] = dist_txt

        except:
            pass

    return df
