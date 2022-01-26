import pytz
from mobilipy.constants import *
import pandas as pd
import numpy as np
from haversine import haversine, Unit

WALK_SPEED_MS = 1
TRANSFER = 60


class GTFS_Helper:

    def __init__(self, directory, lon_lat_step=0.003):
        self.stops = pd.read_csv(
            directory + "stops.txt").drop(['stop_url', 'location_type'], axis=1, errors='ignore')
        self.stops['bucket'] = list(zip(round(self.stops.stop_lon - (self.stops.stop_lon % lon_lat_step), 3),
                                    round(self.stops.stop_lat - (self.stops.stop_lat % lon_lat_step), 3)))
        self.stops_dic = {}
        for index, row in self.stops.iterrows():
            self.stops_dic.setdefault(row['bucket'], []).append(
                (row['stop_id'], row['stop_name'], row['stop_lon'], row['stop_lat']))

        self.calendar = pd.read_csv(directory + 'calendar.txt')
        self.calendar['start_date'] = pd.to_datetime(
            self.calendar['start_date'], format='%Y%m%d', yearfirst=True, infer_datetime_format=True).map(lambda x: pytz.utc.localize(x))
        self.calendar['end_date'] = pd.to_datetime(
            self.calendar['end_date'], format='%Y%m%d', yearfirst=True, infer_datetime_format=True).map(lambda x: pytz.utc.localize(x))

        def get_days_of_week(row):
            l = []
            for i in range(0, 7):
                if row[i] == 1:
                    l.append(i)
            return l
        self.calendar['days'] = self.calendar[['monday', 'tuesday', 'wednesday',
                                               'thursday', 'friday', 'saturday', 'sunday']].apply(get_days_of_week, axis=1)

        self.calendar_dates = pd.read_csv(directory + 'calendar_dates.txt')
        self.calendar_dates['date'] = pd.to_datetime(
            self.calendar_dates['date'], format='%Y%m%d', yearfirst=True, infer_datetime_format=True).map(lambda x: pytz.utc.localize(x))

        self.stop_times = pd.read_csv(directory + 'stop_times.txt')

        arrival_times = self.stop_times['arrival_time'].values
        departure_times = self.stop_times['departure_time'].values

        self.stop_times['arrival_time'] = np.array(
            [str(int(x[:2]) % 24) + x[2:] for x in arrival_times])
        self.stop_times['departure_time'] = np.array(
            [str(int(x[:2]) % 24) + x[2:] for x in departure_times])

        self.stop_times['arrival_time'] = pd.to_datetime(
            self.stop_times['arrival_time'], format="%H:%M:%S").dt.time
        self.stop_times['departure_time'] = pd.to_datetime(
            self.stop_times['departure_time'], format="%H:%M:%S").dt.time

        self.trips = pd.read_csv(directory + 'trips.txt').set_index('trip_id')
        self.transfers = self.get_transfers()

    def id_to_name(self, stop_id) -> str:
        """Finds the name of the stop with the given ID

        Args:
            stop_id (str): ID of the stop

        Returns:
            str: Name of the stop with the given ID
        """
        return self.stops[self.stops.stop_id == stop_id].iloc[0].stop_name

    def get_coordinates(self, stop_id):# -> tuple(float, float):
        """Finds coordinates of a stop with the given ID

        Args:
            stop_id (str): ID of the stop

        Returns:
            tuple[float, float]: Coordinates of the stop as (latitude, longitude)
        """
        stop = self.stops[self.stops.stop_id == stop_id].iloc[0]
        return stop.stop_lat, stop.stop_lon

    def get_nearby_stops(self, longitude, latitude, lon_lat_step=0.003, df=True) -> pd.DataFrame:
        """Finds nearest stops to the given location. Uses a grid search, checking the cell of the location as well as all the ones around it.

        Args:
            longitude (float): Longitude as degrees
            latitude (float): Latitude as degrees
            lon_lat_step (float, optional): Size of cells on map, in latitude/longitude degrees. Defaults to 0.003.

        Returns:
            pandas.DataFrame: DataFrame with info on all the nearest stops
        """
        lon_remainder = longitude % lon_lat_step
        lat_remainder = latitude % lon_lat_step

        lon = round(longitude - lon_remainder, 3)
        lat = round(latitude - lat_remainder, 3)

        output = []
        for lon_offset in [-lon_lat_step, 0, lon_lat_step]:
            for lat_offset in [-lon_lat_step, 0, lon_lat_step]:
                output += self.stops_dic.get((lon +
                                             lon_offset, lat+lat_offset), [])

        if(df):
            return pd.DataFrame(output, columns=['stop_id', 'stop_name', 'stop_lon', 'stop_lat'])
        else: 
            return output

    def get_n_closest_stops(self, longitude, latitude, n=1, lon_lat_step=0.003) -> pd.DataFrame:
        """Returns n closest stops to the given location

        Args:
            longitude (float): Longitude as degrees
            latitude (float): Latitude as degrees
            n (int, optional): Number of stops to be returned. Defaults to 1.
            lon_lat_step (float, optional): Size of cells on map, in latitude/longitude degrees. Defaults to 0.003.

        Returns:
            pandas.DataFrame: DataFrame with information about n closest stops
        """
        stops_df = self.get_nearby_stops(longitude, latitude, lon_lat_step)
        stops_df['dist'] = stops_df.apply(lambda row: haversine(
            (row.stop_lat, row.stop_lon), (latitude, longitude), Unit.METERS), axis=1)
        return stops_df.sort_values('dist', ascending=True).head(n)

    def get_transfers(self) -> pd.DataFrame:
        """Finds possible transfers within the same parent station.

        Returns:
            pandas.DataFrame: DataFrame containing all the possible transfers in the dataset.
        """
        transfers = self.stops.copy()
        transfers['neigh'] = transfers.apply(lambda row: self.get_nearby_stops(
            row.stop_lon, row.stop_lat, df=False), axis=1)
        transfers = transfers.explode('neigh')
        transfers[['neigh_id', 'neigh_name', 'neigh_lon', 'neigh_lat']] = pd.DataFrame(
            transfers['neigh'].tolist(), index=transfers.index)
        transfers = transfers[transfers.stop_id != transfers.neigh_id]
        transfers['distance'] = transfers.apply(lambda row: haversine(
            (row['stop_lat'], row['stop_lon']), (row['neigh_lat'], row['neigh_lon']), Unit.METERS), axis=1)
        transfers = transfers[transfers.distance <= 50]
        transfers['time_s'] = transfers.distance.map(
            lambda dist: dist * WALK_SPEED_MS)
        self.transfers = transfers
        return self.transfers
