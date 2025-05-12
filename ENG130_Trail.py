import dash
from dash import html, dcc, Output, Input, State
import numpy as np
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# Define scope and auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Open sheet
sheet = client.open("STACK").sheet1  # assumes it's the first sheet

# Consistently define a single to_float helper function to use throughout the app
def to_float(val):
    """Convert value to float, return None if it fails"""
    try:
        if val is None or val == "":
            return None
        return float(val)
    except (ValueError, TypeError):
        return None

def log_attempt(student_id, f1, f2, f3, a1, a2, a3, score):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = [now, student_id, f1, f2, f3, a1, a2, a3, score]

    # Define the expected header
    header = ["Timestamp", "Student ID", "F1", "F2", "F3", "Ans1", "Ans2", "Ans3", "Score", "Status"]

    # Read the first row
    existing_header = sheet.row_values(1)

    # If the sheet is empty or header doesn't match, insert header
    if existing_header != header:
        if len(existing_header) == 0:
            sheet.insert_row(header, 1)
        else:
            print("Warning: Existing header mismatch. Header not overwritten.")

    # Append the student row
    sheet.append_row(row)

app = dash.Dash(__name__)
server = app.server
app.title = "Resultant Force Calculator"

# Utility to generate new force values and answers
def generate_problem():
    F1 = 350 + random.randint(0, 20)
    F2 = 125 + random.randint(0, 15)
    F3 = 200 + random.randint(0, 15)

    Ans1_A = np.sqrt(F2**2 + F3**2 - 2 * F2 * F3 * np.cos(np.deg2rad(30)))
    IntTheta = np.rad2deg(np.arcsin(F2 * np.sin(np.deg2rad(30)) / Ans1_A))
    Ans2_A = np.sqrt(Ans1_A**2 + F1**2 - 2 * Ans1_A * F1 * np.cos(np.deg2rad(60 - IntTheta)))
    ResultantDeg = np.rad2deg(np.arcsin(Ans1_A * np.sin(np.deg2rad(60 - IntTheta)) / Ans2_A))
    Ans3_A = 90 + 60 + ResultantDeg

    # Ensure all answers are properly calculated and rounded
    problem = {
        "F1": F1,
        "F2": F2,
        "F3": F3,
        "Ans1": round(Ans1_A, 3),
        "Ans2": round(Ans2_A, 3),
        "Ans3": round(Ans3_A, 3),
    }
    
    # Verify all problem data is properly generated
    for key in ["F1", "F2", "F3", "Ans1", "Ans2", "Ans3"]:
        if problem[key] is None:
            print(f"Warning: {key} is None during problem generation!")
            # Use a default value instead of None
            if key.startswith("F"):
                problem[key] = 200  # Default force value
            else:
                problem[key] = 100.0  # Default answer
    
    return problem

def save_attempt(student_id, f1, f2, f3, a1, a2, a3, score, status):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = [now, student_id, f1, f2, f3, a1, a2, a3, score, status]

    # Header as before
    header = ["Timestamp", "Student ID", "F1", "F2", "F3", "Ans1", "Ans2", "Ans3", "Score", "Status"]
    existing_header = sheet.row_values(1)
    if existing_header != header:
        if len(existing_header) == 0:
            sheet.insert_row(header, 1)

    sheet.append_row(row)

def update_max_score(student_id, f1, f2, f3, a1, a2, a3, score):
    try:
        max_sheet = client.open("STACK").worksheet("MaxScores")
    except gspread.exceptions.WorksheetNotFound:
        max_sheet = client.open("STACK").add_worksheet(title="MaxScores", rows="100", cols="20")

    header = ["Student ID", "F1", "F2", "F3", "Ans1", "Ans2", "Ans3", "Max Score", "Last Updated"]
    existing_header = max_sheet.row_values(1)

    if existing_header != header:
        if not existing_header:
            max_sheet.insert_row(header, 1)

    all_records = max_sheet.get_all_records()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for idx, row in enumerate(all_records, start=2):  # start=2 because of header
        if str(row["Student ID"]).strip().lower() == str(student_id).strip().lower():
            if score > row["Max Score"]:
                max_sheet.update(f"B{idx}:I{idx}", [[f1, f2, f3, a1, a2, a3, score, now]])
            return

    # Not found → insert new row
    new_row = [student_id, f1, f2, f3, a1, a2, a3, score, now]
    max_sheet.append_row(new_row)

# Helper function
def is_close(user, correct, tol=0.005):
    """Check if user answer is close to correct answer within tolerance"""
    try:
        user_val = to_float(user)
        if user_val is None:
            return False
        correct_val = to_float(correct)
        if correct_val is None or correct_val == 0:
            return user_val == 0
        return abs(user_val - correct_val) / correct_val < tol
    except (TypeError, ValueError, ZeroDivisionError):
        return False

