import os
import pandas as pd
import matplotlib

import requests
from IPython.display import Image, display

from pyairtable import Api
from dotenv import load_dotenv

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import datetime as dt
from datetime import timedelta

def save_csv(df, name):
    path = f'../data/{name}.csv'
    df.to_csv(path,index=False)

def get_table(api, baseid, tableid):
    table = api.table(baseid,tableid)
    records = table.all()
    return records

def airtable_to_df(at,fields_col='fields',cols_to_keep=['id', 'createdTime']):
    at_copy = at.copy()
    df = pd.DataFrame(at_copy)
    fields_df = pd.json_normalize(df[fields_col])
    df = pd.concat([df[cols_to_keep], fields_df], axis=1)
    return df

def response_to_df(response):
    # Extract column names from the dimension and metric headers
    dimension_names = [dim.name for dim in response.dimension_headers]
    metric_names = [met.name for met in response.metric_headers]
    
    # Create lists to store the data
    rows_data = []
    
    # Loop through the rows in the response and collect values
    for row in response.rows:
        row_dict = {}
        for idx, dim_value in enumerate(row.dimension_values):
            row_dict[dimension_names[idx]] = dim_value.value
        for idx, met_value in enumerate(row.metric_values):
            row_dict[metric_names[idx]] = met_value.value
        rows_data.append(row_dict)
    
    # Create a DataFrame from the collected data
    df = pd.DataFrame(rows_data)

    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df.sort_values(by='date', inplace=True)
    
    return df

def run_report(property_id,dimension=None,metric=None, start_date='2022-01-01',end_date='today'):
    """Runs a simple report on a Google Analytics 4 property."""
    # TODO(developer): Uncomment this variable and replace with your
    #  Google Analytics 4 property ID before running the sample.
    # property_id = "YOUR-GA4-PROPERTY-ID"

    # Using a default constructor instructs the client to use the credentials
    # specified in GOOGLE_APPLICATION_CREDENTIALS environment variable.
    client = BetaAnalyticsDataClient()

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[
            Dimension(name=dimension),
        ],
        metrics=[
            Metric(name=metric),
        ],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
)

    response = client.run_report(request)

    if len(response.rows) == 0:
        print("No data found in the API response.")
    else:
        print("Data found:", response.rows)

    df = response_to_df(response)

    return df

def retrieve_submissions_data(submissions_records_df, start_date, end_date, submission_directory):
    # Select relevant columns and drop rows with all NaN values in the CSV columns
    csvs = submissions_records_df[['id', 'Project','Created', 'Image #1', 'Image #2', 'Image #3', 
                                    'Image 1 CSV File', 'Image 2 CSV File', 'Image 3 CSV File']].dropna(
        subset=['Image 1 CSV File', 'Image 2 CSV File', 'Image 3 CSV File'], how='all')
    print(f'test')
    # Convert 'Created' to datetime and filter the DataFrame
    csvs['Created'] = pd.to_datetime(csvs['Created'])
    csvs.sort_values(by='Created', ascending=False, inplace=True)

    csvs_filtered = csvs[(csvs['Created'] >= start_date) & (csvs['Created'] <= end_date)]

    # Create a list to hold the structured data
    submissions_data = []

    for _, row in csvs_filtered.iterrows():
        # Prepare image and CSV data
        images = {}
        csv_files = {}

        for i in range(1, 4):
            # Access images
            image_key = f'Image #{i}'
            image_info = row[image_key]

            # Check if image_info is a non-empty list
            if isinstance(image_info, list) and image_info:
                image_url = image_info[0]['url']  # Extract URL
                image_filename = image_info[0]['filename']  # Extract filename
                images[f'image_{i}'] = image_url
                # Download the image
                download_file(image_url, submission_directory, image_filename)

        for i in range(1, 4):
            # Access CSV files
            csv_key = f'Image {i} CSV File'
            csv_info = row[csv_key]

            # Check if csv_info is a non-empty list
            if isinstance(csv_info, list) and csv_info:
                csv_url = csv_info[0]['url']  # Extract URL
                csv_filename = csv_info[0]['filename']  # Extract filename
                csv_files[f'csv_{i}'] = csv_filename  # Store the filename instead of the URL
                # Download the CSV file
                print(f'csv file: {csv_filename}')
                download_file(csv_url, submission_directory, csv_filename)

        # Constructing a dictionary for each submission
        submission_dict = {
            'dt': row['Created'],
            'project': row['Project'],
            'id': row['id'],
            'image': images,
            'data': csv_files  # This now contains the filenames of the CSV files
        }
        print(f'submission_dict: {submission_dict}')
        submissions_data.append(submission_dict)

    return submissions_data

def download_file(url, directory, filename):
    """Download a file from a URL and save it to the specified directory."""
    file_path = os.path.join(directory, filename)

    # Download the file
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Write the content to a local file
        with open(file_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded {filename} successfully.")
    else:
        print(f"Failed to download {filename}. Status code: {response.status_code}")

def main(SPREADSHEET_ID, SHEET_NAME,SCOPES,token_path,creds_path,skip_first_row=False):
    """Retrieves and prints the entire table from a specific sheet in Google Sheets."""
    creds = None

    token_path = os.path.join("config", f"{token_path}")

    creds_path = os.path.join("config", f"{creds_path}")


    print(f'token_path: {token_path}')
    print(f'scopes: {SCOPES}')
    print(f'spreadsheet:{SPREADSHEET_ID}')

    # if os.path.exists(token_path):
    #     creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    # if not creds or not creds.valid:
    #     if creds and creds.expired and creds.refresh_token:
    #         creds.refresh(Request())
    #     else:
    #         flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    #         creds = flow.run_local_server(port=0)
    #     with open(token_path, "w") as token:
    #         token.write(creds.to_json())

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)

        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=f"'{SHEET_NAME}'!A1:Z"
        ).execute()

        values = result.get("values", [])

        if not values:
            print("No data found.")
            return

        # Print the entire table from the specific sheet
        print("Retrieved table data from the specified sheet:")
        for row in values:
            print(row)

        # Convert the values to a DataFrame
        df = convert_to_dataframe(values,skip_first_row=skip_first_row)
        if df is not None:
            print("Converted DataFrame:")
            print(df.head())  # Display the first few rows of the DataFrame

            return df

    except HttpError as err:
        print(f"An error occurred: {err}")

def convert_to_dataframe(values, skip_first_row=False):
    if not values or len(values) < 3:  # Check for at least 3 rows (1 header + 1 data row)
        print("Not enough data to convert to DataFrame.")
        return None

    # Optionally skip the first row and use the second row as headers
    if skip_first_row:
        headers = values[1]  # Use the second row as headers
        data = values[2:]    # Remaining rows are the data
    else:
        headers = values[0]  # Use the first row as headers
        data = values[1:]    # Remaining rows are the data

    print(f'headers: {headers}')

    # Initialize an empty list to hold processed rows
    processed_data = []

    # Check for consistent row lengths and handle mismatches
    for row in data:
        if len(row) == len(headers):
            processed_data.append(row)
        else:
            # Create a new row that matches the number of headers, fill missing spots with None
            new_row = [None] * len(headers)
            for i in range(min(len(row), len(headers))):  # Only fill up to the number of headers
                new_row[i] = row[i]
            processed_data.append(new_row)

    # Create the DataFrame
    df = pd.DataFrame(processed_data, columns=headers)

    # Optionally: clean up the DataFrame (e.g., remove empty rows)
    df = df.dropna(how='all')  # Drop rows where all elements are NaN

    return df
