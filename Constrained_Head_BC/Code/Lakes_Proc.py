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
#from tkinter import *
from tkinter import ttk
from tkinter import filedialog
import matplotlib

# Excel libraries
import openpyxl

#%% Helper Functions





#%% Read in folder/files

# Set current directory
#TODO: remove once script standalone
os.chdir(r'C:\SGMBranch\29_C2VSim\C2VSim_Lakes\Code')

#%% Download/select CDEC reservoirs

# Read reservoir information table from web
cdec_res_url = r'https://cdec.water.ca.gov/reportapp/javareports?name=ResInfo'

cdec_res_info = pd.read_html(cdec_res_url, skiprows=1, header=0)

cdec_res_df = cdec_res_info[0]

cdec_res_df.sort_values(by='ID', inplace=True)

# Export 
res_out_pth = os.path.join('.', 'cdec_reservoirs.xlsx')

with pd.ExcelWriter('cdec_reservoirs.xlsx', mode='a', if_sheet_exists='replace') as dfw:
    
    cdec_res_df[cdec_res_df.columns[:-2]].to_excel(dfw, sheet_name='reservoir_list',
                                                   index=False)

# User needs to open spreadsheet and select the reservoirs they want to download
# Read back in the dataset after user selects reservoirs to download
res_to_dl = pd.read_excel('cdec_reservoirs.xlsx', sheet_name='download_selection',
                          skiprows=1)

#%% Check reading
#TODO: refresh excel sheet (open & save) via code. Otherwise, name will be nan
res_to_dl.head()

#%% Request download data from CDEC

#TODO: add sensor list/types/change depending on the dataset

start_date = '1950-01-01'
end_date = ''
sens_nos_df = pd.read_excel('cdec_reservoirs.xlsx', sheet_name='sensor_list',
                            skiprows=1)
dur_code = 'D'

for stn in res_to_dl['ID']:
    
    sens_no = str(sens_nos_df.loc[sens_nos_df['ID']==stn, 'Sensor_No'].values[0])
    
    cdec_res_data_url = rf'https://cdec.water.ca.gov/dynamicapp/req/CSVDataServlet?Stations={stn}&SensorNums={sens_no}&dur_code={dur_code}&Start={start_date}&End={end_date}'
    
    # Read data to dataframe
    res_df = pd.read_csv(cdec_res_data_url, low_memory=False)
    
    # Process datetime column
    res_df['Datetime'] = pd.to_datetime(res_df['DATE TIME'], format='%Y%m%d %H%M')
    
    # Replace null values ('---') with nan and convert to float
    res_df.replace({'VALUE': {'---': np.nan}}, inplace=True)
    
    res_df['VALUE'] = res_df['VALUE'].astype(float)
    
    # QAQC - Plot
    res_df.plot(x='Datetime', y='VALUE')#, ylim=[300.0, 500.0])
    
    # Remove outliers (anything outside 95% CI)
    
    
    # Print min/max datetimes - don't eval non-null data vals though
    print(f'Station: {stn}' + '\n' + \
          f'Min date: {min(res_df["Datetime"])}' + '\n' + \
          f'Max date: {max(res_df["Datetime"])}'
          )
    
    # Write to file
    res_df.to_csv(stn+'.csv', index=False)
    
    # Process monthly data
    res_mon_df = res_df.groupby([res_df['Datetime'].dt.year, \
                                 res_df['Datetime'].dt.month]).agg({'VALUE':'mean'})
    
 #%% Process downloaded CSVs into monthly avg datasets
 for stn in res


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


















































#%% Reference code

#%% Import necessary libraries

# General libraries
import os
import pandas as pd
import re
import time

# HTTP/URL library imports
import requests
import urllib
import shutil
import ssl
from bs4 import BeautifulSoup
# Note, this library installed last via PIP (not conda) in environment
import pyrfc6266
import http

# Chrome browser control libraries
from selenium.common.exceptions import WebDriverException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

# Image/screenshot library
from PIL import ImageGrab
from PIL import Image

# GUI libraries
from tkinter import *
from tkinter import ttk
from tkinter import filedialog

# Excel libraries
import openpyxl
from openpyxl.styles import borders, Font, Color, PatternFill
from openpyxl.styles.differential import DifferentialStyle
from openpyxl.formatting.rule import Rule


#%% Helper functions

# Build excel-clickable hyperlinks
def build_excel_link(name_col, url_col):
    
    lnk_str = f'=HYPERLINK("{url_col}", "{name_col}")'
    
    return lnk_str

