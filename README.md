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

Istio-Kiali deployment:

```mermaid
graph TD
    V1Deployment_kiali[Deployment: kiali]
    Pod_kiali-77c74f7d9c-298nt[kiali-77c74f7d9c-298nt]
    V1Deployment_kiali --> Pod_kiali-77c74f7d9c-298nt
    Service_kiali[Service: kiali]
    Service_kiali --> Pod_kiali-77c74f7d9c-298nt

```

Check the `output_<CLUSTER_NAME>` directory for generated markdown files with diagrams.
