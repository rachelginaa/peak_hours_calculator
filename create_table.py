import pandas as pd
import pytz
from datetime import datetime, timedelta

# Load the CSV
input_file = 'peak_hours.csv'
output_file = 'output.xlsx'
df = pd.read_csv(input_file)

# Helper: Round to nearest 10 minutes
def round_to_nearest_10(dt):
    discard = timedelta(minutes=dt.minute % 10,
                        seconds=dt.second,
                        microseconds=dt.microsecond)
    dt -= discard
    if discard >= timedelta(minutes=5):
        dt += timedelta(minutes=10)
    return dt

# Setup timezones
sgt = pytz.timezone('Asia/Singapore')
fixed_cet = pytz.timezone('Etc/GMT-1')  # Fixed UTC+1
cest = pytz.timezone('Europe/Berlin')   # CEST (DST aware)

# Prepare output rows
output_rows = []

# Group by entity
for entity, group in df.groupby('entity'):
    group = group.sort_values('peak_start')  # ensure sorted
    row = {'country': entity.upper()}

    for idx, record in enumerate(group.itertuples(), start=1):
        # Parse SGT time
        start_sgt = sgt.localize(datetime.strptime(record.peak_start, '%Y-%m-%d %H:%M:%S'))
        end_sgt = sgt.localize(datetime.strptime(record.peak_end, '%Y-%m-%d %H:%M:%S'))

        # Round times
        start_sgt = round_to_nearest_10(start_sgt)
        end_sgt = round_to_nearest_10(end_sgt)

        # Convert to CET and CEST
        start_cet = start_sgt.astimezone(fixed_cet)
        end_cet = end_sgt.astimezone(fixed_cet)

        start_cest = start_sgt.astimezone(cest)
        end_cest = end_sgt.astimezone(cest)

        # Format strings
        peak_sgt = f"{start_sgt.strftime('%I:%M %p')} - {end_sgt.strftime('%I:%M %p')}"
        peak_cet = f"{start_cet.strftime('%I:%M %p')} - {end_cet.strftime('%I:%M %p')}"
        peak_cest = f"{start_cest.strftime('%I:%M %p')} - {end_cest.strftime('%I:%M %p')}"

        # Add columns dynamically
        row[f'Peak Range {idx} (SGT)'] = peak_sgt
        row[f'Peak Range {idx} (CET)'] = peak_cet
        row[f'Peak Range {idx} (CEST)'] = peak_cest

    output_rows.append(row)

# Create DataFrame
output_df = pd.DataFrame(output_rows)

# Save to Excel
output_df.to_excel(output_file, index=False)

print(f"Conversion completed: {output_file}")