def build_links(link_tup):
    '''
    
    The purpose of this function is to build a full hyperlink to the resource,
    as the SGMA portal download links seem relative to the original page location.
    
    Then, this function calls another function to format all of the links for excel.
    
    Parameters
    ----------
    link_tup: tuple of strings. (link name, URL)
        link string. either full path or relative SGMA portal path.
        
    Returns
    -------
    link_new: string
        New link that removes relative reference (adds full https)
        
    '''
    
    # Links generally of the relative format ('/portal/service/gspdocument/download/7475')
    # or full path ('https://www.sierravalleygmd.org/files/cc4b3186e/Beckwourth+Cap+M-Pavement+Cracking-Assessment+and+Mitigation+Recommendations.pdf')
    # or full path without extension ('https://www.sierravalleygmd.org/files/cc4b3186e') Not valid link
    
    link_name = link_tup[0]
    link_url = link_tup[1]
    
    # Add full link path
    if link_tup[1].split('/')[1].lower() == 'portal':
        link_new = f'https://sgma.water.ca.gov{link_tup[1]}' # slash already present
    else:
        link_new = link_tup[1]
    
    return link_new

# Extracts the filename from the 'Content-Disposition' header when the 
# pyrfc6266 library fails
def get_filename(s):
    s_fmt = re.findall("filename\*?=([^;]+)", s, flags=re.IGNORECASE)
    
    s_fmt = s_fmt[0].strip().strip('"')
    
    return s_fmt

# Purpose of this function is to format the title into a filepath-friendly form
def fmt_title(title):
    
    # Should work even if '.' in file name
    #title, ext = os.path.splitext(title)
    
    # Reformat the title to replace non-alphanumeric with underscores
    # Has duplicate underscores when consecutive spaces or special chars
    title_fname = ''.join(x if x.isalnum() else '_' for x in title)
    
    # Remove duplicate underscore characters
    origname_flag = True
    title_fname_nodupes = title_fname
    
    for i, ltr in enumerate(title_fname):
        
        # Index shifter for changing new string
        shifter = len(title_fname) - len(title_fname_nodupes)
        
        if i ==0:
            continue
        elif ltr == '_' and ltr == title_fname[i-1]:
            origname_flag = False
            title_fname_nodupes = title_fname_nodupes[:(i-shifter)] + title_fname_nodupes[((i-shifter)+1):]
    
    if origname_flag:
        print('*** File name reset to original ***')
        title_fname_nodupes = title_fname
    
    # Trim for Windows OS max path file lengths
    if len(title_fname_nodupes)>100:
        title_fname_nodupes = title_fname_nodupes[:99] # max should really be (260 [max]-143 [longest gsp path]-15 [screenshot.png])
    
    # Strip trailing underscores
    title_fname_nodupes = title_fname_nodupes.rstrip('_')
    title_fname_nodupes = title_fname_nodupes.rstrip('.')
    
    return title_fname_nodupes

# Purpose of this function is to take a screenshot of webpage-only URLs
def scrnsht(title, dl_url):
    
    dl_msg = None
    notes = None
    fname = None
    
    # Format paths and check for file existence
    title_fname = fmt_title(title)
    
    fname = title_fname+'_screenshot.png'
    
    # Path to save image file
    img_pth = os.path.join(wrk_fldr, fname)
    
    if os.path.exists(img_pth):
        print('Screenshot already exists, skipping...')
        dl_msg = 'screenshot'
        return [dl_msg, notes, fname]
    
    else:
        
        # Current working directory should change to wherever the script is
        # saved.
        
        # Generate paths to saved folder/file for chrome driver location
        save_fldr = os.path.join('.', 'Ref_Download')
        save_fpth = os.path.join(save_fldr, 'saved_paths.csv')
        
        # Create subdirectories if they do not exist
        os.makedirs(save_fldr, exist_ok=True)
        
        if os.path.exists(save_fpth):
            df_cmdrv = pd.read_csv(save_fpth)
            cmdrv_pth = df_cmdrv['chrome_path'].values[0]
            
        # Request user provide path and then write a csv with that information
        else:
            # Start chrome driver to navigate webpage and then screenshot
            root = Tk()
            
            cmdrv_pth = filedialog.askopenfilename(title='Select Chrome Driver exe file',
                                                   initialdir = '.')
            
            root.destroy()
            
            df_cmdrv = pd.DataFrame([cmdrv_pth],
                                    columns=['chrome_path'])
            df_cmdrv.to_csv(save_fpth, index=False)
            
            
        
        # Alternate hard-coded implementation
        # cmdrv_pth = r'C:\Users\nanchor\Documents\Software\chromedriver.exe'
        
        ser = Service(cmdrv_pth)
        driver = webdriver.Chrome(service = ser)
        driver.maximize_window()
        
        # Added to account for certificate errors, which I don't seem to be able 
        # to currently isolate and don't want to bypass
        try:
            driver.get(dl_url)
        except WebDriverException:
            dl_msg = 'problem'
            notes = f'Certificate issue, check manually: {dl_url}'
            print(notes)
            
        time.sleep(8)
        
        # Note, this is an alternative method to grab the screenshot; however,
        # it does not grab the URL/address bar at the top.
        #screenshot = driver.save_screenshot(os.path.join(wrk_fldr, title+'_screenshot.png'))
        
        # This method grabs the full page, including task bar (and will cause issues
        # if the computer is locked)
        screenshot = ImageGrab.grab()
    
        try:
            screenshot.save(os.path.join(wrk_fldr, fname))
        
        except FileNotFoundError:
            print('File name still too long, change script.')
            
            fname = title_fname[:29]+'_screenshot.png'
            
            screenshot.save(os.path.join(wrk_fldr, fname)) # A bit arbitrary, may still throw error.
            
        driver.quit()
        
    return [dl_msg, notes, fname]

