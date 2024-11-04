import os

import sys

# Dynamically get the directory of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Append the pipeline scripts directory to sys.path
sys.path.append(os.path.join(current_dir, 'pipeline', 'scripts'))

print("Current working directory:", os.getcwd())
print("Current directory:", current_dir)

import pandas as pd
import matplotlib

from pyairtable import Api
from dotenv import load_dotenv

from scripts.pipeline_utils import save_csv, get_table,airtable_to_df,response_to_df,run_report, main,retrieve_submissions_data

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
import json

import datetime as dt
from datetime import datetime
from datetime import timedelta

load_dotenv()

class data_pipeline():
    def __init__(self,submission_directory,
                 save_directory, use_cached_data=False):
        self.submission_records = None
        self.use_cached_data = use_cached_data
        
        # Get the current working directory
        current_dir = os.getcwd()  # Gets the current working directory
        
        # Construct the submission directory as a variable
        self.submission_directory = submission_directory
        print(f'self.submission_directory:{self.submission_directory}')

        self.save_directory = save_directory
        print(f'self.save_directory:{self.save_directory}')

        self.twitter_data = None

    def set_use_cached_data(self, use_cached_data):
        self.use_cached_data = use_cached_data

    def save_data(self, data_struct, file):  
        # Define a custom serializer to handle Timestamp objects
        def custom_serializer(obj):
            if isinstance(obj, (pd.Timestamp, datetime)):
                return obj.isoformat()  # Convert Timestamp to string in ISO format
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        # Set the directory to 'pipeline/data/cleaned/'
        directory = self.save_directory
        
        # Ensure the directory exists
        if not os.path.exists(directory):
            os.makedirs(directory)  # Create the directory if it doesn't exist

        # Set the full file path
        path = os.path.join(directory, file)

        print(f'path: {path}')

        # Handle saving to JSON format
        if file.endswith('.json'):
            if isinstance(data_struct, dict):
                # Convert each DataFrame to a JSON-compatible format
                json_data_struct = {key: df.to_dict(orient='records') for key, df in data_struct.items()}
                with open(path, 'w') as f:
                    json.dump(json_data_struct, f, indent=4, default=custom_serializer)  # Use custom_serializer here
            else:
                raise ValueError("data_struct must be a dictionary for JSON saving.")

        # Handle saving to CSV format
        elif file.endswith('.csv'):
            if isinstance(data_struct, pd.DataFrame):
                data_struct.to_csv(path, index=False)
            else:
                raise ValueError("data_struct must be a DataFrame for CSV saving.")
            
    def load_data(self,file):
        directory = self.save_directory
        path = os.path.join(directory, file)

        # Load data from JSON file
        if file.endswith('.json'):
            with open(path, 'r') as f:
                json_data = json.load(f)
                # Convert the JSON data back to a dictionary of DataFrames
                data_struct = {key: pd.DataFrame(value) for key, value in json_data.items()}
                return data_struct

        # Load data from CSV file
        elif file.endswith('.csv'):
            # Load the CSV into a DataFrame
            data_frame = pd.read_csv(path)
            return data_frame  # Return the DataFrame directly

        else:
            raise ValueError("Unsupported file format. Please provide a .json or .csv file.")

    def get_airtable_data(self):

        if self.use_cached_data:
            return self.load_data('airtable_data.json')
        
        api = Api(os.environ['AIRTABLE_API_KEY'])

        submissions_records = get_table(api,os.environ['baseID'], os.environ['tableID'])
        submissions_records_df = airtable_to_df(submissions_records)

        contributor_records = get_table(api,os.environ['baseID'], os.environ['tableID'])
        contributor_records_df = airtable_to_df(contributor_records)

        project_records = get_table(api,os.environ['baseID'], os.environ['tableID'])
        project_records_df = airtable_to_df(project_records)

        data_struct = {
            "project_records": project_records_df,
            "contributor_records": contributor_records_df,
            "submissions_records": submissions_records_df
        }

        self.submission_records = submissions_records_df

        self.save_data(data_struct,'airtable_data.json')

        return data_struct
    
    def get_google_analytics_data(self):

        if self.use_cached_data:
            return self.load_data('google_analytics.json')

        GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        property_id = os.getenv('property_id')

        twenty_eight_days = str(dt.date.today() - timedelta(28))
        seven_days = str(dt.date.today() - timedelta(7))
        twelve_months = str(dt.date.today() - timedelta(365))
        today = str(dt.date.today())

        cities = run_report(property_id,dimension="cityid",metric="activeUsers")
        users_timeseries = run_report(property_id,dimension="date",metric="activeUsers")

        new_v_return_7d = run_report(property_id,dimension='newVsReturning',metric='active7DayUsers',start_date=today)
        new_v_return_7d = new_v_return_7d[new_v_return_7d['newVsReturning'] != '']

        new_v_return_28 = run_report(property_id,dimension='newVsReturning',metric='active28DayUsers',start_date=today)
        new_v_return_28 = new_v_return_28[new_v_return_28['newVsReturning'] != '']

        devices_7d = run_report(property_id,dimension='platformDeviceCategory',metric='active7DayUsers',start_date=today)

        devices_28d = run_report(property_id,dimension='platformDeviceCategory',metric='active28DayUsers',start_date=today)

        devices_at = run_report(property_id,dimension='platformDeviceCategory',metric='activeUsers')

        source_7d = run_report(property_id,dimension='firstUserDefaultChannelGroup',metric='active7DayUsers',start_date=today)

        source_28d = run_report(property_id,dimension='firstUserDefaultChannelGroup',metric='active28DayUsers',start_date=today)

        source_at = run_report(property_id,dimension='firstUserDefaultChannelGroup',metric='activeUsers')

        views_7d = run_report(property_id,dimension='unifiedScreenClass',metric='screenPageViews', start_date=seven_days)

        views_28d = run_report(property_id,dimension='unifiedScreenClass',metric='screenPageViews', start_date=twenty_eight_days)

        views_at = run_report(property_id,dimension='unifiedScreenClass',metric='screenPageViews')

        data_struct = {
            "cities": cities,
            "users_timeseries": users_timeseries,
            "new_v_return_7d": new_v_return_7d,
            "new_v_return_28d": new_v_return_28,
            "devices_7d": devices_7d,
            "devices_28d": devices_28d,
            "devices_at":devices_at,
            "source_7d":source_7d,
            "source_28d":source_28d,
            "source_at":source_at,
            "views_7d":views_7d,
            "views_28d":views_28d,
            "views_at":views_at
        }

        self.save_data(data_struct,'google_analytics.json')

        # data_struct = self.load_data('google_analytics.json')

        return data_struct

    def get_sheets_data(self):

        SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
        SCOPES = [os.getenv('SCOPES')]
        token_path = os.getenv('token_path')
        creds_path = os.getenv('creds_path')

        print(f'token_path: {token_path}')

        if self.use_cached_data:
            return self.load_data('google_sheets.json')

        # Google Sheets API; includes Ghost NL Data
        log_df = main(SPREADSHEET_ID=SPREADSHEET_ID,
                      SCOPES=SCOPES,
                      token_path=token_path,
                      creds_path=creds_path,
                      SHEET_NAME="Issue Log Data",
                      skip_first_row=True)
        
        subscriber_df = main(SPREADSHEET_ID=SPREADSHEET_ID,
                      SCOPES=SCOPES,
                      token_path=token_path,
                      creds_path=creds_path,
                      SHEET_NAME='Subscriber CSV',
                      skip_first_row=False)
        
        issue_df = main(SPREADSHEET_ID=SPREADSHEET_ID,
                      SCOPES=SCOPES,
                      token_path=token_path,
                      creds_path=creds_path,
                      SHEET_NAME='Issue CSV',
                      skip_first_row=False)

        ON_twitter = main(SPREADSHEET_ID=SPREADSHEET_ID,
                      SCOPES=SCOPES,
                      token_path=token_path,
                      creds_path=creds_path,
                      SHEET_NAME='Twitter CSV',
                      skip_first_row=False)
        
        Spencer_twitter = main(SPREADSHEET_ID=SPREADSHEET_ID,
                      SCOPES=SCOPES,
                      token_path=token_path,
                      creds_path=creds_path,
                      SHEET_NAME='Spencer Twitter CSV',
                      skip_first_row=False)
        
        data_struct = {
            "log_df":log_df,
            "subscriber_df":subscriber_df,
            "issue_df":issue_df,
            "ON_twitter":ON_twitter,
            "Spencer_twitter":Spencer_twitter
        }

        twitter_data = {
            "ON_twitter":ON_twitter,
            "Spencer_twitter":Spencer_twitter
        }

        for key in data_struct.keys():
            print(data_struct[key])

        self.save_data(data_struct,'google_sheets.json')

        self.twitter_data = twitter_data

        return data_struct
    
    def get_twitter_data(self):
        # For now we get from local folder

        if self.twitter_data is None:
            sheets = self.load_data('google_sheets.json')
            ON_twitter = sheets['ON_twitter']
            Spencer_twitter = sheets['Spencer_twitter']

            twitter_data = {
            "ON_twitter":ON_twitter,
            "Spencer_twitter":Spencer_twitter
        }
            
            self.twitter_data = twitter_data
            
        
        return self.twitter_data
    
    def get_substack_data(self,path1,
                          path2):
        substack1 = pd.read_csv(path1)
        substack2 = pd.read_csv(path2)

        data_struct = {
            'substack1':substack1,
            'substack2':substack2
        }

        return data_struct
    
    def get_submissions(self, start_date, end_date):
        # Use the current directory as the base if submission_directory is not provided
        self.get_airtable_data()
        
        if self.use_cached_data:
            data = self.load_data('airtable_data.json')
            self.submission_records = data['submissions_records']

        submissions = retrieve_submissions_data(self.submission_records, start_date, end_date, self.submission_directory)
        return submissions



        












    