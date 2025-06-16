import pandas as pd
from datetime import datetime, timedelta, time
from io import StringIO
import csv

def find_typical_weekday_peak_times(
    csv_data,
    time_col="Time",
    peak_threshold_percent=0.85,
    max_peaks=2,
    merge_time_threshold="01:30:00",  # Reduced threshold for sharper peaks
):
    """
    Finds the top N typical peak timings (hours:minutes:seconds) on average for weekdays for multiple entities from a CSV string.
    Handles a CSV format with 'Time' column and subsequent entity columns.
    Identifies the top N peak timings based on average count, regardless of a global threshold.
    Merges timings within a specified time threshold.

    Input CSV format:
    Time,entity1,entity2,...
    YYYY-MM-DD HH:MM:SS,value1,value2,...

    Args:
        csv_data: The CSV data as a string.
        time_col: The name of the column containing the time (YYYY-MM-DD HH:MM:SS format).
        peak_threshold_percent: Percentage of the maximum count to consider as the start of a peak.
        max_peaks: The maximum number of peak timings to return per entity.
        merge_time_threshold: Time threshold for merging peak timings (e.g., "00:30:00").

    Returns:
        A CSV string with the top N peak timings for each entity, averaged across weekdays.
    """

    results = {}

    try:
        df = pd.read_csv((csv_data))
    except pd.errors.EmptyDataError:
        print("Error: CSV data is empty.")
        return ""
    except pd.errors.ParserError:
        print("Error: Could not parse CSV data.")
        return ""
    except Exception as e:
        print(f"An unexpected error occurred during CSV parsing: {e}")
        return ""

    try:
        df[time_col] = pd.to_datetime(df[time_col], format="%Y-%m-%d %H:%M:%S", errors='coerce')
    except KeyError:
        print(f"Error: Column '{time_col}' not found in CSV data.")
        return {}

    entity_cols = df.columns.tolist()[1:]

    for entity in entity_cols:
        entity_df = df[[time_col, entity]].copy().rename(columns={entity: "count"})
        entity_df = entity_df.dropna(subset=[time_col, 'count'])
        entity_df['weekday'] = entity_df[time_col].dt.weekday  # 0: Mon, 1: Tue, ..., 4: Fri
        weekday_df = entity_df[entity_df['weekday'] < 5]

        if weekday_df.empty:
            results[entity] = []
            continue

        # Aggregate by Time (5-minute intervals)
        weekday_df['time_group'] = weekday_df[time_col].dt.floor('5min')  # Group by 5-minute intervals
        time_group_avg = weekday_df.groupby(weekday_df['time_group'])['count'].mean()
        max_avg = time_group_avg.max()
        peak_threshold_count = max_avg * peak_threshold_percent

        peak_timings = []
        in_peak = False
        peak_start = None

        for current_time, avg_count in time_group_avg.items():
            if avg_count >= peak_threshold_count:
                if not in_peak:
                    in_peak = True
                    peak_start = current_time.time()  # Time at the start of the interval
                peak_end = current_time.time()  # Update peak_end continuously
            else:
                if in_peak:
                    in_peak = False
                    if peak_start:
                        peak_timings.append((peak_start, peak_end))
                    peak_start = None

        if in_peak and peak_start:
            peak_timings.append((peak_start, time_group_avg.index[-1].time()))  # End of day

        # Merge Peak Timings (More Aggressively)
        merged_peak_timings = []
        if peak_timings:
            peak_timings.sort()
            merged_peak_timings = merge_time_intervals(peak_timings, merge_time_threshold)

        # Select top N peak timings based on total count within the interval
        final_peak_timings = []
        if merged_peak_timings:
            peak_counts = []
            for start, end in merged_peak_timings:
                # Calculate the average count within the peak interval
                start_dt = datetime.combine(datetime.today(), start)
                end_dt = datetime.combine(datetime.today(), end)
                interval_avg = time_group_avg.loc[start_dt:end_dt].mean()
                peak_counts.append((start, end, interval_avg))
            
            # Sort by average count and select top N
            final_peak_timings = sorted(peak_counts, key=lambda x: x[2], reverse=True)[:max_peaks]
            final_peak_timings = [(start, end) for start, end, _ in final_peak_timings]

        results[entity] = final_peak_timings

    # Create CSV string
    output = StringIO()
    writer = csv.writer(output)

    # Write Header
    header = ["entity"] + [f"peak_start_{i+1}" for i in range(max_peaks)] + [f"peak_end_{i+1}" for i in range(max_peaks)]
    writer.writerow(header)

    for entity, timings in results.items():
        # Pad lists with empty strings to ensure consistent row length
        padded_timings = []
        for start, end in timings:
            padded_timings.extend([start, end])
        padded_timings.extend([""] * (2 * max_peaks - len(padded_timings)))
        row = [entity] + [t.strftime("%H:%M:%S") if isinstance(t, time) else "" for t in padded_timings]
        writer.writerow(row)

    return output.getvalue()


def merge_time_intervals(intervals, merge_threshold="00:30:00"):
    """
    Merges time intervals that are within a specified threshold.

    Args:
        intervals: A sorted list of datetime.time tuples representing peak timings.
        merge_threshold: A string representing the time threshold for merging (e.g., "01:00:00").

    Returns:
        A list of merged datetime.time tuples.
    """

    if not intervals:
        return []

    merged = [intervals[0]]
    threshold = timedelta(hours=int(merge_threshold[:2]), minutes=int(merge_threshold[3:5]), seconds=int(merge_threshold[6:]))

    for i in range(1, len(intervals)):
        current_start, current_end = intervals[i]
        previous_start, previous_end = merged[-1]

        start_dt = datetime.combine(datetime.today(), current_start)
        end_dt = datetime.combine(datetime.today(), previous_end)
        diff = start_dt - end_dt

        if diff <= threshold:
            merged[-1] = (min(previous_start, current_start), max(previous_end, current_end))
        else:
            merged.append(intervals[i])
    return merged


def time_to_seconds(t):
    """Converts a datetime.time object to total seconds since midnight."""
    return (t.hour * 3600 + t.minute * 60 + t.second)

# Example Usage (Replace with your actual CSV data)
csv_data = "combined.csv"

peak_timings_csv = find_typical_weekday_peak_times(csv_data, max_peaks=2)
print(peak_timings_csv)