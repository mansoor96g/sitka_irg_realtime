"""Utility functions for analyzing stream gauge data, and slide data.
"""

import math, datetime, csv

from xml.etree import ElementTree as ET

import requests, pytz

# Assume this file will be imported in a directory outside of utils.
from utils.ir_reading import IRReading


# Critical values.
# Critical rise in feet. Critical slope, in ft/hr.
RISE_CRITICAL = 2.5
M_CRITICAL = 0.5


def fetch_current_data(fresh=True, filename='current_data/current_data.txt'):
    """Fetches current data from the river gauge.

    If fresh is False, looks for cached data.
      Cached data is really just for development purposes, to avoid hitting
      the server unnecessarily.

    Returns the current data as text.
    """
    if fresh:
        gauge_url = "https://water.weather.gov/ahps2/hydrograph_to_xml.php?gage=irva2&output=tabular"
        gauge_url_xml = "https://water.weather.gov/ahps2/hydrograph_to_xml.php?gage=irva2&output=xml"
        r = requests.get(gauge_url_xml)

        with open(filename, 'w') as f:
            f.write(r.text)

        return r.text

    else:
        # Try to use cached data.
        try:
            with open(filename) as f:
                current_data = f.read()
        except:
            # Can't read from file, so fetch fresh data.
            return fetch_current_data(fresh=True)
        else:
            return current_data


def fetch_current_data_usgs(fresh=True,
            filename='current_data/current_data_usgs.txt'):
    """Fetches current data directly from the usgs source.

    If fresh is False, looks for cached data.
      Cached data is really just for development purposes, to avoid hitting
      the server unnecessarily.

    Returns the current data file.
    """

    # Data url format:
    # https://waterdata.usgs.gov/ak/nwis/uv?cb_00065=on&format=rdb \ 
    #   &site_no=15087700&period=&begin_date=2020-02-18&end_date=2020-02-21
    # Grab last 3 days of data; will be 48 hrs + today's hours.
    # Make sure I make an appropriate ak timestamp, because this needs to run
    #  on my system which is localized to ak, and a server which is on utc.
    #  Start with utc time, then localize to ak.
    aktz = pytz.timezone('US/Alaska')
    dt_end_naive = datetime.datetime.utcnow()
    dt_end_utc = pytz.utc.localize(dt_end_naive)
    dt_end_ak = dt_end_utc.astimezone(aktz)
    dt_end_ak_str = dt_end_ak.strftime("%Y-%m-%d")
    dt_start_ak = dt_end_ak - datetime.timedelta(days=3)
    dt_start_ak_str = dt_start_ak.strftime("%Y-%m-%d")

    usgs_url = f"https://waterdata.usgs.gov/ak/nwis/uv?cb_00065=on&format=rdb"
    usgs_url += f"&site_no=15087700&period=&begin_date={dt_start_ak_str}"
    usgs_url += f"&end_date={dt_end_ak_str}"

    if fresh:
        # All of above should be moved to a helper function if fresh.
        r = requests.get(usgs_url)

        with open(filename, 'w') as f:
            f.write(r.text)

        return filename

    else:
        # Try to use cached data.
        try:
            with open(filename) as f:
                current_data = f.read()
        except:
            # Can't read from file, so fetch fresh data.
            return fetch_current_data_usgs(fresh=True)
        else:
            return filename


def process_xml_data(data):
    """Processes xml data from text file.
    Returns a list of readings.
    """

    # Parse xml tree from file.
    root = ET.fromstring(data)
    tree = ET.ElementTree(root)

    # 6th element is the set of observed readings.
    # 1st and 2nd elements of each reading are datetime, height.
    readings = []
    for reading in root[5]:
        dt_reading_str = reading[0].text
        dt_reading = datetime.datetime.strptime(dt_reading_str,
                 "%Y-%m-%dT%H:%M:%S-00:00")
        dt_reading_utc = dt_reading.replace(tzinfo=pytz.utc)
        height = float(reading[1].text)

        reading = IRReading(dt_reading_utc, height)
        readings.append(reading)

    # Readings need to be in chronological order.
    # DEV: This should be an absolute ordering, not just relying on 
    #      input file format.
    readings.reverse()

    return readings

def process_usgs_data(usgs_data_file):
    """Processes data that came directly from the USGS.
    Returns a list of readings.
    """
    aktz = pytz.timezone('US/Alaska')
    with open(usgs_data_file) as f:
        reader = csv.reader(f, delimiter='\t')
        # Skip past all the header rows.
        for _ in range(28):
            next(reader)
        readings = []
        for row in reader:
            # Skip any data that causes errors.
            try:
                ts_naive = datetime.datetime.strptime(row[2], '%Y-%m-%d %H:%M')
                tz_str = row[3]
                height = float(row[4])
            except Exception as e:
                # DEV: Bare except is bad, but fix.
                # Log this?
                pass
                print('exception', e)
            else:
                ts_ak = aktz.localize(ts_naive)
                ts_utc = ts_ak.astimezone(pytz.utc)
                new_reading = IRReading(ts_utc, height)
                readings.append(new_reading)

    # Make sure readings are in chronological order.
    if readings[-1].dt_reading < readings[0].dt_reading:
        readings.reverse()

    return readings


