## Data Dictionary

This data dictionary explains the columns generated in the final output file (`RIPTA_All_Routes_Exact_Logic.csv`).

| Column Name | Description |
| :--- | :--- |
| **Route.Number** | The specific RIPTA bus route number. |
| **AppID** | The unique Trip ID from the Farebox (Ridership) system. |
| **SystemID** | The unique Trip ID from the AVL (OTP/System) dataset. |
| **Level_of_Confidence** | The categorical confidence level of the match (e.g., "Highly Confident", "Confident", "Uncertain") based on stop validation and IoU. |
| **IoU** | Intersection over Union (Jaccard Index) of the time duration between the Farebox trip and AVL trip. |
| **Containment** | The temporal intersection divided by the duration of the shorter trip. |
| **Ratio_Within_2Min** | The proportion of shared physical stops where the time difference is within the 120-second tolerance. |
| **Weighted_OTP** | On-Time Performance metric, weighted by the actual number of passengers (`Ride.Count`) at the matched stops. |
| **Max_Stop_Diff** | The maximum time difference (in seconds) observed among all shared stops for this matched trip. |
| **Common_Stops** | The total number of physical stops shared between the Farebox and AVL records for the matched trip. |
| **Number_of_Riders** | The total passenger count for this specific trip. |
| **App_Start_Time / End_Time** | The median start and end times of the trip according to the Farebox data. |
| **Sys_Start_Time / End_Time** | The median start and end times of the trip according to the AVL system data. |
