# C2VSimFG V2.0 surface water components

## General Process
Reservoirs and lakes were largely modeled in C2VSimFG v1.01 & v1.5 as constrained general head boundary conditions (CBC). C2VSimFG v2.0 continues this practice, but also models Woodward Reservoir seepage as a diversion. 

C2VSimFG v1.01 & v1.5 included Camanche Reservoir, Thermalito Afterbay, and Black Butte Lake. C2VSimFG v2.0 adds Turlock Lake, Modesto Reservoir, Lake Natoma, and Woodward Reservoir. 

To model the reservoirs as CBCs, the approximate model nodes to which the boundary condition should be applied must be listed along with:
1. Aquifer layer
2. Time series boundary head value
3. Conductance
4. Time series max flow value

The existing reservoir datasets will be updated to current (beyond end of simuation, WY 2021) and the new reservoirs' entire timeseries datasets will be input.

## Specific Process
To update the CBC files, a combination of python scripting and manual tweaks/selections is utilized:
1. Select reservoirs to download in the *cdec_reservoirs.xlsx* file
2. Download/process the applicable reservoir elevation (or storage) timeseries from CDEC
    - This requires some iteration as various CDEC station sensors have different timeseries periods of length, for different variables. Plots of the selected sensors were reviewed and the longest period of record and/or most complete relative to the simulation period were utilized. 
    - The two sensors utilized for this work are sensor 6 (reservoir elevation) and sensor 15 (reservoir storage).
    - In the case where a reservoir only had reservoir storage data available, CalSim3 reservoir storage and elevation relationship tables were utilized to convert storage to elevation (head).
      * The CalSim3 storage-->elevation tables were interpolated via 1st-order splines (considerate of time-index value spacing) to develop elevation values for each reservoir.
      * Values were aggregated to a monthly average, if not already on a monthly basis.
      * Then, values were linearly interpolated to the monthly simulation stress period.
4. Read previous version CBC specs and timeseries files.
5. Merge previous version and updated version CBC timeseries.
6. Develop set of nodes for reservoirs/lakes
    - As a starting point, intersects the C2VSimFG model nodes and the applicable NHD lake/reservoir boundary polygons is performed. Then the user must manually edit the shapefile, then the script continues.
7. Estimate lakebed conductance
    - Initially estimated as Kv / &Delta;b * A, where:
      * Kv = vertical hydraulic conductivity (of top model layer, layer #1) *[From model preprocessor input file]*
      * &Delta;b = vertical thickness/conductance linear pathway, estimated as layer 1 thickness *[From model stratigraphy preprocessor input file]*
      * A = effective nodal area *[From preprocessor output file]*
    - A second estimate was made similar to the v1.01 model update where Kv / &Delta;b * A / 10,000 and:
      * &Delta;b = vertical thickness/conductance linear pathway, **estimated as 1 foot**.
8. Extract ESJWRM diversion for Woodward reservoir.
    - Woodward Reservoir data not found in CDEC; however, ESJWRM modeled Woodward Reservoir seepage. This diversion (ESJWRM diversion #32) was extracted and mapped to C2VSimFG.

## Output (*.\Code\output*)
1. *cbc_specs_YYYYMMDD.csv*
  - Constrained general head boundary conditions data file, which replaces the main specification portion of the file.
  - The NGB parameter will still need to be updated manually.
2. *cbc_timeseries_YYYYMMDD.csv*
  - Constrained general head time series file, which replaces the existing time series data.
  - Preserves the original data, extends with new CDEC timeseries data, and adds entire timeseries datasets for new lakes/reservoirs.
3. *Woodward_Seepage.csv*
  - Diversion spec and timeseries data mapped to C2VSimFG (from ESJWRM).
