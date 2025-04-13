Project specifications document: https://docs.google.com/document/d/1I36S6lHBOS_8Y0obdqbV9QHCZuPZmXLyRHPsV7EtCxo/edit?tab=t.0

** Initial setup **

1. Download Docker
2. Run the command `docker-compose up`

** Keycloak **

1. Access Keycloak via `http://localhost:8080/admin`
2. Sign in with username: `admin` & password: `admin`
3. Select `cyber` as the realm

** HashiCorp Vault **

1. Access HashiCorp Vault via `http://localhost:8200`
2. Sign in with the token `dev-only-token`

03/23/2025
- Created client: `test-client`
- Created user username: `martyna` & password: `123` -> can login here: `http://localhost:8080/realms/cyber/account`
- Statically generated JWT can be seen by going into Inspect -> Network -> token -> Response -> access_token
- You can use this tool (https://www.jstoolset.com/jwt) to decode JWTs
- Created user username: `eggbtr` & password: `345` -> can login here: `http://localhost:8080/realms/cyber/account`

03/30/2025
- Created `main.py` - our simple Flask app will run on localhost:5000
- Added a `Dockerfile` and refrenced it in `docker-compose.yml` - this is how our Flask app will run
  (the `Dockerfile` has instructions on how to run the Flask app; the .yml file points to it when `docker-compose up` is ran)
- Created a `venv` (for running `main.py` w/o using `docker-compose up`)

How to create a `venv` & activate it (on Windows):
1. `python -m venv venv` -> venv creation
2. `.\venv\Scripts\activate` -> venv activation
3. `pip install -r requirements.txt` -> downloading requirements to run `main.py`

04/13/2025
1. The `cyber` realm now has the Access settings configured
2. We are able to login and out using the users configured in the `cyber` realm