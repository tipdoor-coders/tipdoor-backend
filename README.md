# Tipdoor Backend

Backend for tipdoor made with Django

## 1. Create a virtual environment

Create a folder and enter the following into the terminal to setup and activate

```
py -m venv venv
venv\Scripts\activate
```

## 2. Install dependencies

```
pip install -r requirements.txt
```

## 3. Setup configuration

Create a file in the tipdoor/ folder called `config.py` with the following template:

```
pg_password = "your_postgres_password"
```

## 4. Setup database

Create a database in postgresql

```
CREATE DATABASE tipdoor
```

To create and apply migrations, move to the tipdoor/ folder and use the following commands:

```
py manage.py makemigrations
py manage.py migrate
```

## 5. Create an admin user

In the tipdoor/ directory, type the following:

```
py manage.py createsuperuser
```

Enter the prompted details to create and admin user. This can be accessed later when the app is running by going to http://127.0.0.1:8000/admin/

## 6. Start the server

Start the server by moving to the tipdoor/ folder and typing:

```
py manage.py runserver
```