# App layout
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    
    html.Div([
        html.Div("Q1.", style={
            'fontSize': '24px',
            'fontWeight': 'bold',
            'marginRight': '20px',
            'marginTop': '50px',
            'textAlign': 'center',
            'color':'red'
        }),
        
        html.Div([
            dcc.Input(id='student-id', type='text', placeholder='Enter Student ID', style={'marginBottom': '10px'}),

            dcc.Store(id='problem-data'),
            dcc.Store(id='show-try-again', data=False),

            html.H2("Vector Resultant Force Question"),

            html.Div(id='force-display', style={'fontWeight': 'bold', 'marginTop': '10px'}),

            html.Img(src='/assets/forces_diagram.png', style={'width': '250px', 'marginTop': '10px'}),

            html.Div([
                html.Label("1. Compute F′ = F₂ + F₃:"),
                dcc.Input(id='ans1', type='number', placeholder='Enter F′ in N'),
                html.Div(id='feedback1', style={'marginTop': '5px'}),
            ]),

            html.Div([
                html.Label("2. Compute Fg = F′ + F₁:"),
                dcc.Input(id='ans2', type='number', placeholder='Enter Fg in N'),
                html.Div(id='feedback2', style={'marginTop': '5px'}),
            ]),

            html.Div([
                html.Label("3. Compute resultant angle from x-axis (°):"),
                dcc.Input(id='ans3', type='number', placeholder='Enter angle in degrees'),
                html.Div(id='feedback3', style={'marginTop': '5px'}),
            ]),

            html.Div([
                html.Button("Check Answers", id='check-btn', n_clicks=0),
                html.Button("Try Again", id='try-btn', n_clicks=0, style={'display': 'none', 'marginLeft': '10px'}),
            ]),
            
            html.Button("Save Progress", id='save-btn', n_clicks=0, style={'marginLeft': '0px'}),
            html.Div(id='last-attempt-info', style={'fontSize': '14px', 'color': '#555'}),
        ], style={'flex': 1})
    ], style={'display': 'flex', 'flexDirection': 'row'})
], style={'maxWidth': '900px', 'margin': '0 auto', 'padding': '20px'})


# Display current forces
@app.callback(
    Output('force-display', 'children'),
    Input('problem-data', 'data')
)
def display_forces(data):
    if data is None:
        return ""
    
    return html.Div([
        html.Span("Given "),
        html.Span(f"𝐅₁ = {data['F1']} N, ", style={'fontWeight': 'bold'}),
        html.Span(f"𝐅₂ = {data['F2']} N, ", style={'fontWeight': 'bold'}),
        html.Span(f"𝐅₃ = {data['F3']} N", style={'fontWeight': 'bold'}),
    ], style={'fontSize': '18px', 'marginBottom': '10px'})


# Show or hide Try Again button
@app.callback(
    Output('try-btn', 'style'),
    Input('show-try-again', 'data')
)
def toggle_try_again(visible):
    if visible:
        return {'display': 'inline-block', 'marginLeft': '10px'}
    return {'display': 'none'}

