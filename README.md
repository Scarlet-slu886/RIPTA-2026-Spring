# RIPTA-2026-Spring


## Background & Project Goal
This project integrates two separate datasets from the Rhode Island Public Transit Authority (RIPTA):
1. **System Dataset (AVL/OTP):** Contains Automated Vehicle Location data (GPS coordinates) and operational timings.
2. **Ridership Dataset (Farebox):** Contains passenger boarding counts, fare collection records, and direct physical Stop IDs.

These two datasets are recorded and stored independently in different systems. However, they contain records that describe the exact same bus trips. **The goal of this project is to accurately match the corresponding records between these two standalone datasets based on time and spatial attributes.** Successfully joining these datasets unlocks the ability to perform advanced downstream analysis, such as evaluating the direct relationship between **On-Time Performance (OTP) and passenger ridership/demand**.

## Repository Contents

### Code Files
* `all_route_April2024_weighted.py`: The main execution script. Iterates through all bus routes, matches the monthly data for April 2024, calculates weighted OTP, and outputs the final matched dataset.
* `stop_level_route1_April2024.py`: A script focused specifically on Route 1, used for granular stop-level processing and validation.
* `testfile.py`: A development script used for testing the weighted graph logic and algorithm tuning.

### Summary / Results
* `Match_Summary_Overview.csv`: The output summary table showing the execution status and total number of successfully matched trips for each route.
* `OTP_Comparison_Scatter.png`: A scatter plot visualizing the weighted and unweighted On-Time Performance analysis derived from the final matched dataset.

## Core Matching Logic
The algorithm connects the two datasets using the following sequence:

0. **Spatial Mapping (GPS to Stops):** The Ridership data contains direct physical Stop IDs, but the System (OTP) data only provides raw GPS coordinates. Before any matching occurs, the **Haversine formula** is applied to calculate spherical distances, mapping the raw AVL GPS pings to official physical bus stops. This spatial join generates the `Mapped_StopId` required for downstream validation.
1. **Multi-Day Profiling:** Groups raw records by `Route` and `Trip ID` across multiple days to calculate the median start and end times for each trip, creating a stable "trip profile".
2. **Temporal Overlap (Jaccard Index & Containment):** Compares the trip profiles from both datasets using two advanced similarity metrics:
   * **IoU / Jaccard Index:** The intersection of the time duration divided by the union.
   * **Containment:** The intersection divided by the duration of the shorter trip.
   Candidate pairs must have at least a 10% overlap to proceed.
3. **Stop-Level Spatial Validation:** The script evaluates the physical `Stop IDs` for candidate pairs. A match is considered valid **only if**:
   * They share at least one physical stop (`Common_Stops > 0`).
   * The time difference at the matched stops does not exceed the maximum headway (`Max_Stop_Diff <= 1800s`).
4. **OTP Ratio & Weighting:** For valid matched trips, the algorithm calculates the `Ratio_Within_2Min` (the proportion of common stops where the bus arrived within a 120-second tolerance). It then calculates a **Weighted OTP** weighted against the passenger boardings (`Ride.Count`) at those specific stops.
5. **Ranking & Confidence Scoring:** Candidates are sorted by validity, the `Ratio_Within_2Min`, and the Jaccard Index. The best match is selected and assigned a specific confidence level.

## Key Results & Achievements
The matching algorithm demonstrated exceptional performance, successfully joining thousands of distinct bus trips across the network. 
* **Total Matched Trips:** successfully matched 6436 trips across the RIPTA system for April 2024.
* **High Confidence Rate:** Approximately 90% of the matched trips were classified as "Confident" or higher level. 
* **Validation Criteria:** A match is rigorously flagged as "Highly Confident" if it dynamically passes the stop-validation threshold (over 50% of shared stops matched within the 2-minute temporal tolerance) or achieves an extremely high Jaccard similarity score (IoU $\ge$ 0.8).
