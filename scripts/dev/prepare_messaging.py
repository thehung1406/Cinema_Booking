"""Generate ignored local credentials and RabbitMQ topology; never print secrets."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[2]


def rabbit_hash(password):
    salt = secrets.token_bytes(4)
    return base64.b64encode(salt + hashlib.sha256(salt + password.encode()).digest()).decode()


def definitions(values):
    public, private = "/cinema-public", "/cinema-private"
    users = [("reporting-consumer",values["BROKER_REPORTING_PASSWORD"],[])] + [("reporting-publisher-"+name,values["BROKER_REPORTING_"+name.upper()+"_PASSWORD"],[]) for name in ("booking","payment","catalog","cinema","review")] + [("booking-publisher", values["BROKER_PUBLISHER_PASSWORD"], []),
             ("notification-consumer", values["BROKER_NOTIFICATION_PASSWORD"], []),
             ("review-publisher", values["BROKER_REVIEW_PASSWORD"], []),
             ("payment-saga", values["BROKER_PAYMENT_PASSWORD"], []),
             ("booking-saga-consumer", values["BROKER_BOOKING_CONSUMER_PASSWORD"], []),
             ("cinema-operator", values["BROKER_OPERATOR_PASSWORD"], ["administrator"])]
    permissions = [dict(user='reporting-consumer',vhost=public,configure='^$',read=r'^reporting\.bootstrap\.v1$',write='^$')] + [dict(user='reporting-publisher-'+name,vhost=public,configure='^$',read='^$',write=r'^cinema\.events\.v1$') for name in ('booking','payment','catalog','cinema','review')] + [
        {"user":"payment-saga","vhost":public,"configure":"^$","read":r"^payment\.booking\.v1$","write":r"^cinema\.events\.v1$"},
        {"user":"booking-saga-consumer","vhost":public,"configure":"^$","read":r"^booking\.payment\.v1$","write":"^$"},
        {"user": "review-publisher", "vhost": public, "configure": "^$", "read": "^$", "write": r"^cinema\.events\.v1$"},
        {"user": "booking-publisher", "vhost": public, "configure": "^$", "read": "^$", "write": r"^cinema\.events\.v1$"},
        {"user": "booking-publisher", "vhost": private, "configure": "^$", "read": "^$", "write": r"^cinema\.notifications\.v1$"},
        {"user": "notification-consumer", "vhost": private, "configure": "^$", "read": r"^notification\.email\.v1$", "write": "^$"},
    ]
    permissions += [{"user": "cinema-operator", "vhost": vhost, "configure": ".*", "read": ".*", "write": ".*"} for vhost in (public, private)]
    exchanges = [
        {"name": "cinema.events.v1", "vhost": public, "type": "topic", "durable": True, "auto_delete": False, "internal": False, "arguments": {}},
        {"name": "cinema.notifications.v1", "vhost": private, "type": "direct", "durable": True, "auto_delete": False, "internal": False, "arguments": {}},
        {"name": "cinema.notifications.dead.v1", "vhost": private, "type": "direct", "durable": True, "auto_delete": False, "internal": False, "arguments": {}},
    ]
    queues = [
        {"name": "reporting.bootstrap.v1", "vhost": public, "durable": True, "auto_delete": False, "arguments": {}},
        {"name": "notification.email.v1", "vhost": private, "durable": True, "auto_delete": False,
         "arguments": {"x-dead-letter-exchange": "cinema.notifications.dead.v1", "x-dead-letter-routing-key": "email.failed"}},
        {"name": "notification.email.dead.v1", "vhost": private, "durable": True, "auto_delete": False, "arguments": {}},
    ]
    bindings = [
        {"source": "cinema.events.v1", "vhost": public, "destination": "reporting.bootstrap.v1", "destination_type": "queue", "routing_key": "#", "arguments": {}},
        {"source": "cinema.notifications.v1", "vhost": private, "destination": "notification.email.v1", "destination_type": "queue", "routing_key": "BookingConfirmationEmailRequested.v1", "arguments": {}},
        {"source": "cinema.notifications.dead.v1", "vhost": private, "destination": "notification.email.dead.v1", "destination_type": "queue", "routing_key": "email.failed", "arguments": {}},
    ]
    exchanges.append(dict(name='cinema.saga.dead.v1',vhost=public,type='direct',durable=True,auto_delete=False,internal=False,arguments={}))
    for queue, kinds in [('booking.payment.v1',['PaymentCaptured.v1']),('payment.booking.v1',['CheckoutCreated.v1','BookingExpired.v1','PaymentBookingResult.v1'])]:
        queues.append(dict(name=queue,vhost=public,durable=True,auto_delete=False,arguments={'x-dead-letter-exchange':'cinema.saga.dead.v1','x-dead-letter-routing-key':queue}))
        queues.append(dict(name=queue+'.dead',vhost=public,durable=True,auto_delete=False,arguments={}))
        bindings.append(dict(source='cinema.saga.dead.v1',vhost=public,destination=queue+'.dead',destination_type='queue',routing_key=queue,arguments={}))
        for kind in kinds: bindings.append(dict(source='cinema.events.v1',vhost=public,destination=queue,destination_type='queue',routing_key=kind,arguments={}))
    queues.append(dict(name='reporting.dead.v1',vhost=public,durable=True,auto_delete=False,arguments={}))
    bindings.append(dict(source='cinema.saga.dead.v1',vhost=public,destination='reporting.dead.v1',destination_type='queue',routing_key='reporting.failed',arguments={}))
    topics=[dict(user='reporting-publisher-'+name,vhost=public,exchange='cinema.events.v1',read='^$',write=r'^Report(FactChanged|Checkpoint)\.v1\.reporting-source:'+name+'$') for name in ('booking','payment','catalog','cinema','review')]
    for user,domain,kinds in [('booking-publisher','booking','BookingConfirmed|CheckoutCreated|BookingExpired|PaymentBookingResult'),('payment-saga','payment','PaymentCaptured'),('review-publisher','review','ReviewChanged|ReviewSentimentUpdated')]:
        topics.append(dict(user=user,vhost=public,exchange='cinema.events.v1',read='.*',write=r'^(('+kinds+r')\.v1|Report(FactChanged|Checkpoint)\.v1\.reporting-source:'+domain+r')$'))
    policies=[dict(name='reporting-bootstrap-dlx',vhost=public,pattern=r'^reporting\.bootstrap\.v1$',definition={'dead-letter-exchange':'cinema.saga.dead.v1','dead-letter-routing-key':'reporting.failed'},priority=10,**{'apply-to':'queues'})]
    return {"topic_permissions":topics,"policies":policies,"vhosts": [{"name": public}, {"name": private}],
            "users": [{"name": name, "password_hash": rabbit_hash(password), "hashing_algorithm": "rabbit_password_hashing_sha256", "tags": tags} for name, password, tags in users],
            "permissions": permissions, "exchanges": exchanges, "queues": queues, "bindings": bindings}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    env_file = ROOT / (".env.messaging-test" if args.test else ".env.microservices")
    runtime = ROOT / "infra/broker/.runtime"
    output = runtime / ("test-definitions.json" if args.test else "definitions.json")
    if not args.test and output.exists() and not env_file.exists():
        raise RuntimeError("Broker definitions already exist. Restore the matching credential file before continuing.")
    values = {}
    if args.test:
        values = {
            "INTERNAL_SERVICE_KEY": "isolated-internal-service-key-32-characters-test-only",
            "NOTIFICATION_DB_PASSWORD": "notification-test-only",
            "BROKER_PUBLISHER_PASSWORD": "isolated-publisher-test-only",
            "BROKER_NOTIFICATION_PASSWORD": "isolated-consumer-test-only",
            "BROKER_OPERATOR_PASSWORD": "isolated-operator-test-only",
        }
    if env_file.exists() and not args.test:
        values = dict(line.split("=", 1) for line in env_file.read_text().splitlines() if line and not line.startswith("#"))
    if args.test:
        values["PAYMENT_DB_PASSWORD"] = "payment-test-only"
        values["BROKER_PAYMENT_PASSWORD"] = "isolated-payment-test-only"
        values["BROKER_BOOKING_CONSUMER_PASSWORD"] = "isolated-booking-consumer-test-only"
        values["BOOKING_DB_PASSWORD"] = "booking-test-only"
        values["CINEMA_DB_PASSWORD"] = "cinema-test-only"
        values["CATALOG_DB_PASSWORD"] = "catalog-test-only"
        values["IDENTITY_DB_PASSWORD"] = "identity-test-only"
        values["AI_DB_PASSWORD"] = "ai-test-only"
        values["REVIEW_DB_PASSWORD"] = "review-test-only"
        values["BROKER_REVIEW_PASSWORD"] = "isolated-review-publisher-test-only"
    for key in ("PAYMENT_DB_PASSWORD", "BROKER_PAYMENT_PASSWORD", "BROKER_BOOKING_CONSUMER_PASSWORD", "INTERNAL_SERVICE_KEY", "NOTIFICATION_DB_PASSWORD", "AI_DB_PASSWORD", "IDENTITY_DB_PASSWORD", "CATALOG_DB_PASSWORD", "CINEMA_DB_PASSWORD", "BOOKING_DB_PASSWORD", "REVIEW_DB_PASSWORD", "BROKER_REVIEW_PASSWORD", "BROKER_PUBLISHER_PASSWORD", "BROKER_NOTIFICATION_PASSWORD", "BROKER_OPERATOR_PASSWORD"):
        values.setdefault(key, secrets.token_hex(32))
    for name in ('booking','payment','catalog','cinema','review'):
        values.setdefault('BROKER_REPORTING_'+name.upper()+'_PASSWORD','isolated-reporting-'+name+'-test-only' if args.test else secrets.token_hex(32))
    values.setdefault('BROKER_REPORTING_PASSWORD','isolated-reporting-consumer-test-only' if args.test else secrets.token_hex(32))
    values.setdefault('REPORTING_DB_PASSWORD','reporting-test-only' if args.test else secrets.token_hex(32))
    # M8 temporarily co-locates legacy VNPay with Booking; copy only its four
    # settings, never source DB/JWT/SMTP values, and preserve explicit overrides.
    backend_env = ROOT / "Backend/.env"
    if not args.test and backend_env.exists():
        legacy = {}
        for line in backend_env.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                legacy[key.strip()] = value.strip().strip('"').strip("'")
        for key in ("TMN_CODE", "HASH_SECRET", "VNPAY_URL", "FRONTEND_URL"):
            if key in legacy: values.setdefault("BOOKING_"+key, legacy[key])
    for key in ('TMN_CODE','HASH_SECRET','VNPAY_URL','FRONTEND_URL'):
        if 'BOOKING_'+key in values:values.setdefault('PAYMENT_'+key,values['BOOKING_'+key])
    values.setdefault("IDENTITY_CURRENT_KID", "local-2026-11")
    values.setdefault("IDENTITY_SIGNING_KEYS", json.dumps({values["IDENTITY_CURRENT_KID"]: secrets.token_hex(32)}, separators=(",", ":")))
    values.setdefault("SERVICE_GATEWAY_DOMAINS", values.get("AI_GATEWAY_DOMAINS", "[]"))
    env_file.write_text("# Generated local credentials. Do not commit.\n" + "".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    runtime.mkdir(parents=True, exist_ok=True)
    if not output.exists() or args.test:
        output.write_text(json.dumps(definitions(values), indent=2) + "\n", encoding="utf-8")
    else:
        # Merge topology additions, preserving every existing credential hash.
        current, proposed = json.loads(output.read_text()), definitions(values)
        keys={'users':('name',),'permissions':('user','vhost'),'exchanges':('name','vhost'),'queues':('name','vhost'),'bindings':('source','vhost','destination','routing_key'),'topic_permissions':('user','vhost','exchange'),'policies':('name','vhost')}
        for section,fields in keys.items():
            for item in proposed[section]:
                if not any(all(existing.get(k)==item.get(k) for k in fields) for existing in current.setdefault(section,[])): current[section].append(item)
        output.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    print("Prepared local credentials and broker definitions (values redacted)." if not args.test else "Prepared isolated test broker credentials/topology (values redacted).")


if __name__ == "__main__":
    main()
