DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS orders;

CREATE TABLE customers (
  id TEXT PRIMARY KEY,
  name TEXT,
  email TEXT
);

CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  customer_id TEXT,
  status TEXT,
  FOREIGN KEY(customer_id) REFERENCES customers(id)
);

INSERT INTO customers VALUES
  ('C001','Alice Smith','alice@example.com'),
  ('C002','Bob Johnson','bob@example.com');

INSERT INTO orders VALUES
  ('ORD001','C001','Delivered'),
  ('ORD002','C001','Shipped'),
  ('ORD003','C002','Processing');
