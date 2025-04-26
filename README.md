# Peak Time Conversion Scripts

This repository contains two Python scripts for processing peak time data from CSV files:

- `calculator.py`: Identifies peak time ranges for multiple countries/entities from a CSV file and outputs the results as a CSV-formatted string.
- `create_table.py`: Converts peak time ranges from a CSV file (with SGT timestamps) to an XLSX-ready Pandas DataFrame.

## Scripts

### `calculator.py`

Identifies peak time ranges for multiple countries from a CSV file and outputs the results as a CSV-formatted string. (An example is a csv-exported file for the throughput panel in Grafana)

**Input**

The script expects a CSV file (e.g., `combined.csv`) with time series data for multiple entities. The CSV file should contain a time column and at least one column representing the count for an country.

**Example Input CSV Format:**

    ```
    Time,CountryA,CountryB,CountryC
    2024-05-02 09:00:00,10,25,12
    2024-05-02 10:00:00,15,30,18
    2024-05-02 11:00:00,20,40,25
    ...

    ```

Where:

- `Time`: The time column, formatted as `YYYY-MM-DD HH:MM:SS`.

- `CountryA`, `CountryB`, `CountryC`: Columns representing the count for each country. There can be one or more country columns.

**Output**

The script outputs a CSV-formatted string representing the peak time ranges for each country and saves it to `peak_hours.csv`.

### `create_table.py`

Converts peak time ranges from a CSV file (with SGT timestamps) to an XLSX-ready Pandas DataFrame.

**Input**

The script expects a CSV file named `peak_hours.csv` with the following format:

    ```csv
    entity,peak_start,peak_end
    A,2024-05-02 10:00:00,2024-05-02 12:00:00
    B,2024-05-02 14:00:00,2024-05-02 15:00:00
    ...

    ```

Where:

- `entity`: A string identifying the country (e.g., A, B, C).

- `peak_start`: The start time of a peak period in SGT, formatted as `YYYY-MM-DD HH:MM:SS`.

- `peak_end`: The end time of a peak period in SGT, formatted as `YYYY-MM-DD HH:MM:SS`.

**Output**

The script generates an XLSX file named `output.xlsx` with the converted peak time ranges.

## Requirements

- Python 3.x

- Pandas

- pytz

## Setup

It is highly recommended to use a virtual environment to manage the project dependencies. This ensures that the project uses the correct package versions and does not interfere with other Python projects.

### Using a Virtual Environment

1.  **Create a virtual environment:**

    ```
    python3 -m venv .venv
    ```

    This command creates a virtual environment in a folder named `.venv` in your project directory.

2.  **Activate the virtual environment:**

    - On macOS/Linux:

      ```
      source .venv/bin/activate
      ```

    When the virtual environment is activated, your terminal prompt will change to show the environment name (e.g., `(.venv)`).

3.  **Install the dependencies:**

    ```
    pip install -r requirements.txt
    ```

    This command installs the packages listed in the `requirements.txt` file into your virtual environment.

### Dependencies

The project uses the following Python packages:

- [Pandas](https://pandas.pydata.org/): For data manipulation and analysis.

- [pytz](https://pypi.org/project/pytz/): For time zone conversions (specifically for `create_table.py`).

A `requirements.txt` file is included in the repository to ensure that you install the correct versions of these packages.

## Usage

### `calculator.py`

1.  Ensure the input CSV file is named `combined.csv` and is in the same directory as the script.

2.  Run the script from the command line:

    ```
    python3 calculator.py
    ```

    - The script will print the output CSV string to the console and also save it to a file named `peak_hours.csv`.
    - Some Arguments can be customised **(Change the default values in the function definition)**
      - `csv_file`: Path to the CSV file containing the data (e.g., "combined.csv").
      - `threshold_percent`: The percentage of the maximum count to consider as the start/end of a peak. Example: 0.1 means 10% of the maximum.
      - `max_peaks`: The maximum number of peak intervals to return per entity.
      - `min_peak_duration`: The minimum duration a peak must last (e.g., "1h", "30m").

### `create_table.py`

1.  Ensure the input CSV file is named `peak_hours.csv` and located in the same directory as the script.

2.  Run the script from the command line:

    ```
    python3 create_table.py
    ```

3.  The script will generate an XLSX file named `output.xlsx` in the same directory.