#TODO: finish/fix updated script implementation.
# Function to extract the embedded PDF(s) from a page
# def scrape_pdf(dl_url, n=None):
    
#     # Default to extracting 1/first PDF link
#     if n is None:
#         n=1
    
#     html_page = urllib.request.urlopen(dl_url)
#     soup = BeautifulSoup(html_page)
    
#     url_list = []
    
#     for link in soup.findAll('a'):
        
#         href = link.get('href')
        
#         #print(href)
#         try:
#             if 'pdf' in href and link not in url_list:
#                 url_list.append(href)
#         except Exception as e:
#             print(f'The following exception occurred: {e}')
#             new_dl_url = dl_url
    
#     if len(url_list) > 0:
#         new_dl_url = url_list[n-1]
#     else:
#         # Send back the original for screenshotting
#         new_dl_url = dl_url
    
#     return new_dl_url

#TODO: delete if not needed, partially cleaned version fot eh full function
def request_download(res_nm, dl_url):
    
    # Initialize notes and content_name variables
    notes, content_name = None, None, None
    
    # Successful request list
    ok_status = [301, 302, 303, 307, 308, 200]
    
    try: 
        r = urllib.request.urlopen(dl_url, timeout=10)
        
    except (urllib.error.HTTPError, TimeoutError, http.client.RemoteDisconnected):
        
        # Build a header with a user agent to see if that fixes the problem
        try:
            # Mimics browser header, some pages more advanced and will still block.
            get_hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'}
            req = urllib.request.Request(dl_url, headers=get_hdr)
            r = urllib.request.urlopen(req, timeout=10)
            
        except (urllib.error.HTTPError, TimeoutError):
            
            try: 
                #TODO: replace with current. Seems depricated.
                scontext = ssl.SSLContext(ssl.PROTOCOL_TLS)
                scontext.verify_mode = ssl.VerifyMode.CERT_NONE
                
                r = urllib.request.urlopen(dl_url, context=scontext, timeout=10)
            
            except Exception as e:
                notes = 'URL request could not be made; review manually: {}'.format(dl_url)
                print(notes)
                print(f'The following exception occurred while processing: {e}')
                
                return [notes, content_name]
    
    # Seems to be DNS/firewall related and won't be able to bypass w/o IT help
    # Note, some invalid URLs throwing InvalidURL error from the client.py...unsure how to handle yet.
    except (urllib.error.URLError, Exception):
        notes = 'URL request could not be made; review manually: {}'.format(dl_url)
        print(notes)
        
        return [notes, content_name]
    
    # Assemble header info into useful container
    header = dict(r.info())
    
    # Check if request is valid (including redirects, but this may be an issue)
    if r.status not in ok_status:
        
        #TODO: add context here for broken links
        notes = 'URL response code {}'.format(r.status)
        
        return [notes, content_name]
    
        
    # Try to download file
    else:
        
        # Check for file existence and skip if exists
        out_fpath = os.path.join(wrk_fldr, content_name)
            
        if os.path.exists(out_fpath):
            print('File {} already exists, skipping...'.format(content_name))
            
            return [notes, content_name]
        
        else:
            
            print(f'Saving file {content_name}...')
            
            # Write file
            with open(out_fpath, 'wb') as out_f:
                
                try:
                    shutil.copyfileobj(r, out_f)
                    
                # Retry the download (not sure if I need to do any file management here)
                except http.client.IncompleteRead:
                    shutil.copyfileobj(r, out_f)
            
            dl_msg = 'downloaded'
            
    return [dl_msg, notes, content_name]

