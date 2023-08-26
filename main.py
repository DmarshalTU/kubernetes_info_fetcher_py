import os
import asyncio
from kubernetes import client, config

config.load_kube_config()

# Fetch current context to get cluster name
current_context = config.list_kube_config_contexts()[1]['context']['cluster']

def fetch_namespaces() -> list:
    try:
        v1 = client.CoreV1Api()
        return v1.list_namespace().items
    except Exception as e:
        print(f"Error fetching namespaces: {e}")
        return []

def fetch_all_workloads(namespace_name: str) -> list:
    try:
        apps_v1 = client.AppsV1Api()
        deployments = apps_v1.list_namespaced_deployment(namespace_name).items
        stateful_sets = apps_v1.list_namespaced_stateful_set(namespace_name).items
        daemon_sets = apps_v1.list_namespaced_daemon_set(namespace_name).items
        return deployments + stateful_sets + daemon_sets
    except Exception as e:
        print(f"Error fetching workloads for namespace {namespace_name}: {e}")
        return []

def fetch_pods_for_workload(namespace_name: str, label_selector: str):
    try:
        v1 = client.CoreV1Api()
        return v1.list_namespaced_pod(namespace_name, label_selector=label_selector).items
    except Exception as e:
        print(f"Error fetching pods for namespace {namespace_name} with label selector {label_selector}: {e}")
        return []

def fetch_services_for_workload(namespace_name: str, label_selector: str) -> list:
    try:
        v1 = client.CoreV1Api()
        return v1.list_namespaced_service(namespace_name, label_selector=label_selector).items
    except Exception as e:
        print(f"Error fetching services for namespace {namespace_name} with label selector {label_selector}: {e}")
        return []

def fetch_resources_for_workload(workload) -> dict:
    namespace_name = workload.metadata.namespace
    workload_name = workload.metadata.name
    workload_kind = type(workload).__name__

    owned_replica_sets = []
    owned_pods = []
    selected_services = []

    # Fetch all potential child resources in the namespace
    pods = fetch_pods_for_workload(namespace_name, "")
    services = fetch_services_for_workload(namespace_name, "")
    apps_v1 = client.AppsV1Api()
    replica_sets = apps_v1.list_namespaced_replica_set(namespace_name).items

    if workload_kind == "V1Deployment":
        owned_replica_sets = [rs for rs in replica_sets if any(owner.uid == workload.metadata.uid for owner in rs.metadata.owner_references)]
        owned_pods = [pod for pod in pods if any(owner.uid == rs.metadata.uid for rs in owned_replica_sets for owner in pod.metadata.owner_references)]
    elif workload_kind in ["V1StatefulSet", "V1DaemonSet", "V1ReplicaSet"]:
        owned_pods = [pod for pod in pods if pod.metadata.owner_references and any(owner.uid == workload.metadata.uid for owner in pod.metadata.owner_references)]
    else:  # Standalone pods
        owned_pods = [pod for pod in pods if not pod.metadata.owner_references]

    selected_services = [service for service in services if service.spec.selector and any(all(item in pod.metadata.labels.items() for item in service.spec.selector.items()) for pod in owned_pods)]


    return {
        "replica_sets": owned_replica_sets,
        "pods": owned_pods,
        "services": selected_services
    }


def generate_markdown(workload, pods, services) -> str:
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
            if service.spec.selector and all(item in pod.metadata.labels.items() for item in service.spec.selector.items()):
                graph_def.append(generate_link("Service", service_name, "Pod", pod_name))

    return "```mermaid\n" + '\n'.join(graph_def) + "\n```"

def generate_node(kind, name) -> str:
    label = f"{kind}: {name}" if kind not in ["Pod"] else name
    return f"{kind}_{name}[{label}]"

def generate_link(source_kind, source_name, target_kind, target_name) -> str:
    return f"{source_kind}{source_name} --> {target_kind}{target_name}"

async def main_async():
    # Create output directory based on cluster name if it doesn't exist
    output_dir = f"output_{current_context}"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    namespaces = fetch_namespaces()
    for ns in namespaces:
        namespace_name = ns.metadata.name
        print(f"Processing namespace: {namespace_name}")

        workloads = fetch_all_workloads(namespace_name)
        for workload in workloads:
            resources = fetch_resources_for_workload(workload)
            markdown_content = generate_markdown(workload, resources["pods"], resources["services"])
            with open(os.path.join(output_dir, f"{namespace_name}_{workload.metadata.name}.md"), "w") as f:
                f.write(markdown_content)

def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_async())

if __name__ == "__main__":
    main()
