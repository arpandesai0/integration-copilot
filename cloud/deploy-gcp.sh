#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"

project_id="${PROJECT_ID:-}"
requested_account="${GCLOUD_ACCOUNT:-}"
region="${REGION:-us-central1}"
vertex_location="${VERTEX_LOCATION:-${region}}"
backend_service="${BACKEND_SERVICE:-integration-copilot-api}"
frontend_service="${FRONTEND_SERVICE:-integration-copilot-web}"
backend_sa_name="${BACKEND_SA_NAME:-integration-copilot-api}"
frontend_sa_name="${FRONTEND_SA_NAME:-integration-copilot-web}"
secret_name="${MONGODB_SECRET_NAME:-integration-copilot-mongodb-uri}"
mongodb_database="${MONGODB_DATABASE:-integration_copilot}"
artifact_repo="${ARTIFACT_REPO:-integration-copilot}"

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

command -v gcloud >/dev/null 2>&1 || die "gcloud CLI is not installed"
[[ -n "${project_id}" ]] || die "set PROJECT_ID to the target Google Cloud project"

if [[ "${ALLOW_EPHEMERAL_SQLITE:-0}" != "1" ]]; then
  die "the app still uses local SQLite metadata. Set ALLOW_EPHEMERAL_SQLITE=1 for a demo deployment; do not use it for persistent production data"
fi

if [[ -n "${requested_account}" ]]; then
  if ! gcloud auth list --filter="account=${requested_account}" --format='value(account)' | grep -Fxq "${requested_account}"; then
    die "${requested_account} is not authenticated; run: gcloud auth login ${requested_account}"
  fi
  gcloud config set account "${requested_account}" --quiet >/dev/null
fi

active_account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1)"
[[ -n "${active_account}" ]] || die "no active gcloud account; run: gcloud auth login"
if ! gcloud projects describe "${project_id}" --account "${active_account}" >/dev/null 2>&1; then
  die "${active_account} cannot access project ${project_id}; authenticate the owning account and rerun with GCLOUD_ACCOUNT=that-account"
fi
if [[ "${active_account}" == *.gserviceaccount.com ]]; then
  deployer_member="serviceAccount:${active_account}"
else
  deployer_member="user:${active_account}"
fi

backend_sa="${backend_sa_name}@${project_id}.iam.gserviceaccount.com"
frontend_sa="${frontend_sa_name}@${project_id}.iam.gserviceaccount.com"
image="${region}-docker.pkg.dev/${project_id}/${artifact_repo}/${frontend_service}:$(date -u +%Y%m%d-%H%M%S)"

printf 'Deploying project %s in %s as %s\n' "${project_id}" "${region}" "${active_account}"
gcloud config set project "${project_id}" --quiet >/dev/null

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com

for account_name in "${backend_sa_name}" "${frontend_sa_name}"; do
  account_email="${account_name}@${project_id}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "${account_email}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${account_name}" \
      --display-name="Integration Copilot ${account_name##*-} runtime"
  fi
  gcloud iam service-accounts add-iam-policy-binding "${account_email}" \
    --member="${deployer_member}" \
    --role="roles/iam.serviceAccountUser" >/dev/null
done

gcloud projects add-iam-policy-binding "${project_id}" \
  --member="serviceAccount:${backend_sa}" \
  --role="roles/aiplatform.user" >/dev/null

if ! gcloud secrets describe "${secret_name}" >/dev/null 2>&1; then
  gcloud secrets create "${secret_name}" --replication-policy=automatic
fi

secret_version=""
if [[ -n "${MONGODB_URI:-}" ]]; then
  secret_ref="$(printf '%s' "${MONGODB_URI}" | gcloud secrets versions add "${secret_name}" --data-file=- --format='value(name)')"
  secret_version="${secret_ref##*/}"
elif ! gcloud secrets versions list "${secret_name}" --filter='state=ENABLED' --format='value(name)' --limit=1 | grep -q .; then
  read -r -s -p "MongoDB Atlas URI: " mongodb_uri
  printf '\n'
  [[ -n "${mongodb_uri}" ]] || die "MongoDB URI cannot be empty"
  secret_ref="$(printf '%s' "${mongodb_uri}" | gcloud secrets versions add "${secret_name}" --data-file=- --format='value(name)')"
  unset mongodb_uri
  secret_version="${secret_ref##*/}"
else
  secret_version="$(gcloud secrets versions list "${secret_name}" --filter='state=ENABLED' --sort-by='~createTime' --limit=1 --format='value(name)')"
  secret_version="${secret_version##*/}"
fi

gcloud secrets add-iam-policy-binding "${secret_name}" \
  --member="serviceAccount:${backend_sa}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

gcloud run deploy "${backend_service}" \
  --source "${repo_dir}/backend" \
  --region "${region}" \
  --service-account "${backend_sa}" \
  --allow-unauthenticated \
  --port 8000 \
  --timeout 300 \
  --max-instances 1 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${project_id},GOOGLE_CLOUD_LOCATION=${vertex_location},MONGODB_DATABASE=${mongodb_database},FRONTEND_URL=https://example.invalid,COOKIE_SECURE=true" \
  --set-secrets "MONGODB_URI=${secret_name}:${secret_version}"

backend_url="$(gcloud run services describe "${backend_service}" --region "${region}" --format='value(status.url)')"
[[ -n "${backend_url}" ]] || die "could not determine backend URL"

if ! gcloud artifacts repositories describe "${artifact_repo}" --location "${region}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${artifact_repo}" \
    --location "${region}" \
    --repository-format docker \
    --description="Integration Copilot images"
fi

gcloud builds submit "${repo_dir}/frontend" \
  --config "${script_dir}/cloudbuild.frontend.yaml" \
  --substitutions "_IMAGE=${image},_NEXT_PUBLIC_API_URL=${backend_url}"

gcloud run deploy "${frontend_service}" \
  --image "${image}" \
  --region "${region}" \
  --service-account "${frontend_sa}" \
  --allow-unauthenticated \
  --port 3000

frontend_url="$(gcloud run services describe "${frontend_service}" --region "${region}" --format='value(status.url)')"
[[ -n "${frontend_url}" ]] || die "could not determine frontend URL"

gcloud run services update "${backend_service}" \
  --region "${region}" \
  --update-env-vars "FRONTEND_URL=${frontend_url},COOKIE_SECURE=true" >/dev/null

printf '\nDeployment complete.\nFrontend: %s\nBackend:  %s\n' "${frontend_url}" "${backend_url}"
printf 'Important: configure MongoDB Atlas Network Access for Cloud Run egress. SQLite metadata remains ephemeral in this demo deployment.\n'

