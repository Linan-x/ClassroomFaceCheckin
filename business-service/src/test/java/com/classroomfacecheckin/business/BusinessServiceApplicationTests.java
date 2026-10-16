package com.classroomfacecheckin.business;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.sql.DataSource;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.classroomfacecheckin.business.domain.ClassroomRepository;
import com.classroomfacecheckin.business.domain.StudentRepository;
import com.classroomfacecheckin.business.domain.StudentPhotoRepository;
import com.classroomfacecheckin.business.domain.CourseRepository;
import com.classroomfacecheckin.business.domain.EnrollmentRepository;
import com.classroomfacecheckin.business.domain.CheckinSessionRepository;
import com.classroomfacecheckin.business.importer.LegacyImportRunner;
import com.classroomfacecheckin.business.importer.LegacyMigrationVerifier;
import com.classroomfacecheckin.business.recognition.RecognitionClient;
import com.classroomfacecheckin.business.recognition.RecognitionResult;
import com.classroomfacecheckin.business.realtime.AttendanceEvent;
import com.classroomfacecheckin.business.realtime.AttendanceEventPublisher;
import com.classroomfacecheckin.business.realtime.AttendanceSseController;
import com.classroomfacecheckin.business.realtime.RealtimeProperties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.boot.test.mock.mockito.MockBean;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ActiveProfiles("test")
@AutoConfigureMockMvc
@SpringBootTest(properties = "compatibility.enabled=true")
class BusinessServiceApplicationTests {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DataSource dataSource;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired private ClassroomRepository classrooms;
    @Autowired private StudentRepository students;
    @Autowired private StudentPhotoRepository photos;
    @Autowired private CourseRepository courses;
    @Autowired private EnrollmentRepository enrollments;
    @Autowired private CheckinSessionRepository sessions;
    @MockBean private RecognitionClient recognitionClient;
    @MockBean private AttendanceEventPublisher eventPublisher;

