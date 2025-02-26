#!/bin/bash
deploy_dir='deploy_scripts'

dirs=(`ls -1 $deploy_dir/`)
for dir in "${dirs[@]}"; do
    cd "${deploy_dir}/${dir}/lambda"
    bash build_lambda.sh
    terraform apply -auto-approve
    cd ../../../
done
