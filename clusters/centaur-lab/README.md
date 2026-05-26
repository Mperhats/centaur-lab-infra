# centaur-lab Cluster

This directory is the cluster definition for one Centaur deployment. It keeps
the environment-specific surface small: Argo CD bootstrap resources, Helm
values, and any raw manifests that live beside the chart.

Apply `argocd/bootstrap/00-namespaces.yaml` first, then
`argocd/bootstrap/centaur.yaml`.
