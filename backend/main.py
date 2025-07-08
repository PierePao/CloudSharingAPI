import os
import tempfile
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, jsonify, request, redirect, url_for, session, send_from_directory
from flask_session import Session
from flask_cors import CORS
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__, static_folder='../')
app.config["SECRET_KEY"] = "a8d9f6c5b7e3a2d1f0c8b5a3d2e1f4g6h7j8k9l0m1n2o3p4q5r6s7t8"
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flask_session')

# Create the session directory if it doesn't exist
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

Session(app)

CORS(app, supports_credentials=True)

# This is a placeholder for a more secure way to store credentials
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]
API_SERVICE_NAME = 'drive'
API_VERSION = 'v3'
REDIRECT_URI = 'http://localhost:5001/oauth2callback'

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(app.static_folder, 'assets'), filename)

@app.route('/files', methods=['GET'])
def list_files():
    """Lists the user's files in Google Drive."""
    if 'credentials' not in session:
        return redirect('authorize')

    credentials = Credentials(**session['credentials'])

    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)

        # Call the Drive v3 API
        results = service.files().list(
            pageSize=10, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            return jsonify({"message": "No files found."})
        else:
            return jsonify(items)
    except Exception as e:
        # If credentials are bad, remove them from the session and re-authorize
        session.pop('credentials', None)
        return jsonify({"error": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'credentials' not in session:
        return jsonify({"error": "User not authenticated"}), 401

    if 'files' not in request.files:
        return jsonify({"error": "No file part"}), 400

    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({"error": "No selected file"}), 400

    credentials = Credentials(**session['credentials'])
    service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)

    uploaded_files_info = []
    for file in files:
        try:
            # It's good practice to save the file to a temporary location first
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, file.filename)
            file.save(temp_path)

            file_metadata = {'name': file.filename}
            media = MediaFileUpload(temp_path, mimetype=file.mimetype, resumable=True)
            created_file = service.files().create(body=file_metadata,
                                                media_body=media,
                                                fields='id, name').execute()
            uploaded_files_info.append(created_file)
            
            # Clean up the temporary file
            os.remove(temp_path)

        except Exception as e:
            return jsonify({"error": f"An error occurred during upload: {e}"}), 500
    
    return jsonify({"message": "Files uploaded successfully", "uploaded_files": uploaded_files_info}), 200

@app.route('/authorize')
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI)

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')

    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store the credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('credentials', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    # This is for local development only.
    # In a production environment, use a proper WSGI server.
    app.run(debug=True, port=5001)
