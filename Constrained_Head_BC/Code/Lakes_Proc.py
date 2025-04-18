# -*- coding: utf-8 -*-
"""
The purpose of this script is to develop IWFM lake input files from
raw data acquired from CDEC and other sources.

General process:
    1. Read existing IWFM input file
    2. Read reservoir sources file (csv)
    3. Read data by dataset
    4. Read geospatial datasets (IWFM nodes, reservoir boundaries (NHD))
    5. Filter NHD dataset by feature (may need to do this manually for now/read
                                      from the sources file)
    6. Format data into input file

Created on Wed Mar  5 14:49:29 2025

@author: nanchor
"""

#%% Import libraries

import pandas as pd
import numpy as np
import os
import geopandas as gpd
import re
import time

# HTTP/URL library imports
import requests
import urllib
import shutil
import ssl
from bs4 import BeautifulSoup
import http

# GUI libraries
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import matplotlib

# Excel libraries
import openpyxl

#%% Helper Functions

def read_c3_res(res_df):
    
    # Read in CalSim3 reservoir info table
    root = tk.Tk()
    c3_res_pth = filedialog.askopenfilename(title='Select CalSim3 res_info.table file',
                                       initialdir='..\Resources\CalSim3', filetypes=[('CalSim3 Table', '.table')])
    root.destroy()
    
    # col_names = ['res_num',
    #              'storage',
    #              'area',
    #              'discharge',
    #              'elevation',		
    #              'coefev']
    
    #Units: af   acre      cfs     ft     [1/ft]
    c3_res_df = pd.read_csv(c3_res_pth, sep='\s+', skiprows=10, header=0,
                            usecols=np.arange(0, 6))
    
    #c3_res_df['res_name'] = c3_res_df[0].apply(lambda x: str(x).split('!', 1)[1] if '!' in x else np.nan)
    
    # Extract sensor codes - NOT NEEDED
    #res_df['Sensor_Code'] = res_df['Sensor_Code'].fillna(res_df['Sensor_No'].apply(lambda x: str(x).split(':')[0]))

    # Filter CalSim reservoir info to just the reservoirs in the list
    c3_res_df = c3_res_df.merge(right=res_df[['CalSim3_Res_ID',
                                              'ID']],
                                left_on='res_num',
                                right_on='CalSim3_Res_ID')
    
    return c3_res_df

# Function to extract the reservoir elevation from CalSim3 reservoir info
def res_bed_elev(c3_res_df):
    
    # First pass estimate lakebed
    c3_res_df.loc[c3_res_df['storage']==0, 'Res_Bed_Elev'] = c3_res_df['elevation']
    
    c3_res_df['Res_Bed_Elev'] = c3_res_df['Res_Bed_Elev'].ffill()
    
    return c3_res_df

# Function to convert storage to elevation with CalSim 3 reservoir info
def stor2elev(res_id, stor_df, c3_df):
    
    '''
    Inputs:
        res_id [string]: reservoir ID of form "BLB"
        stor_df [pandas dataframe]: storage values to convert to elevation
        c3_df [pandas dataframe]: storage-to-elevation CalSim3 values to use for
            interpolation
    
    Returns:
        elev_s [pandas series]: converted values 
    
    '''
    #TODO: remove (testing only)
    stor_df = res_mon_dict[res_id]
    
    res_df = c3_df.loc[c3_df['ID']==res_id,
                        ['ID','VALUE', 'VALUE_ELEV']]
    
    concat_df = pd.concat([stor_df[['VALUE',
                                    'VALUE_ELEV']], 
                           res_df[['VALUE',
                                  'VALUE_ELEV']]],
                          axis=0)
    
    concat_df.set_index('VALUE', inplace=True)
    
    concat_df.sort_values(by='VALUE', inplace=True)
    
    concat_df['VALUE_ELEV'].interpolate(method='slinear',
                                        inplace=True,
                                        limit_direction='both')
    
    return elev_ts

# Function to read the C2VSim constrain head BC file
def read_cbc_c2v():
    
    
    
    return cbc_df


#%% Read in folder/files

# Set current directory
#TODO: remove once script standalone
os.chdir(r'C:\Users\nanchor\Documents\GitHub\C2VSimFGv2.0_surface_water\Constrained_Head_BC\Code')

#%% Download/select CDEC reservoirs

