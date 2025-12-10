#!/bin/bash

set -e

echo "🚀 Knative audio-feldolgozó környezet beállítása..."
echo "---"

# Minikube indítása
echo "🟡 Minikube indítása..."
minikube start || { echo "❌ Hiba a minikube indításakor."; exit 1; }
echo "✅ Minikube elindult."
echo "---"

# MnIO telepítése
echo "🟡 MinIO telepítése..."
kubectl apply -f ./Monolithic/Minio/minio-deployment.yaml
echo "✅ MinIO telepítve."
echo "---"
sleep 5

# -----------------------------
echo "🟡 Alkalmazás telepítése"
kubectl apply -f ./Monolithic/Deployments/audio-processor.yaml
echo "🕒 Várakozás, amíg az audio-processor pod létrejön és Running állapotba kerül..."
while [[ -z $(kubectl get pods -l app=audio-processor -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) ]]; do
  sleep 2
done
POD_NAME=$(kubectl get pods -l app=audio-processor -o jsonpath='{.items[0].metadata.name}')
while [[ $(kubectl get pod $POD_NAME -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 3
done
echo "✅ Az audio-processor pod fut (Running)."
kubectl wait --for=condition=Ready pod -l app=audio-processor
echo "✅ Az audio-processor pod készen áll."

echo "🎉 **Telepítés befejezve!**"
echo "---"