def request_download(title, dl_url):
    
    # Initialize download message and notes variables
    dl_msg, notes, content_name = None, None, None
    
    # Successful request list
    ok_status = [301, 302, 303, 307, 308, 200]
    
    try: 
        r = urllib.request.urlopen(dl_url, timeout=10)
        
    except (urllib.error.HTTPError, TimeoutError, http.client.RemoteDisconnected):
        
        # Build a header with a user agent to see if that fixes the problem
        try:
            # Mimics browser header, some pages more advanced and will still block.
            get_hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'}
            req = urllib.request.Request(dl_url, headers=get_hdr)
            r = urllib.request.urlopen(req, timeout=10)
            
        except (urllib.error.HTTPError, TimeoutError):
            
            try: 
                #TODO: replace with current. Seems depricated.
                scontext = ssl.SSLContext(ssl.PROTOCOL_TLS)
                scontext.verify_mode = ssl.VerifyMode.CERT_NONE
                
                r = urllib.request.urlopen(dl_url, context=scontext, timeout=10)
            
            except Exception as e:
                notes = 'URL request could not be made; review manually: {}'.format(dl_url)
                print(notes)
                print(f'The following exception occurred while processing: {e}')
                
                dl_msg = 'problem'
                
                # Grab screenshot anyways
                print('Calling screenshot function...')
                dl_msg_unused, notes_unused, content_name_unused = scrnsht(title, dl_url)
                
                return [dl_msg, notes, content_name]
    
    # Seems to be DNS/firewall related and won't be able to bypass w/o IT help
    # Note, some invalid URLs throwing InvalidURL error from the client.py...unsure how to handle yet.
    except (urllib.error.URLError, Exception):
        notes = 'URL request could not be made; review manually: {}'.format(dl_url)
        print(notes)
        dl_msg = 'problem'
        
        # Grab screenshot anyways
        print('Calling screenshot function...')
        dl_msg_unused, notes_unused, content_name_unused = scrnsht(title, dl_url)
        
        return [dl_msg, notes, content_name]
    
    # Assemble header info into useful container
    header = dict(r.info())
    
    # Extract MIME content type (e.g., application/pdf, text/html, application/octet-stream, etc.)
    try:
        content_type = header['Content-Type']
    except KeyError:
        content_type = header['content-type']
    
    # Check if request is valid (including redirects, but this may be an issue)
    if r.status not in ok_status:
        
        dl_msg = 'broken link'
        
        #TODO: add context here for broken links
        notes = 'URL response code {}'.format(r.status)
        
        # Grab screenshot anyways
        print('Calling screenshot function...')
        dl_msg_unused, notes_unused, content_name_unused = scrnsht(title, dl_url)
        
        return [dl_msg, notes, content_name]
    
    #TODO: add sub function to try and extract all PDFs on given page (or n
    # PDFS on a given page)
    elif 'text' in content_type:
        
        print('Content type {}'.format(content_type))
        
        # print(f'Attempting to extract {n_file} PDFs on webpage')
        
        print('Calling screenshot function...')
        
        dl_msg, notes, content_name = scrnsht(title, dl_url)
        
        if dl_msg is None:
            dl_msg = 'screenshot'
        
    # Try to download file
        #application/octet-stream
        #'text/html; charset=ISO-8859-1'
        # application/pdf
        # etc.
    else:
        
        # Extract file name
        try:
            
            # Extract file name from content-disposition response. 
            # Seems to fail with certain whitespace chars
            content_name = pyrfc6266.requests_response_to_filename(r)
            
            # Remove any URL formatting, including "+" chars
            content_name = urllib.parse.unquote_plus(content_name)
            
        
        # Not the best documentation 
        except pyrfc6266.ParseException:
            
            try:
                content_name = get_filename(header['Content-Disposition'])
                
            except Exception as unk_e:
                
                print('get_filename() function has error: {}'.format(unk_e))
                
        except KeyError:
            
            print('Keyerror raised, check url that is being parsed by pyrfc6266')
        
        # Check for special case of download duplicates, prevalent amongst
        # USGS report filenames. Trim if long file name that will cause OS issues.
        if content_name.lower() == 'report.pdf': 
            content_name=fmt_title(title) + '.pdf'
            
        
        # Check for file existence and skip if exists
        out_fpath = os.path.join(wrk_fldr, content_name)
        
        # Purposely not enabling longer pathnames (seems possible, limit via
        # MSDOS). Not the best coding processing here...
        if len(out_fpath) >= 260:
            
            head, tail = os.path.splitext(out_fpath)
            len_diff = len(out_fpath)-259
            
            # Presumes we won't ever cut into folder paths...which may not be true
            content_name = content_name[:(len(content_name)-len_diff-len(tail))] + tail
            out_fpath = os.path.join(wrk_fldr, content_name)
            
        if os.path.exists(out_fpath):
            print('File {} already exists, skipping...'.format(content_name))
            dl_msg = 'downloaded'
            return [dl_msg, notes, content_name]
        
        else:
            
            print(f'Saving file {content_name}...')
            
            # Write file
            with open(out_fpath, 'wb') as out_f:
                
                try:
                    shutil.copyfileobj(r, out_f)
                    
                # Retry the download (not sure if I need to do any file management here)
                except http.client.IncompleteRead:
                    shutil.copyfileobj(r, out_f)
            
            dl_msg = 'downloaded'
            
    return [dl_msg, notes, content_name]

