import numpy as np
import more_itertools as mit
import skfuzzy as fuzz
import multiprocessing as mp
import pandas as pd
pd.options.mode.chained_assignment = None

def _detect_walks(args):
    """Tags the DataFrame at given indexes with 'walk' in the 'detection' column, for the points corresponding to walks

    Args:
        args: df, walk_speed_th, walk_acceleration_th, minimal_walk_duration, minimal_trip_duration 

    Returns:
        pandas.DataFrame: Tagged DataFrame
    """
    df, walk_speed_th, walk_acceleration_th, minimal_walk_duration, minimal_trip_duration = args
    i = 0
    window = []
    window_time = 0
    window_speed_median = 0
    window_acceleration_median = 0
    while i < len(df):
        condition_on_current_elem = (
            df.iloc[i]['speed'] <= walk_speed_th and df.iloc[i]['acceleration'] <= walk_acceleration_th)
        condition_on_existing_window = (
            window_speed_median <= walk_speed_th and window_acceleration_median <= walk_acceleration_th)

        if not condition_on_current_elem and not condition_on_existing_window:
            if len(window) and window_time >= minimal_walk_duration:

                # Update walk status
                trip_before_time = df.iloc[0:window[0]]["time_delta"].sum()
                trip_after_time = df.iloc[window[-1] + 1:]["time_delta"].sum()

                elements_before = window[0]
                elements_after = len(df) - window[-1] + 1

                if elements_before == 0 and elements_after == 0:
                    df.iloc[window, df.columns.get_loc('detection')] = 'walk'
                elif elements_before == 0 and trip_after_time >= minimal_trip_duration:
                    df.iloc[window, df.columns.get_loc('detection')] = 'walk'
                elif elements_after == 0 and trip_before_time >= minimal_trip_duration:
                    df.iloc[window, df.columns.get_loc('detection')] = 'walk'
                elif trip_before_time >= minimal_trip_duration and trip_after_time >= minimal_trip_duration:
                    df.iloc[window, df.columns.get_loc('detection')] = 'walk'

                i = window[-1] + 1
                window = []
                window_time = 0
                window_speed_median = 0
                window_acceleration_median = 0
            else:
                i += 1
                window = []
                window_time = 0
                window_speed_median = 0
                window_acceleration_median = 0
        else:
            window.append(i)
            window_time += df.iloc[i]['time_delta']
            window_speed_median = df.iloc[window].speed.median()
            window_acceleration_median = df.iloc[window].acceleration.median()
            i += 1
    return df

