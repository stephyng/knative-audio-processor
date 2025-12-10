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

# Knative Service - MinIO Processor
knative_service_minio_processor = k8s.apiextensions.CustomResource(
    "knative-minio-processor",
    api_version="serving.knative.dev/v1",
    kind="Service",
    metadata={
        "name": "knative-minio-processor"
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
                "nodeSelector": {
                    "kubernetes.io/hostname": "agent"
                },
                "containers": [
                    {
                        "image": "stephyng/micro-minio-processor-test:latest",
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

# Knative Service - Audio Splitter
knative_service_audio_splitter = k8s.apiextensions.CustomResource(
    "knative-audio-splitter",
    api_version="serving.knative.dev/v1",
    kind="Service",
    metadata={
        "name": "knative-audio-splitter"
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
                "nodeSelector": {
                    "kubernetes.io/hostname": "agent"
                },
                "containers": [
                    {
                        "image": "stephyng/micro-audio-splitter-test:latest",
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
    },
    opts=pulumi.ResourceOptions(depends_on=[knative_service_minio_processor])
)

# Knative Service - Audio Transcriber
knative_service_audio_transcriber = k8s.apiextensions.CustomResource(
    "knative-audio-transcriber",
    api_version="serving.knative.dev/v1",
    kind="Service",
    metadata={
        "name": "knative-audio-transcriber"
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
                        "image": "stephyng/micro-audio-transcriber-test:latest",
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
    },
    opts=pulumi.ResourceOptions(depends_on=[knative_service_minio_processor, knative_service_audio_splitter])
)

# Knative Service - Audio Merger
knative_service_audio_merger = k8s.apiextensions.CustomResource(
    "knative-audio-merger",
    api_version="serving.knative.dev/v1",
    kind="Service",
    metadata={
        "name": "knative-audio-merger"
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
                        "image": "stephyng/micro-audio-merger-test:latest",
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
    },
    opts=pulumi.ResourceOptions(depends_on=[knative_service_minio_processor, knative_service_audio_splitter, knative_service_audio_transcriber])
)

# Broker létrehozása
default_broker = k8s.apiextensions.CustomResource(
    "default-broker",
    api_version="eventing.knative.dev/v1",
    kind="Broker",
    metadata={
        "name": "default",
        "namespace": "default"
    },
    opts=pulumi.ResourceOptions(depends_on=[knative_service_minio_processor, knative_service_audio_splitter, knative_service_audio_transcriber, knative_service_audio_merger])
)

# Trigger 1: audio-splitter
audio_splitter_trigger = k8s.apiextensions.CustomResource(
    "audio-splitter-trigger",
    api_version="eventing.knative.dev/v1",
    kind="Trigger",
    metadata={
        "name": "audio-splitter-trigger",
        "namespace": "default"
    },
    spec={
        "broker": "default",
        "filter": {
            "attributes": {
                "type": "dev.knative.minio.object.created"
            }
        },
        "subscriber": {
            "ref": {
                "apiVersion": "serving.knative.dev/v1",
                "kind": "Service",
                "name": "knative-audio-splitter"
            }
        }
    },
    opts=pulumi.ResourceOptions(depends_on=[knative_service_minio_processor, knative_service_audio_splitter, knative_service_audio_transcriber, knative_service_audio_merger, default_broker])
)

# Trigger 2: audio-transcriber
audio_transcriber_trigger = k8s.apiextensions.CustomResource(
    "audio-transcriber-trigger",
    api_version="eventing.knative.dev/v1",
    kind="Trigger",
    metadata={
        "name": "audio-transcriber-trigger",
        "namespace": "default"
    },
    spec={
        "broker": "default",
        "filter": {
            "attributes": {
                "type": "dev.knative.audio.chunks.ready"
            }
        },
        "subscriber": {
            "ref": {
                "apiVersion": "serving.knative.dev/v1",
                "kind": "Service",
                "name": "knative-audio-transcriber"
            }
        }
    },
    opts=pulumi.ResourceOptions(depends_on=[knative_service_minio_processor, knative_service_audio_splitter, knative_service_audio_transcriber, knative_service_audio_merger, default_broker])
)

# Trigger 3: audio-merger
audio_merger_trigger = k8s.apiextensions.CustomResource(
    "audio-merger-trigger",
    api_version="eventing.knative.dev/v1",
    kind="Trigger",
    metadata={
        "name": "audio-merger-trigger",
        "namespace": "default"
    },
    spec={
        "broker": "default",
        "filter": {
            "attributes": {
                "type": "dev.knative.audio.chunk.processed"
            }
        },
        "subscriber": {
            "ref": {
                "apiVersion": "serving.knative.dev/v1",
                "kind": "Service",
                "name": "knative-audio-merger"
            }
        }
    },
    opts=pulumi.ResourceOptions(depends_on=[knative_service_minio_processor, knative_service_audio_splitter, knative_service_audio_transcriber, knative_service_audio_merger, default_broker])
)


pulumi.export("minio_service_name", minio_service.metadata["name"])
pulumi.export("namespace", minio_namespace.metadata["name"])
pulumi.export("knative_service_name", knative_service_minio_processor.metadata["name"])
pulumi.export("knative_service_audio_splitter_name", knative_service_audio_splitter.metadata["name"])
pulumi.export("knative_service_audio_transcriber_name", knative_service_audio_transcriber.metadata["name"])
pulumi.export("knative_service_audio_merger_name", knative_service_audio_merger.metadata["name"])
pulumi.export("broker_name", default_broker.metadata["name"])
pulumi.export("triggers", [
    audio_splitter_trigger.metadata["name"],
    audio_transcriber_trigger.metadata["name"],
    audio_merger_trigger.metadata["name"],
])