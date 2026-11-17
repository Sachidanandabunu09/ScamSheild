# Start and restart ScamShield on AWS

This runbook is for the existing public-IP demo on the `scamshield-server` EC2 instance. The app is already deployed in `~/scamshield` and uses HTTP on port 80.

## 1. Start the EC2 instance

1. Open the [AWS EC2 console](https://console.aws.amazon.com/ec2/) and select **Asia Pacific (Mumbai)** (`ap-south-1`).
2. Go to **Instances** and select **scamshield-server**.
3. If the instance is **Stopped**, choose **Instance state → Start instance**.
4. Wait for the state to show **Running** and for the status checks to pass.
5. Copy the current **Public IPv4 address** from the instance details. Use this address for the rest of the guide because it can change after a stop and start.

## 2. Verify the website

Replace `PUBLIC_IP` with the address copied from EC2. Open these addresses in your laptop browser:

- `http://PUBLIC_IP/` opens the ScamShield interface.
- `http://PUBLIC_IP/api/health` checks the API, model and database.

The health endpoint should return:

```json
{"status":"ok","model_loaded":true,"database":"ok"}
```

Click **KYC request**, then **Analyze message**. If the page shows a risk score and explanation, the app is ready for your evaluation. If the interface or API fails to load, continue with step 3.

## 3. Start the containers manually if needed

Open **PowerShell on Windows** and replace `PUBLIC_IP` in this command:

```powershell
ssh -i "D:\sem_5\Cloud Computing\scamshield-server.pem" ubuntu@PUBLIC_IP
```

If SSH times out, confirm the public IPv4 address and EC2 status checks. If you switched between college Wi-Fi and a mobile hotspot, open the instance's **Security** tab, select its security group, and use **Edit inbound rules** to refresh **My IP** for SSH on port 22. Save the rule and retry.

Run the following in the **Ubuntu SSH terminal**:

```bash
cd ~/scamshield
sudo systemctl start docker
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --wait --wait-timeout 300
docker compose -f docker-compose.yml -f docker-compose.demo.yml ps
```

Look for all three services, `db`, `api` and `ui`, to be **Up (healthy)**. Repeat the browser checks in step 2. You can also run the end-to-end check from Ubuntu:

```bash
python3 scripts/smoke.py http://127.0.0.1
```

If a service fails to start or stays unhealthy, inspect its recent logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml logs --tail=80 db api ui
```

## 4. Restart all three containers while EC2 is running

Run these commands in the **Ubuntu SSH terminal**. The website will be briefly unavailable.

```bash
cd ~/scamshield
docker compose -f docker-compose.yml -f docker-compose.demo.yml stop
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --wait --wait-timeout 300
docker compose -f docker-compose.yml -f docker-compose.demo.yml ps
```

Repeat the browser checks in step 2. The restart preserves the PostgreSQL volume. Keep the existing `.env` and database password. Add `--build` to `up` when you want to deploy changes to the source files.

## 5. Stop EC2 after your evaluation

1. Select **scamshield-server** in the EC2 console.
2. Choose **Instance state → Stop instance** and confirm.
3. Wait until the state shows **Stopped**.

Use **Stop instance** to retain the server disk for your next demo. Compute charges stop when the instance is stopped, and the attached EBS disk remains billable. [AWS instance lifecycle](https://docs.aws.amazon.com/us_en/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)
