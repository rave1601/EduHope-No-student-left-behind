EduHope — setup for your friend
================================

This share package contains the EduHope Streamlit app, its pretrained models,
and a small demo CSV. It intentionally does not include the live SQLite database
(accounts, imported students, and support plans) or the full academic dataset.
The app creates a fresh local database on first run.

Run on Windows
--------------
1. Install Python 3.10 or newer.
2. Open PowerShell in the extracted project folder.
3. Run:  py -m venv .venv
4. Run:  .venv\Scripts\Activate.ps1
5. Run:  python -m pip install -r requirements.txt
6. Run:  streamlit run app.py
7. On the login screen, expand Register and create a teacher account.
8. In Students, import teacher_demo_dataset.csv to load the included demo records.

The model files are included, so prediction works without retraining. The training
and database seeding scripts are included for reference, but require an authorized
copy of dataset.csv, which is not included in this share package. Do not copy the
live eduhope.db, eduhope.db-wal, or eduhope.db-shm into a shared archive.
