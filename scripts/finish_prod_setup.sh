#!/bin/bash
set -e

# 1. Build the Image (Required because we changed code)
echo "1. Building new container image..."
/Users/abhijeet/Downloads/google-cloud-sdk/bin/gcloud builds submit --tag gcr.io/striking-effort-475914-v5/eventyay-next app/ --quiet

# 2. Run Database Migrations (using Cloud Run Job with Sidecar)
echo "2. Running Database Migrations..."

# Delete existing job if any
/Users/abhijeet/Downloads/google-cloud-sdk/bin/gcloud run jobs delete migrate-db --region us-central1 --quiet || true

# Create and Execute Job from YAML
/Users/abhijeet/Downloads/google-cloud-sdk/bin/gcloud run jobs replace cloudrun-migration.yaml --region us-central1 --quiet
/Users/abhijeet/Downloads/google-cloud-sdk/bin/gcloud run jobs execute migrate-db --region us-central1 --wait --quiet

# 3. Deploy Services
echo "3. Deploying Web Service..."
/Users/abhijeet/Downloads/google-cloud-sdk/bin/gcloud run services replace cloudrun-web.yaml --region=us-central1 --quiet
/Users/abhijeet/Downloads/google-cloud-sdk/bin/gcloud run services update eventyay-next-web \
    --region=us-central1 \
    --network=default \
    --subnet=default \
    --vpc-egress=private-ranges-only \
    --quiet

echo "4. Deploying Worker Service..."
/Users/abhijeet/Downloads/google-cloud-sdk/bin/gcloud run services replace cloudrun-worker.yaml --region=us-central1 --quiet
/Users/abhijeet/Downloads/google-cloud-sdk/bin/gcloud run services update eventyay-next-worker \
    --region=us-central1 \
    --network=default \
    --subnet=default \
    --vpc-egress=private-ranges-only \
    --quiet

echo "5. Enabling Public Access..."
/Users/abhijeet/Downloads/google-cloud-sdk/bin/gcloud run services add-iam-policy-binding eventyay-next-web --member="allUsers" --role="roles/run.invoker" --region=us-central1 --quiet

echo "---------------------------------------------------"
echo "Deployment Complete! Your Production App is Ready."