# GUI-specific functions
def browse_dialog(*args, idir):
    
    try:
        wrk_fldr.set(filedialog.askdirectory(initialdir= idir))
        
    except Exception as e:
        print(f'The following Exception occurred: {e}')
        pass
    
def cancel(*args):
    
    try:
        root.destroy()
        raise SystemExit
    except Exception as e:
        print(f'The following Exception occurred: {e}')
        pass
    
#%% Read in the GSPs for GUI list provision
#TODO: read in all submitted GSPs from the webpage and present user a list
# of choice options. Table includes URLs, so that would be perfect.
#gsp_all = pd.read_html('http://sgma.water.ca.gov/portal/gsp/all')

# root = Tk()
# gsp_fpath = filedialog.askopenfilename(title='Select GSP Submittal list')

# root.destroy()

# gsp_submits = pd.read_csv(gsp_fpath)

# # Now, need to consolidate
# gsp_submits['GSP_Name'] = gsp_submits['GSP Local ID'].fillna(gsp_submits['Basin'].apply(lambda x: x.split(' ', maxsplit=1)[1])).copy()

#%% Load references folder for GSP and URL path to references

#TODO: make this dynamic with full GSP list. Add GUI prompts.
# Initialize workspace/frames
root = Tk()
root.title('Select Folder/URL')
mainframe = ttk.Frame(root, padding = '3 3 12 12')
mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

# Set variable
wrk_fldr = StringVar()

# Create widget
wrk_fldr_entry = ttk.Entry(mainframe, width=200, textvariable=wrk_fldr)

# Place widget in grid
wrk_fldr_entry.grid(column=0, row=1, columnspan=2, sticky=(W,E))

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


#TODO: remove, once GUI working fully.
# Old method of inputting working folder and URL
#wrk_fldr = r'C:\SGMBranch\1_7_1_GSP_Assessment_Eval\08_GSP_Submittals\GSP_Submittals\2022_GSP_Submittals\5-022.02_Modesto\References_Test'

# URL link to the applicable GSP page on SGMA Portal
# 's' removed from https
#url = 'https://sgma.water.ca.gov/portal/gsp/preview/85'

#%% Read HTML table, iterate links, submit URL request, download data or screenshot,
# then roll up into table and format.

df_notags = pd.read_html(url)[1] # filtered 3-item list to just applicable table

df_alltags = pd.read_html(url, extract_links='all')[1] # filtered 3-item list to just applicable table

df_alltags.columns = df_notags.columns

# Combine for clean dataframe with hrefs
df = df_notags.merge(right=df_alltags['File Name or URL'],
                     left_index=True,
                     right_index=True)

# Add full URL paths to relative SGMA portal paths
df['URL'] = df['File Name or URL_y'].apply(lambda x: build_links(x))

# Clean up table
df.rename(columns={'File Name or URL_x': 'Link_Text'},
          inplace=True)
df.drop(columns=['File Name or URL_y'],
        axis=1,
        inplace=True)

# Add excel-clickable hyperlinks
df['File Name or URL'] = df.apply(lambda x: build_excel_link(x['Link_Text'], x['URL']),
                                  axis=1)

