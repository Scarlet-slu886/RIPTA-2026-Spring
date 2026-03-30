# RIPTA-2026-Spring


## Background & Project Goal
This project integrates two separate datasets from the Rhode Island Public Transit Authority (RIPTA):
1. **System Dataset (AVL/OTP):** Contains Automated Vehicle Location data (GPS coordinates) and operational timings.
2. **Ridership Dataset (Farebox):** Contains passenger boarding counts, fare collection records, and direct physical Stop IDs.

These two datasets are recorded and stored independently in different systems. However, they contain records that describe the exact same bus trips. **The goal of this project is to accurately match the corresponding records between these two standalone datasets based on time and spatial attributes.** Successfully joining these datasets unlocks the ability to perform advanced downstream analysis, such as evaluating the direct relationship between **On-Time Performance (OTP) and passenger ridership/demand**.

## Repository Contents

* `all_route_April2024_weighted.py`: The main execution script. Iterates through all bus routes, matches the monthly data for April 2024, calculates weighted OTP, and outputs the final matched dataset.
* `stop_level_route1_April2024.py`: A script focused specifically on Route 1, used for granular stop-level processing and validation.
* `testfile.py`: A development script used for testing the weighted graph logic and algorithm tuning.
* `Data Dictionary.md`: Explains the columns generated in the final output file.

---

## Expectations for Input Data
To run the matching pipeline successfully, you must provide two preprocessed CSV files. The datasets must contain the following required columns:

### 1. Ridership Dataset (Farebox)
- `Route.Number`: The bus route identifier.
- `Trip.Number`: The unique ID for the trip in the Farebox system.
- `Stop.Number`: The physical stop code/ID where boarding occurred.
- `Time`: The timestamp of the record (format can be mixed, but must be parsable by pandas).
- `Ride.Count`: The number of passengers boarding at that specific stop.

### 2. System Dataset (AVL / OTP)
- `RouteId`: The bus route identifier.
- `TripId`: The unique ID for the trip in the AVL system.
- `Mapped_StopId`: The physical stop ID (This MUST be pre-calculated using spatial mapping/Haversine formula to match the Farebox `Stop.Number`).
- `IncidentDateTime`: The timestamp of the AVL ping.

---

## How to Run

**Step 1: Clone the repository**
```bash
git clone <your-repo-link>
cd <your-repo-folder>
```

**Step 2: Prepare your data**
Ensure your two CSV files meet the input expectations listed above. *(Do not commit raw data to GitHub).*

**Step 3: Configure the paths**
Open `all_route_April2024_weighted.py` and update the file paths under the `CONFIGURATION` section to point to your local datasets:
```python
PATH_TO_RIDERSHIP_CSV = r'path/to/your/ridership_data.csv'
PATH_TO_SYSTEM_CSV = r'path/to/your/avl_system_data.csv'
```

**Step 4: Execute the pipeline**
Run the main script via terminal:
```bash
python all_route_April2024_weighted.py
```
The script will print the progress route by route and generate the final matched dataset (`RIPTA_All_Routes_Exact_Logic.csv`) and a summary overview (`Match_Summary_Overview.csv`) locally in the same directory.

   
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


## Future Work (Post-Spring Break)
With the foundational matching pipeline completed, the next phase of this research will shift from data integration to advanced network analysis, specifically focusing on **Driver Transition and Route Switching behaviors**.

* **Graph Modeling:** Modeling the RIPTA transit network as a large-scale directed graph (estimated ~40k nodes representing trips/stops/events, and edges representing possible driver transitions).
* **Transition Metrics:** Analyzing switching patterns between routes, calculating median transition times, and evaluating how ridership demand influences driver switching behaviors.
* **Network Clustering:** Applying graph clustering algorithms to partition the complex system into smaller, localized sub-problems to uncover distinct operational patterns.
