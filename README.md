# C2VSimFG V2.0 surface water components

## General Process
Reservoirs and lakes were largely modeled in C2VSimFG v1.01 & v1.5 as constrained general head boundary conditions (CBC). C2VSimFG v2.0 continues this practice, but also models Woodward Reservoir seepage as a diversion. 

C2VSimFG v1.01 & v1.5 included Camanche Reservoir, Thermalito Afterbay, and Black Butte Lake. C2VSimFG v2.0 adds Turlock Lake, Modesto Reservoir, Lake Natoma, and Woodward Reservoir. 

To model the reservoirs as CBCs, 

The existing reservoir datasets will be updated to current and the new reservoirs' entire timeseries datasets will be downloaded.

1. Select reservoirs to download in the cdec_reservoirs.xlsx
2. Download the applicable reservoir elevation (or storage) timeseries
3. Read current CBC specs and timeseries files
4. Develop set of nodes for reservoirs/lakes
5. Estimate lakebed conductance
6. Extract ESJWRM diversion for Woodward reservoir. 

## Specific Process
Additional process steps related to 
