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
import datetime

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

def cur_date():
    
    cur_date = datetime.datetime.now()
    
    cur_date = cur_date.strftime('%Y%m%d')
    
    return cur_date

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
    
    # Read in Constrained head BC specs file
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
    
    with open(cbc_pth, 'r') as f:
        
        lines = f.readlines()
        for i, line in enumerate(lines):
            if 'INODE' in line and \
                'ILAYER' in line and \
                    'BH' in line and \
                        'BC' in line:
                skiprow = i+2 # skip ahead two lines (0-based index)
                break
    
    #TODO: generalize...
    cbc_df = pd.read_csv(cbc_pth, sep='\t+', skiprows=skiprow,
                         header=None, names=cols, keep_default_na=False,
                         na_filter=False)
    
    #TODO: left off here
    # Can't read GH new file, above not flexible enough
    if all(cbc_df[cbc_df.columns[1:]].isna()):
        # cbc_df = pd.read_csv(cbc_pth, sep='\s+', skiprows=skiprow,
        #                      header=None, names=cols, na_filter=False)
        
        for col in cbc_df[cbc_df.columns[1:]]:
            cbc_df[col] = cbc_df[col].fillna('')
        
        cbc_df.loc[:, 'Notes'] = cbc_df['INODE'].apply(lambda x: x.split('/')[1])
        
        cbc_df.loc[:, 'Notes'] = '/' + cbc_df.loc[:, 'Notes']
        
        cbc_df.loc[:, 'INODE'] = cbc_df['INODE'].apply(lambda x: x.split('/')[0].strip())
        
        split_df = cbc_df['INODE'].str.split(r'\s+', expand=True)
        
        split_df.columns = cbc_df.columns[:-1]
        
        cbc_df.loc[:, cbc_df.columns[:-1]] = split_df
        
    return cbc_df

# Function to read the C2VSim constrained head BC file
def read_cbcts_c2v():
    
    # Read in the BC timeseries file
    root = tk.Tk()
    cbcts_pth = filedialog.askopenfilename(title='Select Constrained Head Boundary Condition Timeseries file',
                                           initialdir='..\Resources\C2VSim', filetypes=[('C2VSim dat', '.dat')])
    root.destroy()
    
    with open(cbcts_pth, 'r') as f:
        
        lines = f.readlines()
        for i, line in enumerate(lines):
            if '24:00' in line:
                skiprow = i
                break
    # Used "C" as comment due to section at bottom of file, misses "*" (captured later)
    cbcts_df = pd.read_csv(cbcts_pth, sep='\s+', skiprows=skiprow, comment='C',
                           header=None)
    
    cbcts_df.rename(columns={0: 'ITHTS'},
                    inplace=True)
    
    for col in cbcts_df:
        if col == 'ITHTS':
            continue
        else:
            cbcts_df.rename(columns={col: f'HQTS({col})'},
                            inplace=True)
    
    # Drop extra cols read
    keep_mask = cbcts_df['ITHTS'].str.startswith('*')
    
    cbcts_df = cbcts_df.loc[~keep_mask]
    
    return cbcts_df

# Function to read the groundwater component main input file parameter section
def read_gwmain_params():
    
    # Read in Constrained head BC specs file
    root = tk.Tk()
    gwmain_pth = filedialog.askopenfilename(title='Select GW Main Input File',
                                       initialdir='..\Resources\C2VSim\c2vsimfg_version2.0\Simulation\Groundwater', 
                                       filetypes=[('C2VSim dat', '.dat')])
    root.destroy()
    
    cols = ['ID',
            'PKH',
            'PS',
            'PN',
            'PV',
            'PL']
    
    temp_out_pth = os.path.join('.', 'gwmain.txt')
    
    with open(gwmain_pth, 'r') as f:
        
        lines = f.readlines()
        for i, line in enumerate(lines):
            if 'ID' in line and \
                'PKH' in line and \
                    'PS' in line and \
                        'PN' in line and \
                            'PV' in line and \
                                'PL' in line and \
                                    'PX' not in line:
                skiprow = i+2 # skip ahead two lines (0-based index)
                
            elif 'Anomaly in Hydraulic Conductivity' in line:
                nrow = i-2-skiprow
                skipfooter = len(lines)-nrow-skiprow
                
                with open(temp_out_pth, 'w+') as f_out:
                    
                    j=skiprow
                    while j<=i:
                        split_line = lines[j].split()
                        
                        if lines[j].startswith('C'): # Lazy way of not doing math/hardcoding
                            j+=1
                            continue
                        
                        if len(split_line) == 6:
                            node=split_line[0]
                        else:
                            split_line.insert(0, node)
                        
                        if j == skiprow:
                            f_out.write('\t'.join(cols) + '\n')
                        
                        # Write line to file
                        f_out.write('\t'.join(split_line) + '\n')
                        
                        j+=1
                
                break
    
    gwmain_df = pd.read_csv(temp_out_pth, sep='\t+')
    
    #TODO: generalize/grab layer info from other files
    lyr_num = input('Input number of model layers [4]: ') or '4'
    lyr_num = int(lyr_num)
    gwmain_df['Lyr'] = list(np.arange(1,lyr_num+1)) * int(len(gwmain_df) / lyr_num)
    
    gwmain_df = gwmain_df.convert_dtypes()
    
    return gwmain_df


