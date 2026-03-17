# RIPTA-2026-Spring


## Background & Project Goal
This project integrates two separate datasets from the Rhode Island Public Transit Authority (RIPTA):
1. **System Dataset (AVL/OTP):** Contains Automated Vehicle Location data and operational timings.
2. **Ridership Dataset (Farebox):** Contains passenger boarding counts and fare collection records.

These two datasets are recorded and stored independently in different systems. However, they contain records that describe the exact same bus trips. **The goal of this project is to accurately match the corresponding records between these two standalone datasets based on time and spatial attributes.** Successfully joining these datasets unlocks the ability to perform advanced downstream analysis, such as evaluating the direct relationship between **On-Time Performance (OTP) and passenger ridership/demand**.

## Repository Contents

### Code Files
* `all_route_April2024_weighted.py`
  The main execution script. It iterates through all bus routes, matches the monthly data for April 2024, calculates weighted OTP, and outputs the final matched dataset.
* `stop_level_route1_April2024.py`
  A script focused specifically on Route 1, used for granular stop-level data processing and validation.
* `testfile.py`
  A development script used for testing the weighted graph logic and algorithm tuning.

### Summary / Results
* `Match_Summary_Overview.csv`
  The output summary table showing the execution status and total number of successfully matched trips for each route.
* `OTP_Comparison_Scatter.png`
  A scatter plot visualizing the On-Time Performance analysis derived from the final matched dataset.

## Core Matching Logic
The algorithm in `all_route_April2024_weighted.py` connects the two datasets using the following sequence:

1. **Multi-Day Profiling:** Groups raw records by `Route` and `Trip ID` across multiple days to calculate the median start and end times for each trip, creating a stable "trip profile".
2. **Temporal Overlap (IoU Filter):** Compares the trip profiles from both datasets using an Intersection over Union (IoU) metric. Candidate pairs must have at least a 10% time overlap to proceed.
3. **Stop-Level Spatial Validation:** The script evaluates the physical `Stop IDs` for candidate pairs. A match is considered valid **only if**:
   * They share at least one physical stop (`Common_Stops > 0`).
   * The time difference at the matched stops does not exceed the maximum headway (`Max_Stop_Diff <= 1800s`).
4. **Weighted OTP Calculation:** For matched trips, the script calculates the On-Time Performance (within a 120-second tolerance) and weights it against the passenger boardings (`Ride.Count`) at those specific stops.
5. **Ranking & Output:** Candidates are sorted by validity, the ratio of on-time stops, and IoU score. The best match is selected, assigned a confidence level, and exported with aggregated ridership data.
