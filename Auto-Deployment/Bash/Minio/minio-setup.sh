#!/bin/bash

# Megjegyzés: Ez a script feltételezi, hogy az 'mc' (MinIO Client) már telepítve van, és elérhető a PATH-ban.

# 1. Alias beállítása a helyi MinIO szerverhez
echo "➡️ Alias beállítása 'local' néven..."
mc alias set local http://127.0.0.1:30911 minioadmin minioadmin
sleep 4

# Ellenőrzés, hogy az alias beállítás sikeres volt-e
if [ $? -ne 0 ]; then
    echo "❌ Hiba történt az alias beállításakor. Lépjen ki."
    exit 1
fi

# 2. 'knative-audio-processor' nevű bucket létrehozása
echo "➡️ 'knative-audio-processor' bucket létrehozása..."
mc mb local/knative-audio-processor
sleep 4

# 3. Webhook értesítési konfiguráció beállítása
echo "➡️ 'knative' webhook értesítési végpont beállítása..."
mc admin config set local notify_webhook:knative endpoint="http://knative-minio-processor.default.svc.cluster.local/minio-event"
sleep 4

# 4. MinIO szolgáltatás újraindítása a konfiguráció alkalmazásához
echo "➡️ MinIO szolgáltatás újraindítása..."
mc admin service restart local
sleep 4

# 5. PUT esemény értesítés hozzáadása a buckethez a 'knative' webhook használatával
echo "➡️ PUT esemény értesítés hozzáadása a 'knative' webhookhoz..."
mc event add local/knative-audio-processor arn:minio:sqs::knative:webhook --event put
sleep 4

echo "✅ A MinIO konfiguráció beállítása befejeződött."