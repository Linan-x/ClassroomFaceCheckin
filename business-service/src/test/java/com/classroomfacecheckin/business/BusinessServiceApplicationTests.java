package com.classroomfacecheckin.business;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import javax.sql.DataSource;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@ActiveProfiles("test")
@AutoConfigureMockMvc
@SpringBootTest
class BusinessServiceApplicationTests {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DataSource dataSource;

    @Test
    void systemInfoUsesTheVersionedUnifiedResponse() throws Exception {
        mockMvc.perform(get("/api/v1/system/info"))
                .andExpect(status().isOk())
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
                    "INSERT INTO students (student_number, full_name, classroom_id) VALUES ('S-001', 'Student', 1)");
            statement.executeUpdate("INSERT INTO courses (code, name) VALUES ('COURSE-001', 'Course')");
            statement.executeUpdate(
                    "INSERT INTO checkin_sessions (course_id, name, status) VALUES (1, 'Session 1', 'OPEN')");
            statement.executeUpdate(
                    "INSERT INTO attendance_records (checkin_session_id, student_id, source, checked_in_at) "
                            + "VALUES (1, 1, 'TEST', CURRENT_TIMESTAMP)");

            assertThatThrownBy(() -> statement.executeUpdate(
                            "INSERT INTO attendance_records (checkin_session_id, student_id, source, checked_in_at) "
                                    + "VALUES (1, 1, 'TEST', CURRENT_TIMESTAMP)"))
                    .isInstanceOf(SQLException.class);
        }
    }
}
