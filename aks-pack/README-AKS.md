# Exotic Telemetry Agent — AKS Pack

This folder contains Dockerfiles and Kubernetes manifests to deploy the project on **Azure Kubernetes Service (AKS)** using **Azure Container Registry (ACR)**.

## Prereqs
- Azure CLI, kubectl, Docker
- Logged in: `az login`

## 1) Build and push images to ACR
```bash
RG=eta-demo-rg
LOC=eastus
ACR=etaregistry$RANDOM
az group create -n $RG -l $LOC
az acr create -g $RG -n $ACR --sku Basic
ACR_SERVER=$(az acr show -n $ACR --query loginServer -o tsv)

# From repo root (that has requirements.txt and app folders)
docker build -t $ACR_SERVER/eta-api:latest -f api/Dockerfile .
docker build -t $ACR_SERVER/eta-ui:latest -f ui/Dockerfile .
docker build -t $ACR_SERVER/eta-sim:latest -f simulator/Dockerfile .
docker build -t $ACR_SERVER/eta-edge:latest -f edge/Dockerfile .

az acr login -n $ACR
docker push $ACR_SERVER/eta-api:latest
docker push $ACR_SERVER/eta-ui:latest
docker push $ACR_SERVER/eta-sim:latest
docker push $ACR_SERVER/eta-edge:latest
```

## 2) Create AKS and connect to ACR
```bash
AKS=eta-aks
az aks create -g $RG -n $AKS --node-count 2 --attach-acr $ACR
az aks get-credentials -g $RG -n $AKS
```

## 3) Deploy manifests
Replace `<ACR_SERVER>` with your real ACR server in all YAMLs:
```bash
ACR_SERVER=$(az acr show -n $ACR --query loginServer -o tsv)
find k8s -type f -name "*.yaml" -print0 | xargs -0 sed -i '' "s|<ACR_SERVER>|$ACR_SERVER|g"
```
Then apply:
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/storage.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/ui.yaml
kubectl apply -f k8s/sim.yaml
kubectl apply -f k8s/edge.yaml   # optional
kubectl -n eta get pods,svc
```

## 4) Access the UI
If you used the included `ui-lb` Service in `ui.yaml`, get its public IP:
```bash
kubectl -n eta get svc ui-lb
```
Then open: `http://EXTERNAL-IP/`

## Notes
- DuckDB is stored on a PVC for the API (`k8s/storage.yaml`). For production, consider Azure Data Explorer (ADX) and make API stateless.
- Swap the LoadBalancer for an Ingress + TLS when ready.
- Set `RCA_API` env for simulator/edge to point at the API Service DNS (already set in YAMLs).
