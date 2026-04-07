#!/bin/bash
deploy_dir='deploy_scripts'

cd "${deploy_dir}/me/lambda"
bash build_lambda.sh
terraform init -upgrade
terraform apply -auto-approve