# # Function to read the stratigraphy file
def read_strat():
    
    # Read in preprocessor stratigraphy file
    root = tk.Tk()
    strat_pth = filedialog.askopenfilename(title='Select Preprocessor Stratigraphy File',
                                       initialdir='..\Resources\C2VSim\c2vsimfg_version2.0\Preprocessor', 
                                       filetypes=[('C2VSim dat', '.dat')])
    root.destroy()
    
    with open(strat_pth, 'r') as f:
        
        lines = f.readlines()
        for i, line in enumerate(lines):
            if '/FACT' in line:
                skiprow = i+1
                break
    # Used "C" as comment due to section at bottom of file, misses "*" (captured later)
    strat_df = pd.read_csv(strat_pth, sep='\s+', skiprows=skiprow, comment='C',
                           header=None)
    
    #TODO: n cols of form aquiclude layer (n/nlyrs?)
    # Of form A1, L1, A2, L2, A3, L3, A(N/2), L(N/2)
    rnm_cols = ['ID',
                'ELV']
    
    lyr_cols = [f'{(int(x) // 2)}' for x in strat_df.columns[2:]]
    
    for i, val in enumerate(lyr_cols):
        
        if i % 2 == 0:
            lyr_cols[i] = 'A' + val
        else:
            lyr_cols[i] = 'L' + val
            
    rnm_cols = rnm_cols + lyr_cols
    
    strat_df.rename(columns=dict(zip(strat_df.columns, rnm_cols)),
                    inplace=True)
    
    return strat_df


# Function to read the preprocessor output file nodal effective areas.
def read_prep_out(params=None):
    '''
    

    Parameters
    ----------
    params : list of string, optional
        List specifying which sections of the preprocessor output file to read. 
        List of options below. The default is None. 
            - xyna = xy coordinates and effective nodal areas
            - elev = each nodes GSE and layer top/bot elevations
        

    Returns
    -------
    prep_dict: dictionary of dataframes

    '''
    
    # Read in preprocessor output file
    root = tk.Tk()
    prep_pth = filedialog.askopenfilename(title='Select Preprocessor Output File',
                                       initialdir='..\Resources\C2VSim\c2vsimfg_version2.0\Preprocessor', 
                                       filetypes=[('C2VSim out', '.out')])
    root.destroy()
    
    #TODO: loop through container and csv read parameters to generalize
    # Initialize container    
    prep_dict=dict(zip(params, [None for x in params]))
    
    with open(prep_pth, 'r') as f:
        
        lines = f.readlines()
        
        for i, line in enumerate(lines):
        
            if 'xyna' in params:
                
                if 'NODE' in line and \
                    'X' in line and \
                        'Y' in line and \
                            'AREA' in line:
                    xy_skiprow = i-1
                    
                #     
                elif 'ELEMENT' in line and \
                    'NODES' in line and \
                        'AREA' in line:
                    xy_nrow = i-4-xy_skiprow
                
                # Set other unique read parameters
                
                
            if 'elev' in params:
                
                if '*** TOP AND BOTTOM' in line:
                    el_skiprow = i+3
                
                elif 'REACH' in line and \
                    'STREAM' in line and \
                        'GRID' in line and \
                            'GROUND' in line and \
                                'INVERT' in line and \
                                    'AQUIFER' in line:
                    el_nrow = i-2-el_skiprow

    
    if 'xyna' in params:
        xyna_df = pd.read_csv(prep_pth, sep='\s+',skiprows=xy_skiprow,
                          nrows=xy_nrow)
    
        prep_dict['xyna'] = xyna_df
                                        
    if 'elev' in params:
        elev_df = pd.read_csv(prep_pth, sep='\s+',skiprows=el_skiprow,
                          header=None, nrows=el_nrow, low_memory=False)
    
        prep_dict['elev'] = elev_df
                
    return prep_dict

