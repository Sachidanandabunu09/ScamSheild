"""Synthetic India-specific scam / legitimate message generator.

Why synthetic? Public datasets (UCI SMS Spam) are UK-centric and miss Indian scam
patterns (KYC, UPI cashback, electricity disconnection, PAN suspension...).
These templates are modelled on commonly reported scam types. For production,
replace/extend with real, labelled messages (e.g. reports from cybercrime.gov.in).
"""

import random

BANKS = [
    "SBI",
    "HDFC Bank",
    "ICICI Bank",
    "Axis Bank",
    "Kotak",
    "PNB",
    "Bank of Baroda",
    "Paytm Payments Bank",
]
BANK_TAG = ["SBIINB", "HDFCBK", "ICICIB", "AXISBK", "KOTAKB", "PNBSMS"]
FAKE_DOMAINS = [
    "sbi-kyc-update{n}.xyz",
    "hdfc-secure-verify.top",
    "icici-netbanking-login.click",
    "paytm-reward{n}.live",
    "upi-cashback-claim.icu",
    "kyc-verify-now{n}.work",
    "bit.ly/3x{c}{c}{n}",
    "tinyurl.com/{c}{n}kyc",
    "incometax-refund-gov.in.cc",
    "amazon-gift-claim{n}.buzz",
    "pan-card-update.support",
    "cutt.ly/{c}{c}{n}",
]


def _rand_url(r):
    t = r.choice(FAKE_DOMAINS)

    def c():
        return r.choice("abcdefghjkmnpqrstuvwxyz")

    out = t
    while "{c}" in out:
        out = out.replace("{c}", c(), 1)
    out = out.replace("{n}", str(r.randint(10, 9999)))
    return ("http://" if r.random() < 0.6 else "https://") + out


def _phone(r):
    return str(r.choice([6, 7, 8, 9])) + "".join(str(r.randint(0, 9)) for _ in range(9))


def _amt(r, lo=500, hi=250000):
    return f"{r.randint(lo, hi):,}"


SCAM = [
    lambda r: (
        f"Dear customer, your {r.choice(BANKS)} account will be blocked today. Update KYC immediately: {_rand_url(r)}"
    ),
    lambda r: (
        f"Your {r.choice(BANKS)} KYC has expired. Account will be suspended in 24 hrs. Complete verification now {_rand_url(r)}"
    ),
    lambda r: (
        f"Congratulations! You have received Rs {_amt(r, 100, 5000)} UPI cashback. Click {_rand_url(r)} to claim now"
    ),
    lambda r: (
        f"Dear consumer, your electricity power will be disconnected tonight 9:30 PM due to unpaid bill. Call {_phone(r)} immediately"
    ),
    lambda r: (
        f"Congratulations!! You won Rs {_amt(r, 500000, 2500000)} in KBC lottery. Contact WhatsApp {_phone(r)} to claim prize"
    ),
    lambda r: (
        f"Part time job work from home. Earn Rs {_amt(r, 2000, 9000)} daily. Just like YouTube videos. Join Telegram {_rand_url(r)}"
    ),
    lambda r: (
        f"Your parcel is held at customs. Pay Rs {_amt(r, 49, 999)} clearance fee at {_rand_url(r)} or it will be returned"
    ),
    lambda r: f"Your PAN card is suspended. Update PAN details now to avoid penalty {_rand_url(r)}",
    lambda r: (
        f"Income Tax Dept: refund of Rs {_amt(r, 5000, 60000)} approved. Verify your bank account at {_rand_url(r)}"
    ),
    lambda r: (
        f"Pre-approved instant loan Rs {_amt(r, 50000, 500000)} without documents. Apply now {_rand_url(r)} limited offer"
    ),
    lambda r: (
        f"Your SIM will be deactivated in 24 hours. Complete re-verification {_rand_url(r)} or call {_phone(r)}"
    ),
    lambda r: (
        f"Dear user your {r.choice(BANKS)} credit card reward points worth Rs {_amt(r, 1000, 9000)} expire today. Redeem {_rand_url(r)}"
    ),
    lambda r: (
        f"URGENT: Unusual login detected on your {r.choice(BANKS)} netbanking. Verify identity {_rand_url(r)} else account freeze"
    ),
    lambda r: (
        f"Hi, I am sending you gift worth Rs {_amt(r, 5000, 50000)}. Share your OTP and UPI PIN to receive payment"
    ),
    lambda r: (
        f"Aadhaar update mandatory. Your Aadhaar will be deactivated. Click {_rand_url(r)} and enter OTP"
    ),
    lambda r: (
        f"Dear customer your FASTag is blocked. Recharge now {_rand_url(r)} to avoid double toll charges"
    ),
]

