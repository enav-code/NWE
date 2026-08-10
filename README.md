# Keeply

Universal Asset & Document Manager — upload, extract, organize, remind.

## Run

```powershell
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000.

The MVP uses SQLite and a local upload directory. Upload a receipt or invoice to create an asset record; the extraction step is intentionally lightweight and ready to be replaced with a provider-backed document model.

## Google sign-in

OAuth settings are loaded from the local `.env` file. In Google Cloud Console, add both authorized redirect URIs exactly. Google treats `localhost` and `127.0.0.1` as different hosts:

`http://127.0.0.1:5000/auth/google/callback`

`http://localhost:5000/auth/google/callback`

The application never places the client secret in browser code. For production, use a production HTTPS callback URI and a strong `SECRET_KEY`.

## PythonAnywhere

On PythonAnywhere, create a `.env` file in the project directory or define the same variables in the Web app WSGI environment. Replace `yourusername` with the PythonAnywhere account name:

```text
APP_BASE_URL=https://yourusername.pythonanywhere.com
GOOGLE_REDIRECT_URI=https://yourusername.pythonanywhere.com/auth/google/callback
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
SECRET_KEY=your-long-random-secret
```

Add the `GOOGLE_REDIRECT_URI` value to the Google OAuth client's **Authorized redirect URIs**, then reload the PythonAnywhere web app. Do not use the local `127.0.0.1` callback in production.