def calc_lakebed_conductance(gwmain, strat, narea):
    '''
    
    Function to calculate the conductance for the constrained general head
    boundary condition. For this initial estimation, approximate as
    Kv / b * A [L^2/T], where:
        Kv = vertical hydraulic conductivity
        b = model layer aquifer thickness
        A = nodal effective area

    Parameters
    ----------
    gwmain : pandas dataframe
        Main groundwater input file read previously containing node 
        aquifer properties, including Kv.
    strat : pandas dataframe
        Stratigraphy preprocessor input file.
    narea : pandas dataframe
        Nodal area extracted from preprocessor output file.

    Returns
    -------
    bc_df : pandas dataframe
        Lakebed conductance value, utilized in the CBC input file.

    '''
    
    # PL = aquifer vertical K - ft/day
    kv = gwmain.loc[gwmain['Lyr']==1, ['ID','PL']].copy()
    
    # Layer 1 aquifer thickness - ft
    l1 = strat[['ID', 'L1']].copy()
    
    # Currently, ft/day units in v2.0
    kv_wstrat = kv.merge(right=l1, on='ID')
    
    # Find the merge col
    area_col = [x for x in narea.columns if 'area' in x.lower()][0]
    
    # Convert to common units
    if 'acre' in area_col.lower():
        narea['Area_SF'] = narea[area_col] * 43560
    
    bc_df = kv_wstrat.merge(right=narea[['NODE',
                                         'Area_SF']], 
                            left_on='ID', 
                            right_on='NODE')
    
    # Calculate BC
    bc_df['BC'] = bc_df['PL'] / bc_df['L1'] * bc_df['Area_SF'] # FT^2 / DAY
    
    return bc_df





#%% Set current directory
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


#TODO: make this work
# User needs to open spreadsheet and select the reservoirs they want to download
# Read back in the dataset after user selects reservoirs to download
temp = input('Open cdec_reservoirs.xlsx and select reservoirs to download.' + \
             '\n' + 'Once complete return here and press [Enter]...') or 'n'

#Snippet to try and reload the vlookup formulas (doesn't currently work)
wb = openpyxl.load_workbook(filename = 'cdec_reservoirs.xlsx')

# Save exported table
wb.save('cdec_reservoirs.xlsx')




#%% Check reading
#TODO: refresh excel sheet (open & save) via code. Otherwise, vlookup names will be nan
res_to_dl = pd.read_excel('cdec_reservoirs.xlsx', sheet_name='download_selection',
                          skiprows=1)

res_to_dl.head()

#%% Request download data from CDEC, interpolate missing values, and 
    # convert storage to elevation.

#TODO: add sensor list/types/change depending on the dataset

start_date = '1950-01-01'
end_date = ''
res_mon_dict = {}
c3_res_df = read_c3_res(res_to_dl)

dl_new = input('Download new CDEC data files ([n]/y)? ') or 'n'

for stn in res_to_dl['ID']:
    
    if len(stn) > 3: # Non-CDEC
        continue
    
    dur_code = res_to_dl.loc[res_to_dl['ID']==stn, 'Duration_Code'].values[0]
    
    sens_no = res_to_dl.loc[res_to_dl['ID']==stn, 'Sensor_No'].values[0].split(':')[0]
    
    out_pth = stn+'_'+dur_code+'.csv'
    
    agg_out_pth = stn+'_agg_monthly'+'.csv'
    
    #CDEC reservoirs
    if isinstance(stn, str) and dl_new =='y': # Check for case like woodward, want CalSim3 ID
        
        
        
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
                                  res_mon_df.copy(),
                                  c3_stor_elev.copy())
            
            res_mon_df = res_mon_df.merge(interp_df[['Datetime_EOM',
                                                     'VALUE_ELEV']], 
                                          on='Datetime_EOM')
        
        # Write to file
        res_df.to_csv(out_pth, index=False)
        res_mon_df.to_csv(agg_out_pth, index=False)
        res_mon_dict[stn] = res_mon_df
    
    elif isinstance(stn, str) and dl_new =='n':
        res_mon_df = pd.read_csv(agg_out_pth)
        res_mon_dict[stn] = res_mon_df
    
    # Capture Woodward and others we want to correlate to CalSim, but aren't in CDEC        
    else:
        continue

