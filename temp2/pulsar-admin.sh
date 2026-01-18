#!/bin/bash
# Helper script for pulsar-admin with JWT authentication

ADMIN_TOKEN=$(cat secrets/admin-token.txt)

docker exec pulsar bin/pulsar-admin \
  --admin-url http://localhost:8080 \
  --auth-plugin org.apache.pulsar.client.impl.auth.AuthenticationToken \
  --auth-params "token:${ADMIN_TOKEN}" \
  "$@"
