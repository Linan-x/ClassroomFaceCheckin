package com.classroomfacecheckin.business.attendance;

import com.classroomfacecheckin.business.api.ConflictException;
import com.classroomfacecheckin.business.domain.CheckinSession;
import com.classroomfacecheckin.business.domain.CheckinSessionRepository;
import com.classroomfacecheckin.business.domain.EnrollmentRepository;
import com.classroomfacecheckin.business.domain.StudentRepository;
import com.classroomfacecheckin.business.recognition.RecognitionClient;
import com.classroomfacecheckin.business.recognition.RecognitionRejectedException;
import com.classroomfacecheckin.business.recognition.RecognitionResult;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AttendanceService {
    private final CheckinSessionRepository sessions;
    private final EnrollmentRepository enrollments;
    private final StudentRepository students;
    private final AttendanceRecordRepository records;
    private final RecognitionClient recognition;

    public AttendanceService(
            CheckinSessionRepository sessions,
            EnrollmentRepository enrollments,
            StudentRepository students,
            AttendanceRecordRepository records,
            RecognitionClient recognition) {
        this.sessions = sessions;
        this.enrollments = enrollments;
        this.students = students;
        this.records = records;
        this.recognition = recognition;
    }

    @Transactional
    public AttendanceResponse recognizeAndRecord(Long sessionId, RecognitionAttendanceRequest request, String requestId) {
        CheckinSession session = sessions.findById(sessionId)
                .orElseThrow(() -> new com.classroomfacecheckin.business.api.NotFoundException("Check-in session not found."));
        if (!"ACTIVE".equals(session.getStatus())) {
            throw new ConflictException("Check-in session is not active.");
        }
        RecognitionResult result = recognition.recognize(request.facebankId(), request.imageBase64(), requestId);
        if (!result.matched()) {
            throw new RecognitionRejectedException("No enrolled student was recognized.");
        }
        Long studentId = result.studentId();
        students.findById(studentId)
                .orElseThrow(() -> new RecognitionRejectedException("Recognition returned an unknown student."));
        if (enrollments.findByCourseIdAndStudentId(session.getCourse().getId(), studentId).isEmpty()) {
            throw new RecognitionRejectedException("Recognized student is not enrolled in this course.");
        }
        AttendanceRecord existing = records.findByCheckinSessionIdAndStudentId(sessionId, studentId).orElse(null);
        if (existing != null) {
            return AttendanceResponse.from(existing, true);
        }
        try {
            AttendanceRecord created = records.saveAndFlush(
                    new AttendanceRecord(sessionId, studentId, "RECOGNITION", result.confidence()));
            return AttendanceResponse.from(created, false);
        } catch (DataIntegrityViolationException exception) {
            AttendanceRecord duplicate = records.findByCheckinSessionIdAndStudentId(sessionId, studentId)
                    .orElseThrow(() -> exception);
            return AttendanceResponse.from(duplicate, true);
        }
    }
}
