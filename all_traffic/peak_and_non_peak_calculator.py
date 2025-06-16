import pandas as pd
from datetime import time, date, timedelta, datetime
import csv
from io import StringIO

def find_typical_peak_hours_csv_multi_entity(
    csv_file="combined.csv",
    time_col="Time",
    threshold_percent=0.1,
    min_peak_duration="2h" # Removed max_peaks parameter
):
    """
    Finds the single longest typical daily peak time range for multiple entities,
    calculates the corresponding non-peak period(s), normalizes over a 24-hour
    period, merges overlapping/adjacent peaks, and outputs a CSV string.

    Identifies peaks based on the average count for each time interval across all days
    relative to the maximum average count observed during the typical 24-hour cycle
    for that specific entity. Filters peaks by minimum duration, merges any
    overlapping or adjacent intervals, selects the single longest merged peak,
    and determines the time(s) outside this peak.

    Args:
        csv_file (str): Path to the CSV file containing the time series data.
                        Example: "combined.csv"
        time_col (str): Name of the column containing timestamps.
                        Must be parsable into 'YYYY-MM-DD HH:MM:SS' format.
                        Example: "Time"
        threshold_percent (float): Percentage of the typical daily maximum average count
                                   to consider as the peak threshold.
                                   Example: 0.8 means 80% of the max average count.
        min_peak_duration (str): Minimum duration a peak must last to be included
                                 (applied *before* merging).
                                 Format should be understandable by pandas.Timedelta
                                 (e.g., "1h", "30m", "2h30m").

    Returns:
        str: A CSV-formatted string representing the single longest typical peak time range
             and the corresponding non-peak time range(s) for each entity.
             Columns: "entity", "peak_start", "peak_end",
                      "non_peak1_start", "non_peak1_end",
                      "non_peak2_start", "non_peak2_end".
             Timestamps use the date from the *first* valid entry in the input CSV
             as a representative date (e.g., "YYYY-MM-DD HH:MM:SS"). Non-peak columns
             may be empty if the peak covers 24h or if only one non-peak period exists.
             Returns an empty string with only headers if no peaks are found or
             if critical errors occur.

    Raises:
        Prints error messages to the console for issues like file not found,
        missing columns, or data processing errors.
    """
    all_peak_ranges = [] # To store final peak dictionaries for all entities
    # Convert minimum duration string to Timedelta object for comparison
    try:
        min_duration_td = pd.Timedelta(min_peak_duration)
    except ValueError:
        print(f"Error: Invalid format for min_peak_duration '{min_peak_duration}'. Use formats like '1h', '30m'.")
        return "entity,peak_start,peak_end,non_peak1_start,non_peak1_end,non_peak2_start,non_peak2_end\n" # Return header only

    # --- 1. Load and Prepare Input Data ---
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: Input CSV file '{csv_file}' not found.")
        return "entity,peak_start,peak_end,non_peak1_start,non_peak1_end,non_peak2_start,non_peak2_end\n"
    except Exception as e:
        print(f"Error reading CSV file '{csv_file}': {e}")
        return "entity,peak_start,peak_end,non_peak1_start,non_peak1_end,non_peak2_start,non_peak2_end\n"

    # --- 1a. Process Time Column ---
    if time_col not in df.columns:
        print(f"Error: Time column '{time_col}' not found in '{csv_file}'.")
        return "entity,peak_start,peak_end,non_peak1_start,non_peak1_end,non_peak2_start,non_peak2_end\n"

    try:
        # Convert time column to datetime objects, coercing errors to NaT (Not a Time)
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce') # Auto-detects format usually

        # Drop rows where time conversion failed
        original_rows = len(df)
        df = df.dropna(subset=[time_col])
        if len(df) < original_rows:
             print(f"Warning: Dropped {original_rows - len(df)} rows due to invalid timestamp format in '{time_col}'.")

        if df.empty:
            print(f"Error: No valid timestamps found in column '{time_col}' after parsing.")
            return "entity,peak_start,peak_end,non_peak1_start,non_peak1_end,non_peak2_start,non_peak2_end\n"

        # Store the first valid date to use as the representative date in the output
        representative_date = df[time_col].iloc[0].date()
        print(f"Using representative date for output: {representative_date}")

        # Extract time of day component for grouping
        df['time_of_day'] = df[time_col].dt.time

    except Exception as e:
        print(f"Error processing time column '{time_col}': {e}")
        return "entity,peak_start,peak_end,non_peak1_start,non_peak1_end,non_peak2_start,non_peak2_end\n"

    # Identify entity columns (all columns except the time column and the new time_of_day column)
    entity_cols = [col for col in df.columns if col not in [time_col, 'time_of_day']]
    if not entity_cols:
        print(f"Error: No entity columns found in '{csv_file}' besides '{time_col}'.")
        return "entity,peak_start,peak_end,non_peak1_start,non_peak1_end,non_peak2_start,non_peak2_end\n"

    print(f"Found entity columns: {entity_cols}")

    # --- 2. Process Each Entity ---
    for entity in entity_cols:
        print(f"\nProcessing entity: {entity}...")

        # Select relevant columns and rename entity column to 'count' for consistency
        entity_df = df[['time_of_day', entity]].copy()
        entity_df = entity_df.rename(columns={entity: "count"})

        # Convert count column to numeric, coercing errors (e.g., non-numeric values) to NaN
        entity_df['count'] = pd.to_numeric(entity_df['count'], errors='coerce')

        # Drop rows where count is missing or non-numeric for this entity
        original_entity_rows = len(entity_df)
        entity_df = entity_df.dropna(subset=['count'])
        if len(entity_df) < original_entity_rows:
             print(f"Info: Dropped {original_entity_rows - len(entity_df)} rows for '{entity}' due to missing/invalid count values.")

        if entity_df.empty:
            print(f"Info: No valid numeric data found for entity '{entity}', skipping.")
            continue

        # --- 3. Calculate Typical Day Profile ---
        typical_day = entity_df.groupby('time_of_day')['count'].mean().reset_index()
        typical_day = typical_day.sort_values('time_of_day').reset_index(drop=True)

        if typical_day.empty:
            print(f"Info: Could not generate typical day profile for entity '{entity}', skipping.")
            continue

        # --- 4. Calculate Daily Max Average and Threshold ---
        daily_max_avg_count = typical_day["count"].max()
        if pd.isna(daily_max_avg_count) or daily_max_avg_count <= 0:
             print(f"Info: Max average count is <= 0 or NaN for entity '{entity}'. Cannot calculate threshold, skipping peak detection.")
             continue

        threshold_count = daily_max_avg_count * threshold_percent
        print(f"  Max avg count: {daily_max_avg_count:.2f}, Threshold: {threshold_count:.2f}")

        # --- 5. Identify Raw Peak Intervals in Typical Day ---
        peak_intervals = []
        in_peak = False
        peak_start_dt = None

        typical_day['datetime'] = typical_day['time_of_day'].apply(
            lambda t: datetime.combine(representative_date, t)
        )
        typical_day = typical_day.sort_values('datetime').reset_index(drop=True)

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
            first_point = typical_day.iloc[0]
            if first_point['count'] >= threshold_count:
                wrap_end_dt = None
                for i, row in typical_day.iterrows():
                     if row['count'] < threshold_count:
                         wrap_end_dt = row['datetime']
                         break
                if wrap_end_dt:
                     effective_end_dt = wrap_end_dt + timedelta(days=1)
                     peak_intervals.append({"start": peak_start_dt, "end": effective_end_dt})
                else:
                     full_day_start = datetime.combine(representative_date, time(0, 0, 0))
                     full_day_end = full_day_start + timedelta(days=1)
                     peak_intervals.append({"start": full_day_start, "end": full_day_end})
            else:
                end_of_cycle_dt = datetime.combine(representative_date, time(0,0,0)) + timedelta(days=1)
                peak_intervals.append({"start": peak_start_dt, "end": end_of_cycle_dt})

        # --- 6. Refine, Filter by Duration ---
        qualified_peaks = []
        processed_intervals_raw = set() # Avoid double processing raw intervals if wrap-around logic created duplicates

        peak_intervals.sort(key=lambda x: x['start']) # Sort raw intervals

        for peak in peak_intervals:
            start_dt = peak['start']
            end_dt = peak['end']

            interval_tuple = (start_dt, end_dt)
            if interval_tuple in processed_intervals_raw:
                continue
            processed_intervals_raw.add(interval_tuple)

            duration = end_dt - start_dt

            final_start_dt = datetime.combine(representative_date, start_dt.time())
            final_end_dt = datetime.combine(representative_date, end_dt.time())

            if final_end_dt <= final_start_dt and duration > timedelta(0):
                 if end_dt.date() > start_dt.date():
                     final_end_dt += timedelta(days=1)
                 elif duration >= timedelta(days=1):
                     final_end_dt += timedelta(days=1)

            final_duration = final_end_dt - final_start_dt

            if final_duration >= min_duration_td:
                qualified_peaks.append({
                    "entity": entity,
                    "start": final_start_dt,
                    "end": final_end_dt,
                    "duration": final_duration # Keep duration for now, will recalculate after merge
                })

        if not qualified_peaks:
            print(f"  No peaks met minimum duration of {min_peak_duration} for {entity}.")
            continue # Skip merging and selection if no peaks qualify

        # --- 7. Merge Overlapping or Adjacent Intervals ---
        qualified_peaks.sort(key=lambda x: x['start'])

        merged_peaks = []
        if qualified_peaks: # Check if list is not empty
            merged_peaks.append(qualified_peaks[0]) # Start with the first peak

            for current_peak in qualified_peaks[1:]:
                last_merged = merged_peaks[-1]

                # Check if current peak starts before or exactly when the last merged peak ends
                # Use a small tolerance (e.g., 1 second) for adjacency check if needed,
                # but exact match <= should work for adjacent intervals derived from the same timeseries.
                if current_peak['start'] <= last_merged['end']:
                    # Overlap or adjacent: Merge them by extending the end time of the last merged peak
                    last_merged['end'] = max(last_merged['end'], current_peak['end'])
                else:
                    # No overlap: Add the current peak as a new separate peak
                    merged_peaks.append(current_peak)

        # --- 8. Recalculate Durations, Select Longest Peak, Calculate Non-Peak ---
        if not merged_peaks:
             print(f"  No peaks remaining after merging for {entity}.")
             continue

        # Recalculate duration for each merged peak
        for peak in merged_peaks:
            peak['duration'] = peak['end'] - peak['start']

        # Sort the *merged* peaks by duration (longest first)
        merged_peaks = sorted(merged_peaks, key=lambda x: x["duration"], reverse=True)

        # Select only the single longest peak
        longest_peak = merged_peaks[0] # The first element after sorting by duration desc
        print(f"  Selected the longest peak for {entity}: {longest_peak['start']} - {longest_peak['end']} (Duration: {longest_peak['duration']})")

        # --- Calculate Non-Peak Period(s) ---
        np1_start, np1_end, np2_start, np2_end = None, None, None, None
        peak_start = longest_peak['start']
        peak_end = longest_peak['end']
        is_full_day_peak = longest_peak['duration'] >= timedelta(days=1) - timedelta(seconds=1)

        if is_full_day_peak:
            # If the peak is 24 hours, there are no non-peak periods
            print("  Peak covers full 24 hours. No non-peak periods.")
        else:
            # Define start and end markers for the representative day
            day_start_dt = datetime.combine(representative_date, time(0, 0, 0))
            # Use 23:59:59 for the end marker of the representative day for intervals
            day_end_dt = datetime.combine(representative_date, time(23, 59, 59))

            # Check if the peak wraps around midnight
            # A peak wraps if its end date is after its start date
            peak_wraps = peak_end.date() > peak_start.date()

            if peak_wraps:
                # Peak wraps (e.g., 22:00 to 06:00 next day)
                # Non-peak is from peak_end time to peak_start time on the representative day
                np1_start = datetime.combine(representative_date, peak_end.time())
                np1_end = datetime.combine(representative_date, peak_start.time())
                print(f"  Non-Peak (wrap-around): {np1_start.time()} - {np1_end.time()}")
            else:
                # Peak is within the same day (e.g., 10:00 to 18:00)
                # Non-peak 1: 00:00 to peak_start time
                # Non-peak 2: peak_end time to 23:59:59
                np1_start = day_start_dt
                np1_end = peak_start # End time is exclusive for the interval before peak
                np2_start = peak_end # Start time is exclusive for the interval after peak
                np2_end = day_end_dt

                # Handle edge case: Peak starts exactly at 00:00
                if peak_start.time() == time(0,0,0):
                    np1_start, np1_end = None, None # No first non-peak period
                    print(f"  Non-Peak (starts 00:00): {np2_start.time()} - {np2_end.time()}")
                # Handle edge case: Peak ends exactly at 23:59:59 (or effectively midnight)
                elif peak_end.time() == time(23,59,59) or peak_end.time() == time(0,0,0): # Check both possibilities
                    np2_start, np2_end = None, None # No second non-peak period
                    print(f"  Non-Peak (ends midnight): {np1_start.time()} - {np1_end.time()}")
                else:
                    print(f"  Non-Peak 1: {np1_start.time()} - {np1_end.time()}")
                    print(f"  Non-Peak 2: {np2_start.time()} - {np2_end.time()}")


        # Store non-peak times in the dictionary
        longest_peak['np1_start'] = np1_start
        longest_peak['np1_end'] = np1_end
        longest_peak['np2_start'] = np2_start
        longest_peak['np2_end'] = np2_end

        all_peak_ranges.append(longest_peak) # Add the single longest peak (with non-peak info)

    # --- 9. Create Final CSV Output String ---
    if not all_peak_ranges:
        print("\nNo peak hours found matching the criteria for any entity after processing.")
        return "entity,peak_start,peak_end,non_peak1_start,non_peak1_end,non_peak2_start,non_peak2_end\n"

    output = StringIO()
    writer = csv.writer(output)
    # Update header row
    writer.writerow(["entity", "peak_start", "peak_end", "non_peak1_start", "non_peak1_end", "non_peak2_start", "non_peak2_end"])

    # Sort final combined list by entity name, then by start time for consistent output
    all_peak_ranges = sorted(all_peak_ranges, key=lambda x: (x['entity'], x['start']))

    for peak in all_peak_ranges:
         # Format peak start/end times
         start_str = peak['start'].strftime("%Y-%m-%d %H:%M:%S")
         end_str = peak['end'].strftime("%Y-%m-%d %H:%M:%S")

         # Adjust peak end for 24h or midnight wrap for clarity in output
         is_full_day = peak['duration'] >= timedelta(days=1) - timedelta(seconds=1)
         # Check if original end time was exactly midnight of the next day
         ends_at_midnight = peak['end'].time() == time(0,0,0) and peak['end'].date() > peak['start'].date()

         if is_full_day:
             # Ensure start is 00:00:00 and end is 23:59:59 of the representative date
             start_dt_corrected = datetime.combine(peak['start'].date(), time(0, 0, 0))
             end_dt_corrected = datetime.combine(peak['start'].date(), time(23, 59, 59))
             start_str = start_dt_corrected.strftime("%Y-%m-%d %H:%M:%S")
             end_str = end_dt_corrected.strftime("%Y-%m-%d %H:%M:%S")
         elif ends_at_midnight:
              # Represent end as 23:59:59 of the start day
              end_dt_corrected = datetime.combine(peak['start'].date(), time(23, 59, 59))
              end_str = end_dt_corrected.strftime("%Y-%m-%d %H:%M:%S")

         # Format non-peak times, handling None values
         np1_start = peak.get('np1_start')
         np1_end = peak.get('np1_end')
         np2_start = peak.get('np2_start')
         np2_end = peak.get('np2_end')

         np1_start_str = np1_start.strftime("%Y-%m-%d %H:%M:%S") if np1_start else ""
         # For non-peak end, if it's the start of the peak, format as is.
         # If it represents the end of the day (23:59:59), format as is.
         np1_end_str = np1_end.strftime("%Y-%m-%d %H:%M:%S") if np1_end else ""
         np2_start_str = np2_start.strftime("%Y-%m-%d %H:%M:%S") if np2_start else ""
         np2_end_str = np2_end.strftime("%Y-%m-%d %H:%M:%S") if np2_end else ""


         # Write row with peak and non-peak times
         writer.writerow([peak['entity'], start_str, end_str, np1_start_str, np1_end_str, np2_start_str, np2_end_str])

    return output.getvalue()

