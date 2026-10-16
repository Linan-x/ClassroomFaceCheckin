package com.classroomfacecheckin.business.domain;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
public interface StudentPhotoRepository extends JpaRepository<StudentPhoto, Long> {
    Optional<StudentPhoto> findByStudentIdAndStorageUri(Long studentId, String storageUri);
}
