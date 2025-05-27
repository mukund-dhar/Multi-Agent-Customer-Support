-- complete_setup.sql
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- 1) Customers table (with loyalty, birth date, support tickets)
CREATE TABLE customers (
  id                    TEXT    PRIMARY KEY,
  name                  TEXT,
  email                 TEXT,
  loyalty_tier          TEXT    DEFAULT 'regular',
  birth_date            TEXT,
  support_ticket_count  INTEGER DEFAULT 0
);

-- 2) Orders table (status, ETA, amount)
CREATE TABLE orders (
  id           TEXT    PRIMARY KEY,
  customer_id  TEXT    NOT NULL,
  status       TEXT,
  eta_date     TEXT,
  total_amount REAL    DEFAULT 0,
  FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- 3) Subscriptions table
CREATE TABLE subscriptions (
  id            TEXT PRIMARY KEY,
  customer_id   TEXT    NOT NULL,
  plan          TEXT,
  status        TEXT,
  renewal_date  TEXT,
  FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- 4) Cancellation requests
CREATE TABLE cancellation_requests (
  id            TEXT PRIMARY KEY,
  customer_id   TEXT    NOT NULL,
  service_id    TEXT    NOT NULL,
  request_date  TEXT,
  status        TEXT,
  FOREIGN KEY(customer_id) REFERENCES customers(id),
  FOREIGN KEY(service_id)   REFERENCES subscriptions(id)
);

-- 5) Seed customers
INSERT INTO customers (id, name, email, loyalty_tier, birth_date, support_ticket_count) VALUES
  ('C001','Alice Smith','alice@example.com','gold','1990-05-27',1),
  ('C002','Bob Johnson','bob@example.com','regular','1985-10-10',4),
  ('C003','Carol Lee','carol@example.com','regular',NULL,0);

-- 6) Seed orders
INSERT INTO orders (id, customer_id, status, eta_date, total_amount) VALUES
  ('ORD001','C001','Delivered','2025-05-20',150.0),
  ('ORD002','C001','Shipped','2025-05-22',200.0),
  ('ORD003','C002','Processing','2025-05-28',50.0),
  ('ORD004','C001','Delayed','2025-06-10',250.0),
  ('ORD005','C003','Delivered','2025-05-25',80.0),
  ('ORD006','C002','Delayed','2025-06-02',120.0);

-- 7) Seed subscriptions
INSERT INTO subscriptions (id, customer_id, plan, status, renewal_date) VALUES
  ('SUB001','C001','Pro','Active','2025-06-15'),
  ('SUB002','C002','Basic','Active','2025-05-30'),
  ('SUB003','C002','Premium','Expired','2025-05-15');

-- 8) Seed cancellation requests
INSERT INTO cancellation_requests (id, customer_id, service_id, request_date, status) VALUES
  ('CR001','C001','SUB001','2025-05-20','Pending'),
  ('CR002','C002','SUB002','2025-05-19','Pending');

COMMIT;
PRAGMA foreign_keys = ON;