# --- Example Usage ---
# Ensure you have a 'combined.csv' file in the same directory
# with a 'Time' column (YYYY-MM-DD HH:MM:SS) and other columns for entities.

# Parameters (adjust as needed)
input_csv = "combined.csv"       # Input CSV file name
time_column_name = "Time"        # Name of the timestamp column
peak_threshold = 0.15            # 15% of the typical daily max average count
# max_num_peaks removed
min_duration = "1h"              # Minimum duration for a peak (BEFORE merging)

# Call the function to find the single longest peak and non-peak periods
peak_hours_csv_output = find_typical_peak_hours_csv_multi_entity(
    csv_file=input_csv,
    time_col=time_column_name,
    threshold_percent=peak_threshold,
    # max_peaks argument removed
    min_peak_duration=min_duration
)

# Print the resulting CSV string to the console
print("\n--- Generated Single Longest Peak + Non-Peak Hours CSV ---")
print(peak_hours_csv_output)

# Optionally, save the CSV string to a file
output_filename = "peak_hours_single_longest_with_nonpeak.csv" # Updated output file name
try:
    # Ensure the output is not empty before writing (it includes headers even if no peaks)
    if peak_hours_csv_output:
        with open(output_filename, "w", newline="") as f:
            f.write(peak_hours_csv_output)
        print(f"\nSuccessfully saved peak and non-peak hours to '{output_filename}'")
    else:
        print("\nSkipped saving file as no output was generated.")
except Exception as e:
    print(f"\nError saving CSV to file '{output_filename}': {e}")

