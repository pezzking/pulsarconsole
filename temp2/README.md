# Apache Pulsar met JWT Authenticatie

Deze setup draait Apache Pulsar met JWT (symmetrische sleutel) authenticatie in Docker Compose.

## Overzicht

- **Pulsar versie**: Latest
- **Authenticatie**: JWT met symmetrische sleutel
- **Ports**: 
  - Broker: 6651 (gemapped naar 6650 intern)
  - Web Service: 8081 (gemapped naar 8080 intern)

## Bestanden

```
temp2/
├── docker-compose.yml          # Pulsar service configuratie
├── secrets/
│   ├── my-secret.key          # JWT geheime sleutel
│   └── admin-token.txt        # Admin JWT token
├── pulsar-admin.sh            # Helper script voor admin commando's
└── README.md                  # Deze file
```

## Admin Token

Het admin token is opgeslagen in `secrets/admin-token.txt`:

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.FO7Erur_sjVRnfa8Y2vRnntSgwdv4DQo0Z61vMB9UGo
```

Dit token heeft de rol `admin` en is geconfigureerd als superuser.

## Gebruik

### Pulsar starten

```bash
docker-compose up -d
```

### Pulsar stoppen

```bash
docker-compose down
```

### Admin commando's uitvoeren

Gebruik het helper script:

```bash
# Lijst brokers
./pulsar-admin.sh brokers list standalone

# Lijst tenants
./pulsar-admin.sh tenants list

# Lijst namespaces
./pulsar-admin.sh namespaces list public

# Lijst topics
./pulsar-admin.sh topics list public/default

# Topic aanmaken
./pulsar-admin.sh topics create persistent://public/default/my-topic
```

### Direct pulsar-admin gebruiken

```bash
ADMIN_TOKEN=$(cat secrets/admin-token.txt)

docker exec pulsar bin/pulsar-admin \
  --admin-url http://localhost:8080 \
  --auth-plugin org.apache.pulsar.client.impl.auth.AuthenticationToken \
  --auth-params "token:${ADMIN_TOKEN}" \
  <commando>
```

## Verbinden vanaf host

Gebruik de volgende connection URLs:

- **Broker URL**: `pulsar://localhost:6651`
- **Admin URL**: `http://localhost:8081`

### Python Client Voorbeeld

```python
import pulsar

# Admin token laden
with open('secrets/admin-token.txt', 'r') as f:
    token = f.read().strip()

# Client met authenticatie
client = pulsar.Client(
    service_url='pulsar://localhost:6651',
    authentication=pulsar.AuthenticationToken(token)
)

# Producer maken
producer = client.create_producer('persistent://public/default/my-topic')
producer.send(b'Hello Pulsar!')

# Consumer maken
consumer = client.subscribe('persistent://public/default/my-topic', 'my-sub')
msg = consumer.receive()
print(f"Ontvangen: {msg.data().decode()}")

consumer.acknowledge(msg)
producer.close()
consumer.close()
client.close()
```

## Nieuwe Tokens Genereren

### Nieuwe geheime sleutel genereren

```bash
docker run -v "$(pwd)/secrets:/pulsar/secrets" apachepulsar/pulsar:latest \
  bin/pulsar tokens create-secret-key --output /pulsar/secrets/my-secret.key
```

### Token voor specifieke rol genereren

```bash
# Token voor 'admin' rol
docker run -v "$(pwd)/secrets:/pulsar/secrets" apachepulsar/pulsar:latest \
  bin/pulsar tokens create \
  --secret-key file:///pulsar/secrets/my-secret.key \
  --subject admin

# Token voor 'producer' rol
docker run -v "$(pwd)/secrets:/pulsar/secrets" apachepulsar/pulsar:latest \
  bin/pulsar tokens create \
  --secret-key file:///pulsar/secrets/my-secret.key \
  --subject producer
```

## Authenticatie Verificatie

### Test zonder token (moet falen)

```bash
docker exec pulsar bin/pulsar-admin \
  --admin-url http://localhost:8080 \
  brokers list standalone
```

Verwacht resultaat: `HTTP 401 Authentication required`

### Test met token (moet slagen)

```bash
./pulsar-admin.sh brokers list standalone
```

Verwacht resultaat: `localhost:8080`

## Rechten Beheer

### Namespace rechten toekennen

```bash
# Producer rechten
./pulsar-admin.sh namespaces grant-permission public/default \
  --actions produce \
  --role producer

# Consumer rechten
./pulsar-admin.sh namespaces grant-permission public/default \
  --actions consume \
  --role consumer

# Volledige rechten
./pulsar-admin.sh namespaces grant-permission public/default \
  --actions produce,consume \
  --role client
```

### Rechten bekijken

```bash
./pulsar-admin.sh namespaces permissions public/default
```

### Rechten intrekken

```bash
./pulsar-admin.sh namespaces revoke-permission public/default \
  --role producer
```

## Configuratie Details

De belangrijkste authenticatie settings in `docker-compose.yml`:

```yaml
environment:
  - PULSAR_PREFIX_authenticationEnabled=true
  - PULSAR_PREFIX_authorizationEnabled=true
  - PULSAR_PREFIX_authenticationProviders=org.apache.pulsar.broker.authentication.AuthenticationProviderToken
  - PULSAR_PREFIX_tokenSecretKey=file:///pulsar/secrets/my-secret.key
  - PULSAR_PREFIX_superUserRoles=admin
  - PULSAR_PREFIX_brokerClientAuthenticationEnabled=true
  - PULSAR_PREFIX_brokerClientAuthenticationPlugin=org.apache.pulsar.client.impl.auth.AuthenticationToken
  - PULSAR_PREFIX_brokerClientAuthenticationParameters=token:...
```

## Troubleshooting

### Container logs bekijken

```bash
docker logs pulsar
```

### Authenticatie errors zoeken

```bash
docker logs pulsar 2>&1 | grep -i "auth"
```

### Container opnieuw starten

```bash
docker-compose restart
```

### Configuratie resetten

```bash
docker-compose down -v
docker-compose up -d
```

## Beveiliging

⚠️ **Belangrijk**:
- Bewaar de geheime sleutel (`my-secret.key`) veilig
- Commit nooit tokens of sleutels naar version control
- Gebruik korte token expiration times in productie
- Overweeg HTTPS/TLS voor productie deployments
