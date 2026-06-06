#!/usr/bin/env bash
# Create a local kind cluster with nginx-ingress preinstalled.
# Idempotent: re-runnable; will skip cluster creation if already present.
set -euo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-scm}

if ! command -v kind >/dev/null 2>&1; then
    echo "kind not installed. See https://kind.sigs.k8s.io/docs/user/quick-start/"
    exit 1
fi
if ! command -v kubectl >/dev/null 2>&1; then
    echo "kubectl not installed. See https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo "kind cluster '${CLUSTER_NAME}' already exists"
else
    echo "creating kind cluster '${CLUSTER_NAME}'..."
    cat <<EOF | kind create cluster --name "${CLUSTER_NAME}" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
EOF
fi

echo "installing nginx-ingress..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

echo "waiting for nginx-ingress to be ready..."
kubectl wait --namespace ingress-nginx \
    --for=condition=ready pod \
    --selector=app.kubernetes.io/component=controller \
    --timeout=180s

echo "cluster ready. point your browser at http://scm.localtest.me after 'just deploy-staging'."
