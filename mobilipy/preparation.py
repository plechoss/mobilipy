import pandas as pd
import math
import numpy as np

def prepare(df) -> pd.DataFrame:
    """
    Cleans a raw GPS points dataframe by filtering in the zurich area, rearranging features and applying gaussian smoothing.
    Args:
        df (pandas.DataFrame): DataFrame to be prepared for route processing
    Returns:
        pandas.DataFrame: the preprocessed DataFrame
    """
    res = df
    if('accuracy' in df.columns):
        res = res[res.accuracy < 1000]
    res = _gaussian_smoothing(res)
    res = res.drop(columns='index', errors='ignore')
    return res

def _gaussian_smoothing(df, sigma=10) -> pd.DataFrame:
    """
    Applies Gaussian smoothing on the given waypoints DataFrame
    Args:
        df (pandas.DataFrame): DataFrame with points to be smoothed
        sigma (float):
    Returns:
        pandas.DataFrame: the smoothed DataFrame
    """
    if df.shape[0] == 0:
        return df

    size = df.shape[0]
    output = df.reset_index()

    output = output.sort_values("tracked_at", ascending=True)
    
    output['latitude'] = pd.to_numeric(output['latitude'])
    output['longitude'] = pd.to_numeric(output['longitude'])
    
    timestamps = pd.to_datetime(output["tracked_at"]).map(lambda x: x.asi8) // 10**9
    timestamps = timestamps.values
    longitudes = output['longitude'].values
    latitudes = output['latitude'].values
    
    output_longitudes = []
    output_latitudes = []
    
    sigma_squared = sigma ** 2

    for i in range(size):
        start = i - 5 if (i - 5 > 0) else 0
        end = i + 6 if (i + 6 < size) else size

        timestamp_df = timestamps[start:end]
        window_longitudes = longitudes[start:end]
        window_latitudes = latitudes[start:end]

        center_timestamp = timestamps[i]
        
        weights = timestamp_df - center_timestamp
        weights = weights ** 2
        weights = weights / sigma_squared
        weights = np.array(list(map(lambda x: math.exp(-x), weights)))
        sum_weights = np.sum(weights)

        new_longitude = np.sum(weights * window_longitudes)/sum_weights
        new_latitude = np.sum(weights * window_latitudes)/sum_weights
        
        output_longitudes.append(new_longitude)
        output_latitudes.append(new_latitude)
    
    
    output_longitudes = pd.Series(output_longitudes)
    output_latitudes = pd.Series(output_latitudes)
    
    output.longitude = output_longitudes
    output.latitude = output_latitudes
        
    return output
