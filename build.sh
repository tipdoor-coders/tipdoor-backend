#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

cd tipdoor

python manage.py collectstatic --no-input

python manage.py migrate

if [[ $CREATE_SUPERUSER ]];
then
  python manage.py createsuperuser --no-input
fi