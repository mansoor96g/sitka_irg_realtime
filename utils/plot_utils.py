"""Utilities for plotting stream gauge data.
"""

import pytz

from plotly.graph_objs import Scatter, Layout
from plotly import offline


aktz = pytz.timezone('US/Alaska')


def plot_current_data_html(readings, critical_points=[], known_slides=[],
        filename=None):
    """Plot IR gauge data, with critical points in red. Known slide
    events are indicated by a vertical line at the time of the event.
    """
    # DEV: This fn should receive any relevant slides, it shouldn't do any
    #   data processing.

    # Plotly considers everything UTC. Send it strings, and it will
    #  plot the dates as they read.
    datetimes = [str(reading.dt_reading.astimezone(aktz)) for reading in readings]
    heights = [reading.height for reading in readings]

    critical_datetimes = [str(reading.dt_reading.astimezone(aktz)) for reading in critical_points]
    critical_heights = [reading.height for reading in critical_points]

    min_height = min([reading.height for reading in readings])
    max_height = max([reading.height for reading in readings])

    # Want current data to be plotted with a consistent scale on the y axis.
    y_min, y_max = 20.0, 27.5

    # Set date string for chart title.
    dt_title = readings[-1].dt_reading.astimezone(aktz)
    title_date_str = dt_title.strftime('%m/%d/%Y')

    # Set filename.
    if not filename:
        filename = f"ir_plot_{readings[-1].dt_reading.__str__()[:10]}.html"

    data = [
        {
            # Non-critical gauge height data.
            'type': 'scatter',
            'x': datetimes,
            'y': heights
        }
    ]
    if critical_points:
        label_dt_str = critical_points[0].dt_reading.astimezone(aktz).strftime(
                '%m/%d/%Y %H:%M:%S')
        data.append(
            {
                # Critical points.
                'type': 'scatter',
                'x': critical_datetimes,
                'y': critical_heights,
                'marker': {'color': 'red'}
            }
        )
        data.append(
            {
                # Label for first critical point.
                'type': 'scatter',
                'x': [critical_datetimes[0]],
                'y': [critical_heights[0]],
                'text': f"{label_dt_str}  ",
                'mode': 'text',
                'textposition': 'middle left'
            }
        )

    my_layout = {
        'title': f"Current Indian River Gauge Readings, {title_date_str}",
        'xaxis': {
                'title': 'Date/ Time',
            },
        'yaxis': {
                'title': 'River height (ft)',
                'range': [y_min, y_max]
            }
    }

    fig = {'data': data, 'layout': my_layout}

    # # Set filename.
    # if not filename:
    #     filename = f"ir_plot_{readings[-1].dt_reading.__str__()[:10]}.html"
    # filename = 'plot_files/simple_irg_plot_current.html'
    # offline.plot(fig, filename=filename, auto_open=False)

    filename = 'irg_viz/templates/irg_viz/plot_fragments/simple_irg_plot_current.html'
    offline.plot(fig, filename=filename, auto_open=False)

def plot_interactive_critical_forecast_html(readings, critical_points=[], known_slides=[],
        filename=None):
    """Plot IR gauge data, with critical points in red. Known slide
    events are indicated by a vertical line at the time of the event.
    """
    # DEV: This fn should receive any relevant slides, it shouldn't do any
    #   data processing.

    # Plotly considers everything UTC. Send it strings, and it will
    #  plot the dates as they read.
    datetimes = [str(reading.dt_reading.astimezone(aktz)) for reading in readings]
    heights = [reading.height for reading in readings]

    critical_datetimes = [str(reading.dt_reading.astimezone(aktz)) for reading in critical_points]
    critical_heights = [reading.height for reading in critical_points]

    min_height = min([reading.height for reading in readings])
    max_height = max([reading.height for reading in readings])

    # Build a set of future readings, once every 15 minutes for the next
    #   6 hours.
    # DEV: May want to only look ahead 4.5 hrs; looking farther ahead
    #   than the critical 5-hour period seems less meaningful.
    # DEV: Doing some imports here, because this will be moved to 
    #   analysis_utils
    import datetime
    from .ir_reading import IRReading

    interval = datetime.timedelta(minutes=15)
    future_readings = []
    new_reading_dt = readings[-1].dt_reading + interval
    for _ in range(18):
        new_reading = IRReading(new_reading_dt, 23.0)
        future_readings.append(new_reading)
        new_reading_dt += interval
    future_datetimes = [str(r.dt_reading.astimezone(aktz)) for r in future_readings]
    future_heights = [r.height for r in future_readings]

    # What are the future critical points?
    #   These are the heights that would result in 5-hour total rise and 
    #     average rate matching critical values.
    #   These are the minimum values needed to become, or remain, critical.
    # DEV: Replace all 0.5 and 2.5 with M_CRITICAL and CRITICAL_RISE
    min_cf_readings = []
    latest_reading = readings[-1]
    for reading in future_readings:
        dt_lookback = reading.dt_reading - datetime.timedelta(hours=5)
        # Get minimum height from last 5 hours of readings, including future readings.
        # print(reading.dt_reading - datetime.timedelta(hours=5))
        relevant_readings = [r for r in readings
            if r.dt_reading >= dt_lookback]
        relevant_readings += min_cf_readings
        critical_height = min([r.height for r in relevant_readings]) + 2.5

        # Make sure critical_height also gives a 5-hour average rise at least
        #   as great as M_CRITICAL. Units are ft/hr.
        m_avg = (critical_height - relevant_readings[0].height) / 5
        if m_avg < 0.5:
            # The critical height satisfies total rise, but not sustained rate
            #   of rise. Bump critical height so it satisfies total rise and
            #   rate of rise.
            critical_height = 5 * 0.5 + relevant_readings[0].height

        new_reading = IRReading(reading.dt_reading, critical_height)
        min_cf_readings.append(new_reading)

    min_cf_datetimes = [str(r.dt_reading.astimezone(aktz)) for r in min_cf_readings]
    min_cf_heights = [r.height for r in min_cf_readings]

    # Want current data to be plotted with a consistent scale on the y axis.
    y_min, y_max = 20.0, 27.5

    # Set date string for chart title.
    dt_title = readings[-1].dt_reading.astimezone(aktz)
    title_date_str = dt_title.strftime('%m/%d/%Y')

    # Set filename.
    if not filename:
        filename = f"ir_plot_{readings[-1].dt_reading.__str__()[:10]}.html"

    data = [
        {
            # Non-critical gauge height data.
            'type': 'scatter',
            'x': datetimes,
            'y': heights,
            'name': 'current readings'
        }
    ]
    if critical_points:
        label_dt_str = critical_points[0].dt_reading.astimezone(aktz).strftime(
                '%m/%d/%Y %H:%M:%S')
        data.append(
            {
                # Critical points.
                'type': 'scatter',
                'x': critical_datetimes,
                'y': critical_heights,
                'marker': {'color': 'red'}
            }
        )
        data.append(
            {
                # Label for first critical point.
                'type': 'scatter',
                'x': [critical_datetimes[0]],
                'y': [critical_heights[0]],
                'text': f"{label_dt_str}  ",
                'mode': 'text',
                'textposition': 'middle left'
            }
        )
    # Plot minimum future critical readings.
    data.append(
        {
            'type': 'scatter',
            'x': min_cf_datetimes,
            'y': min_cf_heights,
            'marker': {'color': 'red', 'opacity': 0.5, 'size': 3},
            'name': 'min critical points',
        }
    )
    # Shade above future critical readings.
    data.append(
        {
            'type': 'scatter',
            'x': min_cf_datetimes,
            'y': [27.5 for dt in min_cf_datetimes],
            'marker': {'color': 'red', 'opacity': 0.5, 'size': 3},
            'fill': 'tonexty',
            'name': 'critical region',
        }
    )

    my_layout = {
        'title': f"Current Indian River Gauge Readings, {title_date_str}",
        'xaxis': {
                'title': 'Date/ Time',
            },
        'yaxis': {
                'title': 'River height (ft)',
                'range': [y_min, y_max]
            }
    }

    fig = {'data': data, 'layout': my_layout}

    # # Set filename.
    # # if not filename:
    # #     filename = f"ir_plot_{readings[-1].dt_reading.__str__()[:10]}.html"
    # filename = 'plot_files/plot_interactive_critical_forecast.html'
    # offline.plot(fig, filename=filename, auto_open=False)

    filename = 'irg_viz/templates/irg_viz/plot_fragments/irg_critical_forecast_current.html'
    offline.plot(fig, filename=filename, auto_open=False)

