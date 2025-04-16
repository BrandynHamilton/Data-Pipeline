import os
import pandas as pd
import matplotlib

import requests
from IPython.display import Image, display
import json

from dotenv import load_dotenv

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

from google.oauth2.service_account import Credentials as ServiceAccountCredentials

import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import datetime as dt
from datetime import timedelta

load_dotenv()

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

def run_report(property_id, dimension=None, metric=None, start_date='2022-01-01', end_date='today'):
    """Runs a report on a Google Analytics 4 property using direct credentials."""
    
    # Get credentials JSON from environment variable
    credentials_json = os.getenv("GOOGLE_CREDENTIALS")
    
    if not credentials_json:
        raise ValueError("GOOGLE_CREDENTIALS environment variable not found.")
    
    # Parse credentials JSON and create a ServiceAccountCredentials object
    credentials_info = json.loads(credentials_json)
    creds = ServiceAccountCredentials.from_service_account_info(credentials_info)
    
    # Initialize the BetaAnalyticsDataClient with the credentials
    client = BetaAnalyticsDataClient(credentials=creds)

    # Build the report request
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name=dimension)],
        metrics=[Metric(name=metric)],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
    )

    # Run the report
    response = client.run_report(request)

    # Check if the response has data
    if len(response.rows) == 0:
        print("No data found in the API response.")
    else:
        print("Data found:", response.rows)

    # Convert the response to DataFrame (assuming `response_to_df` is defined)
    df = response_to_df(response)

    return df

def retrieve_submissions_data(submissions_records_df, start_date, end_date, submission_directory):
    # Select relevant columns
    image_columns = [col for col in submissions_records_df.columns if 'Image #' in col]
    csv_columns = [col for col in submissions_records_df.columns if 'CSV File' in col]

    # Drop rows where all CSVs are NaN
    csvs = submissions_records_df[['id', 'Project', 'Created'] + image_columns + csv_columns].dropna(
        subset=csv_columns, how='all')

    # Convert 'Created' to datetime and filter the DataFrame
    csvs['Created'] = pd.to_datetime(csvs['Created'])
    csvs_filtered = csvs[(csvs['Created'] >= start_date) & (csvs['Created'] <= end_date)]
    
    submissions_data = []

    for _, row in csvs_filtered.iterrows():
        images = {}
        csv_files = {}

        # Dynamically extract all images
        for col in image_columns:
            image_info = row[col]
            if isinstance(image_info, list) and image_info:  # Ensure it's a list
                for idx, img in enumerate(image_info):  # Handle multiple images in the list
                    image_url = img.get('url')
                    image_filename = img.get('filename')
                    images[f'image_{col}_{idx+1}'] = image_url
                    download_file(image_url, submission_directory, image_filename)

        # Dynamically extract all CSV files
        for col in csv_columns:
            csv_info = row[col]
            if isinstance(csv_info, list) and csv_info:  # Ensure it's a list
                for idx, csv in enumerate(csv_info):  # Handle multiple CSVs in the list
                    csv_url = csv.get('url')
                    csv_filename = csv.get('filename')
                    csv_files[f'csv_{col}_{idx+1}'] = csv_filename
                    download_file(csv_url, submission_directory, csv_filename)

        submission_dict = {
            'dt': row['Created'],
            'project': row['Project'],
            'id': row['id'],
            'images': images,  # Now supports multiple images
            'data': csv_files   # Now supports multiple CSVs
        }

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

def get_submission_df(submissions_data, submission_num, submission_directory):
    try:
        submission = submissions_data[submission_num]
    except IndexError:
        raise ValueError("Submission number is out of range.")

    project = submission['project']
    data_struct = {}
    images = {}

    # Load all CSV files dynamically
    for csv_key, csv_filename in submission['data'].items():
        csv_path = os.path.join(submission_directory, csv_filename)
        try:
            if csv_filename.endswith('.xlsx') or csv_filename.endswith('.xls'):
                df = pd.read_excel(csv_path)
            else:
                df = pd.read_csv(csv_path)
            data_struct[csv_filename] = df
        except Exception as e:
            print(f"Error loading {csv_path}: {e}")

    # Store image URLs dynamically
    images = submission['images']

    return {
        "project": project,
        "file_names": list(data_struct.keys()),
        "image_urls": list(images.values())
    }



def show_file_and_img(submission):
    print(f"Project: {submission['project']}")
    
    # Display all file names
    for file_name in submission['file_names']:
        print(f"File: {file_name}")

    # Display all images
    for img_url in submission['image_urls']:
        display(Image(url=img_url))


def get_files(submission):
    return {"files": submission["file_names"]}

def main(SPREADSHEET_ID, SHEET_NAME, SCOPES, skip_first_row=False):
    """Retrieves and prints the entire table from a specific sheet in Google Sheets."""
    
    creds = None
    
    # Load token and credentials from environment variables
    token_json = os.getenv("GOOGLE_SHEETS_TOKEN")
    creds_json = os.getenv("GOOGLE_SHEETS_CRED")

    # print(f'token_json: {token_json}')
    # print(f'creds_json: {creds_json}')

    if token_json:
        # Load user token directly from environment variable
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    elif creds_json:
        # Load service account credentials directly from environment variable
        creds = ServiceAccountCredentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)

    # Refresh the token if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds:
        print("No valid credentials available.")
        return

    try:
        service = build("sheets", "v4", credentials=creds)
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=f"'{SHEET_NAME}'!A1:Z"
        ).execute()

        values = result.get("values", [])
        if not values:
            print("No data found.")
            return

        print("Retrieved table data from the specified sheet:")
        for row in values:
            print(row)

        df = convert_to_dataframe(values, skip_first_row=skip_first_row)
        if df is not None:
            print("Converted DataFrame:")
            print(df.head())
            return df

    except HttpError as err:
        print(f"An error occurred: {err}")
