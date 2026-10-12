# Sector Performance Dashboard

Streamlit dashboard for Indian equity sector performance (Infrastructure, Roads,
Paints, Civil Construction, Defence) vs the Nifty 50. Pick a date range and
sectors; every chart's table can be downloaded as CSV.

Access is protected by a single shared access key (`APP_PASSWORD`).

## Run locally

```bash
python -m venv venv
venv/Scripts/python -m pip install -r requirements.txt
venv/Scripts/python -m streamlit run app.py
```

The access key is read from `.streamlit/secrets.toml` (not committed):

```toml
APP_PASSWORD = "your-access-key"
```

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository (private is fine).
2. Go to https://share.streamlit.io, sign in with GitHub, click **Create app**.
3. Choose the repository, branch `main`, main file `app.py`.
4. Under **Advanced settings**: Python 3.12, and paste into **Secrets**:
   `APP_PASSWORD = "your-access-key"`
5. Deploy. In the app's **Share** settings, make the app **public** so teammates
   only need the link + access key (no email/Google sign-in).

To change the key later: app menu → **Settings → Secrets**, edit, save.

## Editing stocks

Sector and ticker lists live in `SECTORS` at the top of `analysis.py`.
