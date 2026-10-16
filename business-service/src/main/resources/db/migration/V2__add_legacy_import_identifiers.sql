ALTER TABLE classrooms ADD COLUMN legacy_key VARCHAR(255);
ALTER TABLE students ADD COLUMN legacy_key VARCHAR(255);
ALTER TABLE courses ADD COLUMN legacy_key VARCHAR(255);
ALTER TABLE checkin_sessions ADD COLUMN legacy_key VARCHAR(255);

CREATE UNIQUE INDEX uk_classrooms_legacy_key ON classrooms (legacy_key);
CREATE UNIQUE INDEX uk_students_legacy_key ON students (legacy_key);
CREATE UNIQUE INDEX uk_courses_legacy_key ON courses (legacy_key);
CREATE UNIQUE INDEX uk_checkin_sessions_legacy_key ON checkin_sessions (legacy_key);
