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
    # stor_df = res_mon_dict[res_id].copy()
    
    stor_df['VALUE_ELEV'] = np.nan
    
    res_df = c3_df.loc[c3_df['ID']==res_id,
                        ['ID','VALUE', 'VALUE_ELEV']]
    
    concat_df = pd.concat([stor_df[['Datetime_EOM',
                                    'VALUE',
                                    'VALUE_ELEV']], 
                           res_df[['VALUE',
                                  'VALUE_ELEV']]],
                          axis=0)
    
    concat_df.set_index('VALUE', inplace=True)
    
    concat_df.sort_values(by='VALUE', inplace=True)
    
    concat_df['VALUE_ELEV'] = concat_df['VALUE_ELEV'].interpolate(method='slinear',
                                        limit_direction='both')
    
    concat_df.reset_index(inplace=True)
    
    concat_df = concat_df.dropna(subset='Datetime_EOM')
    
    concat_df.sort_values(by='Datetime_EOM', inplace=True)
    
    return concat_df

# Function to build full model timeseries
def build_ts(ts, tunit):
    '''
    
    Parameters
    ----------
    ts : series
        Time series to analyze and fill any missing data
    
    tunit : string
        Enter stress period time unit.
            ME = month end
            D = daily
            
            See list of offset aliases here: https://pandas.pydata.org/docs/user_guide/timeseries.html#timeseries-offset-aliases
            ...

    Returns
    -------
    fullts : series
        Full time series with missing days/months/etc. filled in
        
    '''
    
    # Find the bounds
    tmin = ts.min()
    
    tmax = ts.max()
    
    # Generate time spans
    fullts = pd.date_range(start=tmin, end=tmax,freq=tunit)
    
    
    return fullts

# Function to read the C2VSim constrained head BC file
def read_cbc_c2v():
    
    # Read in CalSim3 reservoir info table
    root = tk.Tk()
    cbc_pth = filedialog.askopenfilename(title='Select Constrained Head Boundary Condition Specs file',
                                       initialdir='..\Resources\C2VSim', filetypes=[('C2VSim dat', '.dat')])
    root.destroy()
    
    cols = ['INODE',	
            'ILAYER',
            'ITSCOL',
            'BH',
            'BC',
            'LBH',
            'ITSCOLF',
            'CFLOW',
            'Notes']
    
    
    cbc_df = pd.read_csv(cbc_pth, sep='\t+', skiprows=119, names=cols)
    
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

#%% Request download data from CDEC, interpolate missing values, and 
    # convert storage to elevation.

#TODO: add sensor list/types/change depending on the dataset

start_date = '1950-01-01'
end_date = ''
res_mon_dict = {}
c3_res_df = read_c3_res(res_to_dl)

for stn in res_to_dl['ID']:
    
    #CDEC reservoirs
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
        
        # Add full time series (may be missing values in record)
        ts = pd.Series(build_ts(res_mon_df['Datetime_EOM'], 'ME'))
        ts.name='Datetime_EOM'
        
        # Merge into current 
        res_mon_df = res_mon_df.merge(right=ts,
                                      on = 'Datetime_EOM',
                                      how = 'right')
        
        # Interpolate the missing values - assume equally-spaced linear
        res_mon_df['VALUE'] = res_mon_df['VALUE'].interpolate(method='linear')
        
        
        res_mon_df['C2VSim_Date'] = res_mon_df['Datetime_EOM'].apply(lambda x: x.strftime('%m/%d/%Y_24:00'))
        
        # Add to be able to flag storage vs. elev
        res_mon_df['Sensor'] = sens_no
        
        # Storage, AF
        if sens_no == '15':
            c3_stor_elev = c3_res_df.loc[c3_res_df['ID']==stn,
                                         ['ID', 'storage','elevation']]
            
            c3_stor_elev.rename(columns={'storage': 'VALUE',
                                         'elevation': 'VALUE_ELEV'},
                                inplace=True)
            
            interp_df = stor2elev(stn, 
                                  res_mon_df,
                                  c3_stor_elev)
            
            res_mon_df = res_mon_df.merge(interp_df[['Datetime_EOM',
                                                     'VALUE_ELEV']], 
                                          on='Datetime_EOM')
        
        # Write to file
        res_df.to_csv(stn+'_'+dur_code+'.csv', index=False)
        res_mon_df.to_csv(stn+'_agg_monthly'+'.csv', index=False)
        res_mon_dict[stn] = res_mon_df
    
    # Capture Woodward and others we want to correlate to CalSim, but aren't in CDEC        
    else:
        continue

#%% Read in the current timeseries file, add new records, and columns


#%% Read in current specs file
cbc_df = read_cbc_c2v()

#%% Add nodes via geopandas
# Start off not changing original specs. 

import os
import sys

os.environ['GDAL_DATA'] = os.path.join(f'{os.sep}'.join(sys.executable.split(os.sep)[:-1]), 'Library', 'share', 'gdal')

c2v_nodes_gdf = gpd.read_file(r'C:\Users\nanchor\Documents\C2VSim\C2VSim\c2vsimfg-v1_0_gis\C2VSimFG-V1_0_GIS\Shapefiles\C2VSimFG_Nodes.shp')
nhd_lakes_gdf = gpd.read_file(r'C:\SGMBranch\29_C2VSim\C2VSim_Lakes\GIS\C2VSimFG_Lakes\C2VSimFG_Lakes.gdb',
                              layer='NHD_C2VSimFG_LakesReservoirs',
                              driver='OpenFileGDB') # has a warning: 198: RuntimeWarning: driver OpenFileGDB does not support open option DRIVER return ogr_read(

# Intersect/overlay lakes with C2VSimFG gw nodes
c2v_lake_int = gpd.sjoin(c2v_nodes_gdf, nhd_lakes_gdf.to_crs(epsg=26910),
                         how='left')

# Write to shapefile for manual iteration
c2v_lake_int['gnis_name'].fillna('0', inplace=True)
c2v_lake_int.to_file(os.path.join('.', 'output', 'c2v_lake_nodes.shp'))

#TODO: LEFT OFF HERE!
# Manually check/modify points
ps = input('Once manually input, press [Enter] to continue...') or 'n'
c2v_lake_nodes = gpd.read_file(os.path.join('.', 'output', 'c2v_lake_nodes.shp'))


#%% 







































