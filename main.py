import os
import asyncio
from kubernetes import client, config
import logging
import pprint


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

config.load_kube_config()
current_context = config.list_kube_config_contexts()[1]['context']['cluster']


def fetch_namespaces() -> list:
    """
    Fetch all the namespaces from the Kubernetes cluster.

    Returns:
        list: A list of namespace objects.
    """
    try:
        v1 = client.CoreV1Api()
        return v1.list_namespace().items
    except Exception as e:
        logging.error(f"Error fetching namespaces: {e}")
        return []


def fetch_all_workloads(namespace_name: str) -> list:
    """
    Fetch all the workloads (Deployments, StatefulSets, DaemonSets) from a given namespace.

    Args:
        namespace_name (str): The name of the namespace.

    Returns:
        list: A list of workload objects.
    """
    try:
        apps_v1 = client.AppsV1Api()
        deployments = apps_v1.list_namespaced_deployment(namespace_name).items
        stateful_sets = apps_v1.list_namespaced_stateful_set(namespace_name).items
        daemon_sets = apps_v1.list_namespaced_daemon_set(namespace_name).items
        return deployments + stateful_sets + daemon_sets
    except Exception as e:
        logging.error(f"Error fetching workloads for namespace {namespace_name}: {e}")
        return []


def fetch_pods_for_workload(namespace_name: str, label_selector: str) -> list:
    """
    Fetch all pods for a given namespace and label selector.

    Args:
        namespace_name (str): The name of the namespace.
        label_selector (str): The label selector to filter the pods.

    Returns:
        list: A list of pod objects.
    """
    try:
        v1 = client.CoreV1Api()
        return v1.list_namespaced_pod(namespace_name, label_selector=label_selector).items
    except Exception as e:
        logging.error(f"Error fetching pods for namespace {namespace_name} with label selector {label_selector}: {e}")
        return []


def fetch_services_for_workload(namespace_name: str, label_selector: str) -> list:
    """
    Fetch all services for a given namespace and label selector.

    Args:
        namespace_name (str): The name of the namespace.
        label_selector (str): The label selector to filter the services.

    Returns:
        list: A list of service objects.
    """
    try:
        v1 = client.CoreV1Api()
        return v1.list_namespaced_service(namespace_name, label_selector=label_selector).items
    except Exception as e:
        logging.error(f"Error fetching services for namespace {namespace_name} with label selector {label_selector}: {e}")
        return []


def fetch_resources_for_workload(workload: object) -> dict:
    """
    Fetch all resources associated with a given workload.

    Args:
        workload (object): The workload object (could be Deployment, StatefulSet, etc.).

    Returns:
        dict: A dictionary containing related replica sets, pods, and services.
    """
    namespace_name = workload.metadata.namespace
    workload_kind = type(workload).__name__

    owned_replica_sets = []

    # Fetch all potential child resources in the namespace
    pods = fetch_pods_for_workload(namespace_name, "")
    services = fetch_services_for_workload(namespace_name, "")
    apps_v1 = client.AppsV1Api()
    replica_sets = apps_v1.list_namespaced_replica_set(namespace_name).items

    if workload_kind == "V1Deployment":
        owned_replica_sets = [rs for rs in replica_sets if
                              any(owner.uid == workload.metadata.uid for owner in rs.metadata.owner_references)]
        owned_pods = [pod for pod in pods if any(
            owner.uid == rs.metadata.uid for rs in owned_replica_sets for owner in pod.metadata.owner_references)]
    elif workload_kind in ["V1StatefulSet", "V1DaemonSet", "V1ReplicaSet"]:
        owned_pods = [pod for pod in pods if pod.metadata.owner_references and any(
            owner.uid == workload.metadata.uid for owner in pod.metadata.owner_references)]
    else:  # Standalone pods
        owned_pods = [pod for pod in pods if not pod.metadata.owner_references]

    selected_services = [service for service in services if service.spec.selector and any(
        all(item in pod.metadata.labels.items() for item in service.spec.selector.items()) for pod in owned_pods)]

    return {
        "replica_sets": owned_replica_sets,
        "pods": owned_pods,
        "services": selected_services
    }