def _detect_modes(df):
    """Detects all modes except for walks. Uses the fuzzy engine.

    Args:
        df (pandas.DataFrame): DataFrame to be processed

    Returns:
        pandas.DataFrame: The modified DataFrame
    """
    

    med_speed_verylow = [0, 0, 1.5, 2]
    med_speed_low = [1.5, 2, 4, 6]
    med_speed_medium = [5, 7, 11, 15]
    med_speed_high = [12, 15, 1000, 1000]

    acc95_low = [0, 0, 0.5, 0.6]
    acc95_medium = [0.5, 0.7, 1, 1.2]
    acc95_high = [1, 1.5, 1000, 1000]

    speed95_low = [0, 0, 6, 8]
    speed95_medium = [7.5, 9.5, 15, 18]
    speed95_high = [15, 20, 1000, 1000]

    possible_modes = []
    median_speed = np.median(df["speed"].values)
    acc_95per, speed_95per = (
        np.percentile(df["acceleration"].values, 95),
        np.percentile(df["speed"].values, 95),
    )

    medspeed_verylow_bool = fuzz.trapmf(
        np.array([median_speed]), med_speed_verylow)[0] > 0
    medspeed_low_bool = fuzz.trapmf(
        np.array([median_speed]), med_speed_low)[0] > 0
    medspeed_medium_bool = fuzz.trapmf(
        np.array([median_speed]), med_speed_medium)[0] > 0
    medspeed_high_bool = fuzz.trapmf(
        np.array([median_speed]), med_speed_high)[0] > 0

    acc95_low_bool = fuzz.trapmf(np.array([acc_95per]), acc95_low)[0] > 0
    acc95_medium_bool = fuzz.trapmf(np.array([acc_95per]), acc95_medium)[0] > 0
    acc95_high_bool = fuzz.trapmf(np.array([acc_95per]), acc95_high)[0] > 0

    speed95_low_bool = fuzz.trapmf(np.array([speed_95per]), speed95_low)[0] > 0
    speed95_medium_bool = fuzz.trapmf(
        np.array([speed_95per]), speed95_medium)[0] > 0
    speed95_high_bool = fuzz.trapmf(
        np.array([speed_95per]), speed95_high)[0] > 0

    # The paper suggests to take the minimum between the membership values.
    # We need to treat all cases where we have a non empty intersection
    if medspeed_verylow_bool and medspeed_low_bool:
        if fuzz.trapmf(np.array([median_speed]), med_speed_verylow)[0] <= fuzz.trapmf(np.array([median_speed]), med_speed_low)[0]:
            medspeed_low_bool = False
        else:
            medspeed_verylow_bool = False

    if medspeed_low_bool and medspeed_medium_bool:
        if fuzz.trapmf(np.array([median_speed]), med_speed_low)[0] <= fuzz.trapmf(np.array([median_speed]), med_speed_medium)[0]:
            medspeed_medium_bool = False
        else:
            medspeed_low_bool = False

    if medspeed_medium_bool and medspeed_high_bool:
        if fuzz.trapmf(np.array([median_speed]), med_speed_medium)[0] <= fuzz.trapmf(np.array([median_speed]), med_speed_high)[0]:
            medspeed_high_bool = False
        else:
            medspeed_medium_bool = False

    if acc95_low_bool and acc95_medium_bool:
        if fuzz.trapmf(np.array([acc_95per]), acc95_low)[0] <= fuzz.trapmf(np.array([acc_95per]), acc95_medium)[0]:
            acc95_medium_bool = False
        else:
            acc95_low_bool = False

    if acc95_medium_bool and acc95_high_bool:
        if fuzz.trapmf(np.array([acc_95per]), acc95_medium)[0] <= fuzz.trapmf(np.array([acc_95per]), acc95_high)[0]:
            acc95_high_bool = False
        else:
            acc95_medium_bool = False

    if speed95_low_bool and speed95_medium_bool:
        if fuzz.trapmf(np.array([speed_95per]), speed95_low)[0] <= fuzz.trapmf(np.array([speed_95per]), speed95_medium)[0]:
            speed95_medium_bool = False
        else:
            speed95_low_bool = False

    if speed95_medium_bool and speed95_high_bool:
        if fuzz.trapmf(np.array([speed_95per]), speed95_medium)[0] <= fuzz.trapmf(np.array([speed_95per]), speed95_high)[0]:
            speed95_high_bool = False
        else:
            speed95_medium_bool = False

    if medspeed_verylow_bool and acc95_low_bool:
        possible_modes.append("Walk")
    if medspeed_verylow_bool and acc95_medium_bool:
        possible_modes.append("Cycle")
    if medspeed_verylow_bool and acc95_high_bool:
        possible_modes.append("Cycle")

    if medspeed_low_bool and acc95_low_bool and speed95_low_bool:
        possible_modes.append("Cycle")
    if medspeed_low_bool and acc95_low_bool and speed95_medium_bool:
        possible_modes.append("Urban")
    if medspeed_low_bool and acc95_low_bool and speed95_high_bool:
        possible_modes.append("Car")
    if medspeed_low_bool and acc95_medium_bool:
        possible_modes.append("Urban")
    if medspeed_low_bool and acc95_high_bool and speed95_low_bool:
        possible_modes.append("Urban")
    if medspeed_low_bool and acc95_high_bool and speed95_medium_bool:
        possible_modes.append("Car")
    if medspeed_low_bool and acc95_high_bool and speed95_high_bool:
        possible_modes.append("Car")

    if medspeed_medium_bool and acc95_low_bool:
        possible_modes.append("Urban")
    if medspeed_medium_bool and acc95_medium_bool:
        possible_modes.append("Car")
    if medspeed_medium_bool and acc95_high_bool:
        possible_modes.append("Car")

    if medspeed_high_bool and acc95_low_bool:
        possible_modes.append("Rail")
    if medspeed_high_bool and acc95_medium_bool:
        possible_modes.append("Car")
    if medspeed_high_bool and acc95_high_bool:
        possible_modes.append("Car")

    df['detected_mode'] = ",".join(possible_modes)
    return df


def mode_detection(df, speed_th=2.78, acceleration_th=0.5, minimal_walking_duration=100, minimal_trip_duration=120, use_multiprocessing=True):
    """Tags the DataFrame at 'trip' indexes with detected modes in the 'detected_mode' column.

    Args:
        df (pandas.DataFrame): DataFrame to be processed, coming from segmentation module
        speed_th (float, optional): The walk speed threshold. Defaults to 2.78.
        acceleration_th (float, optional): The walk acceleration threshold. Defaults to 0.5.
        minimal_walking_duration (int, optional): The walk duration threshold. Defaults to 100.
        minimal_trip_duration (int, optional): The minimal trip duration threshold. Defaults to 120.
        use_multiprocessing (bool, optional): Specifies whether the multiprocessing package should be used. Defaults to True.

    Returns:
        pandas.DataFrame: Segments DataFrame with modes of transport tagged in the mode_detected column.
    """
    df["detected_mode"] = np.nan
    user_trips = df[df.detection == "trip"].index.values

    arguments = [list(x) for x in mit.consecutive_groups(user_trips)]
    arguments = list(
        map(lambda x: (df.iloc[x], speed_th, acceleration_th, minimal_walking_duration, minimal_trip_duration), arguments))

    if use_multiprocessing:
        pool = mp.Pool(processes=(mp.cpu_count() - 1))
        results = pool.map_async(_detect_walks, arguments)
        pool.close()
        pool.join()

        for res in results.get(timeout=1):
            df.loc[res.index] = res
    else:
        for argument_list in arguments:
            res = _detect_walks(argument_list)
            df.loc[res.index] = res

    # Pool on speed detection also
    user_trips = df[df.detection == "trip"].index.values

    arguments = [list(x) for x in mit.consecutive_groups(user_trips)]
    arguments = list(map(lambda x: (df.iloc[x]), arguments))

    if use_multiprocessing:
        pool = mp.Pool(processes=(mp.cpu_count() - 1))
        results = pool.map_async(_detect_modes, arguments)
        pool.close()
        pool.join()

        for res in results.get(timeout=1):
            df.loc[res.index] = res
    else:
        for argument_list in arguments:
            res = _detect_modes(argument_list)
            df.loc[res.index] = res

    df.loc[df.detection == "walk", 'detected_mode'] = "Walk"
    
    return df
