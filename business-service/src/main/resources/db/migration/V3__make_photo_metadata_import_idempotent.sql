ALTER TABLE student_photos MODIFY storage_uri VARCHAR(512) NOT NULL;
CREATE UNIQUE INDEX uk_student_photos_student_uri ON student_photos (student_id, storage_uri);
