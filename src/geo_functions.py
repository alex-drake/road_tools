import geopandas as gpd
import pandas as pd
from numpy import sqrt, arctan2
import numpy as np
#import networkx as nx
import math
from shapely import geometry
from shapely.geometry import Point
import os
import matplotlib.pyplot as plt

latlong = {'init':'epsg:4326'}
ukgrid = {'init':'epsg:27700'}

def stretch_gradient(shape, shape_length):
    """
    Uses network geometry to calculate the average gradient for a road stretch
    """
    length = shape[shape_length]
    coords = shape.geometry[0].coords

    first_z = coords[0][2]
    last_z = coords[-1][2]
    z_delta = first_z - last_z

    grad = round(100 * z_delta / length,1)

    return grad

def stretch_key_coords(shape):
    """
    Uses network geometry to return the key coordinates (start x,y and end x,y)

    This is mainly used to match each TOID to the expanded DfT TOIDS 
    That is DfT shows one TOID for each direction
    """
    coords = shape.geometry[0].coords
    x1, y1 = coords[0][0:2]
    x2, y2 = coords[-1][0:2]

    x1 = round(x1, 0)
    x2 = round(x2, 0)
    y1 = round(y1, 0)
    y2 = round(y2, 0)

    return x1, x2, y1, y2

def stretch_sinuosity(shape, shape_length):
    """
    Uses network geometry to calculate the sinuosity (curvature) for a road 
    stretch.
    
    Sinuosity values will range from 1 (a straight line) to infinity (a 
    closed circle or loop).

    Some key values are:

    90 degrees = 1.11072
    180 degrees = 1.57096
    270 degrees = 3.33216
    """
    length = shape[shape_length]
    coords = shape.geometry[0].coords

    x1, y1 = coords[0][0:2]
    x2, y2 = coords[-1][0:2]

    crow_flies = sqrt((x1 - x2)**2 + (y1 - y2)**2)

    return round(length / crow_flies, 2)

def stretch_bearing(shape):
    """
    Uses network geometry to calculate the bearing (direction) for a road in degrees

    Range is -180 to 180
    """
    if shape.geometry.geom_type == 'MultiLineString':
        coords = shape.geometry[0].coords
    elif shape.geometry.geom_type == 'LineString':
        coords = shape.geometry.coords
    else:
        coords = [(0, 0),(0, 0)]
    
    x1, y1 = coords[0][0:2]
    x2, y2 = coords[-1][0:2]
    x_delta = x2 - x1

    x = math.cos(math.radians(y2)) * math.sin(math.radians(x_delta))
    y = math.cos(math.radians(y1)) * math.sin(math.radians(y2)) - math.sin(math.radians(y1)) * math.cos(math.radians(y2)) * math.cos(math.radians(x_delta))
    bearing = arctan2(x, y)
    bearing = int(((math.degrees(bearing) + 360) % 360))

    return bearing

def stretch_location(shape, cent_y = 181223, cent_x = 529028):
    """
    Uses network geometry to calculate the mid-point for a stretch of road, and then compare this with
    a relative location. For example, the distance from the city centre to the road stretch.

    In London, we take the city centre as Oxford Circus (529028, 181223)
    """
    coords = shape.geometry[0].coords

    x1, y1 = coords[0][0:2]
    x2, y2 = coords[-1][0:2]

    ave_x = (x1 + x2) / 2
    ave_y = (y1 + y2) / 2

    crow_flies = int(sqrt((ave_x - cent_x)**2 + (ave_y - cent_y)**2))

    return crow_flies

# create a graph network representation to calculate centrality etc
# def gdf_to_nx(gdf_network):
#     net = nx.Graph()
#     net.graph['crs'] = gdf_network.crs
#     fields = list(gdf_network.columns)

#     for index, row in gdf_network.iterrows():
#         first = row.geometry[0].coords[0][0:2]
#         last = row.geometry[0].coords[-1][0:2]

#         data = [row[f] for f in fields]
#         attributes = dict(zip(fields, data))
#         net.add_edge(first, last, **attributes)

#     return net

# def nx_to_gdf(net, nodes=True, edges=True):
#     # generate nodes and edges geodataframes from graph
#     if nodes is True:
#         node_xy, node_data = zip(*net.nodes(data=True))
#         gdf_nodes = gpd.GeoDataFrame(list(node_data), geometry=[Point(i, j) for i, j in node_xy])
#         gdf_nodes.crs = net.graph['crs']

#     if edges is True:
#         starts, ends, edge_data = zip(*net.edges(data=True))
#         gdf_edges = gpd.GeoDataFrame(list(edge_data))
#         gdf_edges.crs = net.graph['crs']

#     if nodes is True and edges is True:
#         return gdf_nodes, gdf_edges
#     elif nodes is True and edges is False:
#         return gdf_nodes
#     else:
#         return gdf_edges

# def match_point_to_line(line_shape, point_shape, buffer=None):
#     """
#     Match a point geometry to the nearest line geometry within a buffer / radius
#     Expects both geometries to share the same CRS
#     """
#     assert line_shape.crs == point_shape.crs, 'The shape CRS do not match'
#     line_shape_tmp = line_shape.geometry.unary_union