LEGIT = [
    lambda r: (
        f"{r.randint(100000, 999999)} is your OTP for login. Do not share it with anyone. - {r.choice(BANKS)}"
    ),
    lambda r: (
        f"OTP {r.randint(100000, 999999)} for transaction of Rs {_amt(r, 100, 20000)}. Valid for 10 mins. Never share OTP. -{r.choice(BANK_TAG)}"
    ),
    lambda r: (
        f"Rs {_amt(r, 50, 30000)} debited from A/c XX{r.randint(1000, 9999)} on {r.randint(1, 28):02d}-Sep-26. Avl bal Rs {_amt(r, 1000, 90000)}. -{r.choice(BANK_TAG)}"
    ),
    lambda r: (
        f"Rs {_amt(r, 50, 30000)} credited to your A/c XX{r.randint(1000, 9999)} via UPI. Ref no {r.randint(10**11, 10**12 - 1)}."
    ),
    lambda r: (
        f"Your Amazon order #{r.randint(100, 999)}-{r.randint(1000000, 9999999)} will be delivered today by 8 PM. Track in the app."
    ),
    lambda r: (
        f"Your electricity bill of Rs {_amt(r, 300, 4000)} is generated. Pay before due date using the official app."
    ),
    lambda r: (
        f"Recharge of Rs {r.choice([199, 239, 299, 479, 666])} successful. Validity 28 days. Thank you for choosing us."
    ),
    lambda r: "Hi, are we meeting at the cafe at 6 today? Let me know if you are running late.",
    lambda r: "Mom said dinner is at 8 tonight. Please bring some fruits on your way back.",
    lambda r: "Meeting moved to 4 pm. Please join on Teams. Agenda attached in the mail.",
    lambda r: (
        f"Your appointment with Dr. Shah is confirmed for {r.randint(1, 28)} Oct at {r.randint(9, 6 + 6)}:30. Reply C to cancel."
    ),
    lambda r: (
        "Dear student, the lab record submission deadline is extended to Friday. - Dept of Computer Engineering"
    ),
    lambda r: (
        f"Your IRCTC ticket PNR {r.randint(10**9, 10**10 - 1)} is confirmed. Coach S{r.randint(1, 9)} berth {r.randint(1, 72)}. Happy journey!"
    ),
    lambda r: (
        f"Your Flipkart order #{r.randint(10**8, 10**9)} has shipped. Track it at https://www.flipkart.com/orders"
    ),
    lambda r: (
        f"Your {r.choice(['HDFC Bank', 'ICICI Bank', 'SBI'])} e-statement is ready. View it on https://www.{r.choice(['hdfcbank.com', 'icicibank.com', 'sbi.co.in'])} or the official app."
    ),
    lambda r: (
        "Join the lab review meeting here: https://teams.microsoft.com/l/meetup-join/19abc. Starts at 4 PM."
    ),
    lambda r: (
        "Notes for tomorrow's exam are shared: https://docs.google.com/document/d/1AbCdEf. Please revise."
    ),
    lambda r: (
        f"Your IRCTC e-ticket is booked. Manage booking at https://www.irctc.co.in. PNR {r.randint(10**9, 10**10 - 1)}."
    ),
    lambda r: "Happy birthday! Wishing you a wonderful year ahead. Party at my place on Saturday.",
    lambda r: f"Your Zomato order is on the way. Delivery partner will reach in {r.randint(5, 25)} minutes.",
]


def generate_split(n_per_template=40, seed=42):
    """Hold out entire template IDs, not random variants of the same template."""
    rng = random.Random(seed)
    train, test, groups = [], [], {}
    for label, templates, name in [(1, SCAM, "scam"), (0, LEGIT, "legitimate")]:
        held_out = set(rng.sample(range(len(templates)), max(1, round(len(templates) * 0.2))))
        groups[name] = {
            "train": [i for i in range(len(templates)) if i not in held_out],
            "test": sorted(held_out),
        }
        for index, template in enumerate(templates):
            destination = test if index in held_out else train
            destination.extend((template(rng), label) for _ in range(n_per_template))
    rng.shuffle(train)
    rng.shuffle(test)
    return train, test, groups
