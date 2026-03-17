# RIPTA-2026-Spring

## Background
This project aims to integrate two separate datasets from the Rhode Island Public Transit Authority (RIPTA):
1. **System Dataset (AVL/OTP):** Contains Automated Vehicle Location data and On-Time Performance metrics.
2. **Ridership Dataset (Farebox):** Contains passenger boarding and fare collection records.

These two datasets are recorded and stored independently in different systems. However, they contain records that describe the exact same bus trips. The goal of this project and the provided scripts is to accurately match the corresponding records between these two standalone datasets based on time and spatial attributes.

## Repository Contents

### Code Files
* `all_route_April2024_weighted.py`
  The main execution script. It iterates through all bus routes to process and match the monthly data for April 2024.
* `stop_level_route1_April2024.py`
  A script focused specifically on Route 1, used for granular stop-level data processing and validation.
* `testfile.py`
  A testing script used during the development phase to verify weighted graph logic.

### Summary Folder
* `Match_Summary_Overview.csv`
  The output summary table showing the total number of successfully matched trips for each route.
* `OTP_Comparison_Scatter.png`
  A scatter plot visualizing the On-Time Performance (OTP) comparison derived from the matched dataset.

## Matching Logic Overview
*(Note: A more detailed wrap-up report can be provided separately)*
The matching algorithm connects the two datasets using the following core steps:
1. **Grouping**: Data is grouped by `Route.Number` and multi-day trip profiles are generated.
2. **Time Window**: A specific time threshold is applied to filter potential trip matches between the System and Ridership records.
3. **Stop Intersection**: The algorithm verifies the match by calculating the intersection of `Stop IDs`. A match is only confirmed if the physical stops in both datasets overlap for a given trip. Trips with 0 common stops are rejected to ensure accuracy.
