"""Control functions for Yelp external API
Each package needs to provide three methods:
1. check_credentials, which returns True if all necessary envars are
defined, False otherwise.
2. get_params, which returns a dictionary with max_records and
max_days_to_store values. The request cannot exceed these values.
3. update_records, which will process up to max_records which are
older than the max_days_to_store value. This method actually writes to
the database.
"""
import os

import time
import datetime

import pandas as pd
import requests


from utilities.db_manager import DBManager


# Check that all required envars are set. Returns true if envars are set, false otherwise.
# NOTE: Does not validate that the envar actually allows API access.
def check_credentials():
    try:
        if os.environ['YELP_ID'] is None:
            return False
        if os.environ['YELP_SECRET'] is None:
            return False
    except:
        return False
    return True


# Set the parameters for Yelp. The maximum number of queries per day is 50,000.
# We can only store the data for 14 days.
# The user can specify values on the command line, but only values smaller than the max are honored.
# Returns params in a dictionary.
def get_params(max_records, older_than):
    params = { 'max_records': 50000, 'max_days_to_store': 14 }
    if max_records > 0:
        params["max_records"] = min(params["max_records"], max_records)
    if older_than > 0:
        params["max_days_to_store"] = min(params["max_days_to_store"], older_than)
    return params


# This actually gets the records to update, calls the API function and writes back to the database.
# Returns the number of records updated, or None if a serious error occurred.
# Can return 0 if nothing found to update.
def update_records(api_params, db_params):
    # Create a DB manager object and a pandas dataframe with just the set of records to be updated.
    # Then call the Yelp API for each entry in the dataframe and update if it works.
    max_records = api_params['max_records']
    max_days_to_store = api_params['max_days_to_store']
    db_url = db_params['db_url']
    dbm = DBManager(db_url=db_url)
    
    sfdo = get_records(dbm, max_records, max_days_to_store)
    if sfdo is None:
        return None
    elif len(sfdo) < 1:
        return 0

    update_count = update_yelp(sfdo)
    if update_count is not None:
        dbm.write_df_table(sfdo, table_name='sba_sfdo_api_calls', schema='stg_analytics', dtype=None, if_exists='append')
    return update_count


# Internal only, to create a timetstamp string.
def get_timestamp():
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    return st

    
# This is internal only, returning a pandas dataframe with the records to be updated.
def get_records(dbm, max_records, max_days_to_store):
    # Build the date/time to compare. Subtract appropriate number of seconds from current time
    ts = time.time()
    ts -= max_days_to_store * 24 * 60 * 60
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
    query = "SELECT sba_sfdo.sba_sfdo_id, sba_sfdo.borr_name, sba_sfdo.borr_street, sba_sfdo.borr_city, sba_sfdo.borr_state, sba_sfdo.borr_zip, yelp_rating, yelp_total_reviews, yelp_url, yelp_timestamp FROM stg_analytics.sba_sfdo LEFT JOIN stg_analytics.sba_sfdo_api_calls ON sba_sfdo.sba_sfdo_id=sba_sfdo_api_calls.sba_sfdo_id WHERE yelp_timestamp is NULL OR yelp_timestamp <= '{}' ORDER BY yelp_timestamp LIMIT {}".format(st, max_records)
    sfdo = dbm.load_query_table(query)
    sfdo['full_address'] = sfdo['borr_street'] + ', '\
                           + sfdo['borr_city'] + ', '\
                           + sfdo['borr_state'] + ', '\
                           + sfdo['borr_zip']
    return sfdo


# This is internal only to actually get the Yelp data and add it to
# the dataframe.
def update_yelp(sfdo):
    data = { 'grant_type' : 'client_credentials',
             'client_id' : os.environ['YELP_ID'],
             'client_secret' : os.environ['YELP_SECRET'] }
    token = requests.post('https://api.yelp.com/oauth2/token', data=data)
    access_token = token.json()['access_token']
    url = 'https://api.yelp.com/v3/businesses/search'
    headers = { 'Authorization' : 'bearer %s' % access_token }

    update_count = 0
    for i in range(len(sfdo)):
        print('.', end='', flush=True)
        address = sfdo.loc[i]['full_address']
        name = sfdo.loc[i]['borr_name']
        params = { 'location' : address,
                   'term' : name,
                   'radius' : 100,
                   'limit' : 1 }
        resp = requests.get(url=url, params=params, headers=headers)
        try:
            bus = resp.json()['businesses'][0]
            sfdo.loc[i, 'yelp_rating'] = bus['rating']
            sfdo.loc[i, 'yelp_total_reviews'] = bus['review_count']
            sfdo.loc[i, 'yelp_url'] = bus['url']
            sfdo.loc[i, 'yelp_timestamp'] = get_timestamp()
            update_count += 1
        except:
            sfdo.loc[i, 'yelp_timestamp'] = get_timestamp()
            pass

    print(' ')
    return update_count