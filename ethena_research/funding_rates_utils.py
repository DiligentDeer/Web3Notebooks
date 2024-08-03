from requests import get, post
from web3 import Web3, HTTPProvider
from icecream import ic
import numpy as np
import pandas as pd
import sys
from dotenv import load_dotenv
import os
import matplotlib.pyplot as plt

def process_funding_rates(df, column_name, position=1):
    """ Process funding rates and calculate interest and cumulative interest. """
    # Extract and rename the column
    new_df = df[[column_name]].rename(columns={column_name: 'funding_rate'})
    new_df['neg_funding_rate'] = new_df['funding_rate'].apply(lambda x: x if x < 0 else 0)

    # Calculate interest and cumulative interest
    new_df['interest'] = new_df['funding_rate'] * position / 365
    new_df['neg_interest'] = new_df['neg_funding_rate'] * position / 365
    
    new_df['cum_interest'] = new_df['interest'].cumsum()
    new_df['neg_cum_interest'] = new_df['neg_interest'].cumsum()
    
    return new_df


def plot_interest_with_highlights(df, title):
    """
    Plot cumulative interests with different highlighting methods for days with zero negative interest,
    displayed on separate subplots.

    Parameters:
    - df (DataFrame): DataFrame containing the interest data.
    - title (str): Title for the plot.
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(19, 10))  # Two subplots in one column

    # Plot for cumulative interest
    ax1.plot(df.index, df['cum_interest'], label='Cumulative Interest', color='blue')
    ax1.set_title(f'{title} - Cumulative Interest')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Cumulative Interest Value')
    ax1.legend()
    ax1.grid(True)

    # Plot for negative cumulative interest
    ax2.plot(df.index, df['neg_cum_interest'], label='Negative Cumulative Interest', color='red')
    ax2.set_title(f'{title} - Negative Cumulative Interest')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Negative Cumulative Interest Value')
    ax2.legend()
    ax2.grid(True)

    plt.tight_layout()  # Adjust layout to prevent overlap
    plt.show()
    

def identify_and_merge_falls(df, window_size, ignore_window):
    """
    Identifies falls in the insurance fund and merges close falls into single events.

    Parameters:
    - df (DataFrame): DataFrame containing the insurance fund data.
    - window_size (int): Smoothing window size for rolling mean.
    - ignore_window (int): Number of days to consider merging falls that are close to each other.

    Returns:
    - DataFrame: Processed DataFrame with start and end dates and values of merged falls.
    """
    # Applying a simple smoothing technique using a rolling window
    df['smoothed_fund'] = df['neg_cum_interest'].rolling(window=window_size, center=True).mean().fillna(method='bfill').fillna(method='ffill')

    # Calculate the daily change in the smoothed insurance fund
    df['change_in_smoothed_fund'] = df['smoothed_fund'].diff().fillna(0)

    # Define a fall as a negative change
    df['is_fall'] = df['change_in_smoothed_fund'] < 0

    # Find the start and end of each significant fall period
    falls = []
    fall_start = None

    for i, row in df.iterrows():
        if row['is_fall']:
            if fall_start is None:
                fall_start = i
        else:
            if fall_start is not None:
                # Calculate the number of days between fall_start and i
                days_between = (i - fall_start).days
                if days_between <= ignore_window:
                    continue
                falls.append((fall_start, i - pd.Timedelta(days=1),
                              df.loc[fall_start, 'smoothed_fund'], df.loc[i - pd.Timedelta(days=1), 'smoothed_fund']))
                fall_start = None

    # Close any open fall period
    if fall_start is not None:
        falls.append((fall_start, df.index[-1],
                      df.loc[fall_start, 'smoothed_fund'], df.iloc[-1]['smoothed_fund']))

    # Create a DataFrame to summarize the falls
    falls_df = pd.DataFrame(falls, columns=['Start_Date', 'End_Date', 'Start_Fund', 'End_Fund'])
    falls_df['Difference'] = falls_df['Start_Fund'] - falls_df['End_Fund']

    return falls_df



def plot_falls(df, falls_df, title):
    """
    Plots the insurance fund over time with highlighted falls, improved visualization.

    Parameters:
    - df (DataFrame): DataFrame containing the insurance fund data.
    - falls_df (DataFrame): DataFrame containing data about the falls.
    - title (str): Title for the plot.
    """
    plt.figure(figsize=(19, 10))
    
    # Plot original fund data
    plt.plot(df.index, df['neg_cum_interest'], label='Original Insurance Fund', color='#127475', linewidth=3, alpha=0.7)
    
    # Plot smoothed fund data
    plt.plot(df.index, df['smoothed_fund'], label='Smoothed Fund', color='skyblue', linewidth=3)
    
    # Highlight fall periods
    for i, row in falls_df.iterrows():
        fall_period = df.loc[row['Start_Date']:row['End_Date']]
        plt.plot(fall_period.index, fall_period['smoothed_fund'], color='red', linewidth=1, alpha=0.8)
        
        # Add text annotation for each fall
        mid_point = fall_period.index[len(fall_period) // 2]
        plt.annotate(f'Fall {i+1}', (mid_point, fall_period['smoothed_fund'].iloc[len(fall_period) // 2]),
                     xytext=(0, 30), textcoords='offset points', ha='center', va='bottom',
                     bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
                     arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

    # Add a legend entry for falls
    plt.plot([], [], color='red', linewidth=2, label='Fall Periods')
    
    plt.title(f'{title} - Insurance Fund Over Time with Smoothed Data and Highlighted Falls')
    plt.xlabel('Date')
    plt.ylabel('Insurance Fund (BTC)')
    plt.legend(loc='upper right')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # plt.tight_layout()
    plt.show()
    
    
def extract_max_difference_row(df):
    """
    Extracts the row with the maximum 'Difference' from the DataFrame.

    Parameters:
    - df (DataFrame): DataFrame containing the columns 'Start_Date', 'End_Date', 'Start_Fund', 'End_Fund', 'Difference'.

    Returns:
    - list: A list containing a dictionary where each key-value pair corresponds to column-name and cell-value of the row with the maximum 'Difference'.
    """
    max_diff_row = df.loc[df['Difference'].idxmax()]
    return [max_diff_row.to_dict()]


def extract_rate_from_endpoints(rate_df, endpoint_dict, cex=None):
    """
    Extracts funding rate data for a specified date range and formats it into a new DataFrame.

    Parameters:
    - rate_df (DataFrame): DataFrame containing the columns 'funding_rate' and 'neg_funding_rate'.
    - endpoint_dict (dict): Dictionary with keys 'Start_Date', 'End_Date' containing the date range and other metadata.
    - cex (str, optional): Central Exchange name to customize the output column names.

    Returns:
    - DataFrame: A DataFrame with two columns for funding rates over the specified date range.
    """
    # Extract date range from endpoint_dict
    start_date = endpoint_dict['Start_Date']
    end_date = endpoint_dict['End_Date']
    
    # Slice the DataFrame to get data within the specified date range
    sliced_df = rate_df.loc[start_date:end_date]
    
    # Define column names based on whether a CEX name is provided
    if cex:
        funding_rate_col = f"{cex}_funding_rate"
        neg_funding_rate_col = f"{cex}_neg_funding_rate"
        cum_interest_col = f"{cex}_cum_interest"
        neg_cum_interest_col = f"{cex}_neg_cum_interest"
        	
    else:
        funding_rate_col = "funding_rate"
        neg_funding_rate_col = "neg_funding_rate"
        cum_interest_col = "cum_interest"
        neg_cum_interest_col = "neg_cum_interest"

    # Create a new DataFrame with the specified column names
    new_df = pd.DataFrame({
        funding_rate_col: sliced_df['funding_rate'],
        neg_funding_rate_col: sliced_df['neg_funding_rate'],
        cum_interest_col: sliced_df['cum_interest'],
        neg_cum_interest_col: sliced_df['neg_cum_interest'],
    })

    return new_df