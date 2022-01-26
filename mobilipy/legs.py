import pandas as pd
import numpy as np
import more_itertools as mit
import datetime
import multiprocessing as mp
from shapely.geometry import MultiPoint
from haversine import haversine, Unit



LEG_FEATURES = [
    "user_id",
    "started_at",
    "finished_at",
    "type",
    "detected_mode",
    "purpose",
    "geometry",
]

def _append_one_category(args):# -> list((str, str, str, str, str, str, MultiPoint)):
    """
    Args:
        indexes (list(str)): list of indexes in the df that have the given category_name
        df (pandas.DataFrame): dataframe containing the waypoints
        user_id (str): id of the user whose waypoints we're processing
        category_name (str): name of the category (Stay or Track)
    Returns:
        list((str, str, str, str, str, str, shapely.geometry.MultiPoint)): list of (user_id, started_at, finished_at, type_, detected_mode, purpose, geometry)
    """
    indexes, df, user_id, category_name = args
    res = []
    user_id = user_id
    started_at = df.loc[df.index[indexes[0]], "tracked_at_start"]
    finished_at = df.loc[df.index[indexes[-1]], "tracked_at_end"]
    detected_mode = df.loc[df.index[indexes[0]], "detected_mode"]
    purpose = np.nan
    type_ = category_name
    if type_ == "Stay":
        points = MultiPoint(list(df.loc[df.index[indexes], ["latitude_start","longitude_start"]].values))
        diameter = haversine((points.bounds[0], points.bounds[1]), (points.bounds[2], points.bounds[3])) * 1000
        geometry = ((points.centroid.x, points.centroid.y), diameter)
    else:
        geometry = list(df.loc[df.index[indexes],["latitude_start","longitude_start"]].values)

    started_at = started_at.to_pydatetime()
    finished_at = finished_at.to_pydatetime()
    started_at = datetime.datetime.strptime(str(started_at), "%Y-%m-%d %H:%M:%S+00:00")
    finished_at = datetime.datetime.strptime(str(finished_at), "%Y-%m-%d %H:%M:%S+00:00")

    if started_at.day != finished_at.day:
        day_after_started = started_at + datetime.timedelta(days=1)
        res.append((user_id, started_at, datetime.datetime(day_after_started.year, day_after_started.month, day_after_started.day,0,0,0), 
                    type_, detected_mode, purpose, geometry))
        res.append((user_id, datetime.datetime(day_after_started.year, day_after_started.month, day_after_started.day,0,0,0),
                    finished_at, type_, detected_mode, purpose, geometry))
    else:
        res.append((user_id, started_at, finished_at, type_, detected_mode, purpose, geometry))
    return res


def get_user_legs(df, user_id, use_multiprocessing=True) -> pd.DataFrame:
    
    """
    Builds the legs DataFrame for the given user.

    Args:
        df (pandas.DataFrame): waypoints DataFrame
        user_id (str): ID of the user whose legs are to be created
        use_multiprocessing (bool, optional): Specifies whether the multiprocessing package should be used. Defaults to True.

    Returns:
        pandas.DataFrame: DataFrame of user's legs
    """
    
    #tzinfo = df.tracked_at_start.iloc[0].tzinfo
    
    res = []
    
    activities = df[df["detection"] == "activity"].index.values
    trips = df[df["detection"] == "trip"].index.values
    walks = df[df["detection"] == "walk"].index.values
    
    
    arguments_act = [list(x) for x in mit.consecutive_groups(activities)]
    arguments_act = list(map(lambda x: (x, df, user_id, "Stay"), arguments_act))
    
    arguments_trips = [list(x) for x in mit.consecutive_groups(trips)]
    arguments_trips = list(map(lambda x: (x, df, user_id, "Track"), arguments_trips))
    
    arguments_walks = [list(x) for x in mit.consecutive_groups(walks)]
    arguments_walks = list(map(lambda x: (x, df, user_id, "Track"), arguments_walks))

    if use_multiprocessing:
        pool = mp.Pool(processes = (mp.cpu_count() - 1))
        result = pool.map_async(_append_one_category, arguments_act)
        pool.close()
        pool.join()
        for res_ in result.get(timeout=1):
            res += res_
    else:
        for argument_list in arguments_act:
            res_ = _append_one_category(argument_list)
            res += res_
    
    if use_multiprocessing:
        pool = mp.Pool(processes = (mp.cpu_count() - 1))
        result = pool.map_async(_append_one_category, arguments_trips)
        pool.close()
        pool.join()
        for res_ in result.get(timeout=1):
            res += res_
    else:
        for argument_list in arguments_trips:
            res_ = _append_one_category(argument_list)
            res += res_

       
    if use_multiprocessing:
        pool = mp.Pool(processes = (mp.cpu_count() - 1))
        result = pool.map_async(_append_one_category, arguments_walks)
        pool.close()
        pool.join()
        for res_ in result.get(timeout=1):
            res += res_
    else:
        for argument_list in arguments_walks:
            res_ = _append_one_category(argument_list)
            res += res_
    
    res = pd.DataFrame(res, columns=LEG_FEATURES)
    res = res.sort_values(by='started_at')
    res = res.reset_index()
    res = res.drop(columns='index')
    
    #res.started_at = res.started_at.dt.tz_localize(tzinfo)
    #res.finished_at = res.finished_at.dt.tz_localize(tzinfo)

    return res