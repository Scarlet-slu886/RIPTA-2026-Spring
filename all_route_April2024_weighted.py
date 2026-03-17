import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# =========================================================
# CONFIGURATION
# =========================================================
APP_STOP_COL_ORIGINAL = 'Stop.Number'
SYS_STOP_COL_ORIGINAL = 'Mapped_StopId'
SYS_ROUTE_COL = 'RouteId'

MAX_HEADWAY_SEC = 1800
TOLERANCE_SEC = 120


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
# 1. Process Multi-day Profiles for a Single Route
# =========================================================
def process_route_multiday_profiles(ridership_df, system_df, route_id):
    # --- 1. Filter and Rename IDs ---
    ridership_route1 = ridership_df[ridership_df['Route.Number'].astype(str) == str(route_id)].copy()
    system_route1 = system_df[system_df[SYS_ROUTE_COL].astype(str) == str(route_id)].copy()

    if ridership_route1.empty or system_route1.empty:
        return None, None, None, None

    ridership_route1.rename(columns={'Trip.Number': 'AppID', APP_STOP_COL_ORIGINAL: 'app_stopID'}, inplace=True)
    system_route1.rename(columns={'TripId': 'SystemID', SYS_STOP_COL_ORIGINAL: 'system_stopID'}, inplace=True)

    # --- 2. Time Conversion ---
    ridership_route1['Time'] = pd.to_datetime(ridership_route1['Time'], format='mixed')
    ridership_route1['ServiceDate'] = ridership_route1['Time'].dt.date
    ridership_route1['Seconds'] = (
            ridership_route1['Time'].dt.hour * 3600 +
            ridership_route1['Time'].dt.minute * 60 +
            ridership_route1['Time'].dt.second
    )

    system_route1['IncidentDateTime'] = pd.to_datetime(system_route1['IncidentDateTime'], format='mixed')
    system_route1['ServiceDate'] = system_route1['IncidentDateTime'].dt.date
    system_route1['Seconds'] = (
            system_route1['IncidentDateTime'].dt.hour * 3600 +
            system_route1['IncidentDateTime'].dt.minute * 60 +
            system_route1['IncidentDateTime'].dt.second
    )

    # --- 3. Generate Trip-Level Profiles ---
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

    app_stop_profile = ridership_route1.groupby(['AppID', 'app_stopID']).agg({
        'Seconds': 'median',
        'Ride.Count': 'mean'
    }).reset_index()
    app_stop_profile.rename(columns={'Seconds': 'App_StopTime_Median'}, inplace=True)

    sys_stop_profile = system_route1.groupby(['SystemID', 'system_stopID'])['Seconds'].median().reset_index()
    sys_stop_profile.rename(columns={'Seconds': 'Sys_StopTime_Median'}, inplace=True)

    return app_profile, system_profile, app_stop_profile, sys_stop_profile


