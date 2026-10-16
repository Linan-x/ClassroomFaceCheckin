package com.classroomfacecheckin.business.domain;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
public interface ClassroomRepository extends JpaRepository<Classroom, Long> {
    Optional<Classroom> findByLegacyKey(String legacyKey);
    long countByLegacyKeyStartingWith(String prefix);
}
