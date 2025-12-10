#!/bin/bash

set -e

echo "🚀 Knative audio-feldolgozó környezet beállítása (Frissített verzió)..."
echo "---"

# Minikube indítása
echo "🟡 Minikube indítása..."
minikube start || { echo "❌ Hiba a minikube indításakor."; exit 1; }
echo "✅ Minikube elindult."
echo "---"

# Knative Serving telepítése
echo "🟡 Knative Serving (v1.14.0) telepítése..."
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

# Knative Eventing telepítése
echo "🟡 Knative Eventing (v1.19.7) telepítése..."
kubectl apply -f https://github.com/knative/eventing/releases/download/knative-v1.19.7/eventing-crds.yaml
sleep 5
kubectl apply -f https://github.com/knative/eventing/releases/download/knative-v1.19.7/eventing-core.yaml
sleep 5
kubectl apply -f https://github.com/knative/eventing/releases/download/knative-v1.19.7/in-memory-channel.yaml
sleep 5
kubectl apply -f https://github.com/knative/eventing/releases/download/knative-v1.19.7/mt-channel-broker.yaml
sleep 5
echo "✅ Eventing telepítve."
echo "---"

# Knative Kafka Broker telepítése
echo "🟡 Knative Kafka Broker (v1.19.8) telepítése..."
kubectl apply -f https://github.com/knative-extensions/eventing-kafka-broker/releases/download/knative-v1.19.8/eventing-kafka-controller.yaml
sleep 5
kubectl apply -f https://github.com/knative-extensions/eventing-kafka-broker/releases/download/knative-v1.19.8/eventing-kafka-broker.yaml
sleep 5
kubectl apply -f https://github.com/knative-extensions/eventing-kafka-broker/releases/download/knative-v1.19.8/eventing-kafka-post-install.yaml
sleep 5
echo "✅ Kafka Broker telepítve."
echo "---"

# Nodeselector engedélyezése
echo "🟡 Nodeselector engedélyezése a Knative Serving-ben..."
kubectl -n knative-serving patch cm config-features --type merge -p '{"data":{"kubernetes.podspec-nodeselector":"enabled"}}'
echo "✅ Nodeselector engedélyezve."
echo "---"

# Microservice-ek telepítése
echo "🟡 Microservice-ek telepítése..."
kubectl apply -f ./Microservices/Local/Minio/minio-deployment.yaml
sleep 3
kubectl apply -f ./Microservices/Local/Deployments/kafka-broker-receiver-patch.yaml
sleep 5

# -----------------------------
kubectl apply -f ./Microservices/Local/Deployments/minio-processor-deployment.yaml
echo "🕒 Várakozás, amíg a knative-minio-processor pod létrejön és Running állapotba kerül..."
while [[ -z $(kubectl get pods -l serving.knative.dev/service=knative-minio-processor -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) ]]; do
  sleep 2
done
POD_NAME=$(kubectl get pods -l serving.knative.dev/service=knative-minio-processor -o jsonpath='{.items[0].metadata.name}')
while [[ $(kubectl get pod $POD_NAME -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 3
done
echo "✅ A knative-minio-processor pod fut (Running)."
kubectl wait --for=condition=Ready pod -l serving.knative.dev/service=knative-minio-processor
echo "✅ A knative-minio-processor pod készen áll."

# -----------------------------
kubectl apply -f ./Microservices/Local/Deployments/audio-splitter-deployment.yaml
echo "🕒 Várakozás, amíg a knative-audio-splitter pod létrejön és Running állapotba kerül..."
while [[ -z $(kubectl get pods -l serving.knative.dev/service=knative-audio-splitter -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) ]]; do
  sleep 2
done
POD_NAME=$(kubectl get pods -l serving.knative.dev/service=knative-audio-splitter -o jsonpath='{.items[0].metadata.name}')
while [[ $(kubectl get pod $POD_NAME -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 3
done
echo "✅ A knative-audio-splitter pod fut (Running)."
kubectl wait --for=condition=Ready pod -l serving.knative.dev/service=knative-audio-splitter
echo "✅ A knative-audio-splitter pod készen áll."

# -----------------------------
kubectl apply -f ./Microservices/Local/Deployments/audio-transcriber-deployment.yaml
echo "🕒 Várakozás, amíg a knative-audio-transcriber pod létrejön és Running állapotba kerül..."
while [[ -z $(kubectl get pods -l serving.knative.dev/service=knative-audio-transcriber -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) ]]; do
  sleep 2
done
POD_NAME=$(kubectl get pods -l serving.knative.dev/service=knative-audio-transcriber -o jsonpath='{.items[0].metadata.name}')
while [[ $(kubectl get pod $POD_NAME -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 3
done
echo "✅ A knative-audio-transcriber pod fut (Running)."
kubectl wait --for=condition=Ready pod -l serving.knative.dev/service=knative-audio-transcriber
echo "✅ A knative-audio-transcriber pod készen áll."

# -----------------------------
kubectl apply -f ./Microservices/Local/Deployments/audio-merger-deployment.yaml
echo "🕒 Várakozás, amíg a knative-audio-merger pod létrejön és Running állapotba kerül..."
while [[ -z $(kubectl get pods -l serving.knative.dev/service=knative-audio-merger -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) ]]; do
  sleep 2
done
POD_NAME=$(kubectl get pods -l serving.knative.dev/service=knative-audio-merger -o jsonpath='{.items[0].metadata.name}')
while [[ $(kubectl get pod $POD_NAME -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 3
done
echo "✅ A knative-audio-merger pod fut (Running)."
kubectl wait --for=condition=Ready pod -l serving.knative.dev/service=knative-audio-merger
echo "✅ A knative-audio-merger pod készen áll."

# -----------------------------
kubectl apply -f ./Microservices/Local/Deployments/eventing-components-deployment.yaml
echo "✅ Microservice-ek telepítve és beállítva."
echo "---"

echo "🎉 **Telepítés befejezve!**"
echo "---"