# =========================================================
# Phase 3 & 4: Stop-Level Evaluation
# =========================================================
def find_best_matches_with_stop_level(app_profile, system_profile, app_stop_profile, sys_stop_profile,
                                      thresh_highly_conf=0.8, thresh_conf=0.5, thresh_contain=0.9):
    candidates = []
    app_records = app_profile.to_dict('records')
    sys_records = system_profile.to_dict('records')

    for app in app_records:
        for sys in sys_records:
            iou_score, contain_score = calculate_metrics(
                sys['Sys_Start_Median'], sys['Sys_End_Median'],
                app['App_Start_Median'], app['App_End_Median']
            )
            if iou_score > 0.1:
                candidates.append({
                    'AppID': app['AppID'], 'SystemID': sys['SystemID'],
                    'IoU': iou_score, 'Containment': contain_score,
                    'App_Start_Sec': app['App_Start_Median'], 'App_End_Sec': app['App_End_Median'],
                    'Sys_Start_Sec': sys['Sys_Start_Median'], 'Sys_End_Sec': sys['Sys_End_Median'],
                    'App_Days_Occurs': app['App_Days_Count'], 'System_Days_Occurs': sys['Sys_Days_Count']
                })

    if not candidates:
        return pd.DataFrame()

    cand_df = pd.DataFrame(candidates)
    stop_eval_results = []

    for idx, row in cand_df.iterrows():
        app_id = row['AppID']
        sys_id = row['SystemID']

        a_stops = app_stop_profile[app_stop_profile['AppID'] == app_id]
        s_stops = sys_stop_profile[sys_stop_profile['SystemID'] == sys_id]
        merged_stops = pd.merge(a_stops, s_stops, left_on='app_stopID', right_on='system_stopID', how='inner')

        if merged_stops.empty:
            stop_eval_results.append(
                {'Max_Stop_Diff': np.nan, 'Ratio_Within_2Min': 0.0, 'Weighted_OTP': 0.0, 'Common_Stops': 0})
            continue

        merged_stops['time_diff'] = abs(merged_stops['App_StopTime_Median'] - merged_stops['Sys_StopTime_Median'])
        max_diff = merged_stops['time_diff'].max()

        is_ontime = merged_stops['time_diff'] <= TOLERANCE_SEC
        ratio_2min = is_ontime.sum() / len(merged_stops)

        total_riders_at_matched_stops = merged_stops['Ride.Count'].sum()
        if total_riders_at_matched_stops > 0:
            weighted_otp = merged_stops.loc[is_ontime, 'Ride.Count'].sum() / total_riders_at_matched_stops
        else:
            weighted_otp = 0.0

        stop_eval_results.append({
            'Max_Stop_Diff': max_diff,
            'Ratio_Within_2Min': ratio_2min,
            'Weighted_OTP': weighted_otp,
            'Common_Stops': len(merged_stops)
        })

    eval_df = pd.DataFrame(stop_eval_results)
    cand_df = pd.concat([cand_df.reset_index(drop=True), eval_df.reset_index(drop=True)], axis=1)

    # find Best Match
    # 1. first, filter out those candidates that have Max_Stop_Diff > MAX_HEADWAY_SEC or have no common stops (Common_Stops=0)
    cand_df['IsValid'] = (cand_df['Max_Stop_Diff'] <= MAX_HEADWAY_SEC) & (cand_df['Common_Stops'] > 0)

    # 2. when sorting, prioritize those with IsValid=True, then by Ratio_Within_2Min, and then by IoU.
    # if some don't pass stop level validation, they'll be kept and ranked lower
    best_matches = cand_df.sort_values(
        by=['IsValid', 'Ratio_Within_2Min', 'IoU'],
        ascending=[False, False, False]
    ).drop_duplicates('AppID').copy()

    def determine_confidence(row):
        if row['Ratio_Within_2Min'] >= 0.5:
            return 'Highly Confident (Stop-Validated)'
        elif row['IoU'] >= thresh_highly_conf:
            return 'Highly Confident'
        elif row['IoU'] >= thresh_conf and row['Containment'] >= thresh_contain:
            return 'Confident'
        elif row['IoU'] >= thresh_conf:
            return 'Confident'
        else:
            return 'Uncertain'

    best_matches['Level_of_Confidence'] = best_matches.apply(determine_confidence, axis=1)

    best_matches['App_Start_Time'] = best_matches['App_Start_Sec'].apply(format_seconds)
    best_matches['App_End_Time'] = best_matches['App_End_Sec'].apply(format_seconds)
    best_matches['Sys_Start_Time'] = best_matches['Sys_Start_Sec'].apply(format_seconds)
    best_matches['Sys_End_Time'] = best_matches['Sys_End_Sec'].apply(format_seconds)

    final_cols = [
        'AppID', 'SystemID', 'Level_of_Confidence', 'IoU', 'Containment',
        'Ratio_Within_2Min', 'Weighted_OTP', 'Max_Stop_Diff', 'Common_Stops',
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

    raw_ridership_df = pd.read_csv(PATH_TO_RIDERSHIP_CSV)
    raw_system_df = pd.read_csv(PATH_TO_SYSTEM_CSV)


    # --- cleaning ---
    def clean_route_id(x):
        try:
            return str(int(float(x)))
        except:
            return str(x).strip()


    raw_ridership_df['Route.Number'] = raw_ridership_df['Route.Number'].apply(clean_route_id)
    raw_system_df[SYS_ROUTE_COL] = raw_system_df[SYS_ROUTE_COL].apply(clean_route_id)

    # take only routes that are in both datasets
    raw_ridership_df['Route.Number'] = raw_ridership_df['Route.Number'].astype(str)
    all_routes = sorted(raw_ridership_df['Route.Number'].unique())

    print(f"Total routes found: {len(all_routes)}")

    final_results = []

    # store summary results for all routes
    summary_results = []

    for route_id in all_routes:
        print(f"Processing Route {route_id}...", end=" ", flush=True)

        app_prof, sys_prof, app_stop, sys_stop = process_route_multiday_profiles(raw_ridership_df, raw_system_df,
                                                                                 route_id)

        if app_prof is None or app_prof.empty:
            print("Skipped (No matched data in system for this route).")
            # record summary result for this route
            summary_results.append({'Route': route_id, 'Matched_Trips': 0, 'Status': 'Skipped (No System Data)'})
            continue

        best_matches = find_best_matches_with_stop_level(app_prof, sys_prof, app_stop, sys_stop)

        if not best_matches.empty:
            # add number of riders for each matched trip
            r_route = raw_ridership_df[raw_ridership_df['Route.Number'] == route_id]
            riders_count = r_route.groupby('Trip.Number')['Ride.Count'].sum().reset_index(name='Number_of_Riders')
            riders_count.rename(columns={'Trip.Number': 'AppID'}, inplace=True)

            best_matches = pd.merge(best_matches, riders_count, on='AppID', how='left')

            # put Route.Number as the first column
            best_matches.insert(0, 'Route.Number', route_id)

            final_results.append(best_matches)

            match_count = len(best_matches)
            print(f"Matched {match_count} trips.")
            # add summary result for this route
            summary_results.append({'Route': route_id, 'Matched_Trips': match_count, 'Status': 'Success'})
        else:
            print("Matched 0 trips.")
            # record summary result for this route
            summary_results.append({'Route': route_id, 'Matched_Trips': 0, 'Status': 'Matched 0'})

    if final_results:
        # reset index and concatenate all route results into one DataFrame
        final_full_df = pd.concat(final_results, ignore_index=True)
        OUTPUT_CSV_PATH = "RIPTA_All_Routes_Exact_Logic.csv"
        final_full_df.to_csv(OUTPUT_CSV_PATH, index=False)
        print(f"\n SUCCESS: All routes compiled and saved to '{OUTPUT_CSV_PATH}'")

        # record summary results into a DataFrame and save
        summary_df = pd.DataFrame(summary_results)
        SUMMARY_CSV_PATH = "Match_Summary_Overview.csv"
        summary_df.to_csv(SUMMARY_CSV_PATH, index=False)

        # calculate total matched trips across all routes and print
        total_matched = summary_df['Matched_Trips'].sum()
        print(f" SUCCESS: Overview saved to '{SUMMARY_CSV_PATH}'")
        print(f" TOTAL MATCHED TRIPS ACROSS ALL ROUTES: {total_matched}")