# Read reservoir information table from web
cdec_res_url = r'https://cdec.water.ca.gov/reportapp/javareports?name=ResInfo'

cdec_res_info = pd.read_html(cdec_res_url, skiprows=1, header=0)

cdec_res_df = cdec_res_info[0]

cdec_res_df.sort_values(by='ID', inplace=True)

# Read sensor list information table from web
sens_list_url = r'https://cdec.water.ca.gov/misc/senslist.html'

sens_list_df = pd.read_html(sens_list_url)[0]

# Basic filtering of sensor list just for reservoir-related codes
sens_list_df = sens_list_df.loc[sens_list_df['Description'].str.startswith('RESERVOIR')]
sens_list_df.rename(columns={'Description': 'Sensor_Description'},
                    inplace=True)

# Export 
res_out_pth = os.path.join('.', 'cdec_reservoirs.xlsx')
sens_list_out_pth = os.path.join('.', 'sens_list.xlsx')

with pd.ExcelWriter('cdec_reservoirs.xlsx', mode='a', if_sheet_exists='replace') as dfw:
    
    cdec_res_df[cdec_res_df.columns[:-2]].to_excel(dfw, sheet_name='reservoir_list',
                                                   index=False)

    sens_list_df.to_excel(dfw, sheet_name='sensor_list', index=False)

# User needs to open spreadsheet and select the reservoirs they want to download
# Read back in the dataset after user selects reservoirs to download

#Snippet to try and reload the vlookup formulas
wb = openpyxl.load_workbook(filename = 'cdec_reservoirs.xlsx')

# Save exported table
wb.save('cdec_reservoirs.xlsx')


res_to_dl = pd.read_excel('cdec_reservoirs.xlsx', sheet_name='download_selection',
                          skiprows=1)

#%% Check reading
#TODO: refresh excel sheet (open & save) via code. Otherwise, vlookup names will be nan
res_to_dl.head()

#%% Request download data from CDEC

#TODO: add sensor list/types/change depending on the dataset

start_date = '1950-01-01'
end_date = ''
res_mon_dict = {}

for stn in res_to_dl['ID']:
    
    # Capture Woodward and others we want to correlate to CalSim, but aren't in CDEC
    if isinstance(stn, str): 
        
        dur_code = res_to_dl.loc[res_to_dl['ID']==stn, 'Duration_Code'].values[0]
        
        sens_no = res_to_dl.loc[res_to_dl['ID']==stn, 'Sensor_No'].values[0].split(':')[0]
        
        cdec_res_data_url = rf'https://cdec.water.ca.gov/dynamicapp/req/CSVDataServlet?Stations={stn}&SensorNums={sens_no}&dur_code={dur_code}&Start={start_date}&End={end_date}'
        
        # Read data to dataframe
        res_df = pd.read_csv(cdec_res_data_url, low_memory=False)
        
        # Process datetime column
        res_df['Datetime'] = pd.to_datetime(res_df['DATE TIME'], format='%Y%m%d %H%M')
        
        # Replace null values ('---') with nan and convert to float
        res_df.replace({'VALUE': {'---': np.nan}}, inplace=True)
        
        res_df['VALUE'] = res_df['VALUE'].astype(float)
        
        # Assume normal distribution, remove outliers (anything outside 1%-99% quantiles)
        quant_out = res_df['VALUE'].quantile([0.01, 0.99])
        
        res_df = res_df.loc[(res_df['VALUE']<quant_out[0.99]) & \
                            (res_df['VALUE']>quant_out[0.01])]
            
        # QAQC - Plot
        res_df.plot(x='Datetime', y='VALUE')#, ylim=[300.0, 500.0])
        
        # Print min/max datetimes - don't eval non-null data vals though
        print(f'Station: {stn}' + '\n' + \
              f'Min date: {min(res_df["Datetime"])}' + '\n' + \
              f'Max date: {max(res_df["Datetime"])}'
              )
        
        # Aggregate into monthly data
        res_mon_df = res_df.groupby([res_df['Datetime'].dt.year, \
                                     res_df['Datetime'].dt.month]).agg({'VALUE':'mean'}).reset_index(names=['Year', 'Month'])
        
        # Create IWFM date formatting
        res_mon_df['Datetime_EOM'] = pd.to_datetime(arg=(res_mon_df['Year'].astype(str)+ \
                                                    res_mon_df['Month'].astype(str)), format='%Y%m') + \
                                                    pd.tseries.offsets.MonthEnd(0)
        
        res_mon_df['C2VSim_Date'] = res_mon_df['Datetime_EOM'].apply(lambda x: x.strftime('%m/%d/%Y_24:00'))
        
        # Add to be able to flag storage vs. elev
        res_mon_df['Sensor'] = sens_no
        
        # Write to file
        res_df.to_csv(stn+'_'+dur_code+'.csv', index=False)
        res_mon_df.to_csv(stn+'_monthly'+'.csv', index=False)
        res_mon_dict[stn] = res_mon_df
        
    else:
        continue
    # For applicable timeseries, convert monthly storage to reservoir elevations