# Iterate links and request download. Create download message and notes lists.
dl_msg_list = []
notes_list = []
fname_list = []
for i, row in df.iterrows():
    
    title = row['Title']
    dl_url = row['URL']
    
    dl_msg, notes, fname = request_download(title, dl_url)
    
    dl_msg_list.append(dl_msg)
    notes_list.append(notes)
    fname_list.append(fname)
    
#%% Run from here to export current state
# Zip messages to dataframe
df_msgs = pd.DataFrame(zip(dl_msg_list, notes_list, fname_list), columns=['Downloaded', 'Notes', 'Saved Filename'])

# Append to reference table dataframe
df = df.merge(right=df_msgs,
              left_index = True,
              right_index = True)


# Export reference table to excel
for col in df.columns:
    df.rename(columns={col:col.upper()},
              inplace=True)

# Export column order
exp_col = ['TITLE', 
           'PUBLICATION NAME', 
           'PUBLISH DATE', 
           'AUTHOR(S)', 
           'LINK_TEXT',
           'URL',
           'SAVED FILENAME',
           'FILE NAME OR URL', 
           'DOWNLOADED', 
           'NOTES']

df[exp_col].to_excel(os.path.join(wrk_fldr, 'ref_tbl.xlsx'),
            index=False)



#%% Attempt to format the table into the template version and rename table

# Extract filenames
# Expects user to have already generated GSP folder of the form:
    # X-XXX_BasinName
ref_fldr_split = os.path.split(os.path.split(wrk_fldr)[0])[1]

# Load workbook for formatting
wb = openpyxl.load_workbook(filename = os.path.join(wrk_fldr, 'ref_tbl.xlsx'))
ws = wb.active # only 1 sheet

col_widths = {'A': 51.71, # Title
              'B': 18.57, # Publication Name
              'C': 14.29, # Publish Date
              'D': 41.57, # Author(s)
              'E': 10, # Link Text
              'F': 10, # URL,
              'G': 15,
              'H': 58.14, # File Name or URL
              'I': 22.86, # Downloaded
              'J': 44} #Notes

# Define border for header row
hborder = borders.Side(style=None, color='DDDDDD', border_style='thick')
thick = borders.Border(bottom=hborder)

# Set column widths to the template widths
for col in col_widths:
    ws.column_dimensions[col].width = col_widths[col]
    
    h_cell = ws[col+'1']
    h_cell.font = Font(color='AAAAAA', bold=True)
    h_cell.border = thick
    

# Iterate table rows, format links, and apply conditional formatting
# Link underline
for i, cell in enumerate(ws['H']):
    
    if i ==0:
        continue
    
    cell.font = Font(color='0563C1', underline='single')
    
    
# Apply conditional formatting
red_text = Font(color='9C0006')
red_fill = PatternFill(bgColor='FFC7CE')

green_text = Font(color='006100')
green_fill = PatternFill(bgColor='C6EFCE')

yel_text = Font(color='9C5700')
yel_fill = PatternFill(bgColor='FFEB9C')

dxf_red = DifferentialStyle(font=red_text, fill=red_fill)
dxf_green = DifferentialStyle(font=green_text, fill=green_fill)
dxf_yel = DifferentialStyle(font=yel_text, fill=yel_fill)

red_flags = ['problem',
             'paywall',
             'broken link',
             'not found']

green_flags = ['downloaded',
               'yes']

for red_flag in red_flags:
    rule = Rule(type='containsText', operator='containsText', text=red_flag,
                dxf=dxf_red)
    rule.formula = [f'NOT(ISERROR(SEARCH("{red_flag}",I2)))'] # this line is necessary to automatically apply conditional formatting
    ws.conditional_formatting.add('I2:I1048576', rule)
    
for green_flag in green_flags:
    rule = Rule(type='containsText', operator='containsText', text=green_flag,
                dxf=dxf_green)
    rule.formula = [f'NOT(ISERROR(SEARCH("{green_flag}",I2)))']
    ws.conditional_formatting.add('I2:I1048576', rule)

rule = Rule(type='containsText', operator='containsText', text='screenshot',
            dxf=dxf_yel)
rule.formula = ['NOT(ISERROR(SEARCH("screenshot",I2)))'] 
ws.conditional_formatting.add('I2:I1048576', rule)

# Save exported table
wb.save(os.path.join(wrk_fldr, f'{ref_fldr_split}_References.xlsx'))

# Remove origional table
os.remove(os.path.join(wrk_fldr, 'ref_tbl.xlsx'))
























