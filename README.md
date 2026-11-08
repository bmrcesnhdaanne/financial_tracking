# Personal Financial Statement

A Streamlit dashboard for tracking net worth from account-balance snapshots: balance sheet over time,
growth by account, allocation, real estate equity, retirement withdrawals and debt payoff.

## Run it locally

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

The app lists every `.csv` in this folder in the sidebar's **Statement file** menu. A file named
`<statement>_plan.csv` next to a statement file is loaded as its retirement plan.

## Data files

Data files are **not** stored in Git (see `.gitignore`). On a deployed app, upload them in the sidebar.

**Statement file** (required). One row per account per snapshot date; debts are negative.

Without a plan file, the sidebar's Retirement section takes a yearly withdrawal and pension/Social Security amount.

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repository. Check that no data files were committed (`git ls-files`).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, and choose **Create app**.
3. Pick the repository and branch, and set the main file path to `dashboard.py`.
4. Under **Advanced settings**, choose Python 3.12.
5. Deploy. Streamlit installs the packages in `requirements.txt` and applies the theme in `.streamlit/config.toml`.
6. In the app's **Settings → Sharing**, make the app private and invite only the people who should see it.

To update the app, push to the same branch; it redeploys automatically.

### Privacy

- Uploaded files stay in the app's memory for that session and are not saved to the server.
- Keep the GitHub repository private. Even without data files, the code shows which accounts and fields you track.
- Never commit statement or plan files. If one is committed by mistake, removing it in a later commit is not enough:
  it stays in the Git history.

## Files

| file | purpose |
|---|---|
| `dashboard.py` | the app |
| `requirements.txt` | Python packages for deployment |
| `.streamlit/config.toml` | theme and server settings |
| `.gitignore` | keeps data files out of Git |
