-- Fictional FYP sample, as of 1 November 2026. No live database was accessed.

-- Import into MySQL to create a SEPARATE schema. Do not replace this schema name with the development database.

-- No DROP/DELETE/UPDATE statements. Creation fails if this schema already exists; use a new isolated schema name.

-- Students only. No staff RBAC, face templates, consent, login tokens or active challenges are seeded.

-- Historical attendance is artificial and tagged stage=sample_data, not an experimental result.

CREATE DATABASE `fyp_biometric_test_20261101` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `fyp_biometric_test_20261101`;

CREATE TABLE courses (
	course_code VARCHAR(10) NOT NULL, 
	course_name VARCHAR(150) NOT NULL, 
	credit_hour INTEGER NOT NULL, 
	PRIMARY KEY (course_code)
);

CREATE TABLE programmes (
	programme_code VARCHAR(10) NOT NULL, 
	programme_name VARCHAR(150) NOT NULL, 
	PRIMARY KEY (programme_code)
);

CREATE TABLE student_groups (
	group_id INTEGER NOT NULL AUTO_INCREMENT, 
	programme_code VARCHAR(10) NOT NULL, 
	group_name VARCHAR(20) NOT NULL, 
	year_of_study INTEGER NOT NULL, 
	semester INTEGER NOT NULL, 
	academic_year INTEGER NOT NULL, 
	PRIMARY KEY (group_id), 
	FOREIGN KEY(programme_code) REFERENCES programmes (programme_code)
);

CREATE TABLE class_schedules (
	schedule_id INTEGER NOT NULL AUTO_INCREMENT, 
	course_code VARCHAR(10) NOT NULL, 
	group_id INTEGER NOT NULL, 
	day_of_week VARCHAR(15) NOT NULL, 
	class_type VARCHAR(20) NOT NULL, 
	start_time TIME NOT NULL, 
	end_time TIME NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	lecturer VARCHAR(100) NOT NULL, 
	PRIMARY KEY (schedule_id), 
	FOREIGN KEY(course_code) REFERENCES courses (course_code), 
	FOREIGN KEY(group_id) REFERENCES student_groups (group_id)
);

CREATE TABLE students (
	student_id VARCHAR(11) NOT NULL, 
	group_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	face_encoding TEXT, 
	biometric_status VARCHAR(20) NOT NULL, 
	account_status VARCHAR(20) NOT NULL, 
	consent_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (student_id), 
	FOREIGN KEY(group_id) REFERENCES student_groups (group_id), 
	UNIQUE (email)
);

CREATE TABLE auth_sessions (
	token_hash VARCHAR(64) NOT NULL, 
	student_id VARCHAR(11) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(student_id) REFERENCES students (student_id)
);

CREATE TABLE class_sessions (
	session_id INTEGER NOT NULL AUTO_INCREMENT, 
	schedule_id INTEGER NOT NULL, 
	session_date DATE NOT NULL, 
	start_time TIME NOT NULL, 
	end_time TIME NOT NULL, 
	venue VARCHAR(50) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	pin_hash VARCHAR(64) NOT NULL, 
	PRIMARY KEY (session_id), 
	UNIQUE (schedule_id, session_date), 
	FOREIGN KEY(schedule_id) REFERENCES class_schedules (schedule_id)
);

CREATE TABLE verification_attempts (
	verification_id INTEGER NOT NULL AUTO_INCREMENT, 
	student_id VARCHAR(11) NOT NULL, 
	session_id INTEGER, 
	verification_result VARCHAR(20) NOT NULL, 
	stage VARCHAR(30) NOT NULL, 
	attempted_at DATETIME NOT NULL, 
	failure_reason VARCHAR(255), 
	face_distance FLOAT, 
	PRIMARY KEY (verification_id), 
	FOREIGN KEY(student_id) REFERENCES students (student_id), 
	FOREIGN KEY(session_id) REFERENCES class_sessions (session_id)
);

CREATE TABLE attendance (
	attendance_id INTEGER NOT NULL AUTO_INCREMENT, 
	session_id INTEGER NOT NULL, 
	student_id VARCHAR(11) NOT NULL, 
	verification_id INTEGER NOT NULL, 
	taken_at DATETIME NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	PRIMARY KEY (attendance_id), 
	CONSTRAINT one_attendance_per_session UNIQUE (session_id, student_id), 
	FOREIGN KEY(session_id) REFERENCES class_sessions (session_id), 
	FOREIGN KEY(student_id) REFERENCES students (student_id), 
	FOREIGN KEY(verification_id) REFERENCES verification_attempts (verification_id)
);

CREATE TABLE verification_challenges (
	challenge_id VARCHAR(64) NOT NULL, 
	student_id VARCHAR(11) NOT NULL, 
	session_id INTEGER NOT NULL, 
	auth_token_hash VARCHAR(64) NOT NULL, 
	verification_id INTEGER NOT NULL, 
	stage VARCHAR(20) NOT NULL, 
	fingers INTEGER, 
	valid_frames INTEGER NOT NULL, 
	frame_hashes TEXT NOT NULL, 
	expires_at DATETIME NOT NULL, 
	consumed BOOL NOT NULL, 
	PRIMARY KEY (challenge_id), 
	FOREIGN KEY(student_id) REFERENCES students (student_id), 
	FOREIGN KEY(session_id) REFERENCES class_sessions (session_id), 
	FOREIGN KEY(auth_token_hash) REFERENCES auth_sessions (token_hash), 
	FOREIGN KEY(verification_id) REFERENCES verification_attempts (verification_id)
);

START TRANSACTION;

INSERT INTO courses (course_code, course_name, credit_hour) VALUES ('BMIT3173', 'Mobile Application Development', 3);

INSERT INTO courses (course_code, course_name, credit_hour) VALUES ('BMIT3093', 'Information Security', 3);

INSERT INTO courses (course_code, course_name, credit_hour) VALUES ('BMIT2023', 'Database Management Systems', 3);

INSERT INTO courses (course_code, course_name, credit_hour) VALUES ('BMIT3063', 'Software Engineering', 3);

INSERT INTO courses (course_code, course_name, credit_hour) VALUES ('BMCS3013', 'Artificial Intelligence', 3);

INSERT INTO courses (course_code, course_name, credit_hour) VALUES ('BMCS3023', 'Computer Networks', 3);

INSERT INTO programmes (programme_code, programme_name) VALUES ('BIT', 'Bachelor of Information Technology (Honours)');

INSERT INTO programmes (programme_code, programme_name) VALUES ('BCS', 'Bachelor of Computer Science (Honours)');

INSERT INTO student_groups (group_id, programme_code, group_name, year_of_study, semester, academic_year) VALUES (1, 'BIT', 'RIT3S1-G1', 3, 1, 2026);

INSERT INTO student_groups (group_id, programme_code, group_name, year_of_study, semester, academic_year) VALUES (2, 'BIT', 'RIT3S1-G2', 3, 1, 2026);

INSERT INTO student_groups (group_id, programme_code, group_name, year_of_study, semester, academic_year) VALUES (3, 'BCS', 'RCS3S1-G1', 3, 1, 2026);

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (1, 'BMIT3173', 1, 'Monday', 'Practical', '09:00:00', '11:00:00', '2026-09-28', '2026-12-18', 'Dr. Faridah Osman');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (2, 'BMIT3093', 1, 'Tuesday', 'Lecture', '10:00:00', '12:00:00', '2026-09-28', '2026-12-18', 'Mr. Adrian Tan');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (3, 'BMIT2023', 1, 'Wednesday', 'Practical', '14:00:00', '16:00:00', '2026-09-28', '2026-12-18', 'Ms. Kavitha Nair');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (4, 'BMIT3063', 1, 'Thursday', 'Tutorial', '09:00:00', '11:00:00', '2026-09-28', '2026-12-18', 'Dr. Melissa Wong');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (5, 'BMIT3173', 2, 'Monday', 'Practical', '14:00:00', '16:00:00', '2026-09-28', '2026-12-18', 'Dr. Faridah Osman');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (6, 'BMIT3093', 2, 'Tuesday', 'Lecture', '14:00:00', '16:00:00', '2026-09-28', '2026-12-18', 'Mr. Adrian Tan');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (7, 'BMIT2023', 2, 'Wednesday', 'Practical', '09:00:00', '11:00:00', '2026-09-28', '2026-12-18', 'Ms. Kavitha Nair');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (8, 'BMIT3063', 2, 'Friday', 'Tutorial', '10:00:00', '12:00:00', '2026-09-28', '2026-12-18', 'Dr. Melissa Wong');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (9, 'BMCS3013', 3, 'Monday', 'Lecture', '11:00:00', '13:00:00', '2026-09-28', '2026-12-18', 'Dr. Kelvin Lim');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (10, 'BMCS3023', 3, 'Tuesday', 'Practical', '09:00:00', '11:00:00', '2026-09-28', '2026-12-18', 'Mr. Hafiz Rahman');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (11, 'BMIT2023', 3, 'Thursday', 'Practical', '14:00:00', '16:00:00', '2026-09-28', '2026-12-18', 'Ms. Kavitha Nair');

