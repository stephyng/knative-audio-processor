import pulumi
import pulumi_kubernetes as k8s

# MinIO namespace létrehozása
minio_namespace = k8s.core.v1.Namespace(
    "minio-namespace",
    metadata={"name": "minio"}
)

# MinIO Deployment
minio_deployment = k8s.apps.v1.Deployment(
    "minio-deployment",
    metadata={
        "name": "minio",
        "namespace": minio_namespace.metadata["name"]
    },
    spec={
        "replicas": 1,
        "selector": {
            "matchLabels": {"app": "minio"}
        },
        "template": {
            "metadata": {"labels": {"app": "minio"}},
            "spec": {
                "containers": [
                    {
                        "name": "minio",
                        "image": "quay.io/minio/minio",
                        "args": [
                            "server",
                            "/data",
                            "--console-address",
                            ":9001"
                        ],
                        "env": [
                            {"name": "MINIO_ROOT_USER", "value": "minioadmin"},
                            {"name": "MINIO_ROOT_PASSWORD", "value": "minioadmin"},
                        ],
                        "ports": [
                            {"containerPort": 9000},
                            {"containerPort": 9001},
                        ],
                        "volumeMounts": [
                            {"name": "data", "mountPath": "/data"}
                        ]
                    }
                ],
                "volumes": [
                    {"name": "data", "emptyDir": {}}
                ]
            }
        }
    }
)

# MinIO Service
minio_service = k8s.core.v1.Service(
    "minio-service",
    metadata={
        "name": "minio",
        "namespace": minio_namespace.metadata["name"]
    },
    spec={
        "selector": {"app": "minio"},
        "ports": [
            {"name": "api", "port": 9000, "targetPort": 9000, "nodePort": 30911},
            {"name": "console", "port": 9001, "targetPort": 9001, "nodePort": 30912}
        ],
        "type": "NodePort"
    }
)

# Audio-processor Deployment
audio_processor_deployment = k8s.apps.v1.Deployment(
    "audio-processor-deployment",
    metadata={
        "name": "audio-processor"
    },
    spec={
        "replicas": 1,
        "selector": {
            "matchLabels": {
                "app": "audio-processor"
            }
        },
        "template": {
            "metadata": {
                "labels": {
                    "app": "audio-processor"
                }
            },
            "spec": {
                "containers": [
                    {
                        "name": "audio-processor",
                        "image": "stephyng/knative-audio-processing-monolithic:latest",
                        "ports": [
                            {"containerPort": 8080}
                        ],
                        "env": [
                            {"name": "MINIO_ENDPOINT", "value": "minio.minio:9000"},
                            {"name": "MINIO_ACCESS_KEY", "value": "minioadmin"},
                            {"name": "MINIO_SECRET_KEY", "value": "minioadmin"}
                        ],
                    }
                ]
            }
        }
    }
)

# Audio-processor Service
audio_processor_service = k8s.core.v1.Service(
    "audio-processor-service",
    metadata={
        "name": "audio-processor"
    },
    spec={
        "selector": {
            "app": "audio-processor"
        },
        "ports": [
            {
                "port": 80,
                "targetPort": 8080,
                "protocol": "TCP"
            }
        ]
    }
)

pulumi.export("minio_service_name", minio_service.metadata["name"])
pulumi.export("namespace", minio_namespace.metadata["name"])
pulumi.export("audio_processor_deployment_name", audio_processor_deployment.metadata["name"])
pulumi.export("audio_processor_service_name", audio_processor_service.metadata["name"])