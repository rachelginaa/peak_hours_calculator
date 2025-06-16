import pandas as pd
from datetime import time, date, timedelta, datetime
import csv
from io import StringIO

def find_typical_peak_hours_csv_multi_entity(
    csv_file="combined.csv",
    time_col="Time",
    threshold_percent=0.1,
    min_peak_duration="2h",
    max_peaks=None  # <-- NEW: Allow multiple peaks
):
    """
    Finds typical daily peak time ranges for multiple entities from a CSV file, normalizing over 24-hour period,
    merging overlapping/adjacent peaks, and outputs a CSV string.

    Args:
        csv_file (str): Path to the CSV file.
        time_col (str): Column containing timestamps.
        threshold_percent (float): % of max average count to consider a peak.
        min_peak_duration (str): Minimum duration a peak must last.
        max_peaks (int or None): Max number of peaks to keep per entity. None = all peaks.

    Returns:
        str: CSV string with columns: entity, peak_start, peak_end
    """

    all_peak_ranges = []
    try:
        min_duration_td = pd.Timedelta(min_peak_duration)
    except ValueError:
        print(f"Error: Invalid min_peak_duration format '{min_peak_duration}'.")
        return "entity,peak_start,peak_end\n"

    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return "entity,peak_start,peak_end\n"

    if time_col not in df.columns:
        print(f"Error: Time column '{time_col}' missing.")
        return "entity,peak_start,peak_end\n"

    try:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.dropna(subset=[time_col])
        representative_date = df[time_col].iloc[0].date()
        df['time_of_day'] = df[time_col].dt.time
    except Exception as e:
        print(f"Error processing time: {e}")
        return "entity,peak_start,peak_end\n"

    entity_cols = [col for col in df.columns if col not in [time_col, 'time_of_day']]
    if not entity_cols:
        print(f"No entity columns found besides '{time_col}'.")
        return "entity,peak_start,peak_end\n"

    for entity in entity_cols:
        print(f"\nProcessing entity: {entity}...")
        entity_df = df[['time_of_day', entity]].copy()
        entity_df = entity_df.rename(columns={entity: "count"})
        entity_df['count'] = pd.to_numeric(entity_df['count'], errors='coerce')
        entity_df = entity_df.dropna(subset=['count'])

        if entity_df.empty:
            print(f"No valid data for {entity}, skipping.")
            continue

        typical_day = entity_df.groupby('time_of_day')['count'].mean().reset_index()
        typical_day = typical_day.sort_values('time_of_day').reset_index(drop=True)

        daily_max_avg_count = typical_day["count"].max()
        if pd.isna(daily_max_avg_count) or daily_max_avg_count <= 0:
            print(f"Max average count is <= 0 for {entity}, skipping.")
            continue

        threshold_count = daily_max_avg_count * threshold_percent
        print(f"  Max avg count: {daily_max_avg_count:.2f}, Threshold: {threshold_count:.2f}")

        peak_intervals = []
        in_peak = False
        peak_start_dt = None

        typical_day['datetime'] = typical_day['time_of_day'].apply(
            lambda t: datetime.combine(representative_date, t)
        )

        last_dt = None

        for i, row in typical_day.iterrows():
            current_dt = row['datetime']
            current_count = row['count']
            is_above_threshold = current_count >= threshold_count

            if is_above_threshold and not in_peak:
                in_peak = True
                peak_start_dt = current_dt
            elif not is_above_threshold and in_peak:
                in_peak = False
                peak_end_dt = current_dt
                if peak_start_dt is not None:
                    peak_intervals.append({"start": peak_start_dt, "end": peak_end_dt})
                peak_start_dt = None
            last_dt = current_dt

        if in_peak and peak_start_dt is not None:
            end_of_cycle_dt = datetime.combine(representative_date, time(0,0,0)) + timedelta(days=1)
            peak_intervals.append({"start": peak_start_dt, "end": end_of_cycle_dt})

        qualified_peaks = []
        peak_intervals.sort(key=lambda x: x['start'])

        for peak in peak_intervals:
            start_dt = peak['start']
            end_dt = peak['end']
            duration = end_dt - start_dt

            final_start_dt = datetime.combine(representative_date, start_dt.time())
            final_end_dt = datetime.combine(representative_date, end_dt.time())

            if final_end_dt <= final_start_dt and duration > timedelta(0):
                final_end_dt += timedelta(days=1)

            final_duration = final_end_dt - final_start_dt

            if final_duration >= min_duration_td:
                qualified_peaks.append({
                    "entity": entity,
                    "start": final_start_dt,
                    "end": final_end_dt,
                    "duration": final_duration
                })

        if not qualified_peaks:
            print(f"  No peaks met minimum duration for {entity}.")
            continue

        # Merge overlapping/adjacent peaks
        qualified_peaks.sort(key=lambda x: x['start'])
        merged_peaks = []
        merged_peaks.append(qualified_peaks[0])

        for current_peak in qualified_peaks[1:]:
            last_merged = merged_peaks[-1]

            if current_peak['start'] <= last_merged['end']:
                last_merged['end'] = max(last_merged['end'], current_peak['end'])
            else:
                merged_peaks.append(current_peak)

        # Recalculate durations
        for peak in merged_peaks:
            peak['duration'] = peak['end'] - peak['start']

        # Sort by duration
        merged_peaks = sorted(merged_peaks, key=lambda x: x["duration"], reverse=True)

        if max_peaks is not None:
            merged_peaks = merged_peaks[:max_peaks]

        for peak in merged_peaks:
            print(f"  Selected peak for {entity}: {peak['start']} - {peak['end']} (Duration: {peak['duration']})")

        all_peak_ranges.extend(merged_peaks)

    if not all_peak_ranges:
        print("\nNo peak hours found matching criteria.")
        return "entity,peak_start,peak_end\n"

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["entity", "peak_start", "peak_end"])

    all_peak_ranges = sorted(all_peak_ranges, key=lambda x: (x['entity'], x['start']))

    for peak in all_peak_ranges:
        start_str = peak['start'].strftime("%Y-%m-%d %H:%M:%S")
        end_str = peak['end'].strftime("%Y-%m-%d %H:%M:%S")

        if peak['duration'] >= timedelta(days=1) - timedelta(seconds=1):
            start_dt_corrected = datetime.combine(peak['start'].date(), time(0, 0, 0))
            end_dt_corrected = datetime.combine(peak['start'].date(), time(23, 59, 59))
            start_str = start_dt_corrected.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end_dt_corrected.strftime("%Y-%m-%d %H:%M:%S")
        elif peak['end'].time() == time(0,0,0) and peak['end'].date() > peak['start'].date():
            end_dt_corrected = datetime.combine(peak['start'].date(), time(23, 59, 59))
            end_str = end_dt_corrected.strftime("%Y-%m-%d %H:%M:%S")

        writer.writerow([peak['entity'], start_str, end_str])

    return output.getvalue()

# --- Example Usage ---
input_csv = "combined.csv"
time_column_name = "Time"
peak_threshold = 0.15
min_duration = "1h"

peak_hours_csv_output = find_typical_peak_hours_csv_multi_entity(
    csv_file=input_csv,
    time_col=time_column_name,
    threshold_percent=peak_threshold,
    min_peak_duration=min_duration,
    max_peaks=3  # <-- NEW: Get up to 3 peaks per entity
)

print("\n--- Generated Peak Hours CSV ---")
print(peak_hours_csv_output)

output_filename = "peak_hours_v3.csv"
try:
    if peak_hours_csv_output:
        with open(output_filename, "w", newline="") as f:
            f.write(peak_hours_csv_output)
        print(f"\nSuccessfully saved peak hours to '{output_filename}'")
    else:
        print("\nSkipped saving as no output was generated.")
except Exception as e:
    print(f"\nError saving CSV: {e}")
