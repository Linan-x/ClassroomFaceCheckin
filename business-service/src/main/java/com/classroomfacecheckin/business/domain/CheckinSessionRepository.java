package com.classroomfacecheckin.business.domain;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
public interface CheckinSessionRepository extends JpaRepository<CheckinSession, Long> {
    Optional<CheckinSession> findByLegacyKey(String legacyKey);
    List<CheckinSession> findByCourseIdOrderByStartsAtDesc(Long courseId);
}
