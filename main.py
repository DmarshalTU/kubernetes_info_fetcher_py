import os
import asyncio
from kubernetes import client, config
import logging
import argparse


parser = argparse.ArgumentParser(description='Generate Mermaid markdown for Kubernetes deployments.')
parser.add_argument('--config', type=str, help='Path to the Kubernetes configuration file', default=None)
args = parser.parse_args()

config_path = args.config
config.load_kube_config(config_path)
current_context = config.list_kube_config_contexts()[1]['context']['cluster']


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


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


def generate_deployment_visualization(details) -> str:
    """Generate the refined Mermaid markdown for a given deployment."""
    dep_name = details['metadata']['name']
    namespace_name = details['metadata']['namespace']

    # Fetch pods associated with the deployment
    label_selector = ",".join([f"{k}={v}" for k, v in details['spec']['selector'].items()])
    pods = fetch_pods_for_workload(namespace_name, label_selector)
    services = fetch_services_for_workload(namespace_name, label_selector)

    # Metadata & Core Details
    metadata_core_def = [
        "graph LR",
        f"A[Deployment: {dep_name}]",
    ]

    # Generate metadata chain
    for key in ['name', 'namespace', 'labels', 'annotations']:
        value_str = simplify_value(details['metadata'].get(key, 'N/A'))
        node_id = f"meta_{key}"
        metadata_core_def.append(f"A --> {node_id}[{key}: {value_str}]")

    # Container Details
    container_details_def = [
        f"C[Container: {details['container']['name']}]",
    ]

    for key in ['name', 'image', 'env', 'volume_mounts', 'image_pull_policy']:
        value_str = simplify_value(details['container'].get(key, 'N/A'))
        node_id = f"cont_{key}"
        container_details_def.append(f"C --> {node_id}[{key}: {value_str}]")

    # Services Details
    service_details_def = []
    for service in services:
        service_name = service.metadata.name
        node_id = f"service_{service_name}"
        service_details_def.append(f"{node_id}[Service: {service_name}]")
        # Link service to Deployment
        metadata_core_def.append(f"A --> {node_id}")

        # Link service to appropriate pods based on label selectors
        for pod in pods:
            if service.spec.selector and all(
                    item in pod.metadata.labels.items() for item in service.spec.selector.items()):
                pod_node_id = f"pod_{pod.metadata.name}"
                service_details_def.append(f"{node_id} --> {pod_node_id}")

    # Add resources details (requests & limits) separately
    resources = details['container'].get('resources', {})
    for res_type, res_values in resources.items():
        for key, value in res_values.items():
            node_id = f"cont_{res_type}_{key}"
            container_details_def.append(f"C --> {node_id}[{res_type} {key}: {value}]")

    # Link Deployment to Container
    metadata_core_def.append("A --> C")

    # Status Overview
    status_def = [
        "S[Status]"
    ]
    for key in details['status'].keys():
        value_str = simplify_value(details['status'].get(key, 'N/A'))
        node_id = f"status_{key}"
        status_def.append(f"S --> {node_id}[{key}: {value_str}]")

    # Link Deployment to Status
    metadata_core_def.append("A --> S")

    # Fetch services and link them to pods
    services = fetch_services_for_workload(namespace_name, label_selector)
    service_def = []
    for service in services:
        service_name = service.metadata.name
        node_id = f"service_{service_name}"
        service_def.append(f"{node_id}[Service: {service_name}]")
        # Link service to Deployment
        metadata_core_def.append(f"A --> {node_id}")

        # Link service to appropriate pods based on label selectors
        for pod in pods:
            if service.spec.selector and all(
                    item in pod.metadata.labels.items() for item in service.spec.selector.items()):
                pod_node_id = f"pod_{pod.metadata.name}"
                service_def.append(f"{node_id} --> {pod_node_id}")

    class_defs = [
        "classDef greenFill fill:#e1f7d5,stroke:#333,stroke-width:2px,color:#333;",
        "classDef yellowFill fill:#c7e59a,stroke:#333,stroke-width:2px,color:#333;",
        "class A greenFill",
        "class C,S yellowFill"
    ]

    full_markdown = (
            "```mermaid\n" +
            '\n'.join(metadata_core_def + container_details_def + status_def + service_details_def + class_defs) +
            "\n```"
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
