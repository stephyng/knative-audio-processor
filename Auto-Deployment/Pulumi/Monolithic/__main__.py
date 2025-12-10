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

# Knative Service - Audio Processor
knative_service_audio_processor = k8s.apiextensions.CustomResource(
    "knative-audio-processor",
    api_version="serving.knative.dev/v1",
    kind="Service",
    metadata={
        "name": "knative-audio-processor"
    },
    spec={
        "template": {
            "metadata": {
                "annotations": {
                    "autoscaling.knative.dev/minScale": "1",
                    "autoscaling.knative.dev/maxScale": "1"
                }
            },
            "spec": {
                "containers": [
                    {
                        "image": "stephyng/knative-audio-processing-monolithic:latest",
                        "env": [
                            {"name": "MINIOENDPOINT", "value": "minio.minio:9000"},
                            {"name": "MINIOACCESSKEY", "value": "minioadmin"},
                            {"name": "MINIOSECRETKEY", "value": "minioadmin"},
                            {"name": "K_SINK", "value": "http://broker-ingress.knative-eventing.svc.cluster.local/default/default"},
                        ],
                    }
                ],
            }
        }
    }
)

pulumi.export("minio_service_name", minio_service.metadata["name"])
pulumi.export("namespace", minio_namespace.metadata["name"])
pulumi.export("knative_service_name", knative_service_audio_processor.metadata["name"])