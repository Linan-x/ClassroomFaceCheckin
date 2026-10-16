package com.classroomfacecheckin.business.attendance;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AttendanceRecordRepository extends JpaRepository<AttendanceRecord, Long> {
    Optional<AttendanceRecord> findByCheckinSessionIdAndStudentId(Long checkinSessionId, Long studentId);
    long countByCheckinSessionId(Long checkinSessionId);
    List<AttendanceRecord> findByCheckinSessionIdOrderByCheckedInAtAsc(Long checkinSessionId);
}
