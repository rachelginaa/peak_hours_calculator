import pandas as pd
from datetime import datetime
import csv
from io import StringIO

def find_peak_hours_csv_multi_entity(csv_file, time_col="Time", threshold_percent=0.1, max_peaks=1, min_peak_duration="2h"):
    """
    Finds peak time ranges for multiple entities (e.g., countries) from a CSV file and outputs a CSV string.

    Args:
        csv_file: Path to the CSV file containing the data (e.g., "combined.csv").
        time_col: The name of the column containing the time (YYYY-MM-DD HH:MM:SS format).
        threshold_percent: The percentage of the maximum count to consider as the start/end of a peak.
                            Example: 0.8 means 80% of the maximum.
        max_peaks: The maximum number of peak intervals to return per entity.
        min_peak_duration: The minimum duration a peak must last (e.g., "1h", "30m").

    Returns:
        A CSV string representing the peak time ranges.
    """

    peak_hours = {}
    try:
        df = pd.read_csv(csv_file)  # Read CSV from file
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found.")
        return ""  # Or raise an exception, depending on your error handling

    # Convert time column to datetime objects
    try:
        df[time_col] = pd.to_datetime(df[time_col], format="%Y-%m-%d %H:%M:%S", errors='coerce')
    except KeyError:
        print(f"Error: Column '{time_col}' not found in CSV file.")
        return ""

    entity_cols = df.columns.tolist()[1:]  # Get all columns except the first (time)

    for entity in entity_cols:
        entity_df = df[[time_col, entity]].copy().rename(columns={entity: "count"})
        entity_df = entity_df.dropna(subset=[time_col, 'count'])

        if entity_df.empty:  # Skip if entity_df is empty after dropping NaNs
            peak_hours[entity] = []
            continue

        max_count = entity_df["count"].max()
        threshold_count = max_count * threshold_percent
        peak_ranges = []
        in_peak = False
        peak_start = None
        peak_starts = []
        peak_ends = []

        for row in entity_df.itertuples():  # Iterate only over the named tuple, not index
            if getattr(row, 'count') >= threshold_count:
                if not in_peak:
                    in_peak = True
                    peak_start = getattr(row, time_col)
            else:
                if in_peak:
                    in_peak = False
                    peak_end = getattr(row, time_col)
                    if peak_start:
                        peak_starts.append(peak_start)
                        peak_ends.append(peak_end)
                    peak_start = None

        if in_peak and peak_start:  # Handle case where peak continues to end of data
            peak_starts.append(peak_start)
            peak_ends.append(entity_df[time_col].iloc[-1])

        # Select top N peak intervals (or fewer if available) based on duration
        if peak_starts:
            peak_ranges = []
            for i in range(len(peak_starts)):
                duration = peak_ends[i] - peak_starts[i]
                if duration >= pd.Timedelta(min_peak_duration):
                    peak_ranges.append((peak_starts[i], peak_ends[i]))

            peak_ranges = sorted(peak_ranges, key=lambda x: x[1] - x[0], reverse=True)[:max_peaks]

        peak_hours[entity] = peak_ranges

    # Create CSV string
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["entity", "peak_start", "peak_end"])

    for entity, ranges in peak_hours.items():
        for start, end in ranges:
            writer.writerow([entity, start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")])

    return output.getvalue()

# Example Usage
csv_file = "combined.csv"  # The script now reads from this file
peak_hours_csv = find_peak_hours_csv_multi_entity(csv_file)

# Print the CSV string
print(peak_hours_csv)

# Optionally, save the CSV to a file:
with open("peak_hours.csv", "w", newline="") as f:
    f.write(peak_hours_csv)