def get_critical_points(readings):
    """Return critical points.
    A critical point is the first point where the slope has been critical
    over a minimum rise. Once a point is considered critical, there are no
    more critical points for the next 6 hours.
    """

    # What's the longest it could take to reach critical?
    #   RISE_CRITICAL / M_CRITICAL
    #  If it rises faster than that, we want to know.
    #    Multiplied by 4, because there are 4 readings/hr.
    readings_per_hr = get_reading_rate(readings)
    max_lookback = math.ceil(RISE_CRITICAL / M_CRITICAL) * readings_per_hr

    critical_points = []
    # Start with 10th reading, so can look back.
    for reading_index, reading in enumerate(readings[max_lookback:]):
        # print(f"  Examining reading: {reading.get_formatted_reading()}")
        # Get prev max_lookback readings.
        prev_readings = [reading for reading in readings[reading_index-max_lookback:reading_index]]
        for prev_reading in prev_readings:
            rise = reading.get_rise(prev_reading)
            m = reading.get_slope(prev_reading)
            # print(f"    Rise: {rise} Slope: {m}")
            if rise >= RISE_CRITICAL and m > M_CRITICAL:
                # print(f"Critical point: {reading.get_formatted_reading()}")
                critical_points.append(reading)
                break

    return critical_points


def get_reading_rate(readings):
    """Return readings/hr.
    Should be 1 or 4, for hourly or 15-min readings.
    """
    reading_interval = (
        (readings[1].dt_reading - readings[0].dt_reading).total_seconds() // 60)
    reading_rate = int(60 / reading_interval)
    # print(f"Reading rate for this set of readings: {reading_rate}")

    return reading_rate


def get_recent_readings(readings, hours_lookback):
    """From a set of readings, return only the most recent x hours
    of readings.
    """
    last_reading = readings[-1]
    td_lookback = datetime.timedelta(hours=hours_lookback)
    dt_first_reading = last_reading.dt_reading - td_lookback
    recent_readings = [r for r in readings
                            if r.dt_reading >= dt_first_reading]

    return recent_readings


def get_first_critical_points(readings):
    """From a long set of data, find the first critical reading in
    each potentially critical event.
    Return this set of readings.
    """

    # What's the longest it could take to reach critical?
    #   RISE_CRITICAL / M_CRITICAL
    #  If it rises faster than that, we want to know.
    #    Multiplied by 4, because there are 4 readings/hr.
    # Determine readings/hr from successive readings.
    #  reading_interval is in minutes
    # Assumes all readings in this set of readings are at a consistent interval.
    reading_interval = (readings[1].dt_reading - readings[0].dt_reading).total_seconds() // 60
    lookback_factor = int(60 / reading_interval)
    # print('lf', lookback_factor)
    max_lookback = math.ceil(RISE_CRITICAL / M_CRITICAL) * lookback_factor

    first_critical_points = []
    # Start with 10th reading, so can look back.
    for reading_index, reading in enumerate(readings[max_lookback:]):
        # print(f"  Examining reading: {reading.get_formatted_reading()}")
        # Get prev max_lookback readings.
        prev_readings = [reading for reading in readings[reading_index-max_lookback:reading_index]]
        for prev_reading in prev_readings:
            rise = reading.get_rise(prev_reading)
            m = reading.get_slope(prev_reading)
            # print(f"    Rise: {rise} Slope: {m}")
            if rise >= RISE_CRITICAL and m > M_CRITICAL:
                # print(f"Critical point: {reading.get_formatted_reading()}")
                # Ignore points 12 hours after an existing critical point.
                if not first_critical_points:
                    first_critical_points.append(reading)
                    break
                elif (reading.dt_reading - first_critical_points[-1].dt_reading).total_seconds() // 3600 > 12:
                    first_critical_points.append(reading)
                    break
                else:
                    # This is shortly after an already-identified point.
                    break

    return first_critical_points


def get_48hr_readings(first_critical_point, all_readings):
    """Return 24 hrs of readings before, and 24 hrs of readings after the
    first critical point."""
    readings_per_hr = get_reading_rate(all_readings)
    # Pull from all_readings, with indices going back 24 hrs and forward
    #  24 hrs.
    fcp_index = all_readings.index(first_critical_point)
    start_index = fcp_index - 24 * readings_per_hr
    end_index = fcp_index + 24 * readings_per_hr
    # print(readings_per_hr, start_index, end_index)

    return all_readings[start_index:end_index]