@app.callback(
    Output('feedback1', 'children'),
    Output('feedback2', 'children'),
    Output('feedback3', 'children'),
    Output('problem-data', 'data'),
    Output('ans1', 'value'),
    Output('ans2', 'value'),
    Output('ans3', 'value'),
    Output('show-try-again', 'data'),
    Output('check-btn', 'disabled'),
    Output('last-attempt-info', 'children'),
    Input('check-btn', 'n_clicks'),
    Input('try-btn', 'n_clicks'),
    Input('url', 'pathname'),
    Input('student-id', 'value'),
    State('ans1', 'value'),
    State('ans2', 'value'),
    State('ans3', 'value'),
    State('problem-data', 'data'),
)
def handle_all(check_clicks, try_clicks, pathname, student_id, a1, a2, a3, data):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    print(f"🔄 Triggered by: {button_id}")

    # 🌐 Initial load
    if button_id == 'url':
        print("🌍 Initial URL load - generating new problem")
        new_problem = generate_problem()
        print(f"📊 New problem data: {new_problem}")
        return '', '', '', new_problem, None, None, None, False, False, ''

    # 💾 Load draft on student ID input
    if button_id == 'student-id' and student_id:
        student_id = str(student_id).strip().lower()
        print(f"🔍 Looking for student ID: {student_id}")
        
        try:
            records = sheet.get_all_records()
            print(f"📚 Found {len(records)} total records")

            # Get all attempts sorted by timestamp (assumes appended order)
            student_attempts = [
                r for r in records
                if str(r.get('Student ID', '')).strip().lower() == student_id
            ]
            print(f"👤 Found {len(student_attempts)} records for this student")

            if not student_attempts:
                print("❌ No saved attempts found for this student")
                return '', '', '', generate_problem(), None, None, None, False, False, "No saved attempt found."

            latest = student_attempts[-1]
            status = str(latest.get("Status", "")).strip().lower()
            print(f"📝 Latest attempt status: {status}")

            # 🟢 Reload only if draft
            score = to_float(latest.get("Score", 0))

            if status == "draft":
                # Ensure we properly handle potentially missing values
                try:
                    print(f"📄 Raw draft data: {latest}")
                    
                    # Important: Calculate actual values based on the forces
                    F1 = int(float(latest.get("F1", 0)))
                    F2 = int(float(latest.get("F2", 0)))
                    F3 = int(float(latest.get("F3", 0)))
                    
                    # First, calculate the expected answers based on the forces
                    Ans1_A = np.sqrt(F2**2 + F3**2 - 2 * F2 * F3 * np.cos(np.deg2rad(30)))
                    IntTheta = np.rad2deg(np.arcsin(F2 * np.sin(np.deg2rad(30)) / Ans1_A))
                    Ans2_A = np.sqrt(Ans1_A**2 + F1**2 - 2 * Ans1_A * F1 * np.cos(np.deg2rad(60 - IntTheta)))
                    ResultantDeg = np.rad2deg(np.arcsin(Ans1_A * np.sin(np.deg2rad(60 - IntTheta)) / Ans2_A))
                    Ans3_A = 90 + 60 + ResultantDeg
                    
                    # Create problem data with the stored values and calculated answers
                    restored_problem = {
                        "F1": F1,
                        "F2": F2,
                        "F3": F3,
                        "Ans1": round(Ans1_A, 3),
                        "Ans2": round(Ans2_A, 3),
                        "Ans3": round(Ans3_A, 3),
                    }
                    
                    print(f"📊 Restored problem with calculated answers: {restored_problem}")
                    
                    # Make sure all the answer values are properly converted to float or None
                    ans1_val = to_float(latest.get("Ans1"))
                    ans2_val = to_float(latest.get("Ans2"))
                    ans3_val = to_float(latest.get("Ans3"))
                    
                    print(f"📊 Student answers: {ans1_val}, {ans2_val}, {ans3_val}")
                    
                    return (
                        '', '', '', restored_problem,
                        ans1_val, ans2_val, ans3_val,
                        False, False,
                        f"📝 Draft loaded for {student_id}."
                    )
                except Exception as e:
                    print(f"❌ Error restoring draft: {e}")
                    # If any conversion errors occur, generate a new problem instead
                    return (
                        '', '', '', generate_problem(),
                        None, None, None,
                        False, False,
                        f"Error loading draft. New question generated."
                    )

            elif status == "final":
                # Determine feedback
                if score == 1.5:
                    feedback = f"✅ Your last attempt was fully correct. Great job!"
                else:
                    feedback = f"ℹ️ Your last score was {score}/1.5. A new question has been generated."

                print("🆕 Final submission found. Generating new problem.")
                new_problem = generate_problem()
                print(f"📊 New problem data: {new_problem}")
                
                return (
                    '', '', '', new_problem,
                    None, None, None,
                    False, False,
                    feedback
                )

            # 🔴 Otherwise, load new problem
            print("❓ Unknown status. Generating new problem.")
            new_problem = generate_problem()
            print(f"📊 New problem data: {new_problem}")
            
            return (
                '', '', '', new_problem,
                None, None, None,
                False, False, f"Previous attempt was final. New question generated."
            )
        
        except Exception as e:
            print(f"❌ Error in student ID lookup: {e}")
            # Fallback to new problem if any error occurs
            new_problem = generate_problem()
            print(f"📊 Fallback new problem data: {new_problem}")
            return (
                '', '', '', new_problem,
                None, None, None,
                False, False, f"Error loading data. New question generated."
            )

    # ✅ Check answers
    if button_id == 'check-btn':
        print("✅ Check button pressed")
        print(f"📝 Answers submitted: a1={a1}, a2={a2}, a3={a3}")
        print(f"🧩 Problem data: {data}")
        
        # Validate input values (entered by student)
        a1_val = to_float(a1)
        a2_val = to_float(a2)
        a3_val = to_float(a3)
        
        if a1_val is None or a2_val is None or a3_val is None:
            print("⚠️ Incomplete answers detected")
            return (
                "⚠️ Please complete all fields.",
                "", "", dash.no_update,
                a1, a2, a3,
                False, False, ""
            )

        # Validate that problem has been generated properly
        required_keys = ['Ans1', 'Ans2', 'Ans3', 'F1', 'F2', 'F3']
        if not isinstance(data, dict) or not all(k in data and data[k] is not None for k in required_keys):
            print("🚨 Incomplete or missing problem data:", data)
            
            # Regenerate based on the forces if possible
            if isinstance(data, dict) and all(k in data and data[k] is not None for k in ['F1', 'F2', 'F3']):
                print("🔄 Regenerating answers from existing forces")
                F1 = int(data['F1'])
                F2 = int(data['F2'])
                F3 = int(data['F3'])
                
                # Calculate answers based on the forces
                Ans1_A = np.sqrt(F2**2 + F3**2 - 2 * F2 * F3 * np.cos(np.deg2rad(30)))
                IntTheta = np.rad2deg(np.arcsin(F2 * np.sin(np.deg2rad(30)) / Ans1_A))
                Ans2_A = np.sqrt(Ans1_A**2 + F1**2 - 2 * Ans1_A * F1 * np.cos(np.deg2rad(60 - IntTheta)))
                ResultantDeg = np.rad2deg(np.arcsin(Ans1_A * np.sin(np.deg2rad(60 - IntTheta)) / Ans2_A))
                Ans3_A = 90 + 60 + ResultantDeg
                
                # Update data with calculated answers
                data = {
                    "F1": F1,
                    "F2": F2,
                    "F3": F3,
                    "Ans1": round(Ans1_A, 3),
                    "Ans2": round(Ans2_A, 3),
                    "Ans3": round(Ans3_A, 3),
                }
                print(f"📊 Regenerated problem data: {data}")
            else:
                print("🆕 Generating completely new problem")
                return (
                    "⚠️ Something went wrong. Please reload the question.",
                    "", "", generate_problem(),
                    None, None, None,
                    False, False, ""
                )

        # Extract expected answers from problem data
        try:
            expected1 = float(data.get('Ans1'))
            expected2 = float(data.get('Ans2'))
            expected3 = float(data.get('Ans3'))
            print(f"✓ Expected answers: {expected1}, {expected2}, {expected3}")
        except (TypeError, ValueError) as e:
            print(f"❌ Error extracting expected answers: {e}")
            return (
                "⚠️ Something went wrong. Please reload the question.",
                "", "", generate_problem(),
                None, None, None,
                False, False, ""
            )

        # Grading
        f1 = "✅ Correct!" if is_close(a1_val, expected1) else f"❌ Incorrect. Expected ≈ {expected1:.3f} N"
        f2 = "✅ Correct!" if is_close(a2_val, expected2) else f"❌ Incorrect. Expected ≈ {expected2:.3f} N"
        f3 = "✅ Correct!" if is_close(a3_val, expected3) else f"❌ Incorrect. Expected ≈ {expected3:.3f}°"

        score = 0
        if is_close(a1_val, expected1): score += 0.5
        if is_close(a2_val, expected2): score += 0.5
        if is_close(a3_val, expected3): score += 0.5

        print(f"📊 Grading results: {f1}, {f2}, {f3}, Score: {score}/1.5")

        if student_id:
            print(f"💾 Saving final attempt for student {student_id}")
            save_attempt(student_id, data['F1'], data['F2'], data['F3'], a1_val, a2_val, a3_val, score, "final")
            update_max_score(student_id, data['F1'], data['F2'], data['F3'], a1_val, a2_val, a3_val, score)

        return f1, f2, f3, data, a1, a2, a3, True, True, ""

    # 🔄 Try again
    if button_id == 'try-btn':
        print("🔄 Try again button pressed - generating new problem")
        new_problem = generate_problem()
        print(f"📊 New problem data: {new_problem}")
        return '', '', '', new_problem, None, None, None, False, False, ""

    raise dash.exceptions.PreventUpdate

#Save Attempt 
@app.callback(
    Output('save-btn', 'children'),
    Input('save-btn', 'n_clicks'),
    State('student-id', 'value'),
    State('ans1', 'value'),
    State('ans2', 'value'),
    State('ans3', 'value'),
    State('problem-data', 'data'),
    prevent_initial_call=True,
)
def save_progress(n_clicks, student_id, a1, a2, a3, data):
    if not student_id or not data:
        print("❌ Save failed: Missing student ID or problem data")
        return "Error Saving"
    
    print(f"💾 Saving draft for student {student_id}")
    print(f"📊 Current problem data: {data}")
    print(f"📝 Student answers: a1={a1}, a2={a2}, a3={a3}")
    
    # Use the to_float function for consistent conversion
    save_attempt(
        student_id,
        data['F1'], data['F2'], data['F3'],
        to_float(a1), to_float(a2), to_float(a3),
        0,  # score
        "draft"
    )
    return "Saved!"


# Run the app
if __name__ == '__main__':
    app.run(debug=True)