def extract_deployment_details(deployment) -> dict:
    """
    Extract metadata, container, and status details from a given deployment.

    Args:
        deployment (object): Kubernetes deployment object.

    Returns:
        dict: Dictionary containing extracted details.
    """
    details = {
        "metadata": {
            "name": deployment.metadata.name,
            "namespace": deployment.metadata.namespace,
            "labels": deployment.metadata.labels,
            "annotations": deployment.metadata.annotations,
        },
        "spec": {
            "replicas": deployment.spec.replicas,
            "selector": deployment.spec.selector.match_labels,
            "min_ready_seconds": deployment.spec.min_ready_seconds,
            "strategy": deployment.spec.strategy.type,
            "revision_history_limit": deployment.spec.revision_history_limit,
            "progress_deadline_seconds": deployment.spec.progress_deadline_seconds
        },
        "container": {
            "name": deployment.spec.template.spec.containers[0].name,
            "image": deployment.spec.template.spec.containers[0].image,
            "env": [env.name for env in deployment.spec.template.spec.containers[0].env] if deployment.spec.template.spec.containers[0].env else [],
            "resources": {
                "requests": {
                    "cpu": deployment.spec.template.spec.containers[0].resources.requests.get('cpu', 'N/A') if deployment.spec.template.spec.containers[0].resources and deployment.spec.template.spec.containers[0].resources.requests else 'N/A',
                    "memory": deployment.spec.template.spec.containers[0].resources.requests.get('memory', 'N/A') if deployment.spec.template.spec.containers[0].resources and deployment.spec.template.spec.containers[0].resources.requests else 'N/A'
                },
                "limits": {
                    "cpu": deployment.spec.template.spec.containers[0].resources.limits.get('cpu', 'N/A') if deployment.spec.template.spec.containers[0].resources and deployment.spec.template.spec.containers[0].resources.limits else 'N/A',
                    "memory": deployment.spec.template.spec.containers[0].resources.limits.get('memory', 'N/A') if deployment.spec.template.spec.containers[0].resources and deployment.spec.template.spec.containers[0].resources.limits else 'N/A'
                }
            },
            "volume_mounts": [vm.name for vm in deployment.spec.template.spec.containers[0].volume_mounts] if deployment.spec.template.spec.containers[0].volume_mounts else [],
            "image_pull_policy": deployment.spec.template.spec.containers[0].image_pull_policy
        },
        "status": {
            "replicas": deployment.status.replicas,
            "updated_replicas": deployment.status.updated_replicas,
            "ready_replicas": deployment.status.ready_replicas,
            "available_replicas": deployment.status.available_replicas,
            "conditions": [condition.type for condition in deployment.status.conditions]
        }
    }
    return details


def generate_markdown(workload: object, pods: list, services: list) -> str:
    """
    Generate a Mermaid markdown representation for the given workload, pods, and services.

    Args:
        workload (object): The workload object.
        pods (list): A list of related pod objects.
        services (list): A list of related service objects.

    Returns:
        str: The Mermaid markdown string.
    """
    graph_def = ["graph TD"]

    # Add workload
    workload_name = workload.metadata.name
    workload_kind = type(workload).__name__
    graph_def.append(generate_node(workload_kind, workload_name))

    # Add pods and link them to workload
    for pod in pods:
        pod_name = pod.metadata.name
        graph_def.append(generate_node("Pod", pod_name))
        graph_def.append(generate_link(workload_kind, workload_name, "Pod", pod_name))

    # Add services and link them to pods
    for service in services:
        service_name = service.metadata.name
        graph_def.append(generate_node("Service", service_name))
        for pod in pods:
            pod_name = pod.metadata.name
            if service.spec.selector and all(
                    item in pod.metadata.labels.items() for item in service.spec.selector.items()):
                graph_def.append(generate_link("Service", service_name, "Pod", pod_name))

    return "```mermaid\n" + '\n'.join(graph_def) + "\n```"


def simplify_value(value):
    """Simplify complex values for visualization."""
    if isinstance(value, dict):
        return ', '.join(value.keys())
    elif isinstance(value, list):
        if len(value) > 3:
            return ', '.join([str(v) for v in value[:3]]) + ', ...'
        return ', '.join([str(v) for v in value])
    else:
        return str(value)


import json