#%% Read in the current timeseries file
cbcts_df = read_cbcts_c2v()

# Add temporary datetime col for merging
cbcts_df['Datetime'] = pd.to_datetime(cbcts_df['ITHTS'],
                                      format='%m/%d/%Y_24:00')

# The bounds from this file are used later when building the spec file.
# After the spec file is built, we'll return to processing the timeseries


#%% Read in current specs file

# User selects, but at time of script dev, 
cbc_df = read_cbc_c2v()


#QAQC GH uploaded v1.5 cbc file on 4/23. Checking vs. v1.01
cbc_v15_pth = r'C:\Users\nanchor\Documents\GitHub\C2VSimFGv2.0_surface_water\Constrained_Head_BC\C2VSimFG_data\cbc_setup.csv'
cbc_v15_df = pd.read_csv(cbc_v15_pth)

for col in cbc_df:
    
    not_equal_mask = cbc_df[col] != cbc_v15_df[col]
    
    print('v1.01 vals: ' + '\n' + cbc_df.loc[not_equal_mask, col].astype(str))
    print('v1.5 vals: ' + '\n' + cbc_v15_df.loc[not_equal_mask, col].astype(str))

'''
    Results of QA/QC:
        Series([], Name: INODE, dtype: object)
        Series([], Name: INODE, dtype: object)
        Series([], Name: ILAYER, dtype: object)
        Series([], Name: ILAYER, dtype: object)
        Series([], Name: ITSCOL, dtype: object)
        Series([], Name: ITSCOL, dtype: object)
        Series([], Name: BH, dtype: object)
        Series([], Name: BH, dtype: object)
        Series([], Name: BC, dtype: object)
        Series([], Name: BC, dtype: object)
        Series([], Name: LBH, dtype: object)
        Series([], Name: LBH, dtype: object)
        Series([], Name: ITSCOLF, dtype: object)
        Series([], Name: ITSCOLF, dtype: object)
        Series([], Name: CFLOW, dtype: object)
        Series([], Name: CFLOW, dtype: object)
        46       v1.01 vals: \n/Camanche
        47       v1.01 vals: \n/Camanche
        48       v1.01 vals: \n/Camanche
        49       v1.01 vals: \n/Camanche
        50       v1.01 vals: \n/Camanche
                   
        104    v1.01 vals: \n/Thermalito
        105    v1.01 vals: \n/Thermalito
        106    v1.01 vals: \n/Thermalito
        107    v1.01 vals: \n/Thermalito
        108    v1.01 vals: \n/Thermalito
        Name: Notes, Length: 63, dtype: object
        46       v1.5 vals: \n/Camanche  
        47       v1.5 vals: \n/Camanche  
        48       v1.5 vals: \n/Camanche  
        49       v1.5 vals: \n/Camanche  
        50       v1.5 vals: \n/Camanche  
                   
        104    v1.5 vals: \n/Thermalito  
        105    v1.5 vals: \n/Thermalito  
        106    v1.5 vals: \n/Thermalito  
        107    v1.5 vals: \n/Thermalito  
        108    v1.5 vals: \n/Thermalito  
        
    
    Only name changes in notes section; utilization of v1.01 cbc file valid
'''    


#%% Add nodes via geopandas - SKIP IF NOT ADDING NEW LAKES/NODES
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
c2v_lake_int['gnis_name'].fillna('0', inplace=True) # Arc was not recognizing nulls for some reason. Added so Arc could have def query.
c2v_lake_int.to_file(os.path.join('..','GIS', 'output', 'c2v_lake_nodes.shp'))

#%%

# Manually check/modify points
#TODO: consider just adding buffer to spatial join for future iterations
ps = input('Once manually input, press [Enter] to continue...') or 'n'
c2v_lake_nodes = gpd.read_file(os.path.join('..', 'GIS', 'output', 'c2v_cbc_nodes_final.shp'))

#TODO: remove (temporary as computer having shut down issues)
# c2v_lake_nodes.to_csv(os.path.join('.', 'output', 'c2v_cbc_nodes_final.csv'),
#                       index=False)