INSERT INTO class_schedules (schedule_id, course_code, group_id, day_of_week, class_type, start_time, end_time, start_date, end_date, lecturer) VALUES (12, 'BMIT3063', 3, 'Friday', 'Tutorial', '14:00:00', '16:00:00', '2026-09-28', '2026-12-18', 'Dr. Melissa Wong');

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10001', 1, 'Aiman Hakim bin Zulkifli', 'aiman.hakim@student.example.test', 'pbkdf2_sha256$600000$V5SUXHoxJBXpxvPT+MOe2Q==$e/iXDbTSfpnDjJYitSOCzok7HJ9RyHXGhkpRuOP4jlM=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10002', 1, 'Tan Wei Jie', 'weijie.tan@student.example.test', 'pbkdf2_sha256$600000$SDZ6yhUUuUd2t17DM/pzOw==$8rsJrhwa4lOHDGTl1cgnRoVOYK5u4KFAps0vx+iOc84=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10003', 1, 'Nur Aisyah binti Rahman', 'aisyah.rahman@student.example.test', 'pbkdf2_sha256$600000$lECZkpP2ucPl/SqCxevb3g==$+9bGZk+0JEVo3KixgIiAiI4bhQY8jRjiFoiQYVHxrx8=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10004', 1, 'Lim Xin Yi', 'xinyi.lim@student.example.test', 'pbkdf2_sha256$600000$5HhYoLmMIKKD8kj9tgdcUQ==$gWnPu/q9s69O19ugGznpm97eDPTaV3Q1YxHSwSM0rHk=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10005', 1, 'Kavinesh a/l Suresh', 'kavinesh.suresh@student.example.test', 'pbkdf2_sha256$600000$S+dCO4Hn1c0hxSjykbXqYA==$rnoZMShgPxj8oi+d1IjB17Wwjcdwd0WibHWubN6foEw=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10006', 1, 'Chong Jia En', 'jiaen.chong@student.example.test', 'pbkdf2_sha256$600000$vVJw7I4P8kAq0LvKlcDN1g==$0mKcY4+PYIAjCJtItAatI9IUGmqbrpiHLmk0wAjfhsE=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10007', 1, 'Muhammad Danish bin Azlan', 'danish.azlan@student.example.test', 'pbkdf2_sha256$600000$lbiFsqbl6NyRhZUo9jaKeQ==$iv7zQ8BCoEU7fDaYZxPt0LWYp9d4T9KE/Y69I/F+u5s=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10008', 1, 'Wong Kai Wen', 'kaiwen.wong@student.example.test', 'pbkdf2_sha256$600000$dMialXUpB+cS4IYWoQS7zA==$+fHYjaq/8TzpALeJIYbbhji+a2yrNt+g+dJCoY6KYCA=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10009', 1, 'Priya a/p Rajendran', 'priya.rajendran@student.example.test', 'pbkdf2_sha256$600000$aYM4wP3lk8ANxZ4hDGMSsw==$Cb7SY5uicXcuvmC1MkiGQDV3QD13glcHcskar+4gYL4=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10010', 1, 'Siti Nur Iman binti Salleh', 'iman.salleh@student.example.test', 'pbkdf2_sha256$600000$xsdENhhkrvJ2BwwvJYKWzA==$EiV2K4OTQuSqNVumBbWcCtIM/zWCFZrFUm3kXxI2IEg=', NULL, 'not_registered', 'active', NULL, '2026-10-26 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10011', 1, 'Lee Jun Hao', 'junhao.lee@student.example.test', 'pbkdf2_sha256$600000$Qv/qb/Cp0e2JgXIfuRdbcQ==$yeaJrdrC8QJkxPMZtNCOJ9yyrFGY92OpOxBVlrDYcCc=', NULL, 'not_registered', 'inactive', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10012', 1, 'Soh Mei Ling', 'meiling.soh@student.example.test', 'pbkdf2_sha256$600000$06IGh8579YKygRB7Wz+7gA==$ubKvfmAGyn9uDOErDXKwRZFt7uKntHFvzQXJHxMdktA=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10101', 2, 'Farah Nabila binti Ismail', 'farah.ismail@student.example.test', 'pbkdf2_sha256$600000$Fy2HXYpWykuD6z6HiQZIug==$zP3FEBvs9yZ0etVvRlDM+9hGXxhkJXVUNGNBWrVYR8c=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10102', 2, 'Ng Zi Xuan', 'zixuan.ng@student.example.test', 'pbkdf2_sha256$600000$C3Ik9+ax37qLIEpMGUVUYw==$zmxETqH/wcLxH7N3A7PHDIGk05Gw1d0+aWZQsEcjFgE=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10103', 2, 'Arvind a/l Krishnan', 'arvind.krishnan@student.example.test', 'pbkdf2_sha256$600000$s+8cX5AzMfEx7IzDmz2bmg==$Ea0I9Wflzaez21a/x2bVhK80EvR+N6hOd58uGirXcoo=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10104', 2, 'Teoh Pei Shan', 'peishan.teoh@student.example.test', 'pbkdf2_sha256$600000$nCiJjIfPQPa85ZjwIXG+BA==$MCNfdXZlgIyizzh0e7zXl2WLS6CctxM/kJcwtAnsArE=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10105', 2, 'Amirul Haziq bin Roslan', 'haziq.roslan@student.example.test', 'pbkdf2_sha256$600000$jz+mc/BsAFjqTCICiOCNQQ==$99E5DtjIlctRatd/UPloNenNGpCYCKijsHnKn7N+vFw=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10106', 2, 'Goh Yu Heng', 'yuheng.goh@student.example.test', 'pbkdf2_sha256$600000$9LDlPkdmjl6hllKmluSYpQ==$kddsfkm0pbjeY0yp725yJH5S8vR4W1b8J+bFHxRdIhM=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10107', 2, 'Nurul Syafiqah binti Hassan', 'syafiqah.hassan@student.example.test', 'pbkdf2_sha256$600000$fmVIuol8oP7t1feDIXeZMw==$dX5NADqociQtY4Hie2Qs1hPgRnAfGCdglVqaxoPlK3I=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10108', 2, 'Liew Wen Qi', 'wenqi.liew@student.example.test', 'pbkdf2_sha256$600000$B1RGeAFcYhGExkdz+x08Ew==$ml7J0Xc/7GfIzqWkUPWW4VSF+u7USz7FnMLzmbPN5sM=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10109', 2, 'Harshini a/p Mohan', 'harshini.mohan@student.example.test', 'pbkdf2_sha256$600000$q9vrRozDmH5+Hs1nAIcm/Q==$7DZQGzl3asrZu2SipjQcpZ1I9sWSKUTLvP99sWQoYMU=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10110', 2, 'Ahmad Firdaus bin Kamal', 'firdaus.kamal@student.example.test', 'pbkdf2_sha256$600000$GL6lK25GubRUsUmPHnpoYA==$YHWyqNguzcJv6TukcO7QsHFjBjDQ936VjhS00Y/zRBA=', NULL, 'not_registered', 'active', NULL, '2026-10-26 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10111', 2, 'Yap Zhi Ming', 'zhiming.yap@student.example.test', 'pbkdf2_sha256$600000$0h/2B8DEmKle7Q+Ba5TXHA==$XfD2ynk2fcm8OCGY+mjn6Cw/dS07V+00aHSDhWJcmQw=', NULL, 'not_registered', 'inactive', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WMR10112', 2, 'Chua Hui Min', 'huimin.chua@student.example.test', 'pbkdf2_sha256$600000$LVwAVSnVDyq9W+ce2z3Haw==$8Zvn1WCCagMkHTUtXeltE4C9mwul7Fx+uW8QrJLXLzc=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10001', 3, 'Siti Balqis binti Abdullah', 'balqis.abdullah@student.example.test', 'pbkdf2_sha256$600000$JhraBFB3ikzPmc9jhqP6tw==$JLe10xrLZq1JpxADCIUoVJAIrr1cUimsjxZp5fMuAZM=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10002', 3, 'Ong Jun Wei', 'junwei.ong@student.example.test', 'pbkdf2_sha256$600000$0cOZtNt54S3pH5zvNyz6QA==$Kgxg8J1hsfqc6s9CKxzfGb6SppTkNm6VXsA8LbBJfBQ=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10003', 3, 'Darshini a/p Kumar', 'darshini.kumar@student.example.test', 'pbkdf2_sha256$600000$HplqDsP4dWutjU850rfynw==$AoXr05RYDiBs2WcVFDIwiw0R24mqmtYJ89MPP7Mfzbk=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10004', 3, 'Chew Xin Rou', 'xinrou.chew@student.example.test', 'pbkdf2_sha256$600000$Y0WdgEPq8Sh0lgI/t489MQ==$5q3RlOFxbD1CD3lmA+5WeegKPisHRkjwueHJHkyMrKI=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10005', 3, 'Muhammad Irfan bin Fauzi', 'irfan.fauzi@student.example.test', 'pbkdf2_sha256$600000$UV0b71o+iKoyuzedalyZww==$h6/k5EY2mmGT8X0ybdLNTtsZoeKh5Xaj5LSe4YSyHq4=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10006', 3, 'Low Zhen Yu', 'zhenyu.low@student.example.test', 'pbkdf2_sha256$600000$3I8O27mzrSyNOvKfa6NIcw==$2ja4qzosIxYq8kz/5lmpZept7CrujzAAwSvNwkGtKz0=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10007', 3, 'Nur Amirah binti Yusof', 'amirah.yusof@student.example.test', 'pbkdf2_sha256$600000$iFn/3z58uYqTHgtWiUVhEw==$IeeeHiHN7sloETNOSk6zq/PNC1r6l6cDN1P0fQB1w0c=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10008', 3, 'Heng Jia Hui', 'jiahui.heng@student.example.test', 'pbkdf2_sha256$600000$/PT3UamQtnMiaBHsMKEDDQ==$tNoknt/IG5DvJNAaA8/EO0Oa672UGMCnd82NubB8TAc=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10009', 3, 'Viknesh a/l Raman', 'viknesh.raman@student.example.test', 'pbkdf2_sha256$600000$52OcWoN/1Q0akFdENercNg==$rEZCyv3enKMbUS6yg4ibdXEf3pf1edY66ooMaLWEN3I=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10010', 3, 'Nur Sabrina binti Hamid', 'sabrina.hamid@student.example.test', 'pbkdf2_sha256$600000$K62JRPsz7Oh1ATDp+Xl4hw==$veSGCXH8/0l8PL2T2xFDOeJ0LMVygQz8sz9c39KMA/Q=', NULL, 'not_registered', 'active', NULL, '2026-10-26 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10011', 3, 'Ho Wei Sheng', 'weisheng.ho@student.example.test', 'pbkdf2_sha256$600000$Buo7szmoZbVpK0/fJotgIA==$HS7+nnPVTo+2daHTF9XunY8XK/mgpzPJ84d1hYL/iRU=', NULL, 'not_registered', 'inactive', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO students (student_id, group_id, name, email, password_hash, face_encoding, biometric_status, account_status, consent_at, created_at, updated_at) VALUES ('24WCS10012', 3, 'Lau Qian Yi', 'qianyi.lau@student.example.test', 'pbkdf2_sha256$600000$BBwRrQkj1naMJ8c2vSAN1w==$zdnLkz5HOmb9z7hY3TfEDO7sAac4tV2FGHoAd773jf0=', NULL, 'not_registered', 'active', NULL, '2026-09-21 08:00:00', NULL);

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (1, 1, '2026-09-28', '09:00:00', '11:00:00', 'ICT Lab B204', 'closed', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (2, 1, '2026-10-05', '09:00:00', '11:00:00', 'ICT Lab B204', 'closed', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (3, 1, '2026-10-12', '09:00:00', '11:00:00', 'ICT Lab B204', 'closed', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (4, 1, '2026-10-19', '09:00:00', '11:00:00', 'ICT Lab B204', 'closed', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (5, 1, '2026-10-26', '09:00:00', '11:00:00', 'ICT Lab B204', 'closed', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (6, 1, '2026-11-02', '09:00:00', '11:00:00', 'ICT Lab B204', 'active', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (7, 1, '2026-11-09', '09:00:00', '11:00:00', 'ICT Lab B204', 'active', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (8, 1, '2026-11-16', '09:00:00', '11:00:00', 'ICT Lab B204', 'active', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (9, 1, '2026-11-23', '09:00:00', '11:00:00', 'ICT Lab B204', 'active', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (10, 1, '2026-11-30', '09:00:00', '11:00:00', 'ICT Lab B204', 'active', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (11, 1, '2026-12-07', '09:00:00', '11:00:00', 'ICT Lab B204', 'active', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (12, 1, '2026-12-14', '09:00:00', '11:00:00', 'ICT Lab B204', 'active', '080bf176a72d105681656ff5e16783e6a60c1fe531a4f3b2e1e7010781534424');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (13, 2, '2026-09-29', '10:00:00', '12:00:00', 'Lecture Hall A201', 'closed', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (14, 2, '2026-10-06', '10:00:00', '12:00:00', 'Lecture Hall A201', 'closed', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (15, 2, '2026-10-13', '10:00:00', '12:00:00', 'Lecture Hall A201', 'closed', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (16, 2, '2026-10-20', '10:00:00', '12:00:00', 'Lecture Hall A201', 'closed', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (17, 2, '2026-10-27', '10:00:00', '12:00:00', 'Lecture Hall A201', 'closed', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (18, 2, '2026-11-03', '10:00:00', '12:00:00', 'Lecture Hall A201', 'active', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (19, 2, '2026-11-10', '10:00:00', '12:00:00', 'Lecture Hall A201', 'active', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (20, 2, '2026-11-17', '10:00:00', '12:00:00', 'Lecture Hall A201', 'active', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (21, 2, '2026-11-24', '10:00:00', '12:00:00', 'Lecture Hall A201', 'active', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (22, 2, '2026-12-01', '10:00:00', '12:00:00', 'Lecture Hall A201', 'active', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (23, 2, '2026-12-08', '10:00:00', '12:00:00', 'Lecture Hall A201', 'active', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (24, 2, '2026-12-15', '10:00:00', '12:00:00', 'Lecture Hall A201', 'active', '2c616e6d7498973b954c3ef30529ca0facf93882e222188897b770e8fc5c34c9');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (25, 3, '2026-09-30', '14:00:00', '16:00:00', 'ICT Lab B206', 'closed', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (26, 3, '2026-10-07', '14:00:00', '16:00:00', 'ICT Lab B206', 'closed', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (27, 3, '2026-10-14', '14:00:00', '16:00:00', 'ICT Lab B206', 'closed', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (28, 3, '2026-10-21', '14:00:00', '16:00:00', 'ICT Lab B206', 'closed', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (29, 3, '2026-10-28', '14:00:00', '16:00:00', 'ICT Lab B206', 'closed', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (30, 3, '2026-11-04', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (31, 3, '2026-11-11', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (32, 3, '2026-11-18', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (33, 3, '2026-11-25', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (34, 3, '2026-12-02', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (35, 3, '2026-12-09', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (36, 3, '2026-12-16', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', '5c525cd06658b0e2f93713fefdac8472b2f3f667cb2345e708710f97f6e4a604');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (37, 4, '2026-10-01', '09:00:00', '11:00:00', 'Tutorial Room C103', 'closed', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (38, 4, '2026-10-08', '09:00:00', '11:00:00', 'Tutorial Room C103', 'closed', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (39, 4, '2026-10-15', '09:00:00', '11:00:00', 'Tutorial Room C103', 'closed', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (40, 4, '2026-10-22', '09:00:00', '11:00:00', 'Tutorial Room C103', 'closed', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (41, 4, '2026-10-29', '09:00:00', '11:00:00', 'Tutorial Room C103', 'closed', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (42, 4, '2026-11-05', '09:00:00', '11:00:00', 'Tutorial Room C103', 'active', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (43, 4, '2026-11-12', '09:00:00', '11:00:00', 'Tutorial Room C103', 'active', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (44, 4, '2026-11-19', '09:00:00', '11:00:00', 'Tutorial Room C103', 'active', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (45, 4, '2026-11-26', '09:00:00', '11:00:00', 'Tutorial Room C103', 'active', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (46, 4, '2026-12-03', '09:00:00', '11:00:00', 'Tutorial Room C103', 'active', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (47, 4, '2026-12-10', '09:00:00', '11:00:00', 'Tutorial Room C103', 'active', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (48, 4, '2026-12-17', '09:00:00', '11:00:00', 'Tutorial Room C103', 'active', '33c01dbbcc7a445b62651bffbda64eb6843bae3e194f2eccde1424fd170d5ab7');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (49, 5, '2026-09-28', '14:00:00', '16:00:00', 'ICT Lab B204', 'closed', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (50, 5, '2026-10-05', '14:00:00', '16:00:00', 'ICT Lab B204', 'closed', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (51, 5, '2026-10-12', '14:00:00', '16:00:00', 'ICT Lab B204', 'closed', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (52, 5, '2026-10-19', '14:00:00', '16:00:00', 'ICT Lab B204', 'closed', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (53, 5, '2026-10-26', '14:00:00', '16:00:00', 'ICT Lab B204', 'closed', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (54, 5, '2026-11-02', '14:00:00', '16:00:00', 'ICT Lab B204', 'active', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (55, 5, '2026-11-09', '14:00:00', '16:00:00', 'ICT Lab B204', 'active', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (56, 5, '2026-11-16', '14:00:00', '16:00:00', 'ICT Lab B204', 'active', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (57, 5, '2026-11-23', '14:00:00', '16:00:00', 'ICT Lab B204', 'active', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (58, 5, '2026-11-30', '14:00:00', '16:00:00', 'ICT Lab B204', 'active', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (59, 5, '2026-12-07', '14:00:00', '16:00:00', 'ICT Lab B204', 'active', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (60, 5, '2026-12-14', '14:00:00', '16:00:00', 'ICT Lab B204', 'active', '297f457da862d021ab0b4b2279b8d182b170e6fd31b50dad97e6636f4e55298f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (61, 6, '2026-09-29', '14:00:00', '16:00:00', 'Lecture Hall A201', 'closed', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (62, 6, '2026-10-06', '14:00:00', '16:00:00', 'Lecture Hall A201', 'closed', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (63, 6, '2026-10-13', '14:00:00', '16:00:00', 'Lecture Hall A201', 'closed', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (64, 6, '2026-10-20', '14:00:00', '16:00:00', 'Lecture Hall A201', 'closed', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (65, 6, '2026-10-27', '14:00:00', '16:00:00', 'Lecture Hall A201', 'closed', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (66, 6, '2026-11-03', '14:00:00', '16:00:00', 'Lecture Hall A201', 'active', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (67, 6, '2026-11-10', '14:00:00', '16:00:00', 'Lecture Hall A201', 'active', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (68, 6, '2026-11-17', '14:00:00', '16:00:00', 'Lecture Hall A201', 'active', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (69, 6, '2026-11-24', '14:00:00', '16:00:00', 'Lecture Hall A201', 'active', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (70, 6, '2026-12-01', '14:00:00', '16:00:00', 'Lecture Hall A201', 'active', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (71, 6, '2026-12-08', '14:00:00', '16:00:00', 'Lecture Hall A201', 'active', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (72, 6, '2026-12-15', '14:00:00', '16:00:00', 'Lecture Hall A201', 'active', '1cfea2f8392f29fe1c4b86c8c88c1d3acb749cb37b6101d3667195be30849520');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (73, 7, '2026-09-30', '09:00:00', '11:00:00', 'ICT Lab B206', 'closed', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (74, 7, '2026-10-07', '09:00:00', '11:00:00', 'ICT Lab B206', 'closed', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (75, 7, '2026-10-14', '09:00:00', '11:00:00', 'ICT Lab B206', 'closed', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (76, 7, '2026-10-21', '09:00:00', '11:00:00', 'ICT Lab B206', 'closed', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (77, 7, '2026-10-28', '09:00:00', '11:00:00', 'ICT Lab B206', 'closed', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (78, 7, '2026-11-04', '09:00:00', '11:00:00', 'ICT Lab B206', 'active', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (79, 7, '2026-11-11', '09:00:00', '11:00:00', 'ICT Lab B206', 'active', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (80, 7, '2026-11-18', '09:00:00', '11:00:00', 'ICT Lab B206', 'active', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (81, 7, '2026-11-25', '09:00:00', '11:00:00', 'ICT Lab B206', 'active', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (82, 7, '2026-12-02', '09:00:00', '11:00:00', 'ICT Lab B206', 'active', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (83, 7, '2026-12-09', '09:00:00', '11:00:00', 'ICT Lab B206', 'active', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (84, 7, '2026-12-16', '09:00:00', '11:00:00', 'ICT Lab B206', 'active', '61803cd36c93d26b3d5f012f7d7572a44de3250abd2d4afa010aecdf91b3ec61');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (85, 8, '2026-10-02', '10:00:00', '12:00:00', 'Tutorial Room C103', 'closed', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (86, 8, '2026-10-09', '10:00:00', '12:00:00', 'Tutorial Room C103', 'closed', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (87, 8, '2026-10-16', '10:00:00', '12:00:00', 'Tutorial Room C103', 'closed', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (88, 8, '2026-10-23', '10:00:00', '12:00:00', 'Tutorial Room C103', 'closed', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (89, 8, '2026-10-30', '10:00:00', '12:00:00', 'Tutorial Room C103', 'closed', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (90, 8, '2026-11-06', '10:00:00', '12:00:00', 'Tutorial Room C103', 'active', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (91, 8, '2026-11-13', '10:00:00', '12:00:00', 'Tutorial Room C103', 'active', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (92, 8, '2026-11-20', '10:00:00', '12:00:00', 'Tutorial Room C103', 'active', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (93, 8, '2026-11-27', '10:00:00', '12:00:00', 'Tutorial Room C103', 'active', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (94, 8, '2026-12-04', '10:00:00', '12:00:00', 'Tutorial Room C103', 'active', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (95, 8, '2026-12-11', '10:00:00', '12:00:00', 'Tutorial Room C103', 'active', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (96, 8, '2026-12-18', '10:00:00', '12:00:00', 'Tutorial Room C103', 'active', '46152069cd57c2542e58abb4ce26dd3938ab6567416e30d71fdc09aac36ba097');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (97, 9, '2026-09-28', '11:00:00', '13:00:00', 'Lecture Hall A203', 'closed', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (98, 9, '2026-10-05', '11:00:00', '13:00:00', 'Lecture Hall A203', 'closed', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (99, 9, '2026-10-12', '11:00:00', '13:00:00', 'Lecture Hall A203', 'closed', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (100, 9, '2026-10-19', '11:00:00', '13:00:00', 'Lecture Hall A203', 'closed', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (101, 9, '2026-10-26', '11:00:00', '13:00:00', 'Lecture Hall A203', 'closed', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (102, 9, '2026-11-02', '11:00:00', '13:00:00', 'Lecture Hall A203', 'active', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (103, 9, '2026-11-09', '11:00:00', '13:00:00', 'Lecture Hall A203', 'active', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (104, 9, '2026-11-16', '11:00:00', '13:00:00', 'Lecture Hall A203', 'active', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (105, 9, '2026-11-23', '11:00:00', '13:00:00', 'Lecture Hall A203', 'active', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (106, 9, '2026-11-30', '11:00:00', '13:00:00', 'Lecture Hall A203', 'active', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (107, 9, '2026-12-07', '11:00:00', '13:00:00', 'Lecture Hall A203', 'active', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (108, 9, '2026-12-14', '11:00:00', '13:00:00', 'Lecture Hall A203', 'active', '22d07dc46029162b0119f54084fd2d8e8ca7425e887bccbe5eb96e2f11e6030f');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (109, 10, '2026-09-29', '09:00:00', '11:00:00', 'Network Lab B301', 'closed', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (110, 10, '2026-10-06', '09:00:00', '11:00:00', 'Network Lab B301', 'closed', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (111, 10, '2026-10-13', '09:00:00', '11:00:00', 'Network Lab B301', 'closed', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (112, 10, '2026-10-20', '09:00:00', '11:00:00', 'Network Lab B301', 'closed', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (113, 10, '2026-10-27', '09:00:00', '11:00:00', 'Network Lab B301', 'closed', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (114, 10, '2026-11-03', '09:00:00', '11:00:00', 'Network Lab B301', 'active', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (115, 10, '2026-11-10', '09:00:00', '11:00:00', 'Network Lab B301', 'active', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (116, 10, '2026-11-17', '09:00:00', '11:00:00', 'Network Lab B301', 'active', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (117, 10, '2026-11-24', '09:00:00', '11:00:00', 'Network Lab B301', 'active', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (118, 10, '2026-12-01', '09:00:00', '11:00:00', 'Network Lab B301', 'active', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (119, 10, '2026-12-08', '09:00:00', '11:00:00', 'Network Lab B301', 'active', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (120, 10, '2026-12-15', '09:00:00', '11:00:00', 'Network Lab B301', 'active', '02083d168b02ea56949717c2641b4f9e509dc94e1b1b475adffa7adf51f83f71');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (121, 11, '2026-10-01', '14:00:00', '16:00:00', 'ICT Lab B206', 'closed', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (122, 11, '2026-10-08', '14:00:00', '16:00:00', 'ICT Lab B206', 'closed', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (123, 11, '2026-10-15', '14:00:00', '16:00:00', 'ICT Lab B206', 'closed', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (124, 11, '2026-10-22', '14:00:00', '16:00:00', 'ICT Lab B206', 'closed', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (125, 11, '2026-10-29', '14:00:00', '16:00:00', 'ICT Lab B206', 'closed', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (126, 11, '2026-11-05', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (127, 11, '2026-11-12', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (128, 11, '2026-11-19', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (129, 11, '2026-11-26', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (130, 11, '2026-12-03', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (131, 11, '2026-12-10', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (132, 11, '2026-12-17', '14:00:00', '16:00:00', 'ICT Lab B206', 'active', 'ec35071236ff89aa20c0a9d3b168cc7d6f59a8b2dfe54209c28b2b58e6d22791');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (133, 12, '2026-10-02', '14:00:00', '16:00:00', 'Tutorial Room C103', 'closed', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (134, 12, '2026-10-09', '14:00:00', '16:00:00', 'Tutorial Room C103', 'closed', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (135, 12, '2026-10-16', '14:00:00', '16:00:00', 'Tutorial Room C103', 'closed', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (136, 12, '2026-10-23', '14:00:00', '16:00:00', 'Tutorial Room C103', 'closed', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (137, 12, '2026-10-30', '14:00:00', '16:00:00', 'Tutorial Room C103', 'closed', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (138, 12, '2026-11-06', '14:00:00', '16:00:00', 'Tutorial Room C103', 'active', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (139, 12, '2026-11-13', '14:00:00', '16:00:00', 'Tutorial Room C103', 'active', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (140, 12, '2026-11-20', '14:00:00', '16:00:00', 'Tutorial Room C103', 'active', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (141, 12, '2026-11-27', '14:00:00', '16:00:00', 'Tutorial Room C103', 'active', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (142, 12, '2026-12-04', '14:00:00', '16:00:00', 'Tutorial Room C103', 'active', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (143, 12, '2026-12-11', '14:00:00', '16:00:00', 'Tutorial Room C103', 'active', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO class_sessions (session_id, schedule_id, session_date, start_time, end_time, venue, status, pin_hash) VALUES (144, 12, '2026-12-18', '14:00:00', '16:00:00', 'Tutorial Room C103', 'active', '35055b0f17d0167ffe72a456db6c052120178eade6c12fd2735f4dfa9b802f5d');

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (1, '24WMR10001', 1, 'success', 'sample_data', '2026-09-28 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (2, '24WMR10002', 1, 'success', 'sample_data', '2026-09-28 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (3, '24WMR10003', 1, 'success', 'sample_data', '2026-09-28 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (4, '24WMR10004', 1, 'success', 'sample_data', '2026-09-28 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (5, '24WMR10005', 1, 'success', 'sample_data', '2026-09-28 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (6, '24WMR10006', 1, 'success', 'sample_data', '2026-09-28 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (7, '24WMR10007', 1, 'success', 'sample_data', '2026-09-28 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (8, '24WMR10008', 1, 'failed', 'sample_data', '2026-09-28 09:02:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (9, '24WMR10009', 1, 'success', 'sample_data', '2026-09-28 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (10, '24WMR10011', 1, 'success', 'sample_data', '2026-09-28 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (11, '24WMR10012', 1, 'success', 'sample_data', '2026-09-28 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (12, '24WMR10001', 2, 'success', 'sample_data', '2026-10-05 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (13, '24WMR10002', 2, 'failed', 'sample_data', '2026-10-05 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (14, '24WMR10003', 2, 'success', 'sample_data', '2026-10-05 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (15, '24WMR10004', 2, 'success', 'sample_data', '2026-10-05 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (16, '24WMR10005', 2, 'success', 'sample_data', '2026-10-05 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (17, '24WMR10006', 2, 'success', 'sample_data', '2026-10-05 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (18, '24WMR10007', 2, 'success', 'sample_data', '2026-10-05 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (19, '24WMR10008', 2, 'success', 'sample_data', '2026-10-05 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (20, '24WMR10009', 2, 'failed', 'sample_data', '2026-10-05 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (21, '24WMR10011', 2, 'failed', 'sample_data', '2026-10-05 09:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (22, '24WMR10012', 2, 'success', 'sample_data', '2026-10-05 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (23, '24WMR10001', 3, 'success', 'sample_data', '2026-10-12 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (24, '24WMR10002', 3, 'success', 'sample_data', '2026-10-12 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (25, '24WMR10003', 3, 'success', 'sample_data', '2026-10-12 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (26, '24WMR10004', 3, 'success', 'sample_data', '2026-10-12 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (27, '24WMR10005', 3, 'failed', 'sample_data', '2026-10-12 09:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (28, '24WMR10006', 3, 'success', 'sample_data', '2026-10-12 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (29, '24WMR10007', 3, 'success', 'sample_data', '2026-10-12 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (30, '24WMR10008', 3, 'success', 'sample_data', '2026-10-12 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (31, '24WMR10009', 3, 'success', 'sample_data', '2026-10-12 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (32, '24WMR10011', 3, 'success', 'sample_data', '2026-10-12 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (33, '24WMR10012', 3, 'success', 'sample_data', '2026-10-12 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (34, '24WMR10001', 4, 'success', 'sample_data', '2026-10-19 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (35, '24WMR10002', 4, 'success', 'sample_data', '2026-10-19 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (36, '24WMR10003', 4, 'success', 'sample_data', '2026-10-19 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (37, '24WMR10004', 4, 'success', 'sample_data', '2026-10-19 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (38, '24WMR10005', 4, 'success', 'sample_data', '2026-10-19 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (39, '24WMR10006', 4, 'success', 'sample_data', '2026-10-19 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (40, '24WMR10007', 4, 'success', 'sample_data', '2026-10-19 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (41, '24WMR10008', 4, 'failed', 'sample_data', '2026-10-19 09:02:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (42, '24WMR10009', 4, 'success', 'sample_data', '2026-10-19 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (43, '24WMR10011', 4, 'success', 'sample_data', '2026-10-19 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (44, '24WMR10012', 4, 'success', 'sample_data', '2026-10-19 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (45, '24WMR10001', 5, 'success', 'sample_data', '2026-10-26 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (46, '24WMR10002', 5, 'failed', 'sample_data', '2026-10-26 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (47, '24WMR10003', 5, 'success', 'sample_data', '2026-10-26 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (48, '24WMR10004', 5, 'success', 'sample_data', '2026-10-26 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (49, '24WMR10005', 5, 'success', 'sample_data', '2026-10-26 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (50, '24WMR10006', 5, 'success', 'sample_data', '2026-10-26 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (51, '24WMR10007', 5, 'success', 'sample_data', '2026-10-26 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (52, '24WMR10008', 5, 'success', 'sample_data', '2026-10-26 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (53, '24WMR10009', 5, 'failed', 'sample_data', '2026-10-26 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (54, '24WMR10011', 5, 'failed', 'sample_data', '2026-10-26 09:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (55, '24WMR10012', 5, 'success', 'sample_data', '2026-10-26 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (56, '24WMR10001', 13, 'success', 'sample_data', '2026-09-29 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (57, '24WMR10002', 13, 'success', 'sample_data', '2026-09-29 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (58, '24WMR10003', 13, 'success', 'sample_data', '2026-09-29 10:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (59, '24WMR10004', 13, 'success', 'sample_data', '2026-09-29 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (60, '24WMR10005', 13, 'success', 'sample_data', '2026-09-29 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (61, '24WMR10006', 13, 'failed', 'sample_data', '2026-09-29 10:07:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (62, '24WMR10007', 13, 'success', 'sample_data', '2026-09-29 10:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (63, '24WMR10008', 13, 'success', 'sample_data', '2026-09-29 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (64, '24WMR10009', 13, 'failed', 'sample_data', '2026-09-29 10:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (65, '24WMR10011', 13, 'success', 'sample_data', '2026-09-29 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (66, '24WMR10012', 13, 'success', 'sample_data', '2026-09-29 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (67, '24WMR10001', 14, 'success', 'sample_data', '2026-10-06 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (68, '24WMR10002', 14, 'success', 'sample_data', '2026-10-06 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (69, '24WMR10003', 14, 'success', 'sample_data', '2026-10-06 10:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (70, '24WMR10004', 14, 'success', 'sample_data', '2026-10-06 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (71, '24WMR10005', 14, 'success', 'sample_data', '2026-10-06 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (72, '24WMR10006', 14, 'success', 'sample_data', '2026-10-06 10:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (73, '24WMR10007', 14, 'success', 'sample_data', '2026-10-06 10:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (74, '24WMR10008', 14, 'success', 'sample_data', '2026-10-06 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (75, '24WMR10009', 14, 'failed', 'sample_data', '2026-10-06 10:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (76, '24WMR10011', 14, 'success', 'sample_data', '2026-10-06 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (77, '24WMR10012', 14, 'success', 'sample_data', '2026-10-06 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (78, '24WMR10001', 15, 'success', 'sample_data', '2026-10-13 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (79, '24WMR10002', 15, 'success', 'sample_data', '2026-10-13 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (80, '24WMR10003', 15, 'failed', 'sample_data', '2026-10-13 10:04:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (81, '24WMR10004', 15, 'success', 'sample_data', '2026-10-13 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (82, '24WMR10005', 15, 'success', 'sample_data', '2026-10-13 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (83, '24WMR10006', 15, 'success', 'sample_data', '2026-10-13 10:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (84, '24WMR10007', 15, 'success', 'sample_data', '2026-10-13 10:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (85, '24WMR10008', 15, 'success', 'sample_data', '2026-10-13 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (86, '24WMR10009', 15, 'success', 'sample_data', '2026-10-13 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (87, '24WMR10011', 15, 'success', 'sample_data', '2026-10-13 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (88, '24WMR10012', 15, 'failed', 'sample_data', '2026-10-13 10:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (89, '24WMR10001', 16, 'success', 'sample_data', '2026-10-20 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (90, '24WMR10002', 16, 'success', 'sample_data', '2026-10-20 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (91, '24WMR10003', 16, 'success', 'sample_data', '2026-10-20 10:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (92, '24WMR10004', 16, 'failed', 'sample_data', '2026-10-20 10:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (93, '24WMR10005', 16, 'success', 'sample_data', '2026-10-20 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (94, '24WMR10006', 16, 'failed', 'sample_data', '2026-10-20 10:07:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (95, '24WMR10007', 16, 'success', 'sample_data', '2026-10-20 10:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (96, '24WMR10008', 16, 'success', 'sample_data', '2026-10-20 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (97, '24WMR10009', 16, 'failed', 'sample_data', '2026-10-20 10:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (98, '24WMR10011', 16, 'success', 'sample_data', '2026-10-20 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (99, '24WMR10012', 16, 'success', 'sample_data', '2026-10-20 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (100, '24WMR10001', 17, 'success', 'sample_data', '2026-10-27 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (101, '24WMR10002', 17, 'success', 'sample_data', '2026-10-27 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (102, '24WMR10003', 17, 'success', 'sample_data', '2026-10-27 10:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (103, '24WMR10004', 17, 'success', 'sample_data', '2026-10-27 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (104, '24WMR10005', 17, 'success', 'sample_data', '2026-10-27 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (105, '24WMR10006', 17, 'success', 'sample_data', '2026-10-27 10:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (106, '24WMR10007', 17, 'failed', 'sample_data', '2026-10-27 10:08:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (107, '24WMR10008', 17, 'success', 'sample_data', '2026-10-27 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (108, '24WMR10009', 17, 'failed', 'sample_data', '2026-10-27 10:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (109, '24WMR10011', 17, 'success', 'sample_data', '2026-10-27 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (110, '24WMR10012', 17, 'success', 'sample_data', '2026-10-27 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (111, '24WMR10001', 25, 'success', 'sample_data', '2026-09-30 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (112, '24WMR10002', 25, 'failed', 'sample_data', '2026-09-30 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (113, '24WMR10003', 25, 'success', 'sample_data', '2026-09-30 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (114, '24WMR10004', 25, 'failed', 'sample_data', '2026-09-30 14:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (115, '24WMR10005', 25, 'success', 'sample_data', '2026-09-30 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (116, '24WMR10006', 25, 'success', 'sample_data', '2026-09-30 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (117, '24WMR10007', 25, 'success', 'sample_data', '2026-09-30 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (118, '24WMR10008', 25, 'success', 'sample_data', '2026-09-30 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (119, '24WMR10009', 25, 'failed', 'sample_data', '2026-09-30 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (120, '24WMR10011', 25, 'success', 'sample_data', '2026-09-30 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (121, '24WMR10012', 25, 'success', 'sample_data', '2026-09-30 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (122, '24WMR10001', 26, 'success', 'sample_data', '2026-10-07 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (123, '24WMR10002', 26, 'success', 'sample_data', '2026-10-07 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (124, '24WMR10003', 26, 'success', 'sample_data', '2026-10-07 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (125, '24WMR10004', 26, 'success', 'sample_data', '2026-10-07 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (126, '24WMR10005', 26, 'failed', 'sample_data', '2026-10-07 14:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (127, '24WMR10006', 26, 'success', 'sample_data', '2026-10-07 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (128, '24WMR10007', 26, 'failed', 'sample_data', '2026-10-07 14:08:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (129, '24WMR10008', 26, 'success', 'sample_data', '2026-10-07 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (130, '24WMR10009', 26, 'success', 'sample_data', '2026-10-07 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (131, '24WMR10011', 26, 'success', 'sample_data', '2026-10-07 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (132, '24WMR10012', 26, 'success', 'sample_data', '2026-10-07 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (133, '24WMR10001', 27, 'success', 'sample_data', '2026-10-14 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (134, '24WMR10002', 27, 'success', 'sample_data', '2026-10-14 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (135, '24WMR10003', 27, 'success', 'sample_data', '2026-10-14 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (136, '24WMR10004', 27, 'success', 'sample_data', '2026-10-14 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (137, '24WMR10005', 27, 'success', 'sample_data', '2026-10-14 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (138, '24WMR10006', 27, 'success', 'sample_data', '2026-10-14 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (139, '24WMR10007', 27, 'success', 'sample_data', '2026-10-14 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (140, '24WMR10008', 27, 'failed', 'sample_data', '2026-10-14 14:02:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (141, '24WMR10009', 27, 'success', 'sample_data', '2026-10-14 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (142, '24WMR10011', 27, 'success', 'sample_data', '2026-10-14 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (143, '24WMR10012', 27, 'success', 'sample_data', '2026-10-14 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (144, '24WMR10001', 28, 'success', 'sample_data', '2026-10-21 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (145, '24WMR10002', 28, 'failed', 'sample_data', '2026-10-21 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (146, '24WMR10003', 28, 'success', 'sample_data', '2026-10-21 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (147, '24WMR10004', 28, 'success', 'sample_data', '2026-10-21 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (148, '24WMR10005', 28, 'success', 'sample_data', '2026-10-21 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (149, '24WMR10006', 28, 'success', 'sample_data', '2026-10-21 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (150, '24WMR10007', 28, 'success', 'sample_data', '2026-10-21 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (151, '24WMR10008', 28, 'success', 'sample_data', '2026-10-21 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (152, '24WMR10009', 28, 'failed', 'sample_data', '2026-10-21 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (153, '24WMR10011', 28, 'failed', 'sample_data', '2026-10-21 14:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (154, '24WMR10012', 28, 'success', 'sample_data', '2026-10-21 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (155, '24WMR10001', 29, 'success', 'sample_data', '2026-10-28 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (156, '24WMR10002', 29, 'success', 'sample_data', '2026-10-28 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (157, '24WMR10003', 29, 'success', 'sample_data', '2026-10-28 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (158, '24WMR10004', 29, 'success', 'sample_data', '2026-10-28 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (159, '24WMR10005', 29, 'failed', 'sample_data', '2026-10-28 14:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (160, '24WMR10006', 29, 'success', 'sample_data', '2026-10-28 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (161, '24WMR10007', 29, 'success', 'sample_data', '2026-10-28 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (162, '24WMR10008', 29, 'success', 'sample_data', '2026-10-28 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (163, '24WMR10009', 29, 'success', 'sample_data', '2026-10-28 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (164, '24WMR10011', 29, 'success', 'sample_data', '2026-10-28 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (165, '24WMR10012', 29, 'success', 'sample_data', '2026-10-28 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (166, '24WMR10001', 37, 'success', 'sample_data', '2026-10-01 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (167, '24WMR10002', 37, 'success', 'sample_data', '2026-10-01 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (168, '24WMR10003', 37, 'success', 'sample_data', '2026-10-01 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (169, '24WMR10004', 37, 'success', 'sample_data', '2026-10-01 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (170, '24WMR10005', 37, 'success', 'sample_data', '2026-10-01 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (171, '24WMR10006', 37, 'success', 'sample_data', '2026-10-01 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (172, '24WMR10007', 37, 'success', 'sample_data', '2026-10-01 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (173, '24WMR10008', 37, 'success', 'sample_data', '2026-10-01 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (174, '24WMR10009', 37, 'failed', 'sample_data', '2026-10-01 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (175, '24WMR10011', 37, 'failed', 'sample_data', '2026-10-01 09:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (176, '24WMR10012', 37, 'success', 'sample_data', '2026-10-01 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (177, '24WMR10001', 38, 'success', 'sample_data', '2026-10-08 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (178, '24WMR10002', 38, 'success', 'sample_data', '2026-10-08 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (179, '24WMR10003', 38, 'failed', 'sample_data', '2026-10-08 09:04:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (180, '24WMR10004', 38, 'success', 'sample_data', '2026-10-08 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (181, '24WMR10005', 38, 'success', 'sample_data', '2026-10-08 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (182, '24WMR10006', 38, 'success', 'sample_data', '2026-10-08 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (183, '24WMR10007', 38, 'success', 'sample_data', '2026-10-08 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (184, '24WMR10008', 38, 'success', 'sample_data', '2026-10-08 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (185, '24WMR10009', 38, 'success', 'sample_data', '2026-10-08 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (186, '24WMR10011', 38, 'success', 'sample_data', '2026-10-08 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (187, '24WMR10012', 38, 'failed', 'sample_data', '2026-10-08 09:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (188, '24WMR10001', 39, 'success', 'sample_data', '2026-10-15 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (189, '24WMR10002', 39, 'success', 'sample_data', '2026-10-15 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (190, '24WMR10003', 39, 'success', 'sample_data', '2026-10-15 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (191, '24WMR10004', 39, 'success', 'sample_data', '2026-10-15 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (192, '24WMR10005', 39, 'success', 'sample_data', '2026-10-15 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (193, '24WMR10006', 39, 'failed', 'sample_data', '2026-10-15 09:07:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (194, '24WMR10007', 39, 'success', 'sample_data', '2026-10-15 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (195, '24WMR10008', 39, 'success', 'sample_data', '2026-10-15 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (196, '24WMR10009', 39, 'failed', 'sample_data', '2026-10-15 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (197, '24WMR10011', 39, 'success', 'sample_data', '2026-10-15 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (198, '24WMR10012', 39, 'success', 'sample_data', '2026-10-15 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (199, '24WMR10001', 40, 'success', 'sample_data', '2026-10-22 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (200, '24WMR10002', 40, 'success', 'sample_data', '2026-10-22 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (201, '24WMR10003', 40, 'success', 'sample_data', '2026-10-22 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (202, '24WMR10004', 40, 'success', 'sample_data', '2026-10-22 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (203, '24WMR10005', 40, 'success', 'sample_data', '2026-10-22 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (204, '24WMR10006', 40, 'success', 'sample_data', '2026-10-22 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (205, '24WMR10007', 40, 'success', 'sample_data', '2026-10-22 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (206, '24WMR10008', 40, 'success', 'sample_data', '2026-10-22 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (207, '24WMR10009', 40, 'failed', 'sample_data', '2026-10-22 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (208, '24WMR10011', 40, 'success', 'sample_data', '2026-10-22 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (209, '24WMR10012', 40, 'success', 'sample_data', '2026-10-22 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (210, '24WMR10001', 41, 'success', 'sample_data', '2026-10-29 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (211, '24WMR10002', 41, 'success', 'sample_data', '2026-10-29 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (212, '24WMR10003', 41, 'failed', 'sample_data', '2026-10-29 09:04:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (213, '24WMR10004', 41, 'success', 'sample_data', '2026-10-29 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (214, '24WMR10005', 41, 'success', 'sample_data', '2026-10-29 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (215, '24WMR10006', 41, 'success', 'sample_data', '2026-10-29 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (216, '24WMR10007', 41, 'success', 'sample_data', '2026-10-29 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (217, '24WMR10008', 41, 'success', 'sample_data', '2026-10-29 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (218, '24WMR10009', 41, 'success', 'sample_data', '2026-10-29 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (219, '24WMR10011', 41, 'success', 'sample_data', '2026-10-29 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (220, '24WMR10012', 41, 'failed', 'sample_data', '2026-10-29 09:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (221, '24WMR10101', 49, 'success', 'sample_data', '2026-09-28 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (222, '24WMR10102', 49, 'success', 'sample_data', '2026-09-28 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (223, '24WMR10103', 49, 'success', 'sample_data', '2026-09-28 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (224, '24WMR10104', 49, 'success', 'sample_data', '2026-09-28 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (225, '24WMR10105', 49, 'success', 'sample_data', '2026-09-28 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (226, '24WMR10106', 49, 'success', 'sample_data', '2026-09-28 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (227, '24WMR10107', 49, 'failed', 'sample_data', '2026-09-28 14:08:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (228, '24WMR10108', 49, 'success', 'sample_data', '2026-09-28 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (229, '24WMR10109', 49, 'success', 'sample_data', '2026-09-28 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (230, '24WMR10111', 49, 'success', 'sample_data', '2026-09-28 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (231, '24WMR10112', 49, 'success', 'sample_data', '2026-09-28 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (232, '24WMR10101', 50, 'success', 'sample_data', '2026-10-05 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (233, '24WMR10102', 50, 'success', 'sample_data', '2026-10-05 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (234, '24WMR10103', 50, 'success', 'sample_data', '2026-10-05 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (235, '24WMR10104', 50, 'success', 'sample_data', '2026-10-05 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (236, '24WMR10105', 50, 'success', 'sample_data', '2026-10-05 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (237, '24WMR10106', 50, 'success', 'sample_data', '2026-10-05 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (238, '24WMR10107', 50, 'success', 'sample_data', '2026-10-05 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (239, '24WMR10108', 50, 'success', 'sample_data', '2026-10-05 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (240, '24WMR10109', 50, 'success', 'sample_data', '2026-10-05 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (241, '24WMR10111', 50, 'success', 'sample_data', '2026-10-05 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (242, '24WMR10112', 50, 'success', 'sample_data', '2026-10-05 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (243, '24WMR10101', 51, 'success', 'sample_data', '2026-10-12 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (244, '24WMR10102', 51, 'failed', 'sample_data', '2026-10-12 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (245, '24WMR10103', 51, 'success', 'sample_data', '2026-10-12 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (246, '24WMR10104', 51, 'failed', 'sample_data', '2026-10-12 14:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (247, '24WMR10105', 51, 'success', 'sample_data', '2026-10-12 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (248, '24WMR10106', 51, 'success', 'sample_data', '2026-10-12 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (249, '24WMR10107', 51, 'success', 'sample_data', '2026-10-12 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (250, '24WMR10108', 51, 'success', 'sample_data', '2026-10-12 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (251, '24WMR10109', 51, 'failed', 'sample_data', '2026-10-12 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (252, '24WMR10111', 51, 'success', 'sample_data', '2026-10-12 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (253, '24WMR10112', 51, 'success', 'sample_data', '2026-10-12 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (254, '24WMR10101', 52, 'success', 'sample_data', '2026-10-19 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (255, '24WMR10102', 52, 'success', 'sample_data', '2026-10-19 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (256, '24WMR10103', 52, 'success', 'sample_data', '2026-10-19 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (257, '24WMR10104', 52, 'success', 'sample_data', '2026-10-19 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (258, '24WMR10105', 52, 'failed', 'sample_data', '2026-10-19 14:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (259, '24WMR10106', 52, 'success', 'sample_data', '2026-10-19 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (260, '24WMR10107', 52, 'failed', 'sample_data', '2026-10-19 14:08:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (261, '24WMR10108', 52, 'success', 'sample_data', '2026-10-19 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (262, '24WMR10109', 52, 'success', 'sample_data', '2026-10-19 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (263, '24WMR10111', 52, 'success', 'sample_data', '2026-10-19 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (264, '24WMR10112', 52, 'success', 'sample_data', '2026-10-19 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (265, '24WMR10101', 53, 'success', 'sample_data', '2026-10-26 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (266, '24WMR10102', 53, 'success', 'sample_data', '2026-10-26 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (267, '24WMR10103', 53, 'success', 'sample_data', '2026-10-26 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (268, '24WMR10104', 53, 'success', 'sample_data', '2026-10-26 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (269, '24WMR10105', 53, 'success', 'sample_data', '2026-10-26 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (270, '24WMR10106', 53, 'success', 'sample_data', '2026-10-26 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (271, '24WMR10107', 53, 'success', 'sample_data', '2026-10-26 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (272, '24WMR10108', 53, 'failed', 'sample_data', '2026-10-26 14:02:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (273, '24WMR10109', 53, 'success', 'sample_data', '2026-10-26 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (274, '24WMR10111', 53, 'success', 'sample_data', '2026-10-26 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (275, '24WMR10112', 53, 'success', 'sample_data', '2026-10-26 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (276, '24WMR10101', 61, 'success', 'sample_data', '2026-09-29 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (277, '24WMR10102', 61, 'success', 'sample_data', '2026-09-29 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (278, '24WMR10103', 61, 'failed', 'sample_data', '2026-09-29 14:04:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (279, '24WMR10104', 61, 'success', 'sample_data', '2026-09-29 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (280, '24WMR10105', 61, 'failed', 'sample_data', '2026-09-29 14:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (281, '24WMR10106', 61, 'success', 'sample_data', '2026-09-29 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (282, '24WMR10107', 61, 'success', 'sample_data', '2026-09-29 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (283, '24WMR10108', 61, 'success', 'sample_data', '2026-09-29 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (284, '24WMR10109', 61, 'success', 'sample_data', '2026-09-29 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (285, '24WMR10111', 61, 'success', 'sample_data', '2026-09-29 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (286, '24WMR10112', 61, 'success', 'sample_data', '2026-09-29 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (287, '24WMR10101', 62, 'success', 'sample_data', '2026-10-06 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (288, '24WMR10102', 62, 'success', 'sample_data', '2026-10-06 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (289, '24WMR10103', 62, 'success', 'sample_data', '2026-10-06 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (290, '24WMR10104', 62, 'success', 'sample_data', '2026-10-06 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (291, '24WMR10105', 62, 'success', 'sample_data', '2026-10-06 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (292, '24WMR10106', 62, 'failed', 'sample_data', '2026-10-06 14:07:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (293, '24WMR10107', 62, 'success', 'sample_data', '2026-10-06 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (294, '24WMR10108', 62, 'failed', 'sample_data', '2026-10-06 14:02:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (295, '24WMR10109', 62, 'success', 'sample_data', '2026-10-06 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (296, '24WMR10111', 62, 'success', 'sample_data', '2026-10-06 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (297, '24WMR10112', 62, 'success', 'sample_data', '2026-10-06 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (298, '24WMR10101', 63, 'success', 'sample_data', '2026-10-13 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (299, '24WMR10102', 63, 'success', 'sample_data', '2026-10-13 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (300, '24WMR10103', 63, 'success', 'sample_data', '2026-10-13 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (301, '24WMR10104', 63, 'success', 'sample_data', '2026-10-13 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (302, '24WMR10105', 63, 'success', 'sample_data', '2026-10-13 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (303, '24WMR10106', 63, 'success', 'sample_data', '2026-10-13 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (304, '24WMR10107', 63, 'success', 'sample_data', '2026-10-13 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (305, '24WMR10108', 63, 'success', 'sample_data', '2026-10-13 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (306, '24WMR10109', 63, 'failed', 'sample_data', '2026-10-13 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (307, '24WMR10111', 63, 'failed', 'sample_data', '2026-10-13 14:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (308, '24WMR10112', 63, 'success', 'sample_data', '2026-10-13 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (309, '24WMR10101', 64, 'success', 'sample_data', '2026-10-20 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (310, '24WMR10102', 64, 'success', 'sample_data', '2026-10-20 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (311, '24WMR10103', 64, 'failed', 'sample_data', '2026-10-20 14:04:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (312, '24WMR10104', 64, 'success', 'sample_data', '2026-10-20 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (313, '24WMR10105', 64, 'success', 'sample_data', '2026-10-20 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (314, '24WMR10106', 64, 'success', 'sample_data', '2026-10-20 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (315, '24WMR10107', 64, 'success', 'sample_data', '2026-10-20 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (316, '24WMR10108', 64, 'success', 'sample_data', '2026-10-20 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (317, '24WMR10109', 64, 'success', 'sample_data', '2026-10-20 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (318, '24WMR10111', 64, 'success', 'sample_data', '2026-10-20 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (319, '24WMR10112', 64, 'failed', 'sample_data', '2026-10-20 14:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (320, '24WMR10101', 65, 'success', 'sample_data', '2026-10-27 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (321, '24WMR10102', 65, 'success', 'sample_data', '2026-10-27 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (322, '24WMR10103', 65, 'success', 'sample_data', '2026-10-27 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (323, '24WMR10104', 65, 'success', 'sample_data', '2026-10-27 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (324, '24WMR10105', 65, 'success', 'sample_data', '2026-10-27 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (325, '24WMR10106', 65, 'failed', 'sample_data', '2026-10-27 14:07:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (326, '24WMR10107', 65, 'success', 'sample_data', '2026-10-27 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (327, '24WMR10108', 65, 'success', 'sample_data', '2026-10-27 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (328, '24WMR10109', 65, 'failed', 'sample_data', '2026-10-27 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (329, '24WMR10111', 65, 'success', 'sample_data', '2026-10-27 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (330, '24WMR10112', 65, 'success', 'sample_data', '2026-10-27 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (331, '24WMR10101', 73, 'success', 'sample_data', '2026-09-30 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (332, '24WMR10102', 73, 'success', 'sample_data', '2026-09-30 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (333, '24WMR10103', 73, 'success', 'sample_data', '2026-09-30 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (334, '24WMR10104', 73, 'success', 'sample_data', '2026-09-30 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (335, '24WMR10105', 73, 'success', 'sample_data', '2026-09-30 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (336, '24WMR10106', 73, 'success', 'sample_data', '2026-09-30 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (337, '24WMR10107', 73, 'success', 'sample_data', '2026-09-30 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (338, '24WMR10108', 73, 'success', 'sample_data', '2026-09-30 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (339, '24WMR10109', 73, 'success', 'sample_data', '2026-09-30 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (340, '24WMR10111', 73, 'success', 'sample_data', '2026-09-30 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (341, '24WMR10112', 73, 'failed', 'sample_data', '2026-09-30 09:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (342, '24WMR10101', 74, 'success', 'sample_data', '2026-10-07 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (343, '24WMR10102', 74, 'success', 'sample_data', '2026-10-07 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (344, '24WMR10103', 74, 'success', 'sample_data', '2026-10-07 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (345, '24WMR10104', 74, 'failed', 'sample_data', '2026-10-07 09:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (346, '24WMR10105', 74, 'success', 'sample_data', '2026-10-07 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (347, '24WMR10106', 74, 'success', 'sample_data', '2026-10-07 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (348, '24WMR10107', 74, 'success', 'sample_data', '2026-10-07 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (349, '24WMR10108', 74, 'success', 'sample_data', '2026-10-07 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (350, '24WMR10109', 74, 'failed', 'sample_data', '2026-10-07 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (351, '24WMR10111', 74, 'success', 'sample_data', '2026-10-07 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (352, '24WMR10112', 74, 'success', 'sample_data', '2026-10-07 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (353, '24WMR10101', 75, 'success', 'sample_data', '2026-10-14 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (354, '24WMR10102', 75, 'success', 'sample_data', '2026-10-14 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (355, '24WMR10103', 75, 'success', 'sample_data', '2026-10-14 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (356, '24WMR10104', 75, 'success', 'sample_data', '2026-10-14 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (357, '24WMR10105', 75, 'success', 'sample_data', '2026-10-14 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (358, '24WMR10106', 75, 'success', 'sample_data', '2026-10-14 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (359, '24WMR10107', 75, 'failed', 'sample_data', '2026-10-14 09:08:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (360, '24WMR10108', 75, 'success', 'sample_data', '2026-10-14 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (361, '24WMR10109', 75, 'success', 'sample_data', '2026-10-14 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (362, '24WMR10111', 75, 'success', 'sample_data', '2026-10-14 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (363, '24WMR10112', 75, 'success', 'sample_data', '2026-10-14 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (364, '24WMR10101', 76, 'success', 'sample_data', '2026-10-21 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (365, '24WMR10102', 76, 'success', 'sample_data', '2026-10-21 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (366, '24WMR10103', 76, 'success', 'sample_data', '2026-10-21 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (367, '24WMR10104', 76, 'success', 'sample_data', '2026-10-21 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (368, '24WMR10105', 76, 'success', 'sample_data', '2026-10-21 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (369, '24WMR10106', 76, 'success', 'sample_data', '2026-10-21 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (370, '24WMR10107', 76, 'success', 'sample_data', '2026-10-21 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (371, '24WMR10108', 76, 'success', 'sample_data', '2026-10-21 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (372, '24WMR10109', 76, 'success', 'sample_data', '2026-10-21 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (373, '24WMR10111', 76, 'success', 'sample_data', '2026-10-21 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (374, '24WMR10112', 76, 'success', 'sample_data', '2026-10-21 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (375, '24WMR10101', 77, 'success', 'sample_data', '2026-10-28 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (376, '24WMR10102', 77, 'failed', 'sample_data', '2026-10-28 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (377, '24WMR10103', 77, 'success', 'sample_data', '2026-10-28 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (378, '24WMR10104', 77, 'failed', 'sample_data', '2026-10-28 09:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (379, '24WMR10105', 77, 'success', 'sample_data', '2026-10-28 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (380, '24WMR10106', 77, 'success', 'sample_data', '2026-10-28 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (381, '24WMR10107', 77, 'success', 'sample_data', '2026-10-28 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (382, '24WMR10108', 77, 'success', 'sample_data', '2026-10-28 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (383, '24WMR10109', 77, 'failed', 'sample_data', '2026-10-28 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (384, '24WMR10111', 77, 'success', 'sample_data', '2026-10-28 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (385, '24WMR10112', 77, 'success', 'sample_data', '2026-10-28 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (386, '24WMR10101', 85, 'success', 'sample_data', '2026-10-02 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (387, '24WMR10102', 85, 'success', 'sample_data', '2026-10-02 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (388, '24WMR10103', 85, 'success', 'sample_data', '2026-10-02 10:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (389, '24WMR10104', 85, 'success', 'sample_data', '2026-10-02 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (390, '24WMR10105', 85, 'success', 'sample_data', '2026-10-02 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (391, '24WMR10106', 85, 'success', 'sample_data', '2026-10-02 10:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (392, '24WMR10107', 85, 'success', 'sample_data', '2026-10-02 10:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (393, '24WMR10108', 85, 'failed', 'sample_data', '2026-10-02 10:02:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (394, '24WMR10109', 85, 'success', 'sample_data', '2026-10-02 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (395, '24WMR10111', 85, 'success', 'sample_data', '2026-10-02 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (396, '24WMR10112', 85, 'success', 'sample_data', '2026-10-02 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (397, '24WMR10101', 86, 'success', 'sample_data', '2026-10-09 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (398, '24WMR10102', 86, 'failed', 'sample_data', '2026-10-09 10:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (399, '24WMR10103', 86, 'success', 'sample_data', '2026-10-09 10:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (400, '24WMR10104', 86, 'success', 'sample_data', '2026-10-09 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (401, '24WMR10105', 86, 'success', 'sample_data', '2026-10-09 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (402, '24WMR10106', 86, 'success', 'sample_data', '2026-10-09 10:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (403, '24WMR10107', 86, 'success', 'sample_data', '2026-10-09 10:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (404, '24WMR10108', 86, 'success', 'sample_data', '2026-10-09 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (405, '24WMR10109', 86, 'failed', 'sample_data', '2026-10-09 10:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (406, '24WMR10111', 86, 'failed', 'sample_data', '2026-10-09 10:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (407, '24WMR10112', 86, 'success', 'sample_data', '2026-10-09 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (408, '24WMR10101', 87, 'success', 'sample_data', '2026-10-16 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (409, '24WMR10102', 87, 'success', 'sample_data', '2026-10-16 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (410, '24WMR10103', 87, 'failed', 'sample_data', '2026-10-16 10:04:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (411, '24WMR10104', 87, 'success', 'sample_data', '2026-10-16 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (412, '24WMR10105', 87, 'failed', 'sample_data', '2026-10-16 10:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (413, '24WMR10106', 87, 'success', 'sample_data', '2026-10-16 10:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (414, '24WMR10107', 87, 'success', 'sample_data', '2026-10-16 10:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (415, '24WMR10108', 87, 'success', 'sample_data', '2026-10-16 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (416, '24WMR10109', 87, 'success', 'sample_data', '2026-10-16 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (417, '24WMR10111', 87, 'success', 'sample_data', '2026-10-16 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (418, '24WMR10112', 87, 'success', 'sample_data', '2026-10-16 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (419, '24WMR10101', 88, 'success', 'sample_data', '2026-10-23 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (420, '24WMR10102', 88, 'success', 'sample_data', '2026-10-23 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (421, '24WMR10103', 88, 'success', 'sample_data', '2026-10-23 10:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (422, '24WMR10104', 88, 'success', 'sample_data', '2026-10-23 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (423, '24WMR10105', 88, 'success', 'sample_data', '2026-10-23 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (424, '24WMR10106', 88, 'failed', 'sample_data', '2026-10-23 10:07:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (425, '24WMR10107', 88, 'success', 'sample_data', '2026-10-23 10:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (426, '24WMR10108', 88, 'failed', 'sample_data', '2026-10-23 10:02:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (427, '24WMR10109', 88, 'success', 'sample_data', '2026-10-23 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (428, '24WMR10111', 88, 'success', 'sample_data', '2026-10-23 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (429, '24WMR10112', 88, 'success', 'sample_data', '2026-10-23 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (430, '24WMR10101', 89, 'success', 'sample_data', '2026-10-30 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (431, '24WMR10102', 89, 'success', 'sample_data', '2026-10-30 10:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (432, '24WMR10103', 89, 'success', 'sample_data', '2026-10-30 10:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (433, '24WMR10104', 89, 'success', 'sample_data', '2026-10-30 10:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (434, '24WMR10105', 89, 'success', 'sample_data', '2026-10-30 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (435, '24WMR10106', 89, 'success', 'sample_data', '2026-10-30 10:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (436, '24WMR10107', 89, 'success', 'sample_data', '2026-10-30 10:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (437, '24WMR10108', 89, 'success', 'sample_data', '2026-10-30 10:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (438, '24WMR10109', 89, 'failed', 'sample_data', '2026-10-30 10:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (439, '24WMR10111', 89, 'failed', 'sample_data', '2026-10-30 10:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (440, '24WMR10112', 89, 'success', 'sample_data', '2026-10-30 10:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (441, '24WCS10001', 97, 'success', 'sample_data', '2026-09-28 11:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (442, '24WCS10002', 97, 'success', 'sample_data', '2026-09-28 11:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (443, '24WCS10003', 97, 'success', 'sample_data', '2026-09-28 11:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (444, '24WCS10004', 97, 'failed', 'sample_data', '2026-09-28 11:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (445, '24WCS10005', 97, 'success', 'sample_data', '2026-09-28 11:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (446, '24WCS10006', 97, 'failed', 'sample_data', '2026-09-28 11:07:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (447, '24WCS10007', 97, 'success', 'sample_data', '2026-09-28 11:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (448, '24WCS10008', 97, 'success', 'sample_data', '2026-09-28 11:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (449, '24WCS10009', 97, 'failed', 'sample_data', '2026-09-28 11:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (450, '24WCS10011', 97, 'success', 'sample_data', '2026-09-28 11:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (451, '24WCS10012', 97, 'success', 'sample_data', '2026-09-28 11:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (452, '24WCS10001', 98, 'success', 'sample_data', '2026-10-05 11:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (453, '24WCS10002', 98, 'success', 'sample_data', '2026-10-05 11:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (454, '24WCS10003', 98, 'success', 'sample_data', '2026-10-05 11:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (455, '24WCS10004', 98, 'success', 'sample_data', '2026-10-05 11:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (456, '24WCS10005', 98, 'success', 'sample_data', '2026-10-05 11:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (457, '24WCS10006', 98, 'success', 'sample_data', '2026-10-05 11:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (458, '24WCS10007', 98, 'failed', 'sample_data', '2026-10-05 11:08:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (459, '24WCS10008', 98, 'success', 'sample_data', '2026-10-05 11:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (460, '24WCS10009', 98, 'failed', 'sample_data', '2026-10-05 11:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (461, '24WCS10011', 98, 'success', 'sample_data', '2026-10-05 11:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (462, '24WCS10012', 98, 'success', 'sample_data', '2026-10-05 11:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (463, '24WCS10001', 99, 'success', 'sample_data', '2026-10-12 11:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (464, '24WCS10002', 99, 'success', 'sample_data', '2026-10-12 11:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (465, '24WCS10003', 99, 'success', 'sample_data', '2026-10-12 11:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (466, '24WCS10004', 99, 'success', 'sample_data', '2026-10-12 11:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (467, '24WCS10005', 99, 'success', 'sample_data', '2026-10-12 11:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (468, '24WCS10006', 99, 'success', 'sample_data', '2026-10-12 11:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (469, '24WCS10007', 99, 'success', 'sample_data', '2026-10-12 11:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (470, '24WCS10008', 99, 'success', 'sample_data', '2026-10-12 11:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (471, '24WCS10009', 99, 'success', 'sample_data', '2026-10-12 11:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (472, '24WCS10011', 99, 'success', 'sample_data', '2026-10-12 11:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (473, '24WCS10012', 99, 'failed', 'sample_data', '2026-10-12 11:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (474, '24WCS10001', 100, 'success', 'sample_data', '2026-10-19 11:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (475, '24WCS10002', 100, 'success', 'sample_data', '2026-10-19 11:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (476, '24WCS10003', 100, 'success', 'sample_data', '2026-10-19 11:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (477, '24WCS10004', 100, 'failed', 'sample_data', '2026-10-19 11:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (478, '24WCS10005', 100, 'success', 'sample_data', '2026-10-19 11:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (479, '24WCS10006', 100, 'success', 'sample_data', '2026-10-19 11:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (480, '24WCS10007', 100, 'success', 'sample_data', '2026-10-19 11:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (481, '24WCS10008', 100, 'success', 'sample_data', '2026-10-19 11:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (482, '24WCS10009', 100, 'failed', 'sample_data', '2026-10-19 11:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (483, '24WCS10011', 100, 'success', 'sample_data', '2026-10-19 11:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (484, '24WCS10012', 100, 'success', 'sample_data', '2026-10-19 11:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (485, '24WCS10001', 101, 'success', 'sample_data', '2026-10-26 11:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (486, '24WCS10002', 101, 'success', 'sample_data', '2026-10-26 11:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (487, '24WCS10003', 101, 'success', 'sample_data', '2026-10-26 11:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (488, '24WCS10004', 101, 'success', 'sample_data', '2026-10-26 11:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (489, '24WCS10005', 101, 'success', 'sample_data', '2026-10-26 11:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (490, '24WCS10006', 101, 'success', 'sample_data', '2026-10-26 11:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (491, '24WCS10007', 101, 'failed', 'sample_data', '2026-10-26 11:08:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (492, '24WCS10008', 101, 'success', 'sample_data', '2026-10-26 11:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (493, '24WCS10009', 101, 'success', 'sample_data', '2026-10-26 11:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (494, '24WCS10011', 101, 'success', 'sample_data', '2026-10-26 11:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (495, '24WCS10012', 101, 'success', 'sample_data', '2026-10-26 11:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (496, '24WCS10001', 109, 'success', 'sample_data', '2026-09-29 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (497, '24WCS10002', 109, 'failed', 'sample_data', '2026-09-29 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (498, '24WCS10003', 109, 'success', 'sample_data', '2026-09-29 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (499, '24WCS10004', 109, 'success', 'sample_data', '2026-09-29 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (500, '24WCS10005', 109, 'success', 'sample_data', '2026-09-29 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (501, '24WCS10006', 109, 'success', 'sample_data', '2026-09-29 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (502, '24WCS10007', 109, 'success', 'sample_data', '2026-09-29 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (503, '24WCS10008', 109, 'success', 'sample_data', '2026-09-29 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (504, '24WCS10009', 109, 'failed', 'sample_data', '2026-09-29 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (505, '24WCS10011', 109, 'failed', 'sample_data', '2026-09-29 09:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (506, '24WCS10012', 109, 'success', 'sample_data', '2026-09-29 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (507, '24WCS10001', 110, 'success', 'sample_data', '2026-10-06 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (508, '24WCS10002', 110, 'success', 'sample_data', '2026-10-06 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (509, '24WCS10003', 110, 'success', 'sample_data', '2026-10-06 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (510, '24WCS10004', 110, 'success', 'sample_data', '2026-10-06 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (511, '24WCS10005', 110, 'failed', 'sample_data', '2026-10-06 09:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (512, '24WCS10006', 110, 'success', 'sample_data', '2026-10-06 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (513, '24WCS10007', 110, 'success', 'sample_data', '2026-10-06 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (514, '24WCS10008', 110, 'success', 'sample_data', '2026-10-06 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (515, '24WCS10009', 110, 'success', 'sample_data', '2026-10-06 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (516, '24WCS10011', 110, 'success', 'sample_data', '2026-10-06 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (517, '24WCS10012', 110, 'success', 'sample_data', '2026-10-06 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (518, '24WCS10001', 111, 'success', 'sample_data', '2026-10-13 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (519, '24WCS10002', 111, 'success', 'sample_data', '2026-10-13 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (520, '24WCS10003', 111, 'success', 'sample_data', '2026-10-13 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (521, '24WCS10004', 111, 'success', 'sample_data', '2026-10-13 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (522, '24WCS10005', 111, 'success', 'sample_data', '2026-10-13 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (523, '24WCS10006', 111, 'success', 'sample_data', '2026-10-13 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (524, '24WCS10007', 111, 'success', 'sample_data', '2026-10-13 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (525, '24WCS10008', 111, 'failed', 'sample_data', '2026-10-13 09:02:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (526, '24WCS10009', 111, 'success', 'sample_data', '2026-10-13 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (527, '24WCS10011', 111, 'success', 'sample_data', '2026-10-13 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (528, '24WCS10012', 111, 'success', 'sample_data', '2026-10-13 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (529, '24WCS10001', 112, 'success', 'sample_data', '2026-10-20 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (530, '24WCS10002', 112, 'failed', 'sample_data', '2026-10-20 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (531, '24WCS10003', 112, 'success', 'sample_data', '2026-10-20 09:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (532, '24WCS10004', 112, 'success', 'sample_data', '2026-10-20 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (533, '24WCS10005', 112, 'success', 'sample_data', '2026-10-20 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (534, '24WCS10006', 112, 'success', 'sample_data', '2026-10-20 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (535, '24WCS10007', 112, 'success', 'sample_data', '2026-10-20 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (536, '24WCS10008', 112, 'success', 'sample_data', '2026-10-20 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (537, '24WCS10009', 112, 'failed', 'sample_data', '2026-10-20 09:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (538, '24WCS10011', 112, 'failed', 'sample_data', '2026-10-20 09:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (539, '24WCS10012', 112, 'success', 'sample_data', '2026-10-20 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (540, '24WCS10001', 113, 'success', 'sample_data', '2026-10-27 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (541, '24WCS10002', 113, 'success', 'sample_data', '2026-10-27 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (542, '24WCS10003', 113, 'failed', 'sample_data', '2026-10-27 09:04:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (543, '24WCS10004', 113, 'success', 'sample_data', '2026-10-27 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (544, '24WCS10005', 113, 'failed', 'sample_data', '2026-10-27 09:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (545, '24WCS10006', 113, 'success', 'sample_data', '2026-10-27 09:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (546, '24WCS10007', 113, 'success', 'sample_data', '2026-10-27 09:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (547, '24WCS10008', 113, 'success', 'sample_data', '2026-10-27 09:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (548, '24WCS10009', 113, 'success', 'sample_data', '2026-10-27 09:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (549, '24WCS10011', 113, 'success', 'sample_data', '2026-10-27 09:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (550, '24WCS10012', 113, 'success', 'sample_data', '2026-10-27 09:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (551, '24WCS10001', 121, 'success', 'sample_data', '2026-10-01 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (552, '24WCS10002', 121, 'success', 'sample_data', '2026-10-01 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (553, '24WCS10003', 121, 'success', 'sample_data', '2026-10-01 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (554, '24WCS10004', 121, 'success', 'sample_data', '2026-10-01 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (555, '24WCS10005', 121, 'success', 'sample_data', '2026-10-01 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (556, '24WCS10006', 121, 'success', 'sample_data', '2026-10-01 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (557, '24WCS10007', 121, 'success', 'sample_data', '2026-10-01 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (558, '24WCS10008', 121, 'success', 'sample_data', '2026-10-01 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (559, '24WCS10009', 121, 'failed', 'sample_data', '2026-10-01 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (560, '24WCS10011', 121, 'success', 'sample_data', '2026-10-01 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (561, '24WCS10012', 121, 'success', 'sample_data', '2026-10-01 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (562, '24WCS10001', 122, 'success', 'sample_data', '2026-10-08 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (563, '24WCS10002', 122, 'success', 'sample_data', '2026-10-08 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (564, '24WCS10003', 122, 'failed', 'sample_data', '2026-10-08 14:04:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (565, '24WCS10004', 122, 'success', 'sample_data', '2026-10-08 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (566, '24WCS10005', 122, 'success', 'sample_data', '2026-10-08 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (567, '24WCS10006', 122, 'success', 'sample_data', '2026-10-08 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (568, '24WCS10007', 122, 'success', 'sample_data', '2026-10-08 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (569, '24WCS10008', 122, 'success', 'sample_data', '2026-10-08 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (570, '24WCS10009', 122, 'success', 'sample_data', '2026-10-08 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (571, '24WCS10011', 122, 'success', 'sample_data', '2026-10-08 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (572, '24WCS10012', 122, 'failed', 'sample_data', '2026-10-08 14:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (573, '24WCS10001', 123, 'success', 'sample_data', '2026-10-15 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (574, '24WCS10002', 123, 'success', 'sample_data', '2026-10-15 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (575, '24WCS10003', 123, 'success', 'sample_data', '2026-10-15 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (576, '24WCS10004', 123, 'failed', 'sample_data', '2026-10-15 14:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (577, '24WCS10005', 123, 'success', 'sample_data', '2026-10-15 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (578, '24WCS10006', 123, 'failed', 'sample_data', '2026-10-15 14:07:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (579, '24WCS10007', 123, 'success', 'sample_data', '2026-10-15 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (580, '24WCS10008', 123, 'success', 'sample_data', '2026-10-15 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (581, '24WCS10009', 123, 'failed', 'sample_data', '2026-10-15 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (582, '24WCS10011', 123, 'success', 'sample_data', '2026-10-15 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (583, '24WCS10012', 123, 'success', 'sample_data', '2026-10-15 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (584, '24WCS10001', 124, 'success', 'sample_data', '2026-10-22 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (585, '24WCS10002', 124, 'success', 'sample_data', '2026-10-22 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (586, '24WCS10003', 124, 'success', 'sample_data', '2026-10-22 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (587, '24WCS10004', 124, 'success', 'sample_data', '2026-10-22 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (588, '24WCS10005', 124, 'success', 'sample_data', '2026-10-22 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (589, '24WCS10006', 124, 'success', 'sample_data', '2026-10-22 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (590, '24WCS10007', 124, 'failed', 'sample_data', '2026-10-22 14:08:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (591, '24WCS10008', 124, 'success', 'sample_data', '2026-10-22 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (592, '24WCS10009', 124, 'failed', 'sample_data', '2026-10-22 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (593, '24WCS10011', 124, 'success', 'sample_data', '2026-10-22 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (594, '24WCS10012', 124, 'success', 'sample_data', '2026-10-22 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (595, '24WCS10001', 125, 'success', 'sample_data', '2026-10-29 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (596, '24WCS10002', 125, 'success', 'sample_data', '2026-10-29 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (597, '24WCS10003', 125, 'success', 'sample_data', '2026-10-29 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (598, '24WCS10004', 125, 'success', 'sample_data', '2026-10-29 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (599, '24WCS10005', 125, 'success', 'sample_data', '2026-10-29 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (600, '24WCS10006', 125, 'success', 'sample_data', '2026-10-29 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (601, '24WCS10007', 125, 'success', 'sample_data', '2026-10-29 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (602, '24WCS10008', 125, 'success', 'sample_data', '2026-10-29 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (603, '24WCS10009', 125, 'success', 'sample_data', '2026-10-29 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (604, '24WCS10011', 125, 'success', 'sample_data', '2026-10-29 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (605, '24WCS10012', 125, 'failed', 'sample_data', '2026-10-29 14:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (606, '24WCS10001', 133, 'success', 'sample_data', '2026-10-02 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (607, '24WCS10002', 133, 'success', 'sample_data', '2026-10-02 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (608, '24WCS10003', 133, 'success', 'sample_data', '2026-10-02 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (609, '24WCS10004', 133, 'success', 'sample_data', '2026-10-02 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (610, '24WCS10005', 133, 'failed', 'sample_data', '2026-10-02 14:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (611, '24WCS10006', 133, 'success', 'sample_data', '2026-10-02 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (612, '24WCS10007', 133, 'failed', 'sample_data', '2026-10-02 14:08:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (613, '24WCS10008', 133, 'success', 'sample_data', '2026-10-02 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (614, '24WCS10009', 133, 'success', 'sample_data', '2026-10-02 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (615, '24WCS10011', 133, 'success', 'sample_data', '2026-10-02 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (616, '24WCS10012', 133, 'success', 'sample_data', '2026-10-02 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (617, '24WCS10001', 134, 'success', 'sample_data', '2026-10-09 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (618, '24WCS10002', 134, 'success', 'sample_data', '2026-10-09 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (619, '24WCS10003', 134, 'success', 'sample_data', '2026-10-09 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (620, '24WCS10004', 134, 'success', 'sample_data', '2026-10-09 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (621, '24WCS10005', 134, 'success', 'sample_data', '2026-10-09 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (622, '24WCS10006', 134, 'success', 'sample_data', '2026-10-09 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (623, '24WCS10007', 134, 'success', 'sample_data', '2026-10-09 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (624, '24WCS10008', 134, 'failed', 'sample_data', '2026-10-09 14:02:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (625, '24WCS10009', 134, 'success', 'sample_data', '2026-10-09 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (626, '24WCS10011', 134, 'success', 'sample_data', '2026-10-09 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (627, '24WCS10012', 134, 'success', 'sample_data', '2026-10-09 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (628, '24WCS10001', 135, 'success', 'sample_data', '2026-10-16 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (629, '24WCS10002', 135, 'failed', 'sample_data', '2026-10-16 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (630, '24WCS10003', 135, 'success', 'sample_data', '2026-10-16 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (631, '24WCS10004', 135, 'success', 'sample_data', '2026-10-16 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (632, '24WCS10005', 135, 'success', 'sample_data', '2026-10-16 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (633, '24WCS10006', 135, 'success', 'sample_data', '2026-10-16 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (634, '24WCS10007', 135, 'success', 'sample_data', '2026-10-16 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (635, '24WCS10008', 135, 'success', 'sample_data', '2026-10-16 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (636, '24WCS10009', 135, 'failed', 'sample_data', '2026-10-16 14:03:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (637, '24WCS10011', 135, 'failed', 'sample_data', '2026-10-16 14:05:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (638, '24WCS10012', 135, 'success', 'sample_data', '2026-10-16 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (639, '24WCS10001', 136, 'success', 'sample_data', '2026-10-23 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (640, '24WCS10002', 136, 'success', 'sample_data', '2026-10-23 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (641, '24WCS10003', 136, 'success', 'sample_data', '2026-10-23 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (642, '24WCS10004', 136, 'success', 'sample_data', '2026-10-23 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (643, '24WCS10005', 136, 'failed', 'sample_data', '2026-10-23 14:06:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (644, '24WCS10006', 136, 'success', 'sample_data', '2026-10-23 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (645, '24WCS10007', 136, 'success', 'sample_data', '2026-10-23 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (646, '24WCS10008', 136, 'success', 'sample_data', '2026-10-23 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (647, '24WCS10009', 136, 'success', 'sample_data', '2026-10-23 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (648, '24WCS10011', 136, 'success', 'sample_data', '2026-10-23 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (649, '24WCS10012', 136, 'success', 'sample_data', '2026-10-23 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (650, '24WCS10001', 137, 'success', 'sample_data', '2026-10-30 14:01:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (651, '24WCS10002', 137, 'success', 'sample_data', '2026-10-30 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (652, '24WCS10003', 137, 'success', 'sample_data', '2026-10-30 14:03:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (653, '24WCS10004', 137, 'success', 'sample_data', '2026-10-30 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (654, '24WCS10005', 137, 'success', 'sample_data', '2026-10-30 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (655, '24WCS10006', 137, 'success', 'sample_data', '2026-10-30 14:06:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (656, '24WCS10007', 137, 'success', 'sample_data', '2026-10-30 14:07:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (657, '24WCS10008', 137, 'failed', 'sample_data', '2026-10-30 14:02:00', '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (658, '24WCS10009', 137, 'success', 'sample_data', '2026-10-30 14:02:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (659, '24WCS10011', 137, 'success', 'sample_data', '2026-10-30 14:04:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO verification_attempts (verification_id, student_id, session_id, verification_result, stage, attempted_at, failure_reason, face_distance) VALUES (660, '24WCS10012', 137, 'success', 'sample_data', '2026-10-30 14:05:50', '[SAMPLE] Imported fictional attendance; no biometric verification performed.', NULL);

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (1, 1, '24WMR10001', 1, '2026-09-28 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (2, 1, '24WMR10002', 2, '2026-09-28 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (3, 1, '24WMR10003', 3, '2026-09-28 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (4, 1, '24WMR10004', 4, '2026-09-28 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (5, 1, '24WMR10005', 5, '2026-09-28 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (6, 1, '24WMR10006', 6, '2026-09-28 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (7, 1, '24WMR10007', 7, '2026-09-28 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (8, 1, '24WMR10009', 9, '2026-09-28 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (9, 1, '24WMR10011', 10, '2026-09-28 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (10, 1, '24WMR10012', 11, '2026-09-28 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (11, 2, '24WMR10001', 12, '2026-10-05 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (12, 2, '24WMR10003', 14, '2026-10-05 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (13, 2, '24WMR10004', 15, '2026-10-05 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (14, 2, '24WMR10005', 16, '2026-10-05 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (15, 2, '24WMR10006', 17, '2026-10-05 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (16, 2, '24WMR10007', 18, '2026-10-05 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (17, 2, '24WMR10008', 19, '2026-10-05 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (18, 2, '24WMR10012', 22, '2026-10-05 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (19, 3, '24WMR10001', 23, '2026-10-12 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (20, 3, '24WMR10002', 24, '2026-10-12 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (21, 3, '24WMR10003', 25, '2026-10-12 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (22, 3, '24WMR10004', 26, '2026-10-12 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (23, 3, '24WMR10006', 28, '2026-10-12 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (24, 3, '24WMR10007', 29, '2026-10-12 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (25, 3, '24WMR10008', 30, '2026-10-12 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (26, 3, '24WMR10009', 31, '2026-10-12 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (27, 3, '24WMR10011', 32, '2026-10-12 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (28, 3, '24WMR10012', 33, '2026-10-12 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (29, 4, '24WMR10001', 34, '2026-10-19 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (30, 4, '24WMR10002', 35, '2026-10-19 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (31, 4, '24WMR10003', 36, '2026-10-19 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (32, 4, '24WMR10004', 37, '2026-10-19 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (33, 4, '24WMR10005', 38, '2026-10-19 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (34, 4, '24WMR10006', 39, '2026-10-19 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (35, 4, '24WMR10007', 40, '2026-10-19 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (36, 4, '24WMR10009', 42, '2026-10-19 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (37, 4, '24WMR10011', 43, '2026-10-19 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (38, 4, '24WMR10012', 44, '2026-10-19 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (39, 5, '24WMR10001', 45, '2026-10-26 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (40, 5, '24WMR10003', 47, '2026-10-26 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (41, 5, '24WMR10004', 48, '2026-10-26 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (42, 5, '24WMR10005', 49, '2026-10-26 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (43, 5, '24WMR10006', 50, '2026-10-26 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (44, 5, '24WMR10007', 51, '2026-10-26 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (45, 5, '24WMR10008', 52, '2026-10-26 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (46, 5, '24WMR10012', 55, '2026-10-26 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (47, 13, '24WMR10001', 56, '2026-09-29 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (48, 13, '24WMR10002', 57, '2026-09-29 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (49, 13, '24WMR10003', 58, '2026-09-29 10:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (50, 13, '24WMR10004', 59, '2026-09-29 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (51, 13, '24WMR10005', 60, '2026-09-29 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (52, 13, '24WMR10007', 62, '2026-09-29 10:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (53, 13, '24WMR10008', 63, '2026-09-29 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (54, 13, '24WMR10011', 65, '2026-09-29 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (55, 13, '24WMR10012', 66, '2026-09-29 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (56, 14, '24WMR10001', 67, '2026-10-06 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (57, 14, '24WMR10002', 68, '2026-10-06 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (58, 14, '24WMR10003', 69, '2026-10-06 10:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (59, 14, '24WMR10004', 70, '2026-10-06 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (60, 14, '24WMR10005', 71, '2026-10-06 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (61, 14, '24WMR10006', 72, '2026-10-06 10:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (62, 14, '24WMR10007', 73, '2026-10-06 10:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (63, 14, '24WMR10008', 74, '2026-10-06 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (64, 14, '24WMR10011', 76, '2026-10-06 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (65, 14, '24WMR10012', 77, '2026-10-06 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (66, 15, '24WMR10001', 78, '2026-10-13 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (67, 15, '24WMR10002', 79, '2026-10-13 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (68, 15, '24WMR10004', 81, '2026-10-13 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (69, 15, '24WMR10005', 82, '2026-10-13 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (70, 15, '24WMR10006', 83, '2026-10-13 10:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (71, 15, '24WMR10007', 84, '2026-10-13 10:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (72, 15, '24WMR10008', 85, '2026-10-13 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (73, 15, '24WMR10009', 86, '2026-10-13 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (74, 15, '24WMR10011', 87, '2026-10-13 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (75, 16, '24WMR10001', 89, '2026-10-20 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (76, 16, '24WMR10002', 90, '2026-10-20 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (77, 16, '24WMR10003', 91, '2026-10-20 10:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (78, 16, '24WMR10005', 93, '2026-10-20 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (79, 16, '24WMR10007', 95, '2026-10-20 10:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (80, 16, '24WMR10008', 96, '2026-10-20 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (81, 16, '24WMR10011', 98, '2026-10-20 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (82, 16, '24WMR10012', 99, '2026-10-20 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (83, 17, '24WMR10001', 100, '2026-10-27 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (84, 17, '24WMR10002', 101, '2026-10-27 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (85, 17, '24WMR10003', 102, '2026-10-27 10:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (86, 17, '24WMR10004', 103, '2026-10-27 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (87, 17, '24WMR10005', 104, '2026-10-27 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (88, 17, '24WMR10006', 105, '2026-10-27 10:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (89, 17, '24WMR10008', 107, '2026-10-27 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (90, 17, '24WMR10011', 109, '2026-10-27 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (91, 17, '24WMR10012', 110, '2026-10-27 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (92, 25, '24WMR10001', 111, '2026-09-30 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (93, 25, '24WMR10003', 113, '2026-09-30 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (94, 25, '24WMR10005', 115, '2026-09-30 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (95, 25, '24WMR10006', 116, '2026-09-30 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (96, 25, '24WMR10007', 117, '2026-09-30 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (97, 25, '24WMR10008', 118, '2026-09-30 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (98, 25, '24WMR10011', 120, '2026-09-30 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (99, 25, '24WMR10012', 121, '2026-09-30 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (100, 26, '24WMR10001', 122, '2026-10-07 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (101, 26, '24WMR10002', 123, '2026-10-07 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (102, 26, '24WMR10003', 124, '2026-10-07 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (103, 26, '24WMR10004', 125, '2026-10-07 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (104, 26, '24WMR10006', 127, '2026-10-07 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (105, 26, '24WMR10008', 129, '2026-10-07 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (106, 26, '24WMR10009', 130, '2026-10-07 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (107, 26, '24WMR10011', 131, '2026-10-07 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (108, 26, '24WMR10012', 132, '2026-10-07 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (109, 27, '24WMR10001', 133, '2026-10-14 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (110, 27, '24WMR10002', 134, '2026-10-14 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (111, 27, '24WMR10003', 135, '2026-10-14 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (112, 27, '24WMR10004', 136, '2026-10-14 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (113, 27, '24WMR10005', 137, '2026-10-14 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (114, 27, '24WMR10006', 138, '2026-10-14 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (115, 27, '24WMR10007', 139, '2026-10-14 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (116, 27, '24WMR10009', 141, '2026-10-14 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (117, 27, '24WMR10011', 142, '2026-10-14 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (118, 27, '24WMR10012', 143, '2026-10-14 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (119, 28, '24WMR10001', 144, '2026-10-21 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (120, 28, '24WMR10003', 146, '2026-10-21 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (121, 28, '24WMR10004', 147, '2026-10-21 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (122, 28, '24WMR10005', 148, '2026-10-21 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (123, 28, '24WMR10006', 149, '2026-10-21 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (124, 28, '24WMR10007', 150, '2026-10-21 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (125, 28, '24WMR10008', 151, '2026-10-21 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (126, 28, '24WMR10012', 154, '2026-10-21 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (127, 29, '24WMR10001', 155, '2026-10-28 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (128, 29, '24WMR10002', 156, '2026-10-28 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (129, 29, '24WMR10003', 157, '2026-10-28 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (130, 29, '24WMR10004', 158, '2026-10-28 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (131, 29, '24WMR10006', 160, '2026-10-28 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (132, 29, '24WMR10007', 161, '2026-10-28 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (133, 29, '24WMR10008', 162, '2026-10-28 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (134, 29, '24WMR10009', 163, '2026-10-28 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (135, 29, '24WMR10011', 164, '2026-10-28 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (136, 29, '24WMR10012', 165, '2026-10-28 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (137, 37, '24WMR10001', 166, '2026-10-01 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (138, 37, '24WMR10002', 167, '2026-10-01 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (139, 37, '24WMR10003', 168, '2026-10-01 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (140, 37, '24WMR10004', 169, '2026-10-01 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (141, 37, '24WMR10005', 170, '2026-10-01 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (142, 37, '24WMR10006', 171, '2026-10-01 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (143, 37, '24WMR10007', 172, '2026-10-01 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (144, 37, '24WMR10008', 173, '2026-10-01 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (145, 37, '24WMR10012', 176, '2026-10-01 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (146, 38, '24WMR10001', 177, '2026-10-08 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (147, 38, '24WMR10002', 178, '2026-10-08 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (148, 38, '24WMR10004', 180, '2026-10-08 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (149, 38, '24WMR10005', 181, '2026-10-08 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (150, 38, '24WMR10006', 182, '2026-10-08 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (151, 38, '24WMR10007', 183, '2026-10-08 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (152, 38, '24WMR10008', 184, '2026-10-08 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (153, 38, '24WMR10009', 185, '2026-10-08 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (154, 38, '24WMR10011', 186, '2026-10-08 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (155, 39, '24WMR10001', 188, '2026-10-15 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (156, 39, '24WMR10002', 189, '2026-10-15 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (157, 39, '24WMR10003', 190, '2026-10-15 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (158, 39, '24WMR10004', 191, '2026-10-15 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (159, 39, '24WMR10005', 192, '2026-10-15 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (160, 39, '24WMR10007', 194, '2026-10-15 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (161, 39, '24WMR10008', 195, '2026-10-15 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (162, 39, '24WMR10011', 197, '2026-10-15 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (163, 39, '24WMR10012', 198, '2026-10-15 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (164, 40, '24WMR10001', 199, '2026-10-22 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (165, 40, '24WMR10002', 200, '2026-10-22 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (166, 40, '24WMR10003', 201, '2026-10-22 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (167, 40, '24WMR10004', 202, '2026-10-22 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (168, 40, '24WMR10005', 203, '2026-10-22 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (169, 40, '24WMR10006', 204, '2026-10-22 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (170, 40, '24WMR10007', 205, '2026-10-22 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (171, 40, '24WMR10008', 206, '2026-10-22 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (172, 40, '24WMR10011', 208, '2026-10-22 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (173, 40, '24WMR10012', 209, '2026-10-22 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (174, 41, '24WMR10001', 210, '2026-10-29 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (175, 41, '24WMR10002', 211, '2026-10-29 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (176, 41, '24WMR10004', 213, '2026-10-29 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (177, 41, '24WMR10005', 214, '2026-10-29 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (178, 41, '24WMR10006', 215, '2026-10-29 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (179, 41, '24WMR10007', 216, '2026-10-29 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (180, 41, '24WMR10008', 217, '2026-10-29 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (181, 41, '24WMR10009', 218, '2026-10-29 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (182, 41, '24WMR10011', 219, '2026-10-29 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (183, 49, '24WMR10101', 221, '2026-09-28 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (184, 49, '24WMR10102', 222, '2026-09-28 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (185, 49, '24WMR10103', 223, '2026-09-28 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (186, 49, '24WMR10104', 224, '2026-09-28 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (187, 49, '24WMR10105', 225, '2026-09-28 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (188, 49, '24WMR10106', 226, '2026-09-28 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (189, 49, '24WMR10108', 228, '2026-09-28 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (190, 49, '24WMR10109', 229, '2026-09-28 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (191, 49, '24WMR10111', 230, '2026-09-28 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (192, 49, '24WMR10112', 231, '2026-09-28 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (193, 50, '24WMR10101', 232, '2026-10-05 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (194, 50, '24WMR10102', 233, '2026-10-05 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (195, 50, '24WMR10103', 234, '2026-10-05 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (196, 50, '24WMR10104', 235, '2026-10-05 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (197, 50, '24WMR10105', 236, '2026-10-05 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (198, 50, '24WMR10106', 237, '2026-10-05 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (199, 50, '24WMR10107', 238, '2026-10-05 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (200, 50, '24WMR10108', 239, '2026-10-05 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (201, 50, '24WMR10109', 240, '2026-10-05 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (202, 50, '24WMR10111', 241, '2026-10-05 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (203, 50, '24WMR10112', 242, '2026-10-05 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (204, 51, '24WMR10101', 243, '2026-10-12 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (205, 51, '24WMR10103', 245, '2026-10-12 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (206, 51, '24WMR10105', 247, '2026-10-12 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (207, 51, '24WMR10106', 248, '2026-10-12 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (208, 51, '24WMR10107', 249, '2026-10-12 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (209, 51, '24WMR10108', 250, '2026-10-12 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (210, 51, '24WMR10111', 252, '2026-10-12 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (211, 51, '24WMR10112', 253, '2026-10-12 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (212, 52, '24WMR10101', 254, '2026-10-19 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (213, 52, '24WMR10102', 255, '2026-10-19 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (214, 52, '24WMR10103', 256, '2026-10-19 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (215, 52, '24WMR10104', 257, '2026-10-19 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (216, 52, '24WMR10106', 259, '2026-10-19 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (217, 52, '24WMR10108', 261, '2026-10-19 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (218, 52, '24WMR10109', 262, '2026-10-19 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (219, 52, '24WMR10111', 263, '2026-10-19 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (220, 52, '24WMR10112', 264, '2026-10-19 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (221, 53, '24WMR10101', 265, '2026-10-26 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (222, 53, '24WMR10102', 266, '2026-10-26 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (223, 53, '24WMR10103', 267, '2026-10-26 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (224, 53, '24WMR10104', 268, '2026-10-26 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (225, 53, '24WMR10105', 269, '2026-10-26 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (226, 53, '24WMR10106', 270, '2026-10-26 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (227, 53, '24WMR10107', 271, '2026-10-26 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (228, 53, '24WMR10109', 273, '2026-10-26 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (229, 53, '24WMR10111', 274, '2026-10-26 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (230, 53, '24WMR10112', 275, '2026-10-26 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (231, 61, '24WMR10101', 276, '2026-09-29 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (232, 61, '24WMR10102', 277, '2026-09-29 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (233, 61, '24WMR10104', 279, '2026-09-29 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (234, 61, '24WMR10106', 281, '2026-09-29 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (235, 61, '24WMR10107', 282, '2026-09-29 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (236, 61, '24WMR10108', 283, '2026-09-29 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (237, 61, '24WMR10109', 284, '2026-09-29 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (238, 61, '24WMR10111', 285, '2026-09-29 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (239, 61, '24WMR10112', 286, '2026-09-29 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (240, 62, '24WMR10101', 287, '2026-10-06 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (241, 62, '24WMR10102', 288, '2026-10-06 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (242, 62, '24WMR10103', 289, '2026-10-06 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (243, 62, '24WMR10104', 290, '2026-10-06 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (244, 62, '24WMR10105', 291, '2026-10-06 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (245, 62, '24WMR10107', 293, '2026-10-06 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (246, 62, '24WMR10109', 295, '2026-10-06 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (247, 62, '24WMR10111', 296, '2026-10-06 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (248, 62, '24WMR10112', 297, '2026-10-06 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (249, 63, '24WMR10101', 298, '2026-10-13 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (250, 63, '24WMR10102', 299, '2026-10-13 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (251, 63, '24WMR10103', 300, '2026-10-13 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (252, 63, '24WMR10104', 301, '2026-10-13 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (253, 63, '24WMR10105', 302, '2026-10-13 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (254, 63, '24WMR10106', 303, '2026-10-13 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (255, 63, '24WMR10107', 304, '2026-10-13 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (256, 63, '24WMR10108', 305, '2026-10-13 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (257, 63, '24WMR10112', 308, '2026-10-13 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (258, 64, '24WMR10101', 309, '2026-10-20 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (259, 64, '24WMR10102', 310, '2026-10-20 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (260, 64, '24WMR10104', 312, '2026-10-20 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (261, 64, '24WMR10105', 313, '2026-10-20 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (262, 64, '24WMR10106', 314, '2026-10-20 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (263, 64, '24WMR10107', 315, '2026-10-20 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (264, 64, '24WMR10108', 316, '2026-10-20 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (265, 64, '24WMR10109', 317, '2026-10-20 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (266, 64, '24WMR10111', 318, '2026-10-20 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (267, 65, '24WMR10101', 320, '2026-10-27 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (268, 65, '24WMR10102', 321, '2026-10-27 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (269, 65, '24WMR10103', 322, '2026-10-27 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (270, 65, '24WMR10104', 323, '2026-10-27 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (271, 65, '24WMR10105', 324, '2026-10-27 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (272, 65, '24WMR10107', 326, '2026-10-27 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (273, 65, '24WMR10108', 327, '2026-10-27 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (274, 65, '24WMR10111', 329, '2026-10-27 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (275, 65, '24WMR10112', 330, '2026-10-27 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (276, 73, '24WMR10101', 331, '2026-09-30 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (277, 73, '24WMR10102', 332, '2026-09-30 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (278, 73, '24WMR10103', 333, '2026-09-30 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (279, 73, '24WMR10104', 334, '2026-09-30 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (280, 73, '24WMR10105', 335, '2026-09-30 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (281, 73, '24WMR10106', 336, '2026-09-30 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (282, 73, '24WMR10107', 337, '2026-09-30 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (283, 73, '24WMR10108', 338, '2026-09-30 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (284, 73, '24WMR10109', 339, '2026-09-30 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (285, 73, '24WMR10111', 340, '2026-09-30 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (286, 74, '24WMR10101', 342, '2026-10-07 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (287, 74, '24WMR10102', 343, '2026-10-07 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (288, 74, '24WMR10103', 344, '2026-10-07 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (289, 74, '24WMR10105', 346, '2026-10-07 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (290, 74, '24WMR10106', 347, '2026-10-07 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (291, 74, '24WMR10107', 348, '2026-10-07 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (292, 74, '24WMR10108', 349, '2026-10-07 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (293, 74, '24WMR10111', 351, '2026-10-07 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (294, 74, '24WMR10112', 352, '2026-10-07 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (295, 75, '24WMR10101', 353, '2026-10-14 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (296, 75, '24WMR10102', 354, '2026-10-14 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (297, 75, '24WMR10103', 355, '2026-10-14 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (298, 75, '24WMR10104', 356, '2026-10-14 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (299, 75, '24WMR10105', 357, '2026-10-14 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (300, 75, '24WMR10106', 358, '2026-10-14 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (301, 75, '24WMR10108', 360, '2026-10-14 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (302, 75, '24WMR10109', 361, '2026-10-14 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (303, 75, '24WMR10111', 362, '2026-10-14 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (304, 75, '24WMR10112', 363, '2026-10-14 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (305, 76, '24WMR10101', 364, '2026-10-21 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (306, 76, '24WMR10102', 365, '2026-10-21 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (307, 76, '24WMR10103', 366, '2026-10-21 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (308, 76, '24WMR10104', 367, '2026-10-21 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (309, 76, '24WMR10105', 368, '2026-10-21 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (310, 76, '24WMR10106', 369, '2026-10-21 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (311, 76, '24WMR10107', 370, '2026-10-21 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (312, 76, '24WMR10108', 371, '2026-10-21 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (313, 76, '24WMR10109', 372, '2026-10-21 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (314, 76, '24WMR10111', 373, '2026-10-21 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (315, 76, '24WMR10112', 374, '2026-10-21 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (316, 77, '24WMR10101', 375, '2026-10-28 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (317, 77, '24WMR10103', 377, '2026-10-28 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (318, 77, '24WMR10105', 379, '2026-10-28 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (319, 77, '24WMR10106', 380, '2026-10-28 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (320, 77, '24WMR10107', 381, '2026-10-28 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (321, 77, '24WMR10108', 382, '2026-10-28 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (322, 77, '24WMR10111', 384, '2026-10-28 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (323, 77, '24WMR10112', 385, '2026-10-28 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (324, 85, '24WMR10101', 386, '2026-10-02 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (325, 85, '24WMR10102', 387, '2026-10-02 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (326, 85, '24WMR10103', 388, '2026-10-02 10:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (327, 85, '24WMR10104', 389, '2026-10-02 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (328, 85, '24WMR10105', 390, '2026-10-02 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (329, 85, '24WMR10106', 391, '2026-10-02 10:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (330, 85, '24WMR10107', 392, '2026-10-02 10:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (331, 85, '24WMR10109', 394, '2026-10-02 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (332, 85, '24WMR10111', 395, '2026-10-02 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (333, 85, '24WMR10112', 396, '2026-10-02 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (334, 86, '24WMR10101', 397, '2026-10-09 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (335, 86, '24WMR10103', 399, '2026-10-09 10:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (336, 86, '24WMR10104', 400, '2026-10-09 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (337, 86, '24WMR10105', 401, '2026-10-09 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (338, 86, '24WMR10106', 402, '2026-10-09 10:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (339, 86, '24WMR10107', 403, '2026-10-09 10:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (340, 86, '24WMR10108', 404, '2026-10-09 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (341, 86, '24WMR10112', 407, '2026-10-09 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (342, 87, '24WMR10101', 408, '2026-10-16 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (343, 87, '24WMR10102', 409, '2026-10-16 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (344, 87, '24WMR10104', 411, '2026-10-16 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (345, 87, '24WMR10106', 413, '2026-10-16 10:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (346, 87, '24WMR10107', 414, '2026-10-16 10:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (347, 87, '24WMR10108', 415, '2026-10-16 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (348, 87, '24WMR10109', 416, '2026-10-16 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (349, 87, '24WMR10111', 417, '2026-10-16 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (350, 87, '24WMR10112', 418, '2026-10-16 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (351, 88, '24WMR10101', 419, '2026-10-23 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (352, 88, '24WMR10102', 420, '2026-10-23 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (353, 88, '24WMR10103', 421, '2026-10-23 10:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (354, 88, '24WMR10104', 422, '2026-10-23 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (355, 88, '24WMR10105', 423, '2026-10-23 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (356, 88, '24WMR10107', 425, '2026-10-23 10:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (357, 88, '24WMR10109', 427, '2026-10-23 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (358, 88, '24WMR10111', 428, '2026-10-23 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (359, 88, '24WMR10112', 429, '2026-10-23 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (360, 89, '24WMR10101', 430, '2026-10-30 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (361, 89, '24WMR10102', 431, '2026-10-30 10:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (362, 89, '24WMR10103', 432, '2026-10-30 10:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (363, 89, '24WMR10104', 433, '2026-10-30 10:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (364, 89, '24WMR10105', 434, '2026-10-30 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (365, 89, '24WMR10106', 435, '2026-10-30 10:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (366, 89, '24WMR10107', 436, '2026-10-30 10:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (367, 89, '24WMR10108', 437, '2026-10-30 10:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (368, 89, '24WMR10112', 440, '2026-10-30 10:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (369, 97, '24WCS10001', 441, '2026-09-28 11:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (370, 97, '24WCS10002', 442, '2026-09-28 11:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (371, 97, '24WCS10003', 443, '2026-09-28 11:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (372, 97, '24WCS10005', 445, '2026-09-28 11:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (373, 97, '24WCS10007', 447, '2026-09-28 11:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (374, 97, '24WCS10008', 448, '2026-09-28 11:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (375, 97, '24WCS10011', 450, '2026-09-28 11:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (376, 97, '24WCS10012', 451, '2026-09-28 11:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (377, 98, '24WCS10001', 452, '2026-10-05 11:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (378, 98, '24WCS10002', 453, '2026-10-05 11:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (379, 98, '24WCS10003', 454, '2026-10-05 11:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (380, 98, '24WCS10004', 455, '2026-10-05 11:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (381, 98, '24WCS10005', 456, '2026-10-05 11:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (382, 98, '24WCS10006', 457, '2026-10-05 11:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (383, 98, '24WCS10008', 459, '2026-10-05 11:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (384, 98, '24WCS10011', 461, '2026-10-05 11:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (385, 98, '24WCS10012', 462, '2026-10-05 11:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (386, 99, '24WCS10001', 463, '2026-10-12 11:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (387, 99, '24WCS10002', 464, '2026-10-12 11:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (388, 99, '24WCS10003', 465, '2026-10-12 11:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (389, 99, '24WCS10004', 466, '2026-10-12 11:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (390, 99, '24WCS10005', 467, '2026-10-12 11:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (391, 99, '24WCS10006', 468, '2026-10-12 11:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (392, 99, '24WCS10007', 469, '2026-10-12 11:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (393, 99, '24WCS10008', 470, '2026-10-12 11:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (394, 99, '24WCS10009', 471, '2026-10-12 11:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (395, 99, '24WCS10011', 472, '2026-10-12 11:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (396, 100, '24WCS10001', 474, '2026-10-19 11:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (397, 100, '24WCS10002', 475, '2026-10-19 11:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (398, 100, '24WCS10003', 476, '2026-10-19 11:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (399, 100, '24WCS10005', 478, '2026-10-19 11:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (400, 100, '24WCS10006', 479, '2026-10-19 11:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (401, 100, '24WCS10007', 480, '2026-10-19 11:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (402, 100, '24WCS10008', 481, '2026-10-19 11:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (403, 100, '24WCS10011', 483, '2026-10-19 11:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (404, 100, '24WCS10012', 484, '2026-10-19 11:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (405, 101, '24WCS10001', 485, '2026-10-26 11:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (406, 101, '24WCS10002', 486, '2026-10-26 11:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (407, 101, '24WCS10003', 487, '2026-10-26 11:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (408, 101, '24WCS10004', 488, '2026-10-26 11:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (409, 101, '24WCS10005', 489, '2026-10-26 11:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (410, 101, '24WCS10006', 490, '2026-10-26 11:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (411, 101, '24WCS10008', 492, '2026-10-26 11:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (412, 101, '24WCS10009', 493, '2026-10-26 11:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (413, 101, '24WCS10011', 494, '2026-10-26 11:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (414, 101, '24WCS10012', 495, '2026-10-26 11:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (415, 109, '24WCS10001', 496, '2026-09-29 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (416, 109, '24WCS10003', 498, '2026-09-29 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (417, 109, '24WCS10004', 499, '2026-09-29 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (418, 109, '24WCS10005', 500, '2026-09-29 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (419, 109, '24WCS10006', 501, '2026-09-29 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (420, 109, '24WCS10007', 502, '2026-09-29 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (421, 109, '24WCS10008', 503, '2026-09-29 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (422, 109, '24WCS10012', 506, '2026-09-29 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (423, 110, '24WCS10001', 507, '2026-10-06 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (424, 110, '24WCS10002', 508, '2026-10-06 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (425, 110, '24WCS10003', 509, '2026-10-06 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (426, 110, '24WCS10004', 510, '2026-10-06 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (427, 110, '24WCS10006', 512, '2026-10-06 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (428, 110, '24WCS10007', 513, '2026-10-06 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (429, 110, '24WCS10008', 514, '2026-10-06 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (430, 110, '24WCS10009', 515, '2026-10-06 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (431, 110, '24WCS10011', 516, '2026-10-06 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (432, 110, '24WCS10012', 517, '2026-10-06 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (433, 111, '24WCS10001', 518, '2026-10-13 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (434, 111, '24WCS10002', 519, '2026-10-13 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (435, 111, '24WCS10003', 520, '2026-10-13 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (436, 111, '24WCS10004', 521, '2026-10-13 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (437, 111, '24WCS10005', 522, '2026-10-13 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (438, 111, '24WCS10006', 523, '2026-10-13 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (439, 111, '24WCS10007', 524, '2026-10-13 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (440, 111, '24WCS10009', 526, '2026-10-13 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (441, 111, '24WCS10011', 527, '2026-10-13 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (442, 111, '24WCS10012', 528, '2026-10-13 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (443, 112, '24WCS10001', 529, '2026-10-20 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (444, 112, '24WCS10003', 531, '2026-10-20 09:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (445, 112, '24WCS10004', 532, '2026-10-20 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (446, 112, '24WCS10005', 533, '2026-10-20 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (447, 112, '24WCS10006', 534, '2026-10-20 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (448, 112, '24WCS10007', 535, '2026-10-20 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (449, 112, '24WCS10008', 536, '2026-10-20 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (450, 112, '24WCS10012', 539, '2026-10-20 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (451, 113, '24WCS10001', 540, '2026-10-27 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (452, 113, '24WCS10002', 541, '2026-10-27 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (453, 113, '24WCS10004', 543, '2026-10-27 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (454, 113, '24WCS10006', 545, '2026-10-27 09:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (455, 113, '24WCS10007', 546, '2026-10-27 09:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (456, 113, '24WCS10008', 547, '2026-10-27 09:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (457, 113, '24WCS10009', 548, '2026-10-27 09:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (458, 113, '24WCS10011', 549, '2026-10-27 09:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (459, 113, '24WCS10012', 550, '2026-10-27 09:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (460, 121, '24WCS10001', 551, '2026-10-01 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (461, 121, '24WCS10002', 552, '2026-10-01 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (462, 121, '24WCS10003', 553, '2026-10-01 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (463, 121, '24WCS10004', 554, '2026-10-01 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (464, 121, '24WCS10005', 555, '2026-10-01 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (465, 121, '24WCS10006', 556, '2026-10-01 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (466, 121, '24WCS10007', 557, '2026-10-01 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (467, 121, '24WCS10008', 558, '2026-10-01 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (468, 121, '24WCS10011', 560, '2026-10-01 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (469, 121, '24WCS10012', 561, '2026-10-01 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (470, 122, '24WCS10001', 562, '2026-10-08 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (471, 122, '24WCS10002', 563, '2026-10-08 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (472, 122, '24WCS10004', 565, '2026-10-08 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (473, 122, '24WCS10005', 566, '2026-10-08 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (474, 122, '24WCS10006', 567, '2026-10-08 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (475, 122, '24WCS10007', 568, '2026-10-08 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (476, 122, '24WCS10008', 569, '2026-10-08 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (477, 122, '24WCS10009', 570, '2026-10-08 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (478, 122, '24WCS10011', 571, '2026-10-08 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (479, 123, '24WCS10001', 573, '2026-10-15 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (480, 123, '24WCS10002', 574, '2026-10-15 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (481, 123, '24WCS10003', 575, '2026-10-15 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (482, 123, '24WCS10005', 577, '2026-10-15 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (483, 123, '24WCS10007', 579, '2026-10-15 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (484, 123, '24WCS10008', 580, '2026-10-15 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (485, 123, '24WCS10011', 582, '2026-10-15 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (486, 123, '24WCS10012', 583, '2026-10-15 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (487, 124, '24WCS10001', 584, '2026-10-22 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (488, 124, '24WCS10002', 585, '2026-10-22 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (489, 124, '24WCS10003', 586, '2026-10-22 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (490, 124, '24WCS10004', 587, '2026-10-22 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (491, 124, '24WCS10005', 588, '2026-10-22 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (492, 124, '24WCS10006', 589, '2026-10-22 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (493, 124, '24WCS10008', 591, '2026-10-22 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (494, 124, '24WCS10011', 593, '2026-10-22 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (495, 124, '24WCS10012', 594, '2026-10-22 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (496, 125, '24WCS10001', 595, '2026-10-29 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (497, 125, '24WCS10002', 596, '2026-10-29 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (498, 125, '24WCS10003', 597, '2026-10-29 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (499, 125, '24WCS10004', 598, '2026-10-29 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (500, 125, '24WCS10005', 599, '2026-10-29 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (501, 125, '24WCS10006', 600, '2026-10-29 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (502, 125, '24WCS10007', 601, '2026-10-29 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (503, 125, '24WCS10008', 602, '2026-10-29 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (504, 125, '24WCS10009', 603, '2026-10-29 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (505, 125, '24WCS10011', 604, '2026-10-29 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (506, 133, '24WCS10001', 606, '2026-10-02 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (507, 133, '24WCS10002', 607, '2026-10-02 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (508, 133, '24WCS10003', 608, '2026-10-02 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (509, 133, '24WCS10004', 609, '2026-10-02 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (510, 133, '24WCS10006', 611, '2026-10-02 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (511, 133, '24WCS10008', 613, '2026-10-02 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (512, 133, '24WCS10009', 614, '2026-10-02 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (513, 133, '24WCS10011', 615, '2026-10-02 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (514, 133, '24WCS10012', 616, '2026-10-02 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (515, 134, '24WCS10001', 617, '2026-10-09 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (516, 134, '24WCS10002', 618, '2026-10-09 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (517, 134, '24WCS10003', 619, '2026-10-09 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (518, 134, '24WCS10004', 620, '2026-10-09 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (519, 134, '24WCS10005', 621, '2026-10-09 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (520, 134, '24WCS10006', 622, '2026-10-09 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (521, 134, '24WCS10007', 623, '2026-10-09 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (522, 134, '24WCS10009', 625, '2026-10-09 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (523, 134, '24WCS10011', 626, '2026-10-09 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (524, 134, '24WCS10012', 627, '2026-10-09 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (525, 135, '24WCS10001', 628, '2026-10-16 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (526, 135, '24WCS10003', 630, '2026-10-16 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (527, 135, '24WCS10004', 631, '2026-10-16 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (528, 135, '24WCS10005', 632, '2026-10-16 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (529, 135, '24WCS10006', 633, '2026-10-16 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (530, 135, '24WCS10007', 634, '2026-10-16 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (531, 135, '24WCS10008', 635, '2026-10-16 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (532, 135, '24WCS10012', 638, '2026-10-16 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (533, 136, '24WCS10001', 639, '2026-10-23 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (534, 136, '24WCS10002', 640, '2026-10-23 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (535, 136, '24WCS10003', 641, '2026-10-23 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (536, 136, '24WCS10004', 642, '2026-10-23 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (537, 136, '24WCS10006', 644, '2026-10-23 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (538, 136, '24WCS10007', 645, '2026-10-23 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (539, 136, '24WCS10008', 646, '2026-10-23 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (540, 136, '24WCS10009', 647, '2026-10-23 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (541, 136, '24WCS10011', 648, '2026-10-23 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (542, 136, '24WCS10012', 649, '2026-10-23 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (543, 137, '24WCS10001', 650, '2026-10-30 14:02:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (544, 137, '24WCS10002', 651, '2026-10-30 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (545, 137, '24WCS10003', 652, '2026-10-30 14:04:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (546, 137, '24WCS10004', 653, '2026-10-30 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (547, 137, '24WCS10005', 654, '2026-10-30 14:06:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (548, 137, '24WCS10006', 655, '2026-10-30 14:07:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (549, 137, '24WCS10007', 656, '2026-10-30 14:08:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (550, 137, '24WCS10009', 658, '2026-10-30 14:03:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (551, 137, '24WCS10011', 659, '2026-10-30 14:05:00', 'Present');

INSERT INTO attendance (attendance_id, session_id, student_id, verification_id, taken_at, status) VALUES (552, 137, '24WCS10012', 660, '2026-10-30 14:06:00', 'Present');

COMMIT;

SELECT 'students' AS fixture_table, COUNT(*) AS row_count FROM students;

SELECT 'class_sessions' AS fixture_table, COUNT(*) AS row_count FROM class_sessions;

SELECT 'seeded_templates' AS fixture_table, COUNT(*) AS row_count FROM students WHERE face_encoding IS NOT NULL;
