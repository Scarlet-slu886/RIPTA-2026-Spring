import pandas as pd
import numpy as np

# =========================================================
# CONFIGURATION
# =========================================================
APP_STOP_COL_ORIGINAL = 'Stop.Number'  # stop name in ridership
SYS_STOP_COL_ORIGINAL = 'Mapped_StopId'  # stop namen in AVL

MAX_HEADWAY_SEC = 1800  # max tolerance gap：1800seconds = 30 minutes
TOLERANCE_SEC = 120  # 2 mintnues tolerance for matching stops (120 seconds)


# =========================================================
# 1. Process Multi-day Profiles (Trip Level & Stop Level)
# =========================================================
def process_route1_multiday_profiles(ridership_df, system_df):
    # --- 1. Filter and Rename IDs ---
    ridership_route1 = ridership_df[ridership_df['Route.Number'] == 1].copy()
    ridership_route1.rename(columns={
        'Trip.Number': 'AppID',
        APP_STOP_COL_ORIGINAL: 'app_stopID'
    }, inplace=True)

    system_route1 = system_df.copy()
    system_route1.rename(columns={
        'TripId': 'SystemID',
        SYS_STOP_COL_ORIGINAL: 'system_stopID'
    }, inplace=True)

    # --- 2. Time Conversion ---
    ridership_route1['Time'] = pd.to_datetime(ridership_route1['Time'])
    ridership_route1['ServiceDate'] = ridership_route1['Time'].dt.date
    ridership_route1['Seconds'] = (
            ridership_route1['Time'].dt.hour * 3600 +
            ridership_route1['Time'].dt.minute * 60 +
            ridership_route1['Time'].dt.second
    )

    system_route1['IncidentDateTime'] = pd.to_datetime(system_route1['IncidentDateTime'])
    system_route1['ServiceDate'] = system_route1['IncidentDateTime'].dt.date
    system_route1['Seconds'] = (
            system_route1['IncidentDateTime'].dt.hour * 3600 +
            system_route1['IncidentDateTime'].dt.minute * 60 +
            system_route1['IncidentDateTime'].dt.second
    )

    # --- 3. Generate Trip-Level Profiles (Your original logic) ---
    app_daily = ridership_route1.groupby(['ServiceDate', 'AppID'])['Seconds'].agg(['min', 'max']).reset_index()
    app_daily.rename(columns={'min': 'Daily_Start', 'max': 'Daily_End'}, inplace=True)
    app_profile = app_daily.groupby('AppID').agg({
        'Daily_Start': 'median', 'Daily_End': 'median', 'ServiceDate': 'count'
    }).reset_index().rename(
        columns={'Daily_Start': 'App_Start_Median', 'Daily_End': 'App_End_Median', 'ServiceDate': 'App_Days_Count'})

    sys_daily = system_route1.groupby(['ServiceDate', 'SystemID'])['Seconds'].agg(['min', 'max']).reset_index()
    sys_daily.rename(columns={'min': 'Daily_Start', 'max': 'Daily_End'}, inplace=True)
    system_profile = sys_daily.groupby('SystemID').agg({
        'Daily_Start': 'median', 'Daily_End': 'median', 'ServiceDate': 'count'
    }).reset_index().rename(
        columns={'Daily_Start': 'Sys_Start_Median', 'Daily_End': 'Sys_End_Median', 'ServiceDate': 'Sys_Days_Count'})


    app_stop_profile = ridership_route1.groupby(['AppID', 'app_stopID'])['Seconds'].median().reset_index()
    app_stop_profile.rename(columns={'Seconds': 'App_StopTime_Median'}, inplace=True)

    sys_stop_profile = system_route1.groupby(['SystemID', 'system_stopID'])['Seconds'].median().reset_index()
    sys_stop_profile.rename(columns={'Seconds': 'Sys_StopTime_Median'}, inplace=True)

    print(f"Profiles Generated! Found {len(app_profile)} App trips and {len(system_profile)} System trips.")
    return app_profile, system_profile, app_stop_profile, sys_stop_profile