#%% Read in CalSim3 res_info.table
# Find the applicable reservoirs
# Get their rating tables?
# Interpolate to get approx. reservoir elevations
c3_res_df = read_c3_res(res_to_dl)


for res_id in res_mon_dict:
    
    # Check for storage values vs. elevation
    sens_val = res_mon_dict[res_id]['Sensor'].max()
    
    # Reservoir elevation, FT
    if sens_val == '6':
        continue
    
    # Storage, AF
    elif sens_val == '15':
        c3_stor_elev = c3_res_df.loc[c3_res_df['ID']==res_id,
                                     ['ID', 'storage','elevation']]
        
        c3_stor_elev.rename(columns={'storage': 'VALUE',
                                     'elevation': 'VALUE_ELEV'},
                            inplace=True)
        
        res_mon_dict[res_id].loc[:,'VALUE_ELEV'] = np.nan
        
        res_mon_dict[res_id].loc[:,'VALUE_ELEV'] = stor2elev(res_id, 
                                                       res_mon_dict[res_id],
                                                       c3_stor_elev)

    
#%% Read in current time series BC file and add new data/extend time series


#%% 



#%%

cdec_res_codes = list(cdec_res_df['ID'])
cdec_res_names = list(cdec_res_df['LAKE'].fillna(''))

cdec_res_options = list(cdec_res_df['ID'] + ': ' + cdec_res_df['LAKE'].fillna(''))

# Launch GUI
# Initialize workspace/frames
root = Tk()
root.title('Select Reservoir Data to Download')
mainframe = ttk.Frame(root, padding = '3 3 3 3')
mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

# Set variable
selected_res = StringVar()

# Create Combobox widget
res_dropdown = ttk.Listbox(mainframe, selectmode='multiple', textvariable=selected_res, values=cdec_res_options)

# Place widget in grid
res_dropdown.grid(column=0, row=1, columnspan=2, sticky=(W,E))

# Set default value
res_dropdown.set('Select reservoir(s) to download')

root.mainloop()

# Label widget
wrk_fldr_lbl = ttk.Label(mainframe, text='Select references folder:')
wrk_fldr_lbl.grid(column=0, row=0, columnspan=2, sticky=(W,E))

# Add URL box
url = StringVar()
url_entry = ttk.Entry(mainframe, width=60, textvariable=url)
url_entry.grid(column=0, row=3, columnspan=2, sticky=(W,E))
url_lbl = ttk.Label(mainframe, text='Input SGMA portal GSP URL:')
url_lbl.grid(column=0, row=2, columnspan=2, sticky=(W,E))

# Add buttons
idir = os.path.join('..',
                    '08_GSP_Submittals', 
                    'GSP_Submittals', 
                    '2022_GSP_Submittals')

browsebut = ttk.Button(mainframe, text='Browse', command=lambda: browse_dialog(idir=idir))
browsebut.grid(column=2, row=1, columnspan=2, sticky=W)

confirmbut = ttk.Button(mainframe, text='Confirm', command=root.destroy)
confirmbut.grid(column=1, row=4, sticky=E)

cancelbut = ttk.Button(mainframe, text='Cancel', command=cancel)
cancelbut.grid(column=2, row=4, sticky=(W,E))

# Enter/return key defaults to activating the confirm button
root.bind('<Return>', lambda z: confirmbut.invoke())

for child in mainframe.winfo_children():
    child.grid_configure(padx=5, pady=5)

wrk_fldr_entry.focus()

root.mainloop()


# Once main loop exited, reassign variables for remainder of script
wrk_fldr = wrk_fldr.get()
url = url.get()














