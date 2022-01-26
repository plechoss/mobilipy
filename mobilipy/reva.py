from mobilipy.poi_detection import detect_home_work
from mobilipy.legs import get_user_legs
from mobilipy.mode_detection import mode_detection
from mobilipy.preparation import prepare
from mobilipy.segmentation import segment

import pandas as pd

def analyse(df, user_id) -> pd.DataFrame:
    """Returns complete trip information from a raw GPS waypoints DataFrame. Segments the data into trips, detects the mode of transport and tags the home and work locations.

    Args:
        df (pandas.DataFrame): waypoints DataFrame
        user_id (str): user's ID

    Returns:
        pandas.DataFrame: DataFrame with selected user's legs
    """
    df_prepared = prepare(df)
    route_clusters_detected = segment(df_prepared)
    route_clusters_detected = mode_detection(route_clusters_detected)
    legs_user = get_user_legs(route_clusters_detected, user_id)
    detect_home_work(legs_user, df_prepared)
        
    return legs_user