package com.classroomfacecheckin.business.attendance;

import java.time.Instant;

public record AttendanceResponse(
        Long attendanceRecordId,
        Long studentId,
        boolean alreadyRecorded,
        String source,
        double confidence,
        Instant checkedInAt) {

    static AttendanceResponse from(AttendanceRecord record, boolean alreadyRecorded) {
        return new AttendanceResponse(
                record.getId(),
                record.getStudentId(),
                alreadyRecorded,
                record.getSource(),
                record.getConfidence().doubleValue(),
                record.getCheckedInAt());
    }
}
