import os
import asyncio
from kubernetes import client, config
import logging


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
            resources = fetch_resources_for_workload(workload)
            markdown_content = generate_markdown(workload, resources["pods"], resources["services"])
            with open(os.path.join(output_dir, f"{namespace_name}_{workload.metadata.name}.md"), "w") as f:
                f.write(markdown_content)


def main():
    """
    Main function that sets up the asynchronous loop and calls the main_async function.
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_async())


if __name__ == "__main__":
    main()
