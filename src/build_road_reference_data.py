import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
import os
import matplotlib.pyplot as plt

import geo_functions as gf
import get_road_environment as gre

latlong = 'epsg:4326'
ukgrid = 'epsg:27700'

refresh_ref_data = False

# create interim folder
os.makedirs('../data/interim/', exist_ok=True)

## Retreive Data
# Highways network - todo: switch to open data, e.g. OS Open Roads or OpenStreetMap
highway = gpd.read_file('../data/os-highways/os_highways_data.geojson')

# Import Reference Data
if refresh_ref_data:
    bus_stop_gdf = gre.get_bus_stop_data('bus_stops')
    crossing_gdf = gre.get_crossing_data('crossings')

else:
    bus_stop_gdf = gpd.read_file('../data/osm/bus_stops.geojson')
    crossing_gdf = gpd.read_file('../data/osm/crossings.geojson')

cyclelane_gdf = gre.get_cycle_lane_layer(download=refresh_ref_data)
traffic_calming_gdf = gre.get_traffic_calming_layer(download=refresh_ref_data)
# bus_lanes_gdf # - find suitable source for bus lane data...OSM?

## set GeoDataframes to UKGRID (EPSG=27700)
for shape_layer in [highway, bus_stop_gdf, crossing_gdf, cyclelane_gdf, traffic_calming_gdf]:
    shape_layer.to_crs(ukgrid, inplace=True)

## Match Crossings to network
crossing_matched_gdf = gf.match_point_to_line(highway, ['TOID','identifier'], crossing_gdf, buffer=15)
crossing_matched_gdf.to_file('../data/interim/crossings_matched.geojson', driver='GeoJSON')
del crossing_gdf

# set crossing types
crossing_matched_gdf['type'] = 'unmarked_crossing'
crossing_matched_gdf.loc[crossing_matched_gdf['crossing'].isin(['traffic_signals','signals','pedestrian_signals','controlled','traffic_signals;marked','pelican']),'type'] = 'signalled_crossing'
crossing_matched_gdf.loc[crossing_matched_gdf['crossing'].isin(['uncontrolled','marked','zebra','uncontrolled;marked','pelican']),'type'] = 'marked_crossing'
crossing_matched_gdf['value'] = 1

# pivot crossings to get types on each stretch
crossing_matched_gdf = pd.crosstab(index=crossing_matched_gdf.TOID, columns=crossing_matched_gdf['type'],values=crossing_matched_gdf.value, aggfunc='max').reset_index().fillna(0)

## Match Bus Stops to network
bus_stop_matched_gdf = gf.match_point_to_line(highway, ['TOID','identifier'], bus_stop_gdf, buffer=15)
bus_stop_matched_gdf.to_file('../data/interim/bus_stop_matched.geojson', driver='GeoJSON')
del bus_stop_gdf

## Match Bus Lanes to network
# Convert multi-part geometrieese to single part ready for looping over
# bus_lanes_gdf = bus_lanes_gdf.explode().reset_index(drop=True)
# bus_lane_matched = gf.match_line_to_line(highway[~highway.routeHierarchy.isin(['Restricted Local Access Road','Local Access Road','Secondary Access Road','Restricted Secondary Access Road'])], bus_lanes_gdf, buffer=5)
# bus_lane_matched = bus_lane_matched[['TOID','identifier','DIRECTION','ROAD_NAME','LANE_TYPE']]

## Match Traffic Calming to network
traffic_calming_matched_gdf = gf.match_point_to_line(highway, ['TOID','identifier'], traffic_calming_gdf, buffer=15)
traffic_calming_matched_gdf.to_file('../data/interim/traffic_calming_matched.geojson', driver='GeoJSON')
del traffic_calming_gdf

# the traffic calming values are the wrong format. Let's change them
tc_cols = ['TRF_RAISED','TRF_ENTRY','TRF_CUSHI','TRF_HUMP','TRF_SINUSO','TRF_BARIER','TRF_NAROW','TRF_CALM']
for col in tc_cols:
    traffic_calming_matched_gdf[col] = traffic_calming_matched_gdf[col].apply(lambda x: 1 if x == 'TRUE' else 0)

# group traffic calming to get values per stretch
traffic_calming_matched_gdf = traffic_calming_matched_gdf.drop(['FEATURE_ID','SVDATE','BOROUGH','PHOTO1_URL','PHOTO2_URL','identifier','geometry'], axis=1).groupby(['TOID'], as_index=False).max()

## Match CID to network
cid_cols = ['CLT_CARR','CLT_SEGREG','CLT_STEPP','CLT_PARSEG','CLT_SHARED','CLT_MANDAT',
       'CLT_ADVIS','CLT_PRIORI','CLT_CONTRA','CLT_BIDIRE','CLT_CBYPAS',
       'CLT_BBYPAS','CLT_PARKR','CLT_WATERR','CLT_PTIME']

for col in cid_cols:
    cyclelane_gdf[col] = cyclelane_gdf[col].apply(lambda x:1 if x == 'TRUE' else 0)
cyclelane_gdf = cyclelane_gdf.drop(['OBJECTID','FEATURE_ID','FEAT_TYPE','SVDATE','BOROUGH',
       'CLT_COLOUR','FWD','Highways_P','Road_Name','Road_Class','OSM_ID','OS_Highw_1','SHAPE_Leng','geometry'],axis=1).groupby(['OS_Highway'], as_index=False).max()

## Determine Highway features
highway['gradient'] = highway.apply(lambda x: gf.stretch_gradient(x, 'length'), axis=1)
highway['sinuosity'] = highway.apply(lambda x: gf.stretch_sinuosity(x, 'length'), axis=1)
highway['bearing'] = highway.apply(lambda x: gf.stretch_bearing(x), axis=1)
highway['relative_location'] = highway.apply(lambda x: gf.stretch_location(x), axis=1)
highway['roadWidthMinimum'] = highway['roadWidthMinimum'].apply(lambda x: float(x.replace('m','')) if len(x) > 0 else np.nan)
highway['roadWidthAverage'] = highway['roadWidthAverage'].apply(lambda x: float(x.replace('m','')) if len(x) > 0 else np.nan)
highway['start_x'], highway['end_x'], highway['start_y'], highway['end_y'] = highway.apply(lambda x: gf.stretch_key_coords(x), axis=1, result_type='expand').T.values

# check existance of bus stop on link
highway['bus_stop'] = highway['TOID'].isin(bus_stop_matched_gdf.TOID.unique()).astype('uint16')

# check existance of bus lane on link
# highway['bus_lane'] = highway['TOID'].isin(bus_lane_matched.TOID.unique()).astype('uint16')

# join crossings to network data
highway = highway.join(crossing_matched_gdf.set_index('TOID'), how='left', on='TOID')

# join traffic calming to network data
highway = highway.join(traffic_calming_matched_gdf.set_index('TOID'), how='left', on='TOID')

# join cid data by TOID
highway = highway.join(cyclelane_gdf.set_index('OS_Highway'), how='left', on='TOID')

## Fill in NaN on joined columns with 0
# gather names of joined columns as a set (will not repeat column names)
fill_cols = set()
for item in [crossing_matched_gdf, traffic_calming_matched_gdf, cyclelane_gdf]:
    fill_cols = fill_cols.union(item.columns.values.tolist())

# remove TOID and OS_Highway from the set - use discard to avoid any name not found errors
fill_cols.discard('TOID')
fill_cols.discard('OS_Highway')

# convert the set to a list
fill_cols = list(fill_cols)

# for all column names in the list, set the NaN values to 0
highway.loc[:, fill_cols] = highway.loc[:, fill_cols].fillna(0)

## Export the road environment data
highway.to_file('../data/interim/road_environment.geojson', driver='GeoJSON')