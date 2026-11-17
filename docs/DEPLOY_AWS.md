# Deploy ScamShield on one AWS EC2 server

This is the final deployment step after local tests pass. No server has been created by this project.
You need an AWS account, an SSH key and a domain/subdomain you control. AWS resources and domains can incur charges.

## 1. Create the server

In the AWS console, choose a region (Mumbai/ap-south-1 is suitable for this project) and launch:

- Ubuntu Server 24.04 LTS, x86_64.
- A small instance with at least 2 GB RAM, such as t3.small, for model builds and three containers.
- A 20 GB or larger encrypted EBS disk.
- Your SSH key pair; keep its private key outside this repository.
- A security group allowing TCP 22 from **your IP only**, TCP 80 and TCP 443 from the internet.
- No inbound rules for 5432 or 8000.

Use a stable public IP (for example an associated Elastic IP) for the domain. Check the AWS console's current charges before launching.
Create a DNS A record such as scamshield.yourdomain.com pointing to that IPv4 address.
Remove incorrect AAAA records unless you have configured working IPv6.

These ports follow [AWS's web-server security-group guidance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html).

## 2. Install Docker

Connect from PowerShell:

```powershell
ssh -i C:/path/to/key.pem ubuntu@YOUR_EC2_IP
```

On Ubuntu, install Docker Engine and the Compose plugin using the [official Ubuntu installation guide](https://docs.docker.com/engine/install/ubuntu/).
Use Docker's apt repository method, then install the packages:

```bash
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo apt install python3 curl git
sudo usermod -aG docker ubuntu
```

Disconnect and reconnect so group membership applies. Verify:

```bash
docker info
docker compose version
```

## 3. Copy the project

If you have put this project in GitHub, clone your repository into ~/scamshield.
Otherwise, from this project's directory in Windows PowerShell:

```powershell
tar -czf scamshield-source.tar.gz --exclude=.venv --exclude=.git --exclude=.env --exclude=api/model --exclude=backups --exclude=.releases --exclude=*.db --exclude=*.pem --exclude=*.key api ui scripts docs .github README.md pyproject.toml docker-compose.yml docker-compose.prod.yml .env.example
scp -i C:/path/to/key.pem scamshield-source.tar.gz ubuntu@YOUR_EC2_IP:~/
```

On EC2:

```bash
mkdir -p ~/scamshield
tar -xzf ~/scamshield-source.tar.gz -C ~/scamshield
cd ~/scamshield
cp .env.example .env
chmod 600 .env
python3 -c 'import secrets; print(secrets.token_hex(24))'
nano .env
```

Put the generated password and your actual domain into .env:

```dotenv
DB_PASSWORD=YOUR_GENERATED_PASSWORD
SITE_ADDRESS=scamshield.yourdomain.com
```

Do not include https://, a port or a path in SITE_ADDRESS. Do not commit .env.
Hex passwords avoid shell/Compose interpolation mistakes; the app also safely constructs database URLs for special characters.
Changing DB_PASSWORD after PostgreSQL has initialized does not change the stored database password. Rotate it with PostgreSQL administration before updating .env.

## 4. Deploy

From ~/scamshield:

```bash
bash scripts/deploy.sh
```

The script checks configuration, builds uniquely tagged API/UI images, validates Caddy, starts the three containers,
waits for their health checks, and checks the public HTTPS health endpoint.
It saves the active release tag only after success. A failed update attempts to restore the previous v2 release.
No ECR, AWS CLI credentials or GitHub deployment secrets are needed.

Open https://scamshield.yourdomain.com and run:

```bash
python3 scripts/smoke.py https://scamshield.yourdomain.com
export TAG="$(cat .releases/current)"
docker compose --project-name scamshield --env-file .env -f ".releases/$TAG/compose.yml" ps
```

Caddy obtains and renews its certificate automatically. Its certificate state persists in a Docker volume.
A first deployment with incorrect DNS or closed ports will fail the public health check; correct those settings and use a new release tag.

## 5. Update or roll back

Copy or pull reviewed source updates, run tests, then:

```bash
bash scripts/deploy.sh
```

A new timestamp tag is generated. Deployments are serialized using flock.
Each release saves its Compose configuration and retains its images. Do not run image prune while you need rollback.

List tags and restore one:

```bash
ls .releases
bash scripts/deploy.sh --rollback 20261101T120000Z
```

Replace the example with an actual saved v2 tag. Rollback changes app images/configuration, not database data or .env secrets.
Old deployments from the original raw-history schema are not supported rollback targets.
A single-host update can have brief downtime.

## 6. Backup and restore

Create an aggregate-counter backup:

```bash
bash scripts/backup.sh
```

Copy the dump to private off-host storage. Keep only the retention period you need.
For automated daily backups on this server, add a cron entry through crontab -e:

```cron
0 2 * * * cd /home/ubuntu/scamshield && /bin/bash scripts/backup.sh >> /home/ubuntu/scamshield/backups.log 2>&1
```

Cron alone does not copy backups off the server or expire them; manage those steps explicitly.

To replace the current counters with a chosen backup, stop incoming traffic first. **This overwrites current database contents.**
Use an actual dump path:

```bash
export TAG="$(cat .releases/current)"
COMPOSE_FILE=".releases/$TAG/compose.yml"
docker compose --project-name scamshield --env-file .env -f "$COMPOSE_FILE" stop ui api
docker compose --project-name scamshield --env-file .env -f "$COMPOSE_FILE" exec -T db \
  pg_restore -U scam -d scamshield --clean --if-exists --no-owner --exit-on-error < backups/YOUR_BACKUP.dump
docker compose --project-name scamshield --env-file .env -f "$COMPOSE_FILE" up -d --wait
python3 scripts/smoke.py https://scamshield.yourdomain.com
```

Test restore on a disposable environment before relying on backups.
Do not use docker compose down -v on the production stack unless you intend to delete its database and certificate volumes.

## Troubleshooting

- **HTTPS not ready:** check the domain A/AAAA records, instance public IP, outbound internet and inbound TCP 80/443.
- **API unhealthy:** inspect API/DB logs; /api/health reports 503 for a missing model or unavailable database.
- **Database authentication fails after an edit:** PostgreSQL volumes retain the original database password.
- **Build runs out of memory:** use at least 2 GB RAM or build on a larger temporary machine.
- **First deployment fails:** there is no previous release to restore. Inspect logs, correct the cause and redeploy with a new tag.
- **Missing Docker engine on Windows:** start Docker Desktop and fix its WSL/virtualization startup error before using local Compose.

Logs, with TAG set:

```bash
docker compose --project-name scamshield --env-file .env -f ".releases/$TAG/compose.yml" logs --tail=100
```
