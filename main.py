import fastf1
import matplotlib.pyplot as plt
from fastf1 import plotting

print("Loading 2024 Las Vegas GP Race session...")

session = fastf1.get_session(2024, 'Las Vegas', 'R')
session.load()

laps = session.laps

print("\n=== DEBUGGING LAP TIMES ===")
fastest_lap = laps.pick_fastest()
print(f"Overall fastest lap:")
print(f"Driver: {fastest_lap['Driver']}")
print(f"LapTime: {fastest_lap['LapTime']}")
print(f"Time column: {fastest_lap['Time']}")

print(f"\nChecking each driver's fastest:")
for driver in ['NOR', 'HAM', 'LAW']:
    driver_laps = laps[laps['Driver'] == driver]
    if not driver_laps.empty:
        driver_fastest = driver_laps.pick_fastest()
        print(f"{driver}: {driver_fastest['LapTime']}")
    else:
        print(f"{driver}: No data")

fastest_lap = laps.pick_fastest()

print("\n=== FASTEST LAP OF THE RACE ===")
print(f"Fastest lap time: {fastest_lap['LapTime']}")
print(f"Driver: {fastest_lap['Driver']}")
print(f"Team: {fastest_lap['Team']}")
print(f"Lap number: {fastest_lap['LapNumber']}")
print(f"Compound: {fastest_lap['Compound']}")

print(f"\nTotal laps in session: {len(laps)}")
print(f"Number of drivers: {len(laps['Driver'].unique())}")

print("\n=== TELEMETRY FOR FASTEST LAP ===")
telemetry = fastest_lap.get_telemetry()

max_speed = telemetry['Speed'].max()
avg_speed = telemetry['Speed'].mean()
max_throttle = telemetry['Throttle'].max()
avg_throttle = telemetry['Throttle'].mean()
max_brake = telemetry['Brake'].max()

print(f"Max speed: {max_speed:.1f} km/h")
print(f"Average speed: {avg_speed:.1f} km/h")
print(f"Max throttle: {max_throttle:.1f}%")
print(f"Average throttle: {avg_throttle:.1f}%")
print(f"Max brake pressure: {max_brake:.1f}")

print(f"\nTelemetry data points: {len(telemetry)}")
print(f"Available telemetry channels: {list(telemetry.columns)}")

print("\n=== MULTI-DRIVER COMPARISON ===")

hamilton_laps = laps[laps['Driver'] == 'HAM']
lawson_laps = laps[laps['Driver'] == 'LAW']

if not hamilton_laps.empty:
    hamilton_fastest = hamilton_laps.pick_fastest()
    ham_telemetry = hamilton_fastest.get_telemetry()
    print(f"Hamilton fastest: {hamilton_fastest['Time']} (Lap {hamilton_fastest['LapNumber']:.0f})")
else:
    print("Hamilton data not found")

if not lawson_laps.empty:
    lawson_fastest = lawson_laps.pick_fastest()
    law_telemetry = lawson_fastest.get_telemetry()
    print(f"Lawson fastest: {lawson_fastest['Time']} (Lap {lawson_fastest['LapNumber']:.0f})")
else:
    print("Lawson data not found")

print("\n=== CREATING SIDE-BY-SIDE COMPARISON WITH SPEED ANALYSIS ===")

plotting.setup_mpl()

fig = plt.figure(figsize=(20, 12))
# Create grid: 2 rows, 3 columns for track maps, and 1 full-width row for speed plot
gs = fig.add_gridspec(2, 3, height_ratios=[2, 1], hspace=0.3)

# Top row: track visualizations
track_axes = [fig.add_subplot(gs[0, i]) for i in range(3)]

drivers_data = [
    ('NOR', telemetry, fastest_lap, 'Norris (Fastest)'),
    ('HAM', ham_telemetry if not hamilton_laps.empty else None, hamilton_fastest if not hamilton_laps.empty else None, 'Hamilton'),
    ('LAW', law_telemetry if not lawson_laps.empty else None, lawson_fastest if not lawson_laps.empty else None, 'Lawson')
]

for i, (driver_code, driver_telemetry, driver_lap, driver_name) in enumerate(drivers_data):
    ax = track_axes[i]
    
    if driver_telemetry is not None:
        points = ax.scatter(driver_telemetry['X'], driver_telemetry['Y'],
                           c=driver_telemetry['Speed'],
                           cmap='plasma',
                           s=8,
                           alpha=0.8)
        
        colorbar = plt.colorbar(points, ax=ax)
        colorbar.set_label('Speed (km/h)', fontsize=10)
        
        lap_time_str = str(driver_lap['LapTime']).split(' ')[-1]  # Extract lap time
        ax.set_title(f'{driver_name}\nLap Time: {lap_time_str}', fontsize=12, pad=15)
    else:
        ax.text(0.5, 0.5, f'{driver_name}\nNo Data Available', 
                ha='center', va='center', transform=ax.transAxes, fontsize=12)
    
    ax.set_xlabel('Track Position X (m)', fontsize=10)
    ax.set_ylabel('Track Position Y (m)', fontsize=10)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

# Bottom row: speed comparison plot
speed_ax = fig.add_subplot(gs[1, :])  # Span all 3 columns

# Interpolate telemetry data to common distance points for comparison
import numpy as np
from scipy import interpolate

if not hamilton_laps.empty and not lawson_laps.empty:
    # Use Norris's distance as reference
    nor_distance = telemetry['Distance']
    ham_distance = ham_telemetry['Distance'] 
    law_distance = law_telemetry['Distance']
    
    # Create common distance array
    min_dist = max(nor_distance.min(), ham_distance.min(), law_distance.min())
    max_dist = min(nor_distance.max(), ham_distance.max(), law_distance.max())
    common_distance = np.linspace(min_dist, max_dist, 200)
    
    # Interpolate speeds
    nor_speed_interp = np.interp(common_distance, nor_distance, telemetry['Speed'])
    ham_speed_interp = np.interp(common_distance, ham_distance, ham_telemetry['Speed'])
    law_speed_interp = np.interp(common_distance, law_distance, law_telemetry['Speed'])
    
    # Plot speed traces
    speed_ax.plot(common_distance, nor_speed_interp, color='#FF8700', linewidth=2, label='Norris (Fastest)', alpha=0.9)
    speed_ax.plot(common_distance, ham_speed_interp, color='#00D2BE', linewidth=2, label='Hamilton', alpha=0.9)
    speed_ax.plot(common_distance, law_speed_interp, color='#6692FF', linewidth=2, label='Lawson', alpha=0.9)
    
    # Fill areas where Norris is faster/slower
    speed_ax.fill_between(common_distance, nor_speed_interp, ham_speed_interp, 
                         where=(nor_speed_interp > ham_speed_interp), color='green', alpha=0.3, label='Norris > Hamilton')
    speed_ax.fill_between(common_distance, nor_speed_interp, law_speed_interp, 
                         where=(nor_speed_interp > law_speed_interp), color='lightgreen', alpha=0.2)
    
    speed_ax.set_xlabel('Track Distance (m)', fontsize=12)
    speed_ax.set_ylabel('Speed (km/h)', fontsize=12)
    speed_ax.set_title('Speed Comparison Along Track Distance', fontsize=14, pad=10)
    speed_ax.legend(fontsize=10)
    speed_ax.grid(True, alpha=0.3)
    
    # Add speed difference annotations
    max_diff_ham = np.max(nor_speed_interp - ham_speed_interp)
    max_diff_law = np.max(nor_speed_interp - law_speed_interp)
    speed_ax.text(0.02, 0.95, f'Max advantage over Hamilton: +{max_diff_ham:.1f} km/h\nMax advantage over Lawson: +{max_diff_law:.1f} km/h', 
                 transform=speed_ax.transAxes, fontsize=10, verticalalignment='top',
                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

plt.suptitle('Las Vegas GP - Complete Driver Comparison Analysis', fontsize=18, y=0.95)
plt.tight_layout()

print("Saving comprehensive comparison as 'comprehensive_analysis.png'...")
plt.savefig('comprehensive_analysis.png', dpi=300, bbox_inches='tight')

print("Comprehensive analysis complete! Check 'comprehensive_analysis.png'")