#!/bin/bash

set -e

echo "🚀 Knative audio-feldolgozó környezet beállítása..."
echo "---"

# Minikube indítása
echo "🟡 Minikube indítása..."
minikube start || { echo "❌ Hiba a minikube indításakor."; exit 1; }
echo "✅ Minikube elindult."
echo "---"

# Knative Serving telepítése
echo "🟡 Knative Serving telepítése..."
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.14.0/serving-crds.yaml
sleep 5
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.14.0/serving-core.yaml
sleep 5
echo "✅ CRD-k és Core telepítve."
echo "---"

# Kourier Ingress konfigurálása
echo "🟡 Kourier telepítése és konfigurálása..."
kubectl apply -f https://github.com/knative-extensions/net-kourier/releases/download/knative-v1.14.0/kourier.yaml
sleep 5
kubectl patch configmap/config-network -n knative-serving --type merge -p '{"data":{"ingress.class":"kourier.ingress.networking.knative.dev"}}'
kubectl patch configmap/config-domain -n knative-serving --type merge -p '{"data":{"127.0.0.1.sslip.io":""}}'
echo "✅ Kourier beállítva."
echo "---"
sleep 5

echo "🟡 MinIO telepítése..."
kubectl apply -f ./Monolithic/Minio/minio-deployment.yaml
echo "✅ MinIO telepítve."
echo "---"
sleep 5

# -----------------------------
echo "🟡 Alkalmazás telepítése"
kubectl apply -f ./Monolithic/Deployments/aws-k3s-service-autoscale-off.yaml
echo "🕒 Várakozás, amíg a knative-audio-processor pod létrejön és Running állapotba kerül..."
while [[ -z $(kubectl get pods -l serving.knative.dev/service=knative-audio-processor -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) ]]; do
  sleep 2
done
POD_NAME=$(kubectl get pods -l serving.knative.dev/service=knative-audio-processor -o jsonpath='{.items[0].metadata.name}')
while [[ $(kubectl get pod $POD_NAME -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 3
done
echo "✅ A knative-audio-processor pod fut (Running)."
kubectl wait --for=condition=Ready pod -l serving.knative.dev/service=knative-audio-processor
echo "✅ A knative-audio-processor pod készen áll."

echo "🎉 **Telepítés befejezve!**"
echo "---"