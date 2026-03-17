import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 1. read the CSV file into a DataFrame
df = pd.read_csv("RIPTA_All_Routes_Exact_Logic.csv")

# 2. filter out trips with no common stops
valid_trips = df[df['Common_Stops'] > 0].copy()

# 3. calculate unweighted OTP: ratio of trips within 2 minutes
route_stats = []
grouped = valid_trips.groupby('Route.Number')

for route_id, group in grouped:
    # filter out trips with zero riders to avoid skewing the weighted OTP
    group = group[group['Number_of_Riders'] > 0]
    if group.empty:
        continue

    # X: unweighted OTP = ratio of trips within 2 minutes
    x_unweighted = group['Ratio_Within_2Min'].mean()

    # Y: passenger-weighted OTP
    numerator = (group['Weighted_OTP'] * group['Number_of_Riders']).sum()
    denominator = group['Number_of_Riders'].sum()
    y_weighted = numerator / denominator

    # gather stats for this route
    route_stats.append({
        'Route': str(route_id),
        'Unweighted_OTP': x_unweighted,
        'Weighted_OTP': y_weighted,
        'Total_Trips': len(group),
        'Total_Riders': denominator
    })

stats_df = pd.DataFrame(route_stats)

plt.figure(figsize=(10, 8))
sns.set_style("whitegrid")

# use scatterplot with size representing total riders
scatter = sns.scatterplot(
    data=stats_df,
    x='Unweighted_OTP',
    y='Weighted_OTP',
    size='Total_Riders', sizes=(50, 800), alpha=0.7, color='b', edgecolor='k'
)

# get the limits for the diagonal line (Y=X)
min_val = min(stats_df['Unweighted_OTP'].min(), stats_df['Weighted_OTP'].min()) - 0.05
max_val = max(stats_df['Unweighted_OTP'].max(), stats_df['Weighted_OTP'].max()) + 0.05
plt.plot([min_val, max_val], [min_val, max_val], 'r--', label='Y = X (Neutral)')

# label 5 largest routes by total riders
top_routes = stats_df.nlargest(5, 'Total_Riders')
for _, row in top_routes.iterrows():
    plt.annotate(f"Rt {row['Route']}",
                 (row['Unweighted_OTP'], row['Weighted_OTP']),
                 xytext=(8, 5), textcoords='offset points', fontsize=9)

# define title and labels
plt.title('Weighted OTP', fontsize=14, fontweight='bold')
plt.xlabel('Unweighted OTP', fontsize=12)
plt.ylabel('Passenger-Weighted OTP', fontsize=12)

#  normalize x and y axis to percentage format
from matplotlib.ticker import PercentFormatter

plt.gca().xaxis.set_major_formatter(PercentFormatter(1))
plt.gca().yaxis.set_major_formatter(PercentFormatter(1))

plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()

# save the figure
plt.savefig('OTP_Comparison_Scatter.png', dpi=300)
print("saved as OTP_Comparison_Scatter.png")
plt.show()

import scipy.stats as stats
import numpy as np

# Calculate the difference (Passenger Gap)
stats_df['Gap'] = stats_df['Weighted_OTP'] - stats_df['Unweighted_OTP']

# 1. Calculate Mean Absolute Error (MAE)
mae = stats_df['Gap'].abs().mean()

# 2. Calculate Pearson Correlation
correlation, _ = stats.pearsonr(stats_df['Unweighted_OTP'], stats_df['Weighted_OTP'])

# 3. Paired T-test
t_stat, p_value = stats.ttest_rel(stats_df['Unweighted_OTP'], stats_df['Weighted_OTP'])

# 4. Bias on Top 5 High-Ridership Routes
top_5_routes = stats_df.nlargest(5, 'Total_Riders')
top_5_bias = top_5_routes['Gap'].mean()

print("\n=== Statistical Validation Metrics ===")
print(f"1. Mean Absolute Error (MAE): {mae:.2%} ")
print(f"2. Pearson Correlation (R): {correlation:.3f}")

if p_value < 0.05:
    print(f"3. Paired T-test p-value: {p_value:.4f} < 0.05")
else:
    print(f"3. Paired T-test p-value: {p_value:.4f} > 0.05")


print(f"4. Top 5 Routes Avg Bias: {top_5_bias:.2%} ")
