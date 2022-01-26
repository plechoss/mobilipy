import pandas as pd
from mobilipy import constants


class WaypointsDataFrame(pd.DataFrame):
    """Class that serves as an entry point for the mobilipy pipeline
    """
    def __init__(self, data, tracked_at=constants.TRACKED_AT, longitude=constants.LONGITUDE,
                 latitude=constants.LATITUDE, user_id='user_id', crs={"init": "epsg:4326"}, timezone=constants.UTC):
        """Initializes the WaypointsDataFrame

        Args:
            data (pandas.DataFrame): DataFrame with raw GPS data
            tracked_at (str, optional): Name of the column containing the timestamp. Defaults to constants.TRACKED_AT.
            longitude (str, optional): Name of the column containing the longitude. Defaults to constants.LONGITUDE.
            latitude (str, optional): Name of the column containing the latitude. Defaults to constants.LATITUDE.
            user_id (str, optional): Name of the column containing the user_id. Defaults to 'user_id'.
            crs (dict, optional): Coordinate Reference System. Defaults to {"init": "epsg:4326"}.
            timezone (str, optional): Timezone available in pytz. Defaults to constants.UTC.
        """

        #self.crs = crs
        required_columns = ['tracked_at', 'longitude', 'latitude', 'user_id']
        optional_columns = ['accuracy', 'speed']

        rename_dict = {
            tracked_at: constants.TRACKED_AT,
            longitude: constants.LONGITUDE,
            latitude: constants.LATITUDE
        }

        # rename columns
        df = data.rename(columns=rename_dict)
        if(user_id in data.columns):
            df['user_id'] = data[user_id]
        else:
            df['user_id'] = 0

        df.tracked_at = pd.to_datetime(df.tracked_at, errors='coerce')
        try:
            df.tracked_at = df.tracked_at.dt.tz_localize(timezone)
        except TypeError:
            pass

        df = df.drop_duplicates(subset='tracked_at')
        df = df.sort_values(by='tracked_at')

        optional_columns = [
            col for col in optional_columns if col in df.columns]

        df = df[[*required_columns, *optional_columns]]

        super(WaypointsDataFrame, self).__init__(df)
