CREATE TABLE roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_roles_code UNIQUE (code)
);

CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(128) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    password_hash VARCHAR(255),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_users_username UNIQUE (username)
);

CREATE TABLE user_roles (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES roles (id)
);

CREATE TABLE classrooms (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    name VARCHAR(128) NOT NULL,
    description VARCHAR(500),
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_classrooms_code UNIQUE (code)
);

CREATE TABLE students (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_number VARCHAR(64) NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    classroom_id BIGINT,
    phone VARCHAR(64),
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_students_student_number UNIQUE (student_number),
    CONSTRAINT fk_students_classroom FOREIGN KEY (classroom_id) REFERENCES classrooms (id)
);

CREATE TABLE student_photos (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT NOT NULL,
    storage_uri VARCHAR(1024) NOT NULL,
    content_hash VARCHAR(128),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_student_photos_student FOREIGN KEY (student_id) REFERENCES students (id)
);

CREATE TABLE courses (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    name VARCHAR(128) NOT NULL,
    description VARCHAR(500),
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_courses_code UNIQUE (code)
);

CREATE TABLE course_classrooms (
    course_id BIGINT NOT NULL,
    classroom_id BIGINT NOT NULL,
    PRIMARY KEY (course_id, classroom_id),
    CONSTRAINT fk_course_classrooms_course FOREIGN KEY (course_id) REFERENCES courses (id),
    CONSTRAINT fk_course_classrooms_classroom FOREIGN KEY (classroom_id) REFERENCES classrooms (id)
);

CREATE TABLE enrollments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    course_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    enrolled_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_enrollments_course_student UNIQUE (course_id, student_id),
    CONSTRAINT fk_enrollments_course FOREIGN KEY (course_id) REFERENCES courses (id),
    CONSTRAINT fk_enrollments_student FOREIGN KEY (student_id) REFERENCES students (id)
);

CREATE TABLE checkin_sessions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    course_id BIGINT NOT NULL,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    starts_at TIMESTAMP(6),
    ends_at TIMESTAMP(6),
    created_by_user_id BIGINT,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_checkin_sessions_course_name UNIQUE (course_id, name),
    CONSTRAINT fk_checkin_sessions_course FOREIGN KEY (course_id) REFERENCES courses (id),
    CONSTRAINT fk_checkin_sessions_creator FOREIGN KEY (created_by_user_id) REFERENCES users (id)
);

CREATE TABLE attendance_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    checkin_session_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    source VARCHAR(32) NOT NULL,
    confidence DECIMAL(8, 6),
    checked_in_at TIMESTAMP(6) NOT NULL,
    recorded_by_user_id BIGINT,
    metadata_json LONGTEXT,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_attendance_records_session_student UNIQUE (checkin_session_id, student_id),
    CONSTRAINT fk_attendance_records_session FOREIGN KEY (checkin_session_id) REFERENCES checkin_sessions (id),
    CONSTRAINT fk_attendance_records_student FOREIGN KEY (student_id) REFERENCES students (id),
    CONSTRAINT fk_attendance_records_recorder FOREIGN KEY (recorded_by_user_id) REFERENCES users (id)
);

CREATE TABLE facebanks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    scope_type VARCHAR(32) NOT NULL,
    scope_id BIGINT NOT NULL,
    version VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    storage_uri VARCHAR(1024) NOT NULL,
    checksum VARCHAR(128),
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_facebanks_scope_version UNIQUE (scope_type, scope_id, version)
);

CREATE TABLE facebank_entries (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    facebank_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    vector_reference VARCHAR(1024) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uk_facebank_entries_facebank_student UNIQUE (facebank_id, student_id),
    CONSTRAINT fk_facebank_entries_facebank FOREIGN KEY (facebank_id) REFERENCES facebanks (id),
    CONSTRAINT fk_facebank_entries_student FOREIGN KEY (student_id) REFERENCES students (id)
);

CREATE TABLE audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    actor_user_id BIGINT,
    action VARCHAR(128) NOT NULL,
    entity_type VARCHAR(128) NOT NULL,
    entity_id VARCHAR(128),
    request_id VARCHAR(128),
    before_json LONGTEXT,
    after_json LONGTEXT,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_audit_logs_actor FOREIGN KEY (actor_user_id) REFERENCES users (id)
);

CREATE INDEX idx_student_photos_student ON student_photos (student_id);
CREATE INDEX idx_students_classroom ON students (classroom_id);
CREATE INDEX idx_enrollments_student ON enrollments (student_id);
CREATE INDEX idx_checkin_sessions_course ON checkin_sessions (course_id);
CREATE INDEX idx_attendance_records_student ON attendance_records (student_id);
CREATE INDEX idx_attendance_records_checked_in_at ON attendance_records (checked_in_at);
CREATE INDEX idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
