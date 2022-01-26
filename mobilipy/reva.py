from mobilipy import poi_detection
from mobilipy import legs
from mobilipy import mode_detection
from mobilipy import preparation
from mobilipy import segmentation

import pandas as pd

def analyse(df, user_id) -> pd.DataFrame:
    """Returns complete trip information from a raw GPS waypoints DataFrame. Segments the data into trips, detects the mode of transport and tags the home and work locations.

    Args:
        df (pandas.DataFrame): WaypointsDataFrame
        user_id (str): user's ID

    Returns:
        pandas.DataFrame: DataFrame with selected user's legs
    """
    df_prepared = preparation.prepare(df)
    route_clusters_detected = segmentation.segment(df_prepared)
    route_clusters_detected = mode_detection.mode_detection(route_clusters_detected)
    legs_user = legs.get_user_legs(route_clusters_detected, user_id)
    poi_detection.detect_home_work(legs_user, df_prepared)
        
    return legs_user