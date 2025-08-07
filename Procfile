release: python database_setup.py
web:  gunicorn -w 4 -b 0.0.0.0:$PORT crmlogic:app

