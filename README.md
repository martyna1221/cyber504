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
- Created user username: `eggbtr` & password: `345` -> can login here: `http://localhost:8080/realms/cyber/account`
- Statically generated JWT can be seen by going into Inspect -> Network -> token -> Response -> access_token
- You can use this tool (https://www.jstoolset.com/jwt) to decode JWTs
