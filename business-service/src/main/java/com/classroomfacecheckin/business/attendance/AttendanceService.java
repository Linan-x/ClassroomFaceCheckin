package com.classroomfacecheckin.business.attendance;

import com.classroomfacecheckin.business.api.ConflictException;
import com.classroomfacecheckin.business.domain.CheckinSession;
import com.classroomfacecheckin.business.domain.CheckinSessionRepository;
import com.classroomfacecheckin.business.domain.EnrollmentRepository;
import com.classroomfacecheckin.business.domain.StudentRepository;
import com.classroomfacecheckin.business.recognition.RecognitionClient;
import com.classroomfacecheckin.business.recognition.RecognitionRejectedException;
import com.classroomfacecheckin.business.recognition.RecognitionResult;
import com.classroomfacecheckin.business.realtime.AttendanceEvent;
import com.classroomfacecheckin.business.realtime.AttendanceEventPublisher;
import java.util.List;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@Service
public class AttendanceService {
    private final CheckinSessionRepository sessions;
    private final EnrollmentRepository enrollments;
    private final StudentRepository students;
    private final AttendanceRecordRepository records;
    private final RecognitionClient recognition;
    private final AttendanceEventPublisher events;

    public AttendanceService(
            CheckinSessionRepository sessions,
            EnrollmentRepository enrollments,
            StudentRepository students,
            AttendanceRecordRepository records,
            RecognitionClient recognition,
            AttendanceEventPublisher events) {
        this.sessions = sessions;
        this.enrollments = enrollments;
        this.students = students;
        this.records = records;
        this.recognition = recognition;
        this.events = events;
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
            publishAfterCommit(created);
            return AttendanceResponse.from(created, false);
        } catch (DataIntegrityViolationException exception) {
            AttendanceRecord duplicate = records.findByCheckinSessionIdAndStudentId(sessionId, studentId)
                    .orElseThrow(() -> exception);
            return AttendanceResponse.from(duplicate, true);
        }
    }

        @Transactional(readOnly = true)
        public long countForSession(Long sessionId) {
            return records.countByCheckinSessionId(sessionId);
        }

        @Transactional(readOnly = true)
        public List<Long> studentIdsForSession(Long sessionId) {
            return records.findByCheckinSessionIdOrderByCheckedInAtAsc(sessionId).stream()
                    .map(AttendanceRecord::getStudentId)
                    .toList();
        }

        private void publishAfterCommit(AttendanceRecord record) {
            AttendanceEvent event = new AttendanceEvent(
                    "attendance-recorded",
                    record.getCheckinSessionId(),
                    record.getStudentId(),
                    record.getId(),
                    record.getCheckedInAt());
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    events.publish(event);
                }
            });
    }
}