#%% Process into CBC input file
c2v_lake_nodes = c2v_lake_nodes.loc[c2v_lake_nodes['gnis_name'] !='0', ['NodeID',
                                                                        'gnis_name']]

c2v_lake_nodes.rename(columns={'NodeID': 'INODE'},
                      inplace=True)

c2v_lake_nodes.loc[:, 'Notes'] = '/'+c2v_lake_nodes['gnis_name']

#TODO: replace with cbc_df once we have access to v1.5 files (global)
lakes_to_drop = cbc_df['Notes'].unique()

#TODO: Keep Woodward in the future (currently being implemented via diversions)
lakes_to_drop = np.append(lakes_to_drop, '/Woodward Reservoir')

for lake in lakes_to_drop:

    lakes_mask = c2v_lake_nodes['Notes'].apply(lambda x: x.startswith(lake.strip()))
    
    # Keep everything except lake to drop
    c2v_lake_nodes = c2v_lake_nodes.loc[~lakes_mask]

# Keep original lake nodes intact
cbc_v2_df = c2v_lake_nodes.copy()

cbc_v2_df = cbc_v2_df.merge(right=cdec_res_df[['LAKE', 'ID']],
                            left_on='gnis_name',
                            right_on='LAKE',
                            how='left')

# Find next column to add to time series BC file
# Time series (TS) BC file can be used by other files other than the CBC, so you
# cannot just look at the CBC specs (although that will be considered)

# Check CBC spec ITSCOL and ITSCOLF and number of data cols in TS BC file.
max_col = max((cbc_df['ITSCOL'].astype(int).max(),
               cbc_df['ITSCOLF'].astype(int).max(),
               len([x for x in cbcts_df.columns if x.startswith('HWTS')])))

# New lakes to add to timeseries file
cbc_ids = cbc_v2_df['ID'].unique()

itscol = np.arange(max_col+1, max_col+len(cbc_ids)+1, 1)
itscolf = itscol + len(itscol)

# Create dataframe
ts_df = pd.DataFrame(zip(cbc_ids, itscol, itscolf), columns=['ID', 'ITSCOL','ITSCOLF'])
# Deviate here because it's the same as v1.5
for col in cbc_df.columns:
    
    if col in c2v_lake_nodes.columns:
        continue
    
    elif col == 'ILAYER':
        cbc_v2_df[col] = '1'
    
    elif col == 'BH':
        cbc_v2_df[col] = '0'
    
    elif col == 'CFLOW':
        cbc_v2_df[col] = '0'
    
    elif col == 'ITSCOL':
        cbc_v2_df = cbc_v2_df.merge(right=ts_df, on='ID')
    
    elif col == 'ITSCOLF':
        continue # Already merged alongside ITSCOL
    
    # Elevation when storage == 0?
    elif col == 'LBH':
        c3_res_nostor = c3_res_df.loc[c3_res_df['storage']==0, ['ID', 'elevation']]
        cbc_v2_df = cbc_v2_df.merge(right=c3_res_nostor, on='ID')
        cbc_v2_df.rename(columns={'elevation': col}, inplace=True)
        
    # Lakebed conductance
    elif col == 'BC':
        # As a first approx, get Kv for layer one from the gw input file (gw main), 
        # divide by layer thickness (strat), and multiply by nodal effective area (preprocessor out).
        # Once done, check local models/GSPs/other sources for more refined estimates.
        gwmain_df = read_gwmain_params()
        
        strat_df = read_strat()
        
        nodal_area_df = read_prep_out(['xyna'])['xyna']
        
        # Now, calculate the conductance
        bc_df = calc_lakebed_conductance(gwmain_df,
                                         strat_df,
                                         nodal_area_df)
        
        cbc_v2_df = cbc_v2_df.merge(right=bc_df[['NODE', 'BC']],
                                    left_on='INODE',
                                    right_on='NODE',
                                    how='left')
        
        

# Sort
cbc_v2_df.sort_values(by=['INODE'], inplace=True)

cbc_df = cbc_df.convert_dtypes()
cbc_v2_df = cbc_v2_df.convert_dtypes()

# Prep for concat
# cbc_v2_df.rename(columns={'gnis_name': 'Notes'}, inplace=True)
# cbc_v2_df['Notes'] = '/' + cbc_v2_df['Notes']

# Continue building spec output
cbc_final_df = pd.concat([cbc_df,
                          cbc_v2_df[[x for x in cbc_v2_df.columns if x.lower() not in ['id',
                                                                           'lake',
                                                                           'node',
                                                                           'gnis_name']]]])


