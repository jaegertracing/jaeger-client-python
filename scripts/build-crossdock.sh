#!/bin/bash

set -euxf -o pipefail

make crossdock

REPO=jaegertracing/xdock-py
BRANCH=${BRANCH:?'missing BRANCH env var'}
TORNADO=${TORNADO:?'missing TORNADO env var'}
TAG=$([ "$BRANCH" == "master" ] && echo "latest" || echo "$BRANCH")
COMMIT=${GITHUB_SHA::8}
DOCKERHUB_LOGIN=${DOCKERHUB_LOGIN:-false}

echo "REPO=$REPO, BRANCH=$BRANCH, TAG=$TAG, TORNADO=$TORNADO, COMMIT=$COMMIT"

# Only push the docker container to dockerhub for master branch and when dockerhub login is done
if [[ "$BRANCH" == "master" && "$DOCKERHUB_LOGIN" == "true" ]]; then
  echo 'upload to Docker Hub'
else 
  echo 'skip docker upload for PR'
  exit 0
fi

# This image is already built in "make crossdock" step
# not specifying a tag means "latest" tag implicitly
docker tag $REPO $REPO:$COMMIT
docker tag $REPO:$COMMIT $REPO:$TAG
docker push $REPO
