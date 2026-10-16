package com.classroomfacecheckin.business.realtime;

import java.time.Instant;

public record AttendanceEvent(
        String type,
        Long sessionId,
        Long studentId,
        Long attendanceRecordId,
        Instant checkedInAt) {
}
