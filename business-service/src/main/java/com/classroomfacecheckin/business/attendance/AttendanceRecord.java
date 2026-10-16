package com.classroomfacecheckin.business.attendance;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.math.BigDecimal;
import java.time.Instant;

@Entity
@Table(
        name = "attendance_records",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_attendance_records_session_student",
                columnNames = {"checkin_session_id", "student_id"}))
public class AttendanceRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "checkin_session_id", nullable = false)
    private Long checkinSessionId;

    @Column(name = "student_id", nullable = false)
    private Long studentId;

    @Column(nullable = false, length = 32)
    private String source;

    @Column(name = "checked_in_at", nullable = false)
    private Instant checkedInAt;

    protected AttendanceRecord() {
    }

    public AttendanceRecord(Long checkinSessionId, Long studentId, String source, double confidence) {
        this.checkinSessionId = checkinSessionId;
        this.studentId = studentId;
        this.source = source;
        this.confidence = BigDecimal.valueOf(confidence);
        this.checkedInAt = Instant.now();
    }

    @Column(nullable = false)
    private BigDecimal confidence;

    public Long getId() {
        return id;
    }

    public Long getCheckinSessionId() {
        return checkinSessionId;
    }

    public Long getStudentId() {
        return studentId;
    }

    public String getSource() {
        return source;
    }

    public BigDecimal getConfidence() {
        return confidence;
    }

    public Instant getCheckedInAt() {
        return checkedInAt;
    }
}
