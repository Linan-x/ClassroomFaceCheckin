package com.classroomfacecheckin.business.domain;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
public interface CourseRepository extends JpaRepository<Course, Long> {
    Optional<Course> findByLegacyKey(String legacyKey);
    long countByLegacyKeyStartingWith(String prefix);
}
