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

OAuth settings are loaded from the local `.env` file. In Google Cloud Console, add this exact authorized redirect URI:

`http://127.0.0.1:5000/auth/google/callback`

The application never places the client secret in browser code. For production, use a production HTTPS callback URI and a strong `SECRET_KEY`.
