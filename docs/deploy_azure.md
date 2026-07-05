# Deploying to Azure Container Apps

Copy-paste procedure for a minimal, low-cost deployment. The image is
code-only; the container builds its index at boot from the configured public
URLs (`INGEST_ON_BOOT=1`), so no volume or storage account is needed.

## Prerequisites

- Azure account with an active subscription (`az login`)
- Azure CLI ≥ 2.60 with the containerapp extension: `az extension add --name containerapp --upgrade`
- A strong token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

## Deploy

```powershell
$RG  = "insight-mcp-rg"
$ENV = "insight-mcp-env"
$APP = "insight-mcp"
$LOC = "francecentral"
$TOKEN = "<paste-generated-token>"

az group create --name $RG --location $LOC
az containerapp env create --name $ENV --resource-group $RG --location $LOC

# Consumption plan, scale-to-zero, public HTTPS ingress on 8020
az containerapp create `
  --name $APP --resource-group $RG --environment $ENV `
  --image ghcr.io/airohh/insight-mcp:0.1.0 `
  --target-port 8020 --ingress external `
  --min-replicas 0 --max-replicas 1 `
  --cpu 0.5 --memory 1.0Gi `
  --secrets mcp-token=$TOKEN `
  --env-vars MCP_AUTH_TOKEN=secretref:mcp-token INGEST_ON_BOOT=1

az containerapp show --name $APP --resource-group $RG `
  --query properties.configuration.ingress.fqdn -o tsv
# → <fqdn> ; MCP endpoint = https://<fqdn>/mcp
```

Notes:
- **GHCR image is public** (published by the release workflow on `v*` tags), so
  no registry credentials are needed.
- `INGEST_ON_BOOT=1`: first boot downloads the seed URLs (~1 min) before the
  server accepts traffic; subsequent boots re-ingest because the filesystem is
  ephemeral. For a persistent index, add an Azure Files volume on `/app/data`
  and drop the env var.
- Scale-to-zero keeps idle cost near nothing; the first request after idle
  pays cold start + ingestion.

## Verify

```powershell
# 401 without token
curl -s -o NUL -w "%{http_code}`n" -X POST https://<fqdn>/mcp

# Tools over authenticated Streamable HTTP
npx @modelcontextprotocol/inspector --cli https://<fqdn>/mcp --transport http `
  --header "Authorization: Bearer $TOKEN" --method tools/list

# End to end through the Anthropic API MCP connector
python scripts/demo_mcp_connector.py --url https://<fqdn>/mcp --token $TOKEN
```

## Tear down

```powershell
az group delete --name $RG --yes --no-wait
```