# =========================================================
# Helper: Metrics & Time Formatting
# =========================================================
def calculate_metrics(start1, end1, start2, end2):
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    intersection = max(0, overlap_end - overlap_start)
    duration1 = max(0, end1 - start1)
    duration2 = max(0, end2 - start2)
    union = duration1 + duration2 - intersection
    iou = (intersection / union) if union > 0 else 0.0
    smaller_duration = min(duration1, duration2)
    containment = (intersection / smaller_duration) if smaller_duration > 0 else 0.0
    return iou, containment


def format_seconds(seconds_val):
    if pd.isna(seconds_val): return ""
    return f"{int(seconds_val // 3600):02d}:{int((seconds_val % 3600) // 60):02d}:{int(seconds_val % 60):02d}"


# =========================================================
# Phase 3 & 4: Stop-Level Evaluation & Best Match Selection
# =========================================================
def find_best_matches_with_stop_level(app_profile, system_profile, app_stop_profile, sys_stop_profile,
                                      thresh_highly_conf=0.8, thresh_conf=0.5, thresh_contain=0.9):
    print("\n--- Phase 3: Generating Candidates (IoU > 0.1) ---")
    candidates = []
    app_records = app_profile.to_dict('records')
    sys_records = system_profile.to_dict('records')

    # list comprehension version
    for app in app_records:
        for sys in sys_records:
            iou_score, contain_score = calculate_metrics(
                sys['Sys_Start_Median'], sys['Sys_End_Median'],
                app['App_Start_Median'], app['App_End_Median']
            )
            if iou_score > 0.1:  # keep all IoU larger than 0.1 as candidates for stop-level validation
                candidates.append({
                    'AppID': app['AppID'], 'SystemID': sys['SystemID'],
                    'IoU': iou_score, 'Containment': contain_score,
                    'App_Start_Sec': app['App_Start_Median'], 'App_End_Sec': app['App_End_Median'],
                    'Sys_Start_Sec': sys['Sys_Start_Median'], 'Sys_End_Sec': sys['Sys_End_Median'],
                    'App_Days_Occurs': app['App_Days_Count'], 'System_Days_Occurs': sys['Sys_Days_Count']
                })

    cand_df = pd.DataFrame(candidates)

    print("--- Phase 4: Stop-Level Validation (The 1-2 Min Rule) ---")
    # build a dictionanry to store test results
    stop_eval_results = []

    for idx, row in cand_df.iterrows():
        app_id = row['AppID']
        sys_id = row['SystemID']

        # abstract the stop profiles for this pair
        a_stops = app_stop_profile[app_stop_profile['AppID'] == app_id]
        s_stops = sys_stop_profile[sys_stop_profile['SystemID'] == sys_id]

        # merge on stop IDs to find common stops
        merged_stops = pd.merge(a_stops, s_stops, left_on='app_stopID', right_on='system_stopID', how='inner')

        if merged_stops.empty:
            stop_eval_results.append({'Max_Stop_Diff': np.nan, 'Ratio_Within_2Min': 0.0, 'Common_Stops': 0})
            continue

        # calulate time differences and evaluate against the 2-minute rule
        merged_stops['time_diff'] = abs(merged_stops['App_StopTime_Median'] - merged_stops['Sys_StopTime_Median'])
        max_diff = merged_stops['time_diff'].max()
        stops_within_2min = len(merged_stops[merged_stops['time_diff'] <= TOLERANCE_SEC])
        ratio_2min = stops_within_2min / len(merged_stops)

        stop_eval_results.append({
            'Max_Stop_Diff': max_diff,
            'Ratio_Within_2Min': ratio_2min,
            'Common_Stops': len(merged_stops)
        })

    # combine the stop-level evaluation results back to the candidate dataframe
    eval_df = pd.DataFrame(stop_eval_results)
    cand_df = pd.concat([cand_df.reset_index(drop=True), eval_df.reset_index(drop=True)], axis=1)

    # find Best Match
    # 1. filter out those that fail the 2-minute rule (max stop time difference must be within 2 minutes) or have no common stops at all
    valid_candidates = cand_df[(cand_df['Max_Sto*p_Diff'] <= MAX_HEADWAY_SEC) & (cand_df['Common_Stops'] > 0)].copy()

    # 2. if no candidates pass the stop-level validation, fall back to the original IoU-based ranking without stop-level validation
    if valid_candidates.empty:
        best_matches = cand_df.sort_values('IoU', ascending=False).drop_duplicates('AppID').copy()
    else:
        # 3. among those that pass the stop-level validation, rank them first by the ratio of stops within 2 minutes, then by IoU, and select the best match for each AppID
        best_matches = valid_candidates.sort_values(by=['Ratio_Within_2Min', 'IoU'],
                                                    ascending=[False, False]).drop_duplicates('AppID').copy()

    # --- Apply Ultimate Confidence Logic ---
    def determine_confidence(row):
        # if the stop-level validation is very strong (e.g., at least 50% of common stops are within 2 minutes), we can directly label it as "Highly Confident (Stop-Validated)"
        if row['Ratio_Within_2Min'] >= 0.5:
            return 'Highly Confident (Stop-Validated)'
        # or if the IoU is very high (e.g., above 0.8), we can also label it as "Highly Confident" even without strong stop-level validation
        elif row['IoU'] >= thresh_highly_conf:
            return 'Highly Confident'
        elif row['IoU'] >= thresh_conf and row['Containment'] >= thresh_contain:
            return 'Confident'
        elif row['IoU'] >= thresh_conf:
            return 'Confident'
        else:
            return 'Uncertain'

    best_matches['Level_of_Confidence'] = best_matches.apply(determine_confidence, axis=1)

    # --- Format Times ---
    best_matches['App_Start_Time'] = best_matches['App_Start_Sec'].apply(format_seconds)
    best_matches['App_End_Time'] = best_matches['App_End_Sec'].apply(format_seconds)
    best_matches['Sys_Start_Time'] = best_matches['Sys_Start_Sec'].apply(format_seconds)
    best_matches['Sys_End_Time'] = best_matches['Sys_End_Sec'].apply(format_seconds)

    final_cols = [
        'AppID', 'SystemID', 'Level_of_Confidence', 'IoU', 'Containment',
        'Ratio_Within_2Min', 'Max_Stop_Diff', 'Common_Stops',  
        'App_Start_Time', 'App_End_Time', 'Sys_Start_Time', 'Sys_End_Time',
        'App_Days_Occurs', 'System_Days_Occurs'
    ]
    return best_matches[final_cols]