#%% Finish building timeseries now that we know where to put the data

# Make a quick key
ts_key = cbc_final_df[['ITSCOL',
                       'ITSCOLF',
                       'Notes']].drop_duplicates()

#TODO: replace with fuzzy matching or some more generalized process
ts_key.loc[ts_key['Notes']=='/Camanche', 'GNIS_Name'] = 'Camanche Reservoir'
ts_key.loc[ts_key['Notes']=='/Thermalito', 'GNIS_Name'] = 'Thermalito Afterbay'

ts_key.loc[ts_key['GNIS_Name'].isna(), 'GNIS_Name'] = ts_key.loc[ts_key['GNIS_Name'].isna(), 'Notes'].apply(lambda x: x.split('/')[1])

ts_key = ts_key.merge(right=res_to_dl[['Name',
                                       'ID']],
                      left_on='GNIS_Name',
                      right_on='Name',
                      how='left')

# Now, add/insert timeseries as appropriate
print('Note, that this process is not the most exhaustive for the existing datasets')
print('Additional data may have been found via storage conversions; however, ')
print(' it was deemed unnecessary due to the existing datasets.')


cbcts_new_df = pd.DataFrame()

for i,row in enumerate(ts_key.itertuples()):
    
    cdec_id = row.ID
    
    # Assign ITSCOL
    rnm_col = 'VALUE'
    if 'VALUE_ELEV' in res_mon_dict[cdec_id].columns:
        rnm_col = 'VALUE_ELEV'
        
    
    new_ts = res_mon_dict[cdec_id][['Datetime_EOM', rnm_col]].copy()
    new_ts.rename(columns={'Datetime_EOM': 'Datetime',
                           rnm_col: f'HQTS({str(row.ITSCOL)})'},
                  inplace=True)
    
    # Add in ITSCOLF
    new_ts[f'HQTS({str(row.ITSCOLF)})'] = '9999'
    
    if i == 0:
        # Initialize the datetime column        
        cbcts_new_df = new_ts.copy()
        
    else:
        
        cbcts_new_df = cbcts_new_df.merge(right=new_ts,
                                          on='Datetime',
                                          how='outer')
        

#TODO: Consolidate loops and make more efficient
for i,row in enumerate(ts_key.itertuples()):
    
    cbcts_new_df[f'HQTS({str(row.ITSCOL)})'].fillna('9999',
                                                      inplace=True)
    
    cbcts_new_df[f'HQTS({str(row.ITSCOLF)})'].fillna('0',
                                                       inplace=True)
    
# Time bounds
tmin = cbcts_df['Datetime'].min()
tmax = cbcts_df['Datetime'].max()

#TODO: need to fix this, full TS for new ones and only new TS for existing

merge_cols = ['Datetime'] + [x for x in cbcts_new_df.columns if x not in cbcts_df.columns]

cbcts_final_df = cbcts_df.merge(right=cbcts_new_df[merge_cols],
                                on='Datetime',
                                how='right')

cbcts_final_df.set_index('Datetime',
                         inplace=True)

cbcts_new_df.set_index('Datetime',
                       inplace=True)

# Set of columns to replace nan values (after previous simulation end)
fill_cols = [x for x in cbcts_df.columns if x.startswith('HQTS')]

for fcol in fill_cols:
    cbcts_final_df.fillna({fcol: cbcts_new_df[fcol]},
                          inplace=True) 

#TODO: change to programmatically
# Trim to last complete month
cbcts_final_df = cbcts_final_df.loc[tmin:'2025-03-31']

# Regen C2VSim time column
cbcts_final_df = cbcts_final_df.fillna({'ITHTS': pd.DataFrame(index=cbcts_final_df.index,
                                             columns=['datef']).apply(lambda x: x.index.strftime('%m/%d/%Y_24:00'))['datef']})

# Export/write to file

# No need to reorder columns, concat to the original dataset
cbc_final_df.to_csv(os.path.join('.', 'output', f'cbc_specs_{cur_date()}.csv'),
                    index=False)


#Reorder columns
col_ord = [cbcts_final_df.columns[0]]+ \
    [f'HQTS({x})' for x in np.arange(1, len(cbcts_final_df.columns))]

cbcts_final_df[col_ord].to_csv(os.path.join('.', 'output', f'cbc_timeseries_{cur_date()}.csv'),
                               index=False)

















