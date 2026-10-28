#!/bin/bash

TAG="ghcr.io/inria-empenn/fmri-confs-runner:latest"
TARNAME="fmri-confs-runner.tar"
LOCAL_PATH="/tmp/$TARNAME"
ABACA_PATH="$HOME/fmri-conf-runner/$TARNAME"

echo "Pulling docker image from GitHub..."
docker pull $TAG
echo "Saving docker image as tar..."
docker save -o "$LOCAL_PATH" "$TAG"
echo "Transferring tar to Abaca..."
scp "$LOCAL_PATH" "rennes.g5k:$ABACA_PATH"
rm -f "$LOCAL_PATH"
echo "Docker image saved as [$ABACA_PATH] on Abaca"