    @Test
    void systemInfoUsesTheVersionedUnifiedResponse() throws Exception {
        mockMvc.perform(get("/api/v1/system/info"))
                .andExpect(status().isOk())
                .andExpect(header().exists("X-Request-ID"))
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.service").value("classroom-face-checkin-business-service"))
                .andExpect(jsonPath("$.data.version").value("v1"))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    void readinessEndpointIsAvailable() throws Exception {
        mockMvc.perform(get("/actuator/health/readiness"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"));
    }

    @Test
    void attendanceUniquenessConstraintIsCreatedByMigration() throws Exception {
        try (Connection connection = dataSource.getConnection();
                Statement statement = connection.createStatement()) {
            statement.executeUpdate("INSERT INTO classrooms (code, name) VALUES ('C-001', 'Classroom')");
            statement.executeUpdate(
                    "INSERT INTO students (student_number, full_name, classroom_id) "
                            + "VALUES ('S-001', 'Student', (SELECT id FROM classrooms WHERE code = 'C-001'))");
            statement.executeUpdate("INSERT INTO courses (code, name) VALUES ('COURSE-001', 'Course')");
            statement.executeUpdate(
                    "INSERT INTO checkin_sessions (course_id, name, status) "
                            + "VALUES ((SELECT id FROM courses WHERE code = 'COURSE-001'), 'Session 1', 'OPEN')");
            statement.executeUpdate(
                    "INSERT INTO attendance_records (checkin_session_id, student_id, source, checked_in_at) "
                            + "VALUES ((SELECT id FROM checkin_sessions WHERE name = 'Session 1'), "
                            + "(SELECT id FROM students WHERE student_number = 'S-001'), 'TEST', CURRENT_TIMESTAMP)");

            assertThatThrownBy(() -> statement.executeUpdate(
                            "INSERT INTO attendance_records (checkin_session_id, student_id, source, checked_in_at) "
                                    + "VALUES ((SELECT id FROM checkin_sessions WHERE name = 'Session 1'), "
                                    + "(SELECT id FROM students WHERE student_number = 'S-001'), 'TEST', CURRENT_TIMESTAMP)"))
                    .isInstanceOf(SQLException.class);
        }
    }

    @Test
    void domainApiCreatesRelationshipsAndEndsAnActiveCheckinSession() throws Exception {
            long classroomId = create("/api/v1/classrooms",
                    "{\"code\":\"C-101\",\"name\":\"Class 101\",\"description\":\"Integration test class\"}");
            long studentId = create("/api/v1/students",
                    "{\"studentNumber\":\"S-101\",\"fullName\":\"Student One\",\"classroomId\":%d,\"phone\":\"123\"}".formatted(classroomId));
            long courseId = create("/api/v1/courses",
                    "{\"code\":\"COURSE-101\",\"name\":\"Course 101\",\"description\":\"Integration test course\"}");

            mockMvc.perform(put("/api/v1/courses/{id}/classrooms", courseId)
                            .contentType("application/json").content("{\"ids\":[" + classroomId + "]}"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data.classroomIds[0]").value(classroomId));
            mockMvc.perform(put("/api/v1/courses/{courseId}/students/{studentId}", courseId, studentId))
                    .andExpect(status().isCreated())
                    .andExpect(jsonPath("$.data.studentId").value(studentId));
            long sessionId = create("/api/v1/courses/" + courseId + "/checkin-sessions", "{\"name\":\"Morning\"}");
            mockMvc.perform(post("/api/v1/checkin-sessions/{id}/end", sessionId))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data.status").value("ENDED"));
            mockMvc.perform(post("/api/v1/checkin-sessions/{id}/end", sessionId))
                    .andExpect(status().isConflict())
                    .andExpect(jsonPath("$.error.code").value("INVALID_STATE"));
    }

    @Test
    void validationAndUnknownReferencesUseUnifiedErrors() throws Exception {
            mockMvc.perform(post("/api/v1/students").contentType("application/json").content("{}"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.error.code").value("VALIDATION_ERROR"));
            mockMvc.perform(post("/api/v1/courses/9999/checkin-sessions")
                            .contentType("application/json").content("{\"name\":\"Missing course\"}"))
                    .andExpect(status().isNotFound())
                    .andExpect(jsonPath("$.error.code").value("NOT_FOUND"));
    }

    @Test
    void recognitionAttendanceVerifiesEnrollmentAndIsIdempotent() throws Exception {
        long classroomId = create("/api/v1/classrooms", "{\"code\":\"C-202\",\"name\":\"Class 202\"}");
        long enrolledStudent = create("/api/v1/students",
                "{\"studentNumber\":\"S-202\",\"fullName\":\"Student 202\",\"classroomId\":%d}".formatted(classroomId));
        long outsider = create("/api/v1/students",
                "{\"studentNumber\":\"S-203\",\"fullName\":\"Student 203\",\"classroomId\":%d}".formatted(classroomId));
        long courseId = create("/api/v1/courses", "{\"code\":\"COURSE-202\",\"name\":\"Course 202\"}");
        mockMvc.perform(put("/api/v1/courses/{courseId}/students/{studentId}", courseId, enrolledStudent))
                .andExpect(status().isCreated());
        long sessionId = create("/api/v1/courses/" + courseId + "/checkin-sessions", "{\"name\":\"Recognition\"}");
        when(recognitionClient.recognize(anyString(), anyString(), anyString()))
                .thenReturn(new RecognitionResult(enrolledStudent, 0.11));

        String request = "{\"facebankId\":\"course-202-v1\",\"imageBase64\":\"aW1hZ2U=\"}";
        mockMvc.perform(post("/api/v1/checkin-sessions/{id}/attendance/recognize", sessionId)
                        .contentType("application/json").content(request))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.studentId").value(enrolledStudent))
                .andExpect(jsonPath("$.data.alreadyRecorded").value(false));
        mockMvc.perform(post("/api/v1/checkin-sessions/{id}/attendance/recognize", sessionId)
                        .contentType("application/json").content(request))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.alreadyRecorded").value(true));
        verify(eventPublisher, times(1)).publish(any(AttendanceEvent.class));

        when(recognitionClient.recognize(anyString(), anyString(), anyString()))
                .thenReturn(new RecognitionResult(outsider, 0.11));
        mockMvc.perform(post("/api/v1/checkin-sessions/{id}/attendance/recognize", sessionId)
                        .contentType("application/json").content(request))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error.code").value("RECOGNITION_REJECTED"));
    }

    @Test
    @Transactional
    void legacyImportSupportsDryRunAndIdempotentMappedRecords(@TempDir Path root) throws Exception {
        Files.writeString(root.resolve("classes.json"), "[\"Legacy Class\"]");
        Files.writeString(root.resolve("students_index.json"),
                "{\"Alice\":{\"name\":\"Alice\",\"class\":\"Legacy Class\",\"phone\":\"555\",\"courses\":[\"legacy-course\"]}}");
        Path course = Files.createDirectories(root.resolve("courses").resolve("legacy-course"));
        Files.writeString(course.resolve("meeting_info.json"),
                "{\"name\":\"Legacy Course\",\"description\":\"Imported course\",\"classes\":[\"Legacy Class\"]}");
        Files.writeString(course.resolve("sessions.json"),
                "{\"sessions\":[{\"id\":\"1\",\"name\":\"First\",\"created_at\":\"2026-01-01T00:00:00Z\"}],\"active\":\"1\"}");
        LegacyImportRunner runner = new LegacyImportRunner(
                objectMapper, classrooms, students, photos, courses, enrollments, sessions);
        long classesBefore = classrooms.count();
        long studentsBefore = students.count();
        runner.importData(root, true);
        assertThat(classrooms.count()).isEqualTo(classesBefore);
        assertThat(students.count()).isEqualTo(studentsBefore);

        runner.importData(root, false);
        long courseId = courses.findByLegacyKey("course:legacy-course").orElseThrow().getId();
        assertThat(enrollments.findByCourseId(courseId)).hasSize(1);
        assertThat(sessions.findByCourseIdOrderByStartsAtDesc(courseId)).hasSize(1);
        long enrollmentCount = enrollments.count();
        long sessionCount = sessions.count();
        runner.importData(root, false);
        assertThat(enrollments.count()).isEqualTo(enrollmentCount);
        assertThat(sessions.count()).isEqualTo(sessionCount);
        String verification = new LegacyMigrationVerifier(
                objectMapper, classrooms, students, courses, sessions).verify(root).render();
        assertThat(verification)
                .contains("classrooms source=1 imported=1 status=MATCH")
                .contains("students source=1 imported=1 status=MATCH")
                .contains("courses source=1 imported=1 status=MATCH")
                .contains("sessions source=1 imported=1 status=MATCH")
                .contains("attendance source=0 imported=UNSUPPORTED status=NOT_MIGRATED");

        mockMvc.perform(get("/api/compat/mobile/courses"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.courses[?(@.name == 'legacy-course')].total").value(1));
        mockMvc.perform(get("/api/compat/course/legacy-course/sessions"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.active").value("1"))
                .andExpect(jsonPath("$.sessions[0].name").value("First"));
    }

    @Test
    void dashboardSseReadsBoundedBacklogAndSubscribes() {
        AttendanceEvent event = new AttendanceEvent(
                "attendance-recorded", 42L, 7L, 9L, java.time.Instant.parse("2026-01-01T00:00:00Z"));
        when(eventPublisher.recent(42L)).thenReturn(java.util.List.of(event));
        when(eventPublisher.subscribe(any(), any())).thenReturn(() -> { });

        AttendanceSseController controller = new AttendanceSseController(
                eventPublisher, new RealtimeProperties(true, 10, "dashboard-token"));

        assertThat(controller.events(42L, "dashboard-token", null)).isNotNull();
        verify(eventPublisher).recent(42L);
        verify(eventPublisher).subscribe(any(), any());
    }

    private long create(String endpoint, String payload) throws Exception {
            String body = mockMvc.perform(post(endpoint).contentType("application/json").content(payload))
                    .andExpect(status().isCreated())
                    .andExpect(jsonPath("$.success").value(true))
                    .andReturn().getResponse().getContentAsString();
            JsonNode response = objectMapper.readTree(body);
            return response.path("data").path("id").asLong();
    }
}
