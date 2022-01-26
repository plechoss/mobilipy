from numba import njit
import numpy as np
from haversine import haversine, Unit
import pandas as pd
pd.options.mode.chained_assignment = None

@njit
def assign_cell(latitude, longitude, cell_size=0.2):
    """`
    Assigns a cell_number based on the cantor pairing function and discretization into 25km * 25km cells.
    Arguments:
        latitude (float): latitude in degrees.
        longitude (float): longitude in degrees.

    Returns:
        cell_number (int): Cell number based on the cantor pair function.
    """

    km_east = 111.320 * np.cos(np.deg2rad(latitude)) * longitude
    km_north = 110.574 * latitude
    x_index = km_east // cell_size
    y_index = km_north // cell_size
    cell_number = (1/2)*(y_index + x_index)*(y_index + x_index + 1) + x_index
    return cell_number


def detect_home_work(legs, waypoints, cell_size=0.2):
    """Detects home and work locations, tags them with 'Home' or 'Work' in the df

    Args:
        legs (list()): list of legs
        waypoints (pandas.DataFrame): the waypoints DataFrame to be processed 
    """
    
    if legs.shape[0] != 0 and waypoints.shape[0] != 0:
        waypoints_ = waypoints[['tracked_at', 'latitude', 'longitude', 'user_id']]
        waypoints_["cell_number"] = assign_cell(waypoints_.latitude.values, waypoints_.longitude.values, cell_size)
        waypoints_["cell_number"] = waypoints_["cell_number"].astype('int64')

        # Waypoints_workdates is waypoints filtered to only contain datapoints from workdays between 7:00 and 19:00
        waypoints_workdates = waypoints_.copy()
        waypoints_workdates['hour'] = waypoints_workdates.tracked_at.dt.hour
        waypoints_workdates['weekday'] = waypoints_workdates.tracked_at.dt.weekday
        waypoints_workdates = waypoints_workdates[(waypoints_workdates.hour >= 7) & (waypoints_workdates.hour <= 19) & (waypoints_workdates.weekday < 5)]
        waypoints_workdates = waypoints_workdates.drop(columns=['hour', 'weekday'])

        # Most_visited_cells_workdates finds the most visited cells during workdays
        most_visited_cells_workdates = waypoints_workdates.drop(columns=["tracked_at", "user_id"])
        most_visited_cells_workdates = most_visited_cells_workdates.groupby("cell_number").agg(["count", "mean"])
        most_visited_cells_workdates.columns = most_visited_cells_workdates.columns.droplevel()
        most_visited_cells_workdates.columns = ["count_lat", "mean_lat", "count_lon", "mean_lon"]
        most_visited_cells_workdates = most_visited_cells_workdates.drop(columns="count_lat").reset_index()
        most_visited_cells_workdates = most_visited_cells_workdates.rename(columns={"mean_lat": "latitude", "mean_lon": "longitude"}).sort_values(by="count_lon", ascending=False)

        # Most_visited_cells finds the most visited cells overall
        most_visited_cells = waypoints_.drop(columns=["tracked_at", "user_id"])
        most_visited_cells = most_visited_cells.groupby("cell_number").agg(["count", "mean"])
        most_visited_cells.columns = most_visited_cells.columns.droplevel()
        most_visited_cells.columns = ["count_lat", "mean_lat", "count_lon", "mean_lon"]
        most_visited_cells = most_visited_cells.drop(columns="count_lat").reset_index()
        most_visited_cells = most_visited_cells.rename(columns={"mean_lat": "latitude", "mean_lon": "longitude"}).sort_values(by="count_lon", ascending=False)

        home_user_cell_number = most_visited_cells.iloc[0].cell_number
        home_user = (most_visited_cells.iloc[0]['latitude'], most_visited_cells.iloc[0]['longitude'])
        
        first_workdates_cell_number = most_visited_cells_workdates.iloc[0].cell_number
        first_workdates = (most_visited_cells_workdates.iloc[0]['latitude'], most_visited_cells_workdates.iloc[0]['longitude'])
        
        if(most_visited_cells_workdates.shape[0]>1):
            second_workdates_cell_number = most_visited_cells_workdates.iloc[1].cell_number
            second_workdates = (most_visited_cells_workdates.iloc[1]['latitude'], most_visited_cells_workdates.iloc[1]['longitude'])
        else:
            second_workdates = None
        
        work_user = first_workdates if first_workdates_cell_number != home_user_cell_number else second_workdates

        user_activities = legs[legs.type == 'Stay']

        for index, row in user_activities.iterrows():
            find_centroid(index, legs, home_user, work_user)
        return home_user, work_user
    else:
        return None, None


# Tags legs as home or work if they're close enough to either
def find_centroid(leg_index, legs, home_user, work_user):
    """
    Tags legs as home or work if they're close enough to either
    Args:
        leg_index (int): index of the leg to be processed
        legs (list(???)): list of legs
        home_user ((latitude, longitude)): user's home location
        work_user ((latitude, longitude)): user's work location
    """
    centroid = (legs.geometry[leg_index][0][0], legs.geometry[leg_index][0][1])
    if home_user is not None:
        d_home = haversine(home_user, centroid)
        if d_home < 0.03:
            legs.loc[leg_index, 'purpose'] = 'Home'
    if work_user is not None:
        d_work = haversine(work_user, centroid)
        if d_work < 0.03:
            legs.loc[leg_index, 'purpose'] = 'Work'