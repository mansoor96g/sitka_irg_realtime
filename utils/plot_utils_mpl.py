"""Plotting utility functions, using mpl."""

import pytz

import matplotlib.pyplot as plt


aktz = pytz.timezone('US/Alaska')


def plot_critical_forecast_mpl(readings, critical_points=[],
        filename=None):
    """Plot IR gauge data, with critical points in red. Known slide
    events are indicated by a vertical line at the time of the event.
    """
    # DEV: This fn should receive any relevant slides, it shouldn't do any
    #   data processing.

    # Matplotlib accepts datetimes as x values, so it should be handling
    #   timezones appropriately.
    datetimes = [reading.dt_reading.astimezone(aktz) for reading in readings]
    heights = [reading.height for reading in readings]

    critical_datetimes = [reading.dt_reading.astimezone(aktz) for reading in critical_points]
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
    future_datetimes = [r.dt_reading.astimezone(aktz) for r in future_readings]
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

    min_cf_datetimes = [r.dt_reading.astimezone(aktz) for r in min_cf_readings]
    min_cf_heights = [r.height for r in min_cf_readings]

    # Calculate 15-min trend.
    #   Get m for last two readings. Build next 6 hrs of readings.
    # Be careful; this slope is still in ft/hr, but it's that rate as measured
    #   over the last 15 minutes.
    m_15_min = readings[-1].get_slope(readings[-2])

    proj_readings_15_min = []
    interval = datetime.timedelta(minutes=15)
    proj_dt = readings[-1].dt_reading + interval
    # Proj height is hourly rate/4, because we're only incrementing 15 min.
    proj_height = readings[-1].height + m_15_min/4
    for reading in future_readings:
        new_reading = IRReading(proj_dt, proj_height)
        proj_readings_15_min.append(new_reading)
        proj_dt += interval
        proj_height += m_15_min / 4

    proj_datetimes_15_min = [r.dt_reading.astimezone(aktz) for r in proj_readings_15_min]
    proj_heights_15_min = [r.height for r in proj_readings_15_min]



    # Want current data to be plotted with a consistent scale on the y axis.
    y_min, y_max = 20.0, 27.5

    # Set date string for chart title.
    dt_title = readings[-1].dt_reading.astimezone(aktz)
    title_date_str = dt_title.strftime('%m/%d/%Y')

    # Set filename.
    if not filename:
        filename = f"ir_plot_{readings[-1].dt_reading.__str__()[:10]}.html"

    # --- Plotting code

    # Build static plot image.
    plt.style.use('seaborn')
    fig, ax = plt.subplots(figsize=(10, 6), dpi=128)

    # Always plot on an absolute y scale.
    ax.set_ylim([20.0, 27.5])

    # Add river heights for the current set of readings.
    ax.plot(datetimes, heights, c='blue', alpha=0.8, linewidth=1)

    # Add critical points if relevant.
    if critical_points:
        ax.plot(critical_datetimes, critical_heights, c='red', alpha=0.6,
                linewidth=1)
        ax.scatter(critical_datetimes, critical_heights, c='red', alpha=0.8,
                s=15)
        # cp_label = critical_points[0].dt_reading.astimezone(aktz).strftime(
                # '%m/%d/%Y %H:%M:%S')
        # Labeling doesn't work well on live plot.
        # label_time = critical_points[0].dt_reading.astimezone(aktz)
        # cp_label = label_time.strftime('%m/%d/%Y %H:%M:%S') + '    '
        # ax.text(label_time, critical_heights[0], cp_label,
        #         horizontalalignment='right')

    # Plot minimum future critical readings.
    #   Plot these points, and shade to max y value.
    ax.plot(min_cf_datetimes, min_cf_heights, c='red', alpha=0.4)
    ax.fill_between(min_cf_datetimes, min_cf_heights, 27.5, color='red', alpha=0.2)

    # Plot current trends.
    ax.plot(proj_datetimes_15_min, proj_heights_15_min, c='blue', alpha=0.4,
                linestyle='dotted')

    # Set chart and axes titles, and other formatting.
    title = f"Indian River Gauge Readings, {title_date_str}"
    ax.set_title(title, loc='left')
    ax.set_xlabel('', fontsize=16)
    ax.set_ylabel("River height (ft)")



    # # Format major x ticks.
    # xaxis_maj_fmt = mdates.DateFormatter('%H:%M\n%b %d, %Y')
    # ax.xaxis.set_major_formatter(xaxis_maj_fmt)
    # # Label day every 12 hours; 0.5 corresponds to half a day
    # ax.xaxis.set_major_locator(ticker.MultipleLocator(0.5))

    # # Format minor x ticks.
    # xaxis_min_fmt = mdates.DateFormatter('%H:%M')
    # ax.xaxis.set_minor_formatter(xaxis_min_fmt)
    # # Label every 6 hours:
    # ax.xaxis.set_minor_locator(ticker.MultipleLocator(0.25))

    # # Format dates that appear in status bar when hovering.
    # hover_fmt = mdates.DateFormatter('%H:%M  %b %d, %Y')
    # ax.fmt_xdata = hover_fmt


    # # Try building my own tick labels.
    # my_ticklabels = []
    # for dt in datetimes:
    #     dt_label = dt.strftime('%H:%M\n%b %d, %Y')

    #     times_to_label = ['00:00', '06:00', '12:00', '18:00']
    #     use_label = any(time in dt_label for time in times_to_label)

    #     if use_label:
    #         my_ticklabels.append(dt_label)
    #     else:
    #         my_ticklabels.append('')

    # # Use these tick labels.
    # ax.set_xticklabels(my_ticklabels, minor=False)


    # Make major and minor x ticks small.
    ax.tick_params(axis='x', which='both', labelsize=8)

    # DEV: Uncomment this to see interactive plots during dev work,
    #   rather than opening file images.
    # plt.show()

    # Save to file.
    filename = f"current_ir_plots/ir_plot_{readings[-1].dt_reading.__str__()[:10]}.png"
    filename = "media/plot_images/irg_critical_forecast_plot.png"
    plt.savefig(filename)

    # filename = "irg_viz/"

    # --- Save the plot

    # # Set filename.
    # if not filename:
    #     filename = f"ir_plot_{readings[-1].dt_reading.__str__()[:10]}.html"
    # filename = 'plot_files/irg_cone_plot_current.html'
    # offline.plot(fig, filename=filename, auto_open=False)

    # filename = 'irg_viz/templates/irg_viz/irg_cone_plot_current.html'
    # offline.plot(fig, filename=filename, auto_open=False)