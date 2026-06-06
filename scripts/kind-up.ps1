# Create a local kind cluster with nginx-ingress preinstalled.
$ErrorActionPreference = "Stop"

$ClusterName = if ($env:CLUSTER_NAME) { $env:CLUSTER_NAME } else { "scm" }

if (-not (Get-Command kind -ErrorAction SilentlyContinue)) {
    Write-Host "kind not installed. See https://kind.sigs.k8s.io/docs/user/quick-start/"
    exit 1
}
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Host "kubectl not installed. See https://kubernetes.io/docs/tasks/tools/"
    exit 1
}

$existing = & kind get clusters
if ($existing -contains $ClusterName) {
    Write-Host "kind cluster '$ClusterName' already exists"
} else {
    Write-Host "creating kind cluster '$ClusterName'..."
    $config = @'
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
'@
    $config | & kind create cluster --name $ClusterName --config -
}

Write-Host "installing nginx-ingress..."
& kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

Write-Host "waiting for nginx-ingress to be ready..."
& kubectl wait --namespace ingress-nginx `
    --for=condition=ready pod `
    --selector=app.kubernetes.io/component=controller `
    --timeout=180s

Write-Host "cluster ready. point your browser at http://scm.localtest.me after 'just deploy-staging'."
