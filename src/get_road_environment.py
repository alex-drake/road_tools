import requests
import os
import re
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point

def get_cycle_lane_layer(url='https://cycling.data.tfl.gov.uk/CyclingInfrastructure/data/lines/cycle_lane_track.json', download = True):
    """
    Download the latest version of the Cycle Lane / Track layer from the Transport for London Cycling Infrastructure Database
    
    The file is approximately 30MB in size (as of May 2021)
    """
    if download:
        r = requests.get(url=url, allow_redirects=True)

        os.makedirs('../data/cid/', exist_ok=True)

        if r.status_code == 200:
            file = open('../data/cid/cycle_lane_track.json','wb')
            file.write(r.content)
            file.close()

        else:
            print(f"Status code {r.status_code}. File not downloaded.")

    cid = gpd.read_file('../data/cid/cycle_lane_track.json')

    return cid


def get_traffic_calming_layer(url='https://cycling.data.tfl.gov.uk/CyclingInfrastructure/data/points/traffic_calming.json', download = True):
    """
    Download the latest version of the Traffic Calming from the Transport for London Cycling Infrastructure Database
    
    The file is approximately 38MB in size (as of May 2021)
    """
    if download:
        r = requests.get(url=url, allow_redirects=True)

        os.makedirs('../data/cid/', exist_ok=True)

        if r.status_code == 200:
            file = open('../data/cid/traffic_calming.json','wb')
            file.write(r.content)
            file.close()

        else:
            print(f"Status code {r.status_code}. File not downloaded.")

    traffic_calming = gpd.read_file('../data/cid/traffic_calming.json')

    return traffic_calming

def get_overpass_turbo_data(url='http://overpass-api.de/api/interpreter', query=None):
    """
    Download data from the Overpass Turbo API
    """

    if query is not None:
        r = requests.get(url, params={'data': query})

        os.makedirs('../data/osm/', exist_ok=True)

        if r.status_code == 200:
            data = r.json()['elements']

        else:
            print(f'Status code {r.status_code}. File not downloaded')

            data = list()

    return data

def get_crossing_data(filename='tmp'):
    crossing_query = """
        [out:json];
        rel[boundary][name="Greater London"];
        map_to_area;
        (node["highway"="crossing"](area);
        );
        out geom;
        """
    data = get_overpass_turbo_data(query=crossing_query)

    if len(data) > 0:

        for feature in data:
            for key, value in feature['tags'].items():
                if key in ['crossing','crossing_ref']:
                    feature[key] = value

        df = pd.DataFrame(data)
        df['geometry'] = [Point(x, y) for x, y in zip(df.lon, df.lat)]
        df = gpd.GeoDataFrame(df.drop(['lat','lon','tags'], axis=1), geometry='geometry')

        df.to_file(f'../data/osm/{filename}.geojson', driver='GeoJSON')

    else:

        df = gpd.GeoDataFrame()
    
    return df

def get_bus_stop_data(filename='tmp'):
    bus_stop_query = """
        [out:json];
        rel[boundary][name="Greater London"];
        map_to_area;
        (node["highway"="bus_stop"](area);
        );
        out geom;
        """
    data = get_overpass_turbo_data(query=bus_stop_query)

    if len(data) > 0:

        for feature in data:
            for key, value in feature['tags'].items():
                if key in ['naptan:AtcoCode','naptan:Bearing']:
                    feature[key] = value

        df = pd.DataFrame(data)
        df['geometry'] = [Point(x, y) for x, y in zip(df.lon, df.lat)]
        df = gpd.GeoDataFrame(df.drop(['lat','lon','tags'], axis=1), geometry='geometry')

        df.to_file(f'../data/osm/{filename}.geojson', driver='GeoJSON')

    else:

        df = gpd.GeoDataFrame()
    
    return df
