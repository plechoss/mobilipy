import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
import more_itertools as mit
import multiprocessing as mp
from numba import njit
pd.options.mode.chained_assignment = None

@njit
def _distance_between_two_coordinates(lat1_degrees, lon1_degrees, lat2_degrees, lon2_degrees) -> float:
    """Distance in meters between two points given in coordinates using the haversine distance.

    Args:
        lat1_degrees (float): latitude of the first point in degrees.
        lon1_degrees (float): longitude of the first point in degrees.
        lat2_degrees (float): latitude of the second point in degrees.
        lon2_degrees (float): longitude of the second point in degrees.

    Returns:
        float: distance in m between the two coordiantes.
    """

    # approximate radius of earth in km
    R = 6373.0

    lat1 = np.deg2rad(lat1_degrees)
    lon1 = np.deg2rad(lon1_degrees)
    lat2 = np.deg2rad(lat2_degrees)
    lon2 = np.deg2rad(lon2_degrees)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * \
        np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    distance = R * c

    return distance * 1000

def _create_route(df) -> pd.DataFrame:
    """Adds distance, time_delta, speed (m/s) and acceleration to the waypoints DataFrame

    Args:
        df (pandas.DataFrame): the waypoints DataFrame to be processed
        
    Returns:
        pandas.DataFrame: waypoints DataFrame with additional statistics: distance, time_delta, speed (m/s) and acceleration
    """
    if df.shape[0] == 0:
        return pd.DataFrame(columns=['tracked_at_start', 'latitude_start', 'longitude_start', 'tracked_at_end', 'latitude_end', 'longitude_end', 'distance', 'time_delta', 'speed', 'acceleration', 'detection'])
    res = df.reset_index().merge(
        df.shift(-1).dropna().reset_index(),  # last row of shift is NA
        on="index",
        suffixes=("_start", "_end"),
    )

    res = res.drop(
        columns=[
            "index",
            "user_id_start",
            "user_id_end",
            "accuracy_start",
            "accuracy_end",
        ], errors='ignore'
    )
    res["distance"] = _distance_between_two_coordinates(
        res.latitude_start.values,
        res.longitude_start.values,
        res.latitude_end.values,
        res.longitude_end.values,
    )
    res["time_delta"] = res.tracked_at_end - res.tracked_at_start
    res["time_delta"] = res["time_delta"].apply(
        lambda x: x.total_seconds()
    )  #  in seconds
    res["speed"] = (
        res["distance"] / res["time_delta"]
    )  # we want to have meters / seconds

    # This will be necessary for mode detection
    res["acceleration"] = res["speed"] / res["time_delta"]
    return res


def _prepare_for_detection(df) -> pd.DataFrame:
    """Flags all detections as trips. By default, we are looking for activities so everything else is tagged as a trip.

    Args:
        df (pandas.DataFrame): Waypoints DataFrame to be flagged
    Returns:
        pandas.DataFrame: DataFrame with 'detection' column being 'trip'
    """
    df["detection"] = "trip"
    return df

def _activities_density(args) -> pd.DataFrame:
    """ Detects activities by density
    
    Args:
        df (pandas.DataFrame): 
        clusterer (sklearn.cluster):

    Returns:
        pandas.DataFrame:
    """
    df, clusterer = args
    clusters_start = clusterer.fit_predict(
        np.radians(df[["latitude_start", "longitude_start"]]))

    df["cluster_start"] = clusters_start
    df["cluster_end"] = df.cluster_start.shift(-1).fillna(0).astype('int')

    # update the detection column: Whenever the clusters column are different, we put trip in detection. Otherwise, we put activity.
    df.loc[
        (df["detection"] == "trip")
        & (df["cluster_start"] == df["cluster_end"])
        & (df["cluster_start"] != -1),
        ["detection"],
    ] = "activity"

    return df


def _correct_clusters(df):
    """Corrects detected clusters by merging them using a window time and mean speed

    Args:
        df (pandas.DataFrame): DataFrame to be corrected, with 'detection', 'speed' and 'time_delta' columns
    """
    activity_indexes = df.loc[df.detection == "activity"].index.values
    trip_indexes = df.loc[df.detection == "trip"].index.values

    time_delta = df['time_delta'].values
    speed = df['speed'].values

    detection = df['detection'].values

    for group in mit.consecutive_groups(activity_indexes):
        indexes = list(group)
        window_time = np.sum(time_delta[indexes])
        if window_time < 120:
            detection[indexes] = 'trip'

    for group in mit.consecutive_groups(trip_indexes):
        indexes = list(group)
        window_time = np.sum(time_delta[indexes])
        mean_speed = np.mean(speed[indexes])
        if window_time < 120 or mean_speed < 1:
            detection[indexes] = 'activity'

    df['detection'] = detection


def segment(prepared_df, radius=0.025, min_samples=50, time_gap=850, use_multiprocessing=True) -> pd.DataFrame:
    """Finds clusters of waypoints for legs

    Args:
        df (pandas.DataFrame): Waypoints DataFrame to be processed
        radius (float): Eps for DBSCAN
        min_samples (int): Minimum number of samples to be considered for
        time_gap (float): Max time gap threshold for detected clusters

    Returns:
        pandas.DataFrame: DataFrame with the segment starts and ends
    """
    
    route_user = _create_route(prepared_df)
    df = _prepare_for_detection(route_user)

    df["day"] = df.tracked_at_start.apply(lambda x: x.day)
    df["month"] = df.tracked_at_start.apply(lambda x: x.month)
    df["year"] = df.tracked_at_start.apply(lambda x: x.year)

    db = DBSCAN(eps=radius / 6371.0, min_samples=min_samples,
                algorithm="ball_tree", metric="haversine")

    route_clusters_detected = pd.DataFrame(columns=list(
        df.columns) + list(['cluster_start', 'cluster_end']))

    arguments = list(df.groupby(['day', 'month', 'year']).groups.items())
    arguments = list(map(lambda x: (df.iloc[list(x[1])], db), arguments))

    if use_multiprocessing:
        pool = mp.Pool(processes=(mp.cpu_count() - 1))
        results = pool.map_async(_activities_density, arguments)
        pool.close()
        pool.join()

        for res in results.get(timeout=1):
            route_clusters_detected = route_clusters_detected.append(res)
    else:
        for argument_list in arguments:
            res = _activities_density(argument_list)
            route_clusters_detected = route_clusters_detected.append(res)

    route_clusters_detected = route_clusters_detected.sort_values(
        by='tracked_at_start', ascending=True)
    route_clusters_detected = route_clusters_detected.drop(
        columns=['day', 'month', 'year'])
    route_clusters_detected = route_clusters_detected.reset_index().drop(columns="index")

    _correct_clusters(route_clusters_detected)

    route_clusters_detected = (route_clusters_detected.drop(
        route_clusters_detected[route_clusters_detected.time_delta >
                                time_gap].index
    )
        .reset_index()
        .drop(columns="index")
    )

    route_clusters_detected = route_clusters_detected.drop(
        columns=['cluster_start', 'cluster_end'])
    return route_clusters_detected