def generate_deployment_visualization(details) -> str:
    """Generate the full Mermaid markdown for a given deployment."""
    dep_name = details['metadata']['name']

    # Metadata & Core Details
    metadata_core_def = [
        "graph TB",
        f"A[Deployment: {dep_name}] --> B[Metadata]",
    ]

    metadata = details['metadata']
    spec = details['spec']

    # # Generate metadata chain
    # prev_key = 'B'
    # for key in ['name', 'namespace', 'labels', 'annotations']:
    #     value_str = simplify_value(metadata.get(key, 'N/A'))
    #     curr_key = f"C_{key}"
    #     metadata_core_def.append(f"{prev_key} --> {curr_key}[{key}: {value_str}]")
    #     prev_key = curr_key

    # Generate metadata chain
    prev_key = 'B'
    for key in ['name', 'namespace', 'labels', 'annotations']:
        value_str = simplify_value(metadata.get(key, 'N/A'))
        curr_key = f"C_{key}"
        metadata_core_def.append(f"{prev_key} --> {curr_key}[{key}: {value_str}]")
        prev_key = curr_key

    # Generate spec chain
    metadata_core_def.append(f"A --> D[Spec]")
    prev_key = 'D'
    for key in ['replicas', 'selector', 'min_ready_seconds', 'strategy', 'revision_history_limit', 'progress_deadline_seconds']:
        value_str = simplify_value(spec.get(key, 'N/A'))
        curr_key = f"E_{key}"
        metadata_core_def.append(f"{prev_key} --> {curr_key}[{key}: {value_str}]")
        prev_key = curr_key

    metadata_core_def.extend([
        "classDef greenFill fill:#e1f7d5,stroke:#333,stroke-width:2px,color:#333;",
        "classDef yellowFill fill:#c7e59a,stroke:#333,stroke-width:2px,color:#333;",
        "class A,B,D greenFill",
        "class C_name,C_namespace,C_labels,C_annotations,E_replicas,E_selector,E_min_ready_seconds,E_strategy,E_revision_history_limit,E_progress_deadline_seconds yellowFill"
    ])

    # Container Details
    cpu_requests = details['container']['resources']['requests']['cpu']
    memory_requests = details['container']['resources']['requests']['memory']
    cpu_limits = details['container']['resources']['limits']['cpu']
    memory_limits = details['container']['resources']['limits']['memory']


    container_def = [
        "graph LR",
        f"A[Container: {details['container']['name']}]",
        f"A --> B_cpu_requests[CPU Requests: {cpu_requests}]",
        f"A --> B_memory_requests[Memory Requests: {memory_requests}]",
        f"A --> B_cpu_limits[CPU Limits: {cpu_limits}]",
        f"A --> B_memory_limits[Memory Limits: {memory_limits}]",
    ]

    for key, value in details['container'].items():
        if key != "resources":  # We've already handled the 'resources' key separately above
            value_str = simplify_value(value)
            container_def.append(f"A --> B_{key}[{key}: {value_str}]")

    container_def.extend([
        "classDef greenFill fill:#e1f7d5,stroke:#333,stroke-width:2px,color:#333;",
        "class A greenFill"
    ])

    # Status Overview
    status_def = [
        "graph TB",
        "A[Status]"
    ]
    for key, value in details['status'].items():
        value_str = simplify_value(value)
        status_def.append(f"A --> B_{key}[{key}: {value_str}]")

    status_def.extend([
        "classDef greenFill fill:#e1f7d5,stroke:#333,stroke-width:2px,color:#333;",
        "class A greenFill"
    ])

    full_markdown = (
            "# " + dep_name +
            "\n\n## Metadata & Core Details\n\n```mermaid\n" + '\n'.join(metadata_core_def) + "\n```\n\n" +
            "## Container Details\n\n```mermaid\n" + '\n'.join(container_def) + "\n```\n\n" +
            "## Status Overview\n\n```mermaid\n" + '\n'.join(status_def) + "\n```"
    )

    return full_markdown







def generate_node(kind: str, name: str) -> str:
    """
    Generate a node representation for Mermaid diagrams.

    Args:
        kind (str): The kind of the Kubernetes resource (e.g., "Pod", "Service").
        name (str): The name of the Kubernetes resource.

    Returns:
        str: The Mermaid node representation.
    """
    node_id = f"{name}_{kind.lower()}"  # Use descriptive node IDs
    label = f"{kind}: {name}" if kind not in ["Pod"] else name
    return f"{node_id}[{label}]"


def generate_link(source_kind: str, source_name: str, target_kind: str, target_name: str) -> str:
    """
    Generate a link representation for Mermaid diagrams.

    Args:
        source_kind (str): The kind of the source Kubernetes resource.
        source_name (str): The name of the source Kubernetes resource.
        target_kind (str): The kind of the target Kubernetes resource.
        target_name (str): The name of the target Kubernetes resource.

    Returns:
        str: The Mermaid link representation.
    """
    source_id = f"{source_name}_{source_kind.lower()}"
    target_id = f"{target_name}_{target_kind.lower()}"
    return f"{source_id} --> {target_id}"


async def main_async():
    """
    Asynchronous main function that fetches Kubernetes resources and generates markdown files.
    """
    # Create output directory based on cluster name if it doesn't exist
    output_dir = f"output_{current_context}"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    namespaces = fetch_namespaces()
    for ns in namespaces:
        namespace_name = ns.metadata.name
        logging.info(f"Processing namespace: {namespace_name}")

        workloads = fetch_all_workloads(namespace_name)
        for workload in workloads:
            if isinstance(workload, client.V1Deployment):
                details = extract_deployment_details(workload)
                markdown_content = generate_deployment_visualization(details)
                with open(os.path.join(output_dir, f"{namespace_name}_{workload.metadata.name}_metadata.md"), "w") as f:
                    f.write(markdown_content)


def main():
    """
    Main function that sets up the asynchronous loop and calls the main_async function.
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_async())


if __name__ == "__main__":
    main()
