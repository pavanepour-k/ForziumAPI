terraform {
  required_providers {
    kubernetes = {
      source = "hashicorp/kubernetes"
      version = ">= 2.0"
    }
  }
}

provider "kubernetes" {
  config_path = var.kubeconfig
}

variable "image" {
  type    = string
  default = "forzium:latest"
}

variable "replicas" {
  type    = number
  default = 1
}

variable "kubeconfig" {
  type    = string
  default = "~/.kube/config"
}

resource "kubernetes_deployment" "forzium" {
  metadata {
    name = "forzium"
    labels = {
      app = "forzium"
    }
  }
  spec {
    replicas = var.replicas
    selector {
      match_labels = {
        app = "forzium"
      }
    }
    template {
      metadata {
        labels = {
          app = "forzium"
        }
      }
      spec {
        container {
          name  = "forzium"
          image = var.image
          port {
            container_port = 8000
          }
        }
      }
    }
  }
}