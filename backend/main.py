from flask import Flask, jsonify, request, redirect, url_for, session
from flask_cors import CORS
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a real secret key
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False # Set to True in production with HTTPS

CORS(app)

# This is a placeholder for a more secure way to store credentials
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
API_SERVICE_NAME = 'drive'
API_VERSION = 'v3'
REDIRECT_URI = 'http://localhost:5001/oauth2callback'

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

    return redirect(url_for('list_files'))


if __name__ == '__main__':
    # This is for local development only.
    # In a production environment, use a proper WSGI server.
    app.run(debug=True, port=5001)