# =========================================================
# MAIN EXECUTION
# =========================================================
if __name__ == "__main__":
    print("Loading data... Please wait.")

    PATH_TO_RIDERSHIP_CSV = r'E:\RIPTA\RIPTA_DATA\april24_preprocessed.csv'
    PATH_TO_SYSTEM_CSV = r'E:\RIPTA\RIPTA_DATA\AVL_april_mapped.csv'

    # 1. Load Data
    raw_ridership_df = pd.read_csv(PATH_TO_RIDERSHIP_CSV)
    raw_system_df = pd.read_csv(PATH_TO_SYSTEM_CSV)

    # 2. Process Profiles (contain stop profile)
    final_app_profile, final_sys_profile, final_app_stop, final_sys_stop = process_route1_multiday_profiles(
        raw_ridership_df, raw_system_df)

    # 3. Find Best Matches with Stop-Level Validation
    final_best_matches = find_best_matches_with_stop_level(final_app_profile, final_sys_profile, final_app_stop,
                                                           final_sys_stop)

    if not final_best_matches.empty:
        # 4. Attach Riders Count
        riders_count = raw_ridership_df[raw_ridership_df['Route.Number'] == 1].groupby(
            'Trip.Number').size().reset_index(name='Number_of_Riders')
        riders_count.rename(columns={'Trip.Number': 'AppID'}, inplace=True)
        final_best_matches = pd.merge(final_best_matches, riders_count, on='AppID', how='left')

        # adjust column order to put 'Number_of_Riders' right after 'AppID'
        cols = final_best_matches.columns.tolist()
        cols.insert(2, cols.pop(cols.index('Number_of_Riders')))
        final_best_matches = final_best_matches[cols]

        print("\n--- Final Output Preview ---")
        print(final_best_matches.head())

        OUTPUT_CSV_PATH = "route1_final_output_stop_validated.csv"
        final_best_matches.to_csv(OUTPUT_CSV_PATH, index=False)

        print(f"\n SUCCESS: Stop-level validated table saved to '{OUTPUT_CSV_PATH}'")
