DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS group_lead_department;
DROP TABLE IF EXISTS department_names;
DROP TABLE IF EXISTS manufacturinglog;
DROP TABLE IF EXISTS manpowerlog;


CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  role TEXT NOT NULL
);

CREATE TABLE group_lead_department (
  id INTEGER PRIMARY KEY,
  department TEXT NOT NULL,
  FOREIGN KEY (id) REFERENCES user (id)
);

CREATE TABLE department_names (
  department_name TEXT PRIMARY KEY
);

INSERT INTO department_names (department_name)
  VALUES ("Group1"), ("Group2"), ("Group3");

CREATE TABLE manufacturinglog (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  userid INTEGER,
  logdate DATE NOT NULL,
  department TEXT NOT NULL,
  unitcount TEXT NOT NULL,
  FOREIGN KEY (userid) REFERENCES user (id)
);

CREATE TABLE manpowerlog (
  logorder INTEGER PRIMARY KEY AUTOINCREMENT,
  ddid INTEGER NOT NULL,
  manpowercount INTEGER NOT NULL,
  manpowerrate INTEGER NOT NULL,
  FOREIGN KEY (ddid) REFERENCES manufacturinglog (id)
);
