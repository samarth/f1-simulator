import dash
from dash import dcc, html, Input, Output, State, callback, ALL, ctx
import plotly.graph_objects as go
import plotly.express as px
import fastf1
import fastf1.plotting
import pandas as pd
import numpy as np
import json

# Initialize FastF1 plotting
fastf1.plotting.setup_mpl()

# Initialize Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)

# Expose Flask server for Gunicorn
server = app.server

# Cache for loaded sessions to avoid re-loading
_session_cache = {}

COMPOUND_COLORS = {
    'SOFT': '#FF3333',
    'MEDIUM': '#FFC300',
    'HARD': '#FFFFFF',
    'INTERMEDIATE': '#39B54A',
    'WET': '#0072C6',
}

MAX_STINTS = 5


def format_lap_time(timedelta_obj):
    """Convert timedelta to MM:SS.sss format."""
    total_seconds = timedelta_obj.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}"


def format_race_time(total_seconds):
    """Convert total seconds to H:MM:SS.sss format."""
    hours = int(total_seconds // 3600)
    remaining = total_seconds % 3600
    minutes = int(remaining // 60)
    seconds = remaining % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:06.3f}"
    return f"{minutes}:{seconds:06.3f}"


def load_session(year, race, session_type):
    """Load and cache a FastF1 session."""
    key = (year, race, session_type)
    if key not in _session_cache:
        f1_session = fastf1.get_session(year, race, session_type)
        f1_session.load()
        _session_cache[key] = f1_session
    return _session_cache[key]


def get_race_degradation_data(session):
    """Extract tire degradation curves from a race session.

    Returns dict of {compound: {'tyre_life': [...], 'avg_lap_time': [...], 'std_lap_time': [...]}}
    Filters out pit in/out laps, safety car laps, and inaccurate laps.
    """
    laps = session.laps
    degradation = {}

    for compound in ['SOFT', 'MEDIUM', 'HARD']:
        try:
            compound_laps = laps.pick_tyre(compound)
            # Filter out pit in/out laps and inaccurate laps
            clean_laps = compound_laps.pick_wo_box().pick_accurate()

            # Filter out safety car laps (TrackStatus '4' = SC, '6' = VSC)
            if 'TrackStatus' in clean_laps.columns:
                clean_laps = clean_laps[
                    clean_laps['TrackStatus'].isin(['1', '2', 1, 2]) |
                    clean_laps['TrackStatus'].isna()
                ]

            if clean_laps.empty:
                continue

            # Convert LapTime to seconds
            clean_laps = clean_laps.copy()
            clean_laps['LapTimeSec'] = clean_laps['LapTime'].dt.total_seconds()

            # Remove extreme outliers (beyond 2 std from mean)
            mean_time = clean_laps['LapTimeSec'].mean()
            std_time = clean_laps['LapTimeSec'].std()
            if std_time > 0:
                clean_laps = clean_laps[
                    (clean_laps['LapTimeSec'] >= mean_time - 2 * std_time) &
                    (clean_laps['LapTimeSec'] <= mean_time + 2 * std_time)
                ]

            if clean_laps.empty:
                continue

            # Group by TyreLife, get mean and std
            grouped = clean_laps.groupby('TyreLife')['LapTimeSec'].agg(['mean', 'std', 'count'])
            grouped = grouped[grouped['count'] >= 2]  # Need at least 2 data points

            if grouped.empty:
                # Fallback: use all data points without count filter
                grouped = clean_laps.groupby('TyreLife')['LapTimeSec'].agg(['mean', 'std', 'count'])

            if grouped.empty:
                continue

            degradation[compound] = {
                'tyre_life': grouped.index.tolist(),
                'avg_lap_time': grouped['mean'].tolist(),
                'std_lap_time': grouped['std'].fillna(0).tolist(),
                'count': grouped['count'].tolist(),
            }
        except Exception as e:
            print(f"Error processing compound {compound}: {e}")
            continue

    return degradation


def get_pit_stop_stats(session):
    """Extract average pit stop duration (pit lane time loss) from the race."""
    laps = session.laps

    pit_times = []
    drivers = laps['Driver'].unique()

    for driver in drivers:
        driver_laps = laps[laps['Driver'] == driver].sort_values('LapNumber')
        for _, lap in driver_laps.iterrows():
            if pd.notna(lap.get('PitInTime')) and pd.notna(lap.get('PitOutTime')):
                pit_duration = (lap['PitOutTime'] - lap['PitInTime']).total_seconds()
                if 15 < pit_duration < 60:  # Reasonable pit stop range
                    pit_times.append(pit_duration)

    if not pit_times:
        # Fallback: estimate from lap time differences around pit stops
        for driver in drivers:
            driver_laps = laps[laps['Driver'] == driver].sort_values('LapNumber')
            for i in range(1, len(driver_laps)):
                cur = driver_laps.iloc[i]
                prev = driver_laps.iloc[i - 1]
                if (pd.notna(cur.get('Stint')) and pd.notna(prev.get('Stint'))
                        and cur['Stint'] != prev['Stint']):
                    if pd.notna(cur['LapTime']) and pd.notna(prev['LapTime']):
                        cur_time = cur['LapTime'].total_seconds()
                        prev_time = prev['LapTime'].total_seconds()
                        avg_clean = laps.pick_wo_box().pick_accurate()
                        if not avg_clean.empty:
                            avg_time = avg_clean['LapTime'].dt.total_seconds().mean()
                            pit_loss = cur_time - avg_time
                            if 15 < pit_loss < 40:
                                pit_times.append(pit_loss)

    if pit_times:
        return {
            'avg_pit_time': np.mean(pit_times),
            'min_pit_time': np.min(pit_times),
            'max_pit_time': np.max(pit_times),
            'num_stops': len(pit_times),
        }
    return {'avg_pit_time': 22.0, 'min_pit_time': 20.0, 'max_pit_time': 25.0, 'num_stops': 0}


def get_driver_actual_strategy(session, driver):
    """Extract what a driver actually did: stints, compounds, lap counts, total time."""
    laps = session.laps
    driver_laps = laps[laps['Driver'] == driver].sort_values('LapNumber')

    if driver_laps.empty:
        return None

    stints = []
    current_stint = None

    for _, lap in driver_laps.iterrows():
        stint_num = lap.get('Stint', 1)
        compound = lap.get('Compound', 'UNKNOWN')

        if current_stint is None or current_stint['stint'] != stint_num:
            if current_stint is not None:
                stints.append(current_stint)
            current_stint = {
                'stint': stint_num,
                'compound': compound,
                'start_lap': int(lap['LapNumber']),
                'end_lap': int(lap['LapNumber']),
                'laps': 1,
            }
        else:
            current_stint['end_lap'] = int(lap['LapNumber'])
            current_stint['laps'] += 1

    if current_stint is not None:
        stints.append(current_stint)

    # Get lap times
    lap_times = []
    for _, lap in driver_laps.iterrows():
        if pd.notna(lap['LapTime']):
            lap_times.append({
                'lap': int(lap['LapNumber']),
                'time_sec': lap['LapTime'].total_seconds(),
                'compound': lap.get('Compound', 'UNKNOWN'),
                'tyre_life': int(lap.get('TyreLife', 0)),
            })

    total_time = sum(lt['time_sec'] for lt in lap_times) if lap_times else 0

    # Find pit stop laps
    pit_laps = []
    for i in range(len(stints) - 1):
        pit_laps.append({
            'lap': stints[i]['end_lap'],
            'from_compound': stints[i]['compound'],
            'to_compound': stints[i + 1]['compound'],
        })

    return {
        'stints': stints,
        'lap_times': lap_times,
        'total_time': total_time,
        'pit_laps': pit_laps,
        'total_laps': int(driver_laps['LapNumber'].max()),
    }


def build_degradation_model(degradation_data):
    """Build interpolation functions from degradation data.

    For each compound, creates a function that given TyreLife returns estimated lap time.
    Uses linear interpolation on the average data, with extrapolation for unseen tyre ages.
    """
    models = {}
    for compound, data in degradation_data.items():
        tyre_life = np.array(data['tyre_life'])
        avg_times = np.array(data['avg_lap_time'])

        if len(tyre_life) < 2:
            # Not enough data for interpolation, use constant
            models[compound] = {
                'base_time': avg_times[0] if len(avg_times) > 0 else 90.0,
                'deg_rate': 0.05,  # Default small degradation
                'type': 'linear',
            }
        else:
            # Fit linear regression: lap_time = base + deg_rate * tyre_life
            coeffs = np.polyfit(tyre_life, avg_times, 1)
            models[compound] = {
                'base_time': coeffs[1],
                'deg_rate': coeffs[0],
                'type': 'linear',
            }

    return models


def estimate_lap_time(models, compound, tyre_life):
    """Estimate lap time for a given compound and tire age."""
    if compound not in models:
        # Use average of available compounds as fallback
        if models:
            avg_base = np.mean([m['base_time'] for m in models.values()])
            avg_deg = np.mean([m['deg_rate'] for m in models.values()])
            return avg_base + avg_deg * tyre_life
        return 90.0  # Ultimate fallback

    model = models[compound]
    return model['base_time'] + model['deg_rate'] * tyre_life


def simulate_strategy(models, stints, pit_loss, total_race_laps):
    """Simulate a strategy and return estimated lap times.

    Args:
        models: degradation models from build_degradation_model()
        stints: list of {'compound': str, 'laps': int}
        pit_loss: seconds lost per pit stop
        total_race_laps: total laps in the race

    Returns:
        list of {'lap': int, 'time_sec': float, 'compound': str, 'tyre_life': int, 'is_pit_lap': bool}
    """
    results = []
    current_lap = 1

    for stint_idx, stint in enumerate(stints):
        compound = stint['compound']
        num_laps = stint['laps']

        for lap_in_stint in range(num_laps):
            tyre_life = lap_in_stint + 1
            lap_time = estimate_lap_time(models, compound, tyre_life)

            # Add pit stop loss on the last lap of a stint (except the final stint)
            is_pit_lap = (lap_in_stint == num_laps - 1 and stint_idx < len(stints) - 1)
            if is_pit_lap:
                lap_time += pit_loss

            results.append({
                'lap': current_lap,
                'time_sec': lap_time,
                'compound': compound,
                'tyre_life': tyre_life,
                'is_pit_lap': is_pit_lap,
            })
            current_lap += 1

    return results


# --- Layout ---

def create_stint_row(stint_num):
    """Create a stint input row with compound dropdown and laps input."""
    return html.Div([
        html.Div([
            html.Label(f"Stint {stint_num}:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
            dcc.Dropdown(
                id={'type': 'stint-compound', 'index': stint_num},
                options=[
                    {'label': 'Soft', 'value': 'SOFT'},
                    {'label': 'Medium', 'value': 'MEDIUM'},
                    {'label': 'Hard', 'value': 'HARD'},
                ],
                value='MEDIUM' if stint_num == 1 else 'HARD',
                style={'width': '140px', 'display': 'inline-block', 'verticalAlign': 'middle'},
                clearable=False,
            ),
            html.Label(" for ", style={'margin': '0 10px'}),
            dcc.Input(
                id={'type': 'stint-laps', 'index': stint_num},
                type='number',
                min=1,
                max=80,
                value='' if stint_num > 1 else '',
                placeholder='laps',
                style={
                    'width': '80px',
                    'display': 'inline-block',
                    'verticalAlign': 'middle',
                    'textAlign': 'center',
                },
            ),
            html.Label(" laps", style={'marginLeft': '5px'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '8px'}),
    ], id={'type': 'stint-row', 'index': stint_num})


# Strategy simulator tab content
strategy_tab_layout = html.Div([
    # Driver selection for strategy
    html.Div([
        html.Div([
            html.Label("Select Driver:", style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='strategy-driver-dropdown',
                placeholder='Select a driver...',
                style={'width': '200px'},
            ),
        ], style={'display': 'inline-block', 'marginRight': '20px', 'verticalAlign': 'top'}),
        html.Button(
            'Load Race Data',
            id='load-strategy-btn',
            n_clicks=0,
            className='strategy-btn',
        ),
    ], style={'marginBottom': '20px', 'display': 'flex', 'alignItems': 'flex-end', 'gap': '15px'}),

    # Race info panel
    html.Div(id='race-info-panel', style={'marginBottom': '20px'}),

    # Degradation chart
    dcc.Loading(
        html.Div([
            dcc.Graph(id='degradation-chart', style={'display': 'none'}),
        ]),
        type='circle',
    ),

    # Strategy planning section
    html.Div(id='strategy-planning-section', style={'display': 'none'}, children=[
        html.H4("Plan Your Strategy", style={'marginBottom': '15px'}),

        # Stint inputs container
        html.Div(id='stint-inputs-container', children=[
            create_stint_row(1),
            create_stint_row(2),
        ]),

        # Add/remove stint buttons
        html.Div([
            html.Button('+ Add Pit Stop', id='add-stint-btn', n_clicks=0, className='strategy-btn-secondary'),
            html.Button('- Remove Pit Stop', id='remove-stint-btn', n_clicks=0,
                        className='strategy-btn-secondary',
                        style={'marginLeft': '10px'}),
        ], style={'marginBottom': '15px', 'marginTop': '5px'}),

        # Lap count validation
        html.Div(id='lap-count-validation', style={'marginBottom': '15px'}),

        # Simulate button
        html.Button(
            'Simulate Strategy',
            id='simulate-btn',
            n_clicks=0,
            className='strategy-btn',
        ),
    ]),

    # Results section
    dcc.Loading(
        html.Div(id='simulation-results', style={'marginTop': '30px'}),
        type='circle',
    ),
])

# Telemetry tab content (existing dashboard)
telemetry_tab_layout = html.Div([
    dcc.Loading(
        id="loading",
        children=[
            html.Div([
                html.Label("Select Drivers to Compare:"),
                dcc.Dropdown(
                    id='driver-dropdown',
                    multi=True,
                    value=['NOR', 'HAM', 'LAW']
                )
            ], style={'marginBottom': 30}),

            html.Div(id='lap-summary', style={'marginBottom': 30}),

            html.Div([
                dcc.Graph(id='track-visualization')
            ]),

            html.Div([
                dcc.Graph(id='speed-comparison')
            ])
        ]
    )
])


app.layout = html.Div([
    html.H1("F1 Telemetry & Strategy Dashboard",
            style={'textAlign': 'center', 'marginBottom': 20}),

    # Shared session selectors
    html.Div([
        html.Div([
            html.Label("Select Year:"),
            dcc.Dropdown(
                id='year-dropdown',
                options=[
                    {'label': '2024', 'value': 2024},
                    {'label': '2023', 'value': 2023},
                    {'label': '2022', 'value': 2022}
                ],
                value=2024
            )
        ], style={'width': '30%', 'display': 'inline-block', 'marginRight': '3%'}),

        html.Div([
            html.Label("Select Race:"),
            dcc.Dropdown(
                id='race-dropdown',
                options=[
                    {'label': 'Las Vegas', 'value': 'Las Vegas'},
                    {'label': 'Abu Dhabi', 'value': 'Abu Dhabi'},
                    {'label': 'Qatar', 'value': 'Qatar'},
                    {'label': 'Brazil', 'value': 'Brazil'},
                    {'label': 'Mexico', 'value': 'Mexico'}
                ],
                value='Las Vegas'
            )
        ], style={'width': '30%', 'display': 'inline-block', 'marginRight': '3%'}),

        html.Div([
            html.Label("Select Session:"),
            dcc.Dropdown(
                id='session-dropdown',
                options=[
                    {'label': 'Race', 'value': 'R'},
                    {'label': 'Qualifying', 'value': 'Q'},
                    {'label': 'Practice 3', 'value': 'FP3'},
                    {'label': 'Practice 2', 'value': 'FP2'},
                    {'label': 'Practice 1', 'value': 'FP1'}
                ],
                value='R'
            )
        ], style={'width': '30%', 'display': 'inline-block'})
    ], style={'marginBottom': 20}),

    # Tabs
    dcc.Tabs(id='main-tabs', value='telemetry-tab', children=[
        dcc.Tab(label='Telemetry Analysis', value='telemetry-tab', children=[
            telemetry_tab_layout
        ]),
        dcc.Tab(label='Strategy Simulator', value='strategy-tab', children=[
            strategy_tab_layout
        ]),
    ]),

    # Stores
    dcc.Store(id='strategy-state', storage_type='memory'),
    dcc.Store(id='strategy-history', storage_type='local'),
    dcc.Store(id='num-stints-store', data=2),
])


# --- Telemetry Tab Callbacks (existing, unchanged logic) ---

@callback(
    Output('driver-dropdown', 'options'),
    Output('driver-dropdown', 'value'),
    Input('year-dropdown', 'value'),
    Input('race-dropdown', 'value'),
    Input('session-dropdown', 'value')
)
def update_drivers(year, race, session):
    try:
        f1_session = load_session(year, race, session)
        drivers = f1_session.laps['Driver'].unique()
        driver_options = [{'label': driver, 'value': driver} for driver in sorted(drivers)]
        default_drivers = sorted(drivers)[:3] if len(drivers) >= 3 else sorted(drivers)
        return driver_options, default_drivers
    except Exception as e:
        print(f"Error loading drivers: {e}")
        return [], []


@callback(
    Output('lap-summary', 'children'),
    Output('track-visualization', 'figure'),
    Output('speed-comparison', 'figure'),
    Input('year-dropdown', 'value'),
    Input('race-dropdown', 'value'),
    Input('session-dropdown', 'value'),
    Input('driver-dropdown', 'value')
)
def update_analysis(year, race, session, selected_drivers):
    if not selected_drivers:
        empty_fig = go.Figure()
        return "Please select drivers to analyze.", empty_fig, empty_fig

    try:
        f1_session = load_session(year, race, session)
        laps = f1_session.laps

        fastest_lap = laps.pick_fastest()
        fastest_time_formatted = format_lap_time(fastest_lap['LapTime'])

        summary = html.Div([
            html.H3(f"{year} {race} GP - {session} Session Analysis"),
            html.P(f"Fastest Lap: {fastest_lap['Driver']} - {fastest_time_formatted} "
                   f"(Lap {fastest_lap['LapNumber']:.0f})")
        ])

        driver_data = {}
        colors = px.colors.qualitative.Set1

        for i, driver in enumerate(selected_drivers):
            try:
                driver_laps = laps[laps['Driver'] == driver]
                if not driver_laps.empty:
                    driver_fastest = driver_laps.pick_fastest()
                    telemetry = driver_fastest.get_telemetry()
                    driver_data[driver] = {
                        'telemetry': telemetry,
                        'lap_time': driver_fastest['LapTime'],
                        'lap_number': driver_fastest['LapNumber'],
                        'color': colors[i % len(colors)]
                    }
            except Exception as e:
                print(f"Error processing driver {driver}: {e}")

        # Track visualization
        track_fig = go.Figure()
        first_trace = True
        for driver, data in driver_data.items():
            if 'telemetry' in data:
                telemetry = data['telemetry']
                track_fig.add_trace(go.Scatter(
                    x=telemetry['X'],
                    y=telemetry['Y'],
                    mode='markers',
                    marker=dict(
                        size=4,
                        color=telemetry['Speed'],
                        colorscale='Viridis',
                        showscale=first_trace,
                        colorbar=dict(
                            title="Speed (km/h)",
                            x=1.15,
                            len=0.7
                        ) if first_trace else None
                    ),
                    name=f"{driver} - {format_lap_time(data['lap_time'])}",
                    hovertemplate=f"<b>{driver}</b><br>"
                                  "Speed: %{marker.color:.1f} km/h<br>"
                                  "X: %{x:.0f}m<br>"
                                  "Y: %{y:.0f}m<extra></extra>"
                ))
                first_trace = False

        track_fig.update_layout(
            title="Track Map - Fastest Laps Comparison",
            xaxis_title="Track Position X (m)",
            yaxis_title="Track Position Y (m)",
            showlegend=True,
            height=600,
            xaxis=dict(scaleanchor="y", scaleratio=1),
            legend=dict(
                orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5
            ),
            margin=dict(l=50, r=200, t=80, b=100)
        )

        # Speed comparison
        speed_fig = go.Figure()
        if len(driver_data) > 1:
            common_distance = None
            speed_traces = {}

            for driver, data in driver_data.items():
                if 'telemetry' in data:
                    telemetry = data['telemetry']
                    distance = telemetry['Distance']
                    speed = telemetry['Speed']

                    if common_distance is None:
                        common_distance = np.linspace(distance.min(), distance.max(), 200)

                    speed_interp = np.interp(common_distance, distance, speed)
                    speed_traces[driver] = speed_interp

                    speed_fig.add_trace(go.Scatter(
                        x=common_distance,
                        y=speed_interp,
                        mode='lines',
                        name=f"{driver} - {format_lap_time(data['lap_time'])}",
                        line=dict(color=data['color'], width=3),
                        hovertemplate=f"<b>{driver}</b><br>"
                                      "Distance: %{x:.0f}m<br>"
                                      "Speed: %{y:.1f} km/h<extra></extra>"
                    ))

            if len(speed_traces) == 2:
                drivers_list = list(speed_traces.keys())
                speed1 = speed_traces[drivers_list[0]]
                speed2 = speed_traces[drivers_list[1]]

                speed_fig.add_trace(go.Scatter(
                    x=common_distance, y=np.maximum(speed1, speed2),
                    fill=None, mode='lines', line_color='rgba(0,0,0,0)',
                    showlegend=False, hoverinfo='skip'
                ))
                speed_fig.add_trace(go.Scatter(
                    x=common_distance, y=np.minimum(speed1, speed2),
                    fill='tonexty', mode='lines', line_color='rgba(0,0,0,0)',
                    fillcolor='rgba(0,255,0,0.2)', name='Speed Difference',
                    hovertemplate="Speed Difference: %{customdata:.1f} km/h<extra></extra>",
                    customdata=np.abs(speed1 - speed2)
                ))

        speed_fig.update_layout(
            title="Speed Comparison Along Track Distance",
            xaxis_title="Track Distance (m)",
            yaxis_title="Speed (km/h)",
            showlegend=True, height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=80, b=50)
        )

        return summary, track_fig, speed_fig

    except Exception as e:
        error_msg = f"Error loading data: {str(e)}"
        empty_fig = go.Figure()
        empty_fig.add_annotation(
            text=error_msg, xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle'
        )
        return error_msg, empty_fig, empty_fig


# --- Strategy Simulator Callbacks ---

@callback(
    Output('strategy-driver-dropdown', 'options'),
    Input('year-dropdown', 'value'),
    Input('race-dropdown', 'value'),
    Input('session-dropdown', 'value'),
    Input('main-tabs', 'value'),
)
def update_strategy_drivers(year, race, session, active_tab):
    if active_tab != 'strategy-tab' or session != 'R':
        return []
    try:
        f1_session = load_session(year, race, session)
        drivers = f1_session.laps['Driver'].unique()
        return [{'label': d, 'value': d} for d in sorted(drivers)]
    except Exception:
        return []


@callback(
    Output('strategy-state', 'data'),
    Output('race-info-panel', 'children'),
    Output('degradation-chart', 'figure'),
    Output('degradation-chart', 'style'),
    Output('strategy-planning-section', 'style'),
    Input('load-strategy-btn', 'n_clicks'),
    State('year-dropdown', 'value'),
    State('race-dropdown', 'value'),
    State('session-dropdown', 'value'),
    State('strategy-driver-dropdown', 'value'),
)
def load_strategy_data(n_clicks, year, race, session, driver):
    empty_fig = go.Figure()
    hidden = {'display': 'none'}

    if not n_clicks or not driver or session != 'R':
        return None, '', empty_fig, hidden, hidden

    try:
        f1_session = load_session(year, race, session)
        laps = f1_session.laps

        # Get race length
        total_laps = int(laps['LapNumber'].max())

        # Get degradation data
        deg_data = get_race_degradation_data(f1_session)
        if not deg_data:
            return None, html.P("No degradation data available for this race.",
                                style={'color': 'red'}), empty_fig, hidden, hidden

        # Get pit stop stats
        pit_stats = get_pit_stop_stats(f1_session)

        # Build degradation models for simulation
        models = build_degradation_model(deg_data)

        # Get actual strategy for comparison
        actual = get_driver_actual_strategy(f1_session, driver)

        # Available compounds
        available_compounds = list(deg_data.keys())

        # Store state
        state = {
            'year': year,
            'race': race,
            'driver': driver,
            'total_laps': total_laps,
            'pit_loss': pit_stats['avg_pit_time'],
            'available_compounds': available_compounds,
            'degradation': deg_data,
            'models': {c: {'base_time': m['base_time'], 'deg_rate': m['deg_rate']}
                       for c, m in models.items()},
            'actual_strategy': actual,
        }

        # Race info panel
        actual_stints_text = ""
        if actual and actual['stints']:
            stint_parts = []
            for s in actual['stints']:
                stint_parts.append(f"{s['compound']}({s['laps']}L)")
            actual_stints_text = " → ".join(stint_parts)

        race_info = html.Div([
            html.Div([
                html.Div([
                    html.Strong("Race Length: "),
                    html.Span(f"{total_laps} laps"),
                ], className='info-item'),
                html.Div([
                    html.Strong("Avg Pit Loss: "),
                    html.Span(f"~{pit_stats['avg_pit_time']:.1f}s"),
                ], className='info-item'),
                html.Div([
                    html.Strong("Compounds Available: "),
                    html.Span(", ".join(available_compounds)),
                ], className='info-item'),
                html.Div([
                    html.Strong("Rule: "),
                    html.Span("Must use at least 2 different compounds"),
                ], className='info-item'),
            ], className='race-info-grid'),
            html.Div([
                html.Strong(f"{driver}'s Actual Strategy: "),
                html.Span(actual_stints_text),
            ], style={'marginTop': '10px'}) if actual_stints_text else None,
        ], className='race-info-card')

        # Degradation chart
        deg_fig = go.Figure()
        for compound, data in deg_data.items():
            color = COMPOUND_COLORS.get(compound, '#888888')
            deg_fig.add_trace(go.Scatter(
                x=data['tyre_life'],
                y=data['avg_lap_time'],
                mode='lines+markers',
                name=compound,
                line=dict(color=color, width=3),
                marker=dict(size=6, color=color,
                            line=dict(width=1, color='#333') if compound == 'HARD' else dict(width=0)),
                hovertemplate=(
                    f"<b>{compound}</b><br>"
                    "Tyre Life: %{x} laps<br>"
                    "Avg Lap Time: %{y:.3f}s<extra></extra>"
                ),
            ))

            # Add model trendline
            model = models[compound]
            x_trend = np.linspace(min(data['tyre_life']), max(data['tyre_life']), 50)
            y_trend = model['base_time'] + model['deg_rate'] * x_trend
            deg_fig.add_trace(go.Scatter(
                x=x_trend, y=y_trend,
                mode='lines', name=f'{compound} trend',
                line=dict(color=color, width=1, dash='dash'),
                showlegend=False,
                hoverinfo='skip',
            ))

        deg_fig.update_layout(
            title="Tire Degradation Curves (from race data)",
            xaxis_title="Tyre Life (laps)",
            yaxis_title="Lap Time (seconds)",
            height=400,
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#2d2d2d',
            font=dict(color='#ffffff'),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=13),
            ),
            xaxis=dict(gridcolor='#444'),
            yaxis=dict(gridcolor='#444'),
        )

        return state, race_info, deg_fig, {'display': 'block'}, {'display': 'block'}

    except Exception as e:
        return None, html.P(f"Error loading race data: {str(e)}", style={'color': 'red'}), \
            empty_fig, hidden, hidden


@callback(
    Output('stint-inputs-container', 'children'),
    Output('num-stints-store', 'data'),
    Input('add-stint-btn', 'n_clicks'),
    Input('remove-stint-btn', 'n_clicks'),
    State('num-stints-store', 'data'),
)
def update_stint_count(add_clicks, remove_clicks, current_count):
    triggered = ctx.triggered_id
    if triggered == 'add-stint-btn' and current_count < MAX_STINTS:
        current_count += 1
    elif triggered == 'remove-stint-btn' and current_count > 2:
        current_count -= 1

    rows = [create_stint_row(i) for i in range(1, current_count + 1)]
    return rows, current_count


@callback(
    Output('lap-count-validation', 'children'),
    Input({'type': 'stint-laps', 'index': ALL}, 'value'),
    State('strategy-state', 'data'),
)
def validate_lap_count(stint_laps, state):
    if not state:
        return ''

    total_laps = state['total_laps']
    filled = [v for v in stint_laps if v is not None and v != '']
    planned_laps = sum(int(v) for v in filled)

    if not filled:
        return html.Span(f"Enter lap counts (race is {total_laps} laps)",
                         style={'color': '#aaa'})

    if planned_laps == total_laps:
        return html.Span(f"Total: {planned_laps} / {total_laps} laps  ✓",
                         style={'color': '#4CAF50', 'fontWeight': 'bold'})
    elif planned_laps < total_laps:
        return html.Span(f"Total: {planned_laps} / {total_laps} laps  ({total_laps - planned_laps} remaining)",
                         style={'color': '#FFC300'})
    else:
        return html.Span(f"Total: {planned_laps} / {total_laps} laps  (exceeds race by {planned_laps - total_laps}!)",
                         style={'color': '#FF3333'})


@callback(
    Output('simulation-results', 'children'),
    Input('simulate-btn', 'n_clicks'),
    State({'type': 'stint-compound', 'index': ALL}, 'value'),
    State({'type': 'stint-laps', 'index': ALL}, 'value'),
    State('strategy-state', 'data'),
    State('strategy-history', 'data'),
)
def run_simulation(n_clicks, compounds, laps_per_stint, state, history):
    if not n_clicks or not state:
        return ''

    # Validate inputs
    if not compounds or not laps_per_stint:
        return html.P("Please fill in your strategy.", style={'color': 'red'})

    # Build stints list
    stints = []
    for compound, laps_val in zip(compounds, laps_per_stint):
        if compound is None or laps_val is None or laps_val == '':
            return html.P("Please fill in all stint details.", style={'color': 'red'})
        stints.append({'compound': compound, 'laps': int(laps_val)})

    total_planned = sum(s['laps'] for s in stints)
    total_race_laps = state['total_laps']

    if total_planned != total_race_laps:
        return html.P(
            f"Total planned laps ({total_planned}) must equal race distance ({total_race_laps}).",
            style={'color': 'red'}
        )

    # Check 2-compound rule
    unique_compounds = set(s['compound'] for s in stints)
    if len(unique_compounds) < 2:
        return html.P("You must use at least 2 different tire compounds!", style={'color': 'red'})

    # Rebuild models from stored state
    models = {}
    for compound, model_data in state['models'].items():
        models[compound] = {
            'base_time': model_data['base_time'],
            'deg_rate': model_data['deg_rate'],
            'type': 'linear',
        }

    pit_loss = state['pit_loss']

    # Run simulation
    sim_results = simulate_strategy(models, stints, pit_loss, total_race_laps)

    # Get actual strategy data
    actual = state['actual_strategy']

    # Calculate totals
    user_total = sum(r['time_sec'] for r in sim_results)
    actual_total = actual['total_time'] if actual else 0

    # --- Build results visualization ---

    # 1. Lap Time Comparison Chart
    lap_fig = go.Figure()

    # User's estimated lap times
    user_laps = [r['lap'] for r in sim_results]
    user_times = [r['time_sec'] for r in sim_results]
    user_compounds = [r['compound'] for r in sim_results]

    lap_fig.add_trace(go.Scatter(
        x=user_laps, y=user_times,
        mode='lines',
        name='Your Strategy',
        line=dict(color='#00BFFF', width=2.5),
        hovertemplate="Lap %{x}<br>Time: %{y:.3f}s<br>%{customdata}<extra>Your Strategy</extra>",
        customdata=user_compounds,
    ))

    # Actual lap times
    if actual and actual['lap_times']:
        actual_laps_x = [lt['lap'] for lt in actual['lap_times']]
        actual_times_y = [lt['time_sec'] for lt in actual['lap_times']]
        actual_compounds_cd = [lt['compound'] for lt in actual['lap_times']]

        lap_fig.add_trace(go.Scatter(
            x=actual_laps_x, y=actual_times_y,
            mode='lines',
            name=f"{state['driver']} Actual",
            line=dict(color='#FF6B6B', width=2.5),
            hovertemplate="Lap %{x}<br>Time: %{y:.3f}s<br>%{customdata}<extra>Actual</extra>",
            customdata=actual_compounds_cd,
        ))

    # Add pit stop markers for user strategy
    user_pit_laps = [r['lap'] for r in sim_results if r['is_pit_lap']]
    for pit_lap in user_pit_laps:
        lap_fig.add_vline(x=pit_lap, line_dash="dash", line_color="#00BFFF",
                          line_width=1, opacity=0.6)

    # Add pit stop markers for actual strategy
    if actual and actual['pit_laps']:
        for pit in actual['pit_laps']:
            lap_fig.add_vline(x=pit['lap'], line_dash="dash", line_color="#FF6B6B",
                              line_width=1, opacity=0.6)

    # Add compound background bands for user strategy
    stint_start = 1
    for stint in stints:
        color = COMPOUND_COLORS.get(stint['compound'], '#888')
        lap_fig.add_vrect(
            x0=stint_start - 0.5, x1=stint_start + stint['laps'] - 0.5,
            fillcolor=color, opacity=0.08, layer="below", line_width=0,
        )
        stint_start += stint['laps']

    lap_fig.update_layout(
        title="Lap Time Comparison: Your Strategy vs Actual",
        xaxis_title="Lap Number",
        yaxis_title="Lap Time (seconds)",
        height=450,
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#2d2d2d',
        font=dict(color='#ffffff'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(gridcolor='#444'),
        yaxis=dict(gridcolor='#444'),
    )

    # 2. Cumulative Time Gap Chart
    gap_fig = go.Figure()

    if actual and actual['lap_times']:
        # Build cumulative times for both strategies
        # Align on common laps
        actual_times_dict = {lt['lap']: lt['time_sec'] for lt in actual['lap_times']}
        user_times_dict = {r['lap']: r['time_sec'] for r in sim_results}

        common_laps = sorted(set(actual_times_dict.keys()) & set(user_times_dict.keys()))

        if common_laps:
            cum_diff = []
            running_diff = 0
            for lap in common_laps:
                running_diff += user_times_dict[lap] - actual_times_dict[lap]
                cum_diff.append(running_diff)

            gap_fig.add_trace(go.Scatter(
                x=common_laps, y=cum_diff,
                mode='lines',
                name='Cumulative Gap',
                line=dict(color='#FFD700', width=2.5),
                fill='tozeroy',
                fillcolor='rgba(255, 215, 0, 0.1)',
                hovertemplate="Lap %{x}<br>Gap: %{y:+.3f}s<extra></extra>",
            ))

            gap_fig.add_hline(y=0, line_dash="solid", line_color="#888", line_width=1)

    gap_fig.update_layout(
        title="Cumulative Time Gap (+ = you're slower)",
        xaxis_title="Lap Number",
        yaxis_title="Time Difference (seconds)",
        height=350,
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#2d2d2d',
        font=dict(color='#ffffff'),
        xaxis=dict(gridcolor='#444'),
        yaxis=dict(gridcolor='#444'),
    )

    # 3. Summary stats
    diff = user_total - actual_total if actual_total > 0 else 0
    diff_sign = "+" if diff > 0 else ""
    diff_label = "slower" if diff > 0 else "faster"
    diff_color = '#FF6B6B' if diff > 0 else '#4CAF50'

    user_stops_text = []
    stint_start = 0
    for i, stint in enumerate(stints):
        if i < len(stints) - 1:
            pit_lap = stint_start + stint['laps']
            next_compound = stints[i + 1]['compound']
            user_stops_text.append(f"L{pit_lap} ({stint['compound'][0]}→{next_compound[0]})")
        stint_start += stint['laps']

    actual_stops_text = []
    if actual and actual['pit_laps']:
        for pit in actual['pit_laps']:
            actual_stops_text.append(
                f"L{pit['lap']} ({pit['from_compound'][0]}→{pit['to_compound'][0]})"
            )

    summary = html.Div([
        html.Hr(style={'borderColor': '#444'}),
        html.H4("Results Summary", style={'marginBottom': '15px'}),
        html.Div([
            html.Div([
                html.Div([
                    html.Strong("Your Total Time"),
                    html.Br(),
                    html.Span(format_race_time(user_total),
                              style={'fontSize': '1.4em', 'color': '#00BFFF'}),
                ], className='result-stat'),
                html.Div([
                    html.Strong(f"{state['driver']}'s Actual Time"),
                    html.Br(),
                    html.Span(
                        format_race_time(actual_total) if actual_total > 0 else "N/A",
                        style={'fontSize': '1.4em', 'color': '#FF6B6B'}
                    ),
                ], className='result-stat'),
                html.Div([
                    html.Strong("Difference"),
                    html.Br(),
                    html.Span(
                        f"{diff_sign}{abs(diff):.3f}s ({diff_label})"
                        if actual_total > 0 else "N/A",
                        style={'fontSize': '1.4em', 'color': diff_color}
                    ),
                ], className='result-stat'),
            ], className='results-grid'),
            html.Div([
                html.Div([
                    html.Strong("Your Pit Stops: "),
                    html.Span(", ".join(user_stops_text) if user_stops_text else "None"),
                ]),
                html.Div([
                    html.Strong(f"{state['driver']}'s Actual Stops: "),
                    html.Span(", ".join(actual_stops_text) if actual_stops_text else "None"),
                ]),
            ], style={'marginTop': '15px'}),
        ], className='results-card'),
    ])

    return html.Div([
        summary,
        dcc.Graph(figure=lap_fig),
        dcc.Graph(figure=gap_fig),
    ])


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8050, debug=True, dev_tools_ui=False)