#     if buffer is not None:
#         line_shape_buffer = gpd.GeoDataFrame(geometry = line_shape.buffer(buffer))
#         point_shape_tmp = gpd.sjoin(point_shape, line_shape_buffer, how='left', op='within')
#         point_shape_tmp.dropna(inplace=True)
#         point_shape_tmp = point_shape[point_shape.index.isin(point_shape_tmp.index)]
#     else:
#         point_shape_tmp = point_shape.copy()

#     point_shape_tmp['geometry'] = point_shape_tmp.apply(lambda row: line_shape_tmp.interpolate(line_shape_tmp.project(row.geometry)), axis = 1)

#     # if buffer is not None:
#     #     point_shape_tmp['geometry'] = point_shape_tmp.geometry.buffer(buffer)

#     return point_shape_tmp

def match_point_to_line(line_shape, line_columns, point_shape, buffer=15, on_first=True):
    """
    Match a point geometry to the nearest line geometry within a radius (buffer)
    Expects both geometries to share the same CRS
    """
    assert line_shape.crs == point_shape.crs, 'The shape CRS do not match'
    line_shape.sindex

    bbox = point_shape.bounds + [-buffer, -buffer, buffer, buffer]
    hits = bbox.apply(lambda row: list(line_shape.sindex.intersection(row)), axis=1)

    tmp = pd.DataFrame({
        # index of points table
        "pt_idx": np.repeat(hits.index, hits.apply(len)),
        # ordinal position of line - access via iloc later
        "line_i": np.concatenate(hits.values)
    })

    # Join back to lines on line_i to give ordinal position of each line
    tmp = tmp.join(line_shape.reset_index(drop=True), on='line_i')

    # Join back to the original points to get their geometry
    tmp = tmp.join(point_shape.geometry.rename('point'), on='pt_idx')
    tmp = gpd.GeoDataFrame(tmp, geometry='geometry', crs=point_shape.crs)

    # calculate distance between each point and associate lines
    tmp['snap_dist'] = tmp.geometry.distance(gpd.GeoSeries(tmp.point))

    # discard lines greater than buffer
    tmp = tmp.loc[tmp.snap_dist <= buffer]

    # sort on ascending snap distance (closest at top)
    tmp = tmp.sort_values(by=['snap_dist'])

    #  group by index and take the closest point (if true)
    if on_first:
        closest = tmp.groupby('pt_idx').first()
    else:
        closest = tmp
    
    closest = gpd.GeoDataFrame(closest, geometry='geometry')

    # position of nearest point from the start of the line
    pos = closest.geometry.project(gpd.GeoSeries(closest.point))
    new_pts = closest.geometry.interpolate(pos)

    # create a new geodataframe from the required columns
    if line_columns is not None:
        snapped = gpd.GeoDataFrame(closest[line_columns], geometry=new_pts)
    else:
        snapped = gpd.GeoDataFrame(closest, geometry=new_pts)

    # join back to original points
    updated_points = point_shape.drop(columns=['geometry']).join(snapped)
    updated_points = updated_points.dropna(subset=['geometry'])

    return updated_points

def check_point_to_line_match(line_shape, point_shape):
    """
    Check the results of the match_point_to_line function by comparing the new point shape geometry to the line shape
    """
    fig, ax = plt.subplots()
    line_shape.plot(ax=ax, color='black', edgecolor='black', linewidth=1)
    point_shape.plot(ax=ax, color='red', markersize=2)
    plt.show()

def match_line_to_line(line1, line2, buffer=10):
    assert line1.crs == line2.crs

    line_as_points = pd.DataFrame()

    for index, row in line2.iterrows():

        if row.geometry.geom_type == 'MultiLineString':
            coords = row.geometry[0].coords
        else:
            coords = row.geometry.coords

        tmp = pd.DataFrame({
            # index of the line
            'line2_idx': np.repeat(index, len(coords)),
            # coordinate values
            'pt_vals': pd.Series(coords)
        })

        line_as_points = pd.concat([line_as_points, tmp], ignore_index=True)

    # join id on by index
    line_as_points = line_as_points.join(line2.drop(columns='geometry').reset_index(drop=True), on='line2_idx')
    
    # convert to geodataframe of points
    line_as_points = gpd.GeoDataFrame(line_as_points, geometry=[Point(i, j) for i, j in line_as_points.pt_vals])
    line_as_points.crs = line2.crs

    # run through points to line match
    line_as_points = match_point_to_line(line1, None, line_as_points, buffer=buffer, on_first=True)

    # limit returned columns and rows
    line_as_points.drop(columns=['line_i','pt_vals','geometry','point','snap_dist'], inplace=True)
    line_as_points.drop_duplicates(inplace=True, ignore_index=True)

    # convert to dataframe
    line_as_points = pd.DataFrame(line_as_points)

    # # calculate expected bearings
    # line1['l1_bearing'] = line1.apply(lambda x: stretch_bearing(x), axis=1)
    # line2['l2_bearing'] = line2.apply(lambda x: stretch_bearing(x), axis=1)

    # # joint to dataframe
    # line_as_points = line_as_points.join(line1[['TOID','l1_bearing']].set_index('TOID'), on='TOID')
    # line_as_points = line_as_points.join(line2[['l2_bearing']], on='line2_idx')

    # line_as_points['bearing_diff'] = abs((((line_as_points['l1_bearing'] - line_as_points['l2_bearing']) + 180) % 360) - 180)
    
    return line_as_points