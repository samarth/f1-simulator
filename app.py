import dash
from dash import dcc, html, Input, Output, callback, State
import plotly.graph_objects as go
import plotly.express as px
import fastf1
import fastf1.plotting
import pandas as pd
import numpy as np

# Initialize FastF1 plotting
fastf1.plotting.setup_mpl()

# Initialize Dash app
app = dash.Dash(__name__)

# Expose Flask server for Gunicorn
server = app.server

# Define CSS styles for light and dark themes
light_theme = {
    'backgroundColor': '#ffffff',
    'color': '#000000',
    'cardBackground': '#f8f9fa',
    'borderColor': '#dee2e6'
}

dark_theme = {
    'backgroundColor': '#1a1a1a',
    'color': '#ffffff',
    'cardBackground': '#2d2d2d',
    'borderColor': '#495057'
}

# Define app layout
app.layout = html.Div(id='main-container', children=[
    # Store for theme state
    dcc.Store(id='theme-store', data='light'),
    
    # Header with title and theme toggle
    html.Div([
        html.H1("F1 Telemetry Analysis Dashboard", 
                style={'textAlign': 'center', 'marginBottom': 30, 'flex': '1'}),
        html.Div([
            html.Label("🌙 Dark Mode", style={'marginRight': '10px'}),
            dcc.Checklist(
                id='theme-toggle',
                options=[{'label': '', 'value': 'dark'}],
                value=[],
                style={'display': 'inline-block'}
            )
        ], style={'position': 'absolute', 'top': '20px', 'right': '20px'})
    ], style={'position': 'relative', 'marginBottom': '20px'}),
    
    # Controls section
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
    ], style={'marginBottom': 30}),
    
    # Loading indicator
    dcc.Loading(
        id="loading",
        children=[
            # Driver selection
            html.Div([
                html.Label("Select Drivers to Compare:"),
                dcc.Dropdown(
                    id='driver-dropdown',
                    multi=True,
                    value=['NOR', 'HAM', 'LAW']
                )
            ], style={'marginBottom': 30}),
            
            # Fastest lap summary
            html.Div(id='lap-summary', style={'marginBottom': 30}),
            
            # Track visualization
            html.Div([
                dcc.Graph(id='track-visualization')
            ]),
            
            # Speed comparison
            html.Div([
                dcc.Graph(id='speed-comparison')
            ])
        ]
    )
])

@callback(
    Output('driver-dropdown', 'options'),
    Output('driver-dropdown', 'value'),
    Input('year-dropdown', 'value'),
    Input('race-dropdown', 'value'),
    Input('session-dropdown', 'value')
)
def update_drivers(year, race, session):
    try:
        # Load session to get available drivers
        f1_session = fastf1.get_session(year, race, session)
        f1_session.load()
        
        drivers = f1_session.laps['Driver'].unique()
        driver_options = [{'label': driver, 'value': driver} for driver in sorted(drivers)]
        
        # Default to first 3 drivers if available
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
    Input('driver-dropdown', 'value'),
    Input('theme-store', 'data')
)
def update_analysis(year, race, session, selected_drivers, theme):
    if not selected_drivers:
        empty_fig = go.Figure()
        theme_settings = get_plotly_theme(theme)
        empty_fig.update_layout(**theme_settings['layout'])
        return "Please select drivers to analyze.", empty_fig, empty_fig
    
    try:
        # Load session data
        f1_session = fastf1.get_session(year, race, session)
        f1_session.load()
        laps = f1_session.laps
        
        # Get fastest lap overall
        fastest_lap = laps.pick_fastest()
        
        # Format lap time properly
        def format_lap_time(timedelta_obj):
            """Convert timedelta to MM:SS.sss format"""
            total_seconds = timedelta_obj.total_seconds()
            minutes = int(total_seconds // 60)
            seconds = total_seconds % 60
            return f"{minutes}:{seconds:06.3f}"
        
        fastest_time_formatted = format_lap_time(fastest_lap['LapTime'])
        
        # Create summary
        summary = html.Div([
            html.H3(f"{year} {race} GP - {session} Session Analysis"),
            html.P(f"Fastest Lap: {fastest_lap['Driver']} - {fastest_time_formatted} (Lap {fastest_lap['LapNumber']:.0f})")
        ])
        
        # Prepare data for selected drivers
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
        
        # Create track visualization
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
                        showscale=first_trace,  # Only show colorbar for first trace
                        colorbar=dict(
                            title="Speed (km/h)",
                            x=1.15,  # Move colorbar further right
                            len=0.7
                        ) if first_trace else None
                    ),
                    name=f"{driver} - {format_lap_time(data['lap_time'])}",
                    hovertemplate=f"<b>{driver}</b><br>" +
                                  "Speed: %{marker.color:.1f} km/h<br>" +
                                  "X: %{x:.0f}m<br>" +
                                  "Y: %{y:.0f}m<extra></extra>"
                ))
                first_trace = False
        
        # Apply theme to track figure
        theme_settings = get_plotly_theme(theme)
        track_fig.update_layout(
            title=f"Track Map - Fastest Laps Comparison",
            xaxis_title="Track Position X (m)",
            yaxis_title="Track Position Y (m)",
            showlegend=True,
            height=600,
            xaxis=dict(scaleanchor="y", scaleratio=1),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.15,
                xanchor="center",
                x=0.5
            ),
            margin=dict(l=50, r=200, t=80, b=100),
            **theme_settings['layout']
        )
        
        # Create speed comparison
        speed_fig = go.Figure()
        
        if len(driver_data) > 1:
            # Interpolate speed data for comparison
            common_distance = None
            speed_traces = {}
            
            for driver, data in driver_data.items():
                if 'telemetry' in data:
                    telemetry = data['telemetry']
                    distance = telemetry['Distance']
                    speed = telemetry['Speed']
                    
                    if common_distance is None:
                        common_distance = np.linspace(distance.min(), distance.max(), 200)
                    
                    # Interpolate speed to common distance points
                    speed_interp = np.interp(common_distance, distance, speed)
                    speed_traces[driver] = speed_interp
                    
                    speed_fig.add_trace(go.Scatter(
                        x=common_distance,
                        y=speed_interp,
                        mode='lines',
                        name=f"{driver} - {format_lap_time(data['lap_time'])}",
                        line=dict(color=data['color'], width=3),
                        hovertemplate=f"<b>{driver}</b><br>" +
                                      "Distance: %{x:.0f}m<br>" +
                                      "Speed: %{y:.1f} km/h<extra></extra>"
                    ))
            
            # Add speed difference highlighting if we have exactly 2 drivers
            if len(speed_traces) == 2:
                drivers_list = list(speed_traces.keys())
                speed1 = speed_traces[drivers_list[0]]
                speed2 = speed_traces[drivers_list[1]]
                
                speed_fig.add_trace(go.Scatter(
                    x=common_distance,
                    y=np.maximum(speed1, speed2),
                    fill=None,
                    mode='lines',
                    line_color='rgba(0,0,0,0)',
                    showlegend=False,
                    hoverinfo='skip'
                ))
                
                speed_fig.add_trace(go.Scatter(
                    x=common_distance,
                    y=np.minimum(speed1, speed2),
                    fill='tonexty',
                    mode='lines',
                    line_color='rgba(0,0,0,0)',
                    fillcolor='rgba(0,255,0,0.2)',
                    name='Speed Difference',
                    hovertemplate=f"Speed Difference: %{{customdata:.1f}} km/h<extra></extra>",
                    customdata=np.abs(speed1 - speed2)
                ))
        
        speed_fig.update_layout(
            title="Speed Comparison Along Track Distance",
            xaxis_title="Track Distance (m)",
            yaxis_title="Speed (km/h)",
            showlegend=True,
            height=400,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=50, r=50, t=80, b=50),
            **theme_settings['layout']
        )
        
        return summary, track_fig, speed_fig
        
    except Exception as e:
        error_msg = f"Error loading data: {str(e)}"
        empty_fig = go.Figure()
        empty_fig.add_annotation(
            text=error_msg,
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle'
        )
        # Apply theme to error figures
        theme_settings = get_plotly_theme(theme)
        empty_fig.update_layout(**theme_settings['layout'])
        return error_msg, empty_fig, empty_fig

# Theme management callbacks
@callback(
    Output('theme-store', 'data'),
    Input('theme-toggle', 'value')
)
def update_theme_store(toggle_value):
    return 'dark' if 'dark' in toggle_value else 'light'

@callback(
    Output('main-container', 'style'),
    Input('theme-store', 'data')
)
def update_theme_styles(theme):
    current_theme = dark_theme if theme == 'dark' else light_theme
    return {
        'backgroundColor': current_theme['backgroundColor'],
        'color': current_theme['color'],
        'minHeight': '100vh',
        'padding': '20px',
        'fontFamily': 'Arial, sans-serif'
    }

# Update chart themes based on selected theme
def get_plotly_theme(theme):
    if theme == 'dark':
        return {
            'layout': {
                'plot_bgcolor': '#2d2d2d',
                'paper_bgcolor': '#1a1a1a',
                'font': {'color': '#ffffff'},
                'xaxis': {'gridcolor': '#555555', 'color': '#ffffff'},
                'yaxis': {'gridcolor': '#555555', 'color': '#ffffff'}
            }
        }
    else:
        return {
            'layout': {
                'plot_bgcolor': '#ffffff',
                'paper_bgcolor': '#ffffff',
                'font': {'color': '#000000'},
                'xaxis': {'gridcolor': '#dddddd', 'color': '#000000'},
                'yaxis': {'gridcolor': '#dddddd', 'color': '#000000'}
            }
        }

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=True)