package com.classroomfacecheckin.business.domain;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
public interface EnrollmentRepository extends JpaRepository<Enrollment, Long> {
    Optional<Enrollment> findByCourseIdAndStudentId(Long courseId, Long studentId);
    List<Enrollment> findByCourseId(Long courseId);
}
