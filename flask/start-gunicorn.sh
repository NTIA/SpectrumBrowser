gunicorn -w 1 -k flask_sockets.worker flaskr:app  -b '0.0.0.0:8000' --debug --log-file - --error-logfile -
#gunicorn -w 1 -k flask_sockets.worker flaskr:app   --debug --log-file - --error-logfile -
