# Kubernetes Info Fetcher

## Introduction

This project fetches details from a Kubernetes cluster and generates markdown files with embedded Mermaid diagrams to visually represent Kubernetes resources. Each markdown file represents an independent workload within a namespace and its associated resources.

## Workflow Diagram

```mermaid
graph TD
A[Start]
B[Fetch Namespaces]
C[For Each Namespace]
D[Fetch All Workloads]
E[For Each Workload]
F[Fetch Pods, ReplicaSets, Services]
G[Generate Markdown with Diagram]
H[Write to File]
I[End]
A --> B
B --> C
C --> D
D --> E
E --> F
F --> G
G --> H
H --> C
C --> I
```

## Sequence Diagram 

```mermaid
sequenceDiagram
User->>Program: Run Program
Program->>K8s API: Fetch Namespaces
loop For Each Namespace
Program->>K8s API: Fetch Workloads (Deployments, StatefulSets, etc.)
loop For Each Workload
Program->>K8s API: Fetch Pods
Program->>K8s API: Fetch Services
Program->>Markdown Generator: Generate Mermaid Diagram
Markdown Generator-->>Program: Return Markdown Content
Program->>File System: Write Markdown to File
end
end
Program-->>User: Completion
```

## Usage

Ensure you have python installed and the required packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

Ensure you have access to the Kubernetes cluster and `~/.kube/config` is properly set up.
Run the program:

```bash
python main.py
```

## Example

istio-ingressgateway-ext deployment:


```mermaid
graph LR
A[Deployment: istio-ingressgateway-ext]
A --> meta_name[name: istio-ingressgateway-ext]
A --> meta_namespace[namespace: istio-system]
A --> meta_labels[labels: app, install.operator.istio.io/owning-resource, install.operator.istio.io/owning-resource-namespace, istio, istio.io/rev, operator.istio.io/component, operator.istio.io/managed, operator.istio.io/version, release]
A --> meta_annotations[annotations: deployment.kubernetes.io/revision, field.cattle.io/publicEndpoints, kubectl.kubernetes.io/last-applied-configuration]
A --> service_istio-ingressgateway-ext
A --> C
A --> S
A --> service_istio-ingressgateway-ext
C[Container: istio-proxy]
C --> cont_name[name: istio-proxy]
C --> cont_image[image: rancher/mirrored-istio-proxyv2:1.14.1-distroless]
C --> cont_env[env: JWT_POLICY, PILOT_CERT_PROVIDER, CA_ADDR, ...]
C --> cont_volume_mounts[volume_mounts: workload-socket, workload-certs, istio-envoy, ...]
C --> cont_image_pull_policy[image_pull_policy: IfNotPresent]
C --> cont_requests_cpu[requests cpu: 100m]
C --> cont_requests_memory[requests memory: 128Mi]
C --> cont_limits_cpu[limits cpu: 2]
C --> cont_limits_memory[limits memory: 1Gi]
S[Status]
S --> status_replicas[replicas: 2]
S --> status_updated_replicas[updated_replicas: 2]
S --> status_ready_replicas[ready_replicas: 2]
S --> status_available_replicas[available_replicas: 2]
S --> status_conditions[conditions: Progressing, Available]
service_istio-ingressgateway-ext[Service: istio-ingressgateway-ext]
service_istio-ingressgateway-ext --> pod_istio-ingressgateway-ext-567549c7f4-bvv4t
service_istio-ingressgateway-ext --> pod_istio-ingressgateway-ext-567549c7f4-lc4kc
classDef greenFill fill:#e1f7d5,stroke:#333,stroke-width:2px,color:#333;
classDef yellowFill fill:#c7e59a,stroke:#333,stroke-width:2px,color:#333;
class A greenFill
class C,S yellowFill
```


Check the `output_<CLUSTER_NAME>` directory for generated markdown files with diagrams.
