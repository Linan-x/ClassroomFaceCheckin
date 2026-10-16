package com.classroomfacecheckin.business.compatibility;

import com.classroomfacecheckin.business.api.NotFoundException;
import com.classroomfacecheckin.business.attendance.AttendanceResponse;
import com.classroomfacecheckin.business.attendance.AttendanceService;
import com.classroomfacecheckin.business.attendance.RecognitionAttendanceRequest;
import com.classroomfacecheckin.business.domain.CheckinSession;
import com.classroomfacecheckin.business.domain.CheckinSessionRepository;
import com.classroomfacecheckin.business.domain.Course;
import com.classroomfacecheckin.business.domain.CourseRepository;
import com.classroomfacecheckin.business.domain.EnrollmentRepository;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.transaction.annotation.Transactional;
import static org.springframework.http.HttpStatus.BAD_REQUEST;
import static org.springframework.http.HttpStatus.PAYLOAD_TOO_LARGE;

@RestController
@RequestMapping("/api/compat")
@ConditionalOnProperty(prefix = "compatibility", name = "enabled", havingValue = "true")
@Transactional
public class LegacyMobileCompatibilityController {
    private final CourseRepository courses;
    private final CheckinSessionRepository sessions;
    private final EnrollmentRepository enrollments;
    private final AttendanceService attendance;
    private final CompatibilityProperties properties;
    private final CompatibilityRateLimiter limiter;

    public LegacyMobileCompatibilityController(
            CourseRepository courses,
            CheckinSessionRepository sessions,
            EnrollmentRepository enrollments,
            AttendanceService attendance,
            CompatibilityProperties properties,
            CompatibilityRateLimiter limiter) {
        this.courses = courses;
        this.sessions = sessions;
        this.enrollments = enrollments;
        this.attendance = attendance;
        this.properties = properties;
        this.limiter = limiter;
    }

    @GetMapping("/mobile/courses")
    public Map<String, Object> courses() {
        return Map.of("courses", courses.findAll().stream()
                .filter(course -> course.getLegacyKey() != null && course.getLegacyKey().startsWith("course:"))
                .map(this::course)
                .toList());
    }

    @GetMapping("/course/{courseKey}/sessions")
    public Map<String, Object> sessions(@PathVariable String courseKey) {
        Course course = course(courseKey);
        List<Map<String, Object>> values = sessions.findByCourseIdOrderByStartsAtDesc(course.getId()).stream()
                .map(this::session).toList();
        String active = values.stream().filter(value -> "ACTIVE".equals(value.get("status")))
                .map(value -> (String) value.get("id")).findFirst().orElse(null);
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("sessions", values);
        response.put("active", active);
        return response;
    }

    @PostMapping("/course/{courseKey}/sessions")
    public Map<String, Object> createSession(
            @PathVariable String courseKey, @RequestBody Map<String, String> request) {
        Course course = course(courseKey);
        String name = request.getOrDefault("name", "").trim();
        if (name.isEmpty() || name.length() > 128) {
            throw new ResponseStatusException(BAD_REQUEST, "A check-in session name is required.");
        }
        CheckinSession created = sessions.save(new CheckinSession(course, name, Instant.now()));
        return Map.of("success", true, "session", session(created));
    }

    @PostMapping("/course/{courseKey}/sessions/end")
    public Map<String, Object> endSession(@PathVariable String courseKey) {
        Course course = course(courseKey);
        CheckinSession active = session(course, null);
        active.end(null);
        sessions.save(active);
        return Map.of("success", true, "ended", session(active));
    }

    @PostMapping(value = "/mobile/checkin", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> checkin(
            @RequestParam("course") String courseKey,
            @RequestParam(value = "session", required = false) String sessionKey,
            @RequestPart("image") MultipartFile image,
            HttpServletRequest request) throws Exception {
        limiter.check(request.getRemoteAddr());
        verifyImage(image);
        Course course = course(courseKey);
        CheckinSession session = session(course, sessionKey);
        String imageBase64 = Base64.getEncoder().encodeToString(image.getBytes());
        AttendanceResponse result = attendance.recognizeAndRecord(
                session.getId(),
                new RecognitionAttendanceRequest(properties.facebankIdTemplate().formatted(course.getId()), imageBase64),
                requestId(request));
        return Map.of(
                "success", true,
                "faces", List.of(Map.of(
                        "name", result.studentId().toString(),
                        "confidence", result.confidence(),
                        "checked_in", true)),
                "unknown_count", 0,
                "total_checked", attendance.countForSession(session.getId()));
    }

    @GetMapping("/mobile/checkin/result")
    public Map<String, Object> result(
            @RequestParam("course") String courseKey,
            @RequestParam(value = "session", required = false) String sessionKey) {
        Course course = course(courseKey);
        CheckinSession session = session(course, sessionKey);
        List<Long> checked = attendance.studentIdsForSession(session.getId());
        long total = enrollments.findByCourseId(course.getId()).size();
        return Map.of(
                "course", courseKey,
                "total", total,
                "checked_in", checked.size(),
                "unchecked", List.of(),
                "checked_list", checked.stream().map(String::valueOf).toList(),
                "records", List.of(),
                "session_id", legacySessionId(session),
                "session_name", session.getName(),
                "rate", total == 0 ? "0%" : Math.round((checked.size() * 1000.0 / total)) / 10.0 + "%");
    }

    private Map<String, Object> course(Course course) {
        CheckinSession active = sessions.findByCourseIdOrderByStartsAtDesc(course.getId()).stream()
                .filter(session -> "ACTIVE".equals(session.getStatus())).findFirst().orElse(null);
        long total = enrollments.findByCourseId(course.getId()).size();
        long checked = active == null ? 0 : attendance.countForSession(active.getId());
        return Map.of(
                "name", legacyCourseKey(course),
                "description", course.getDescription() == null ? "" : course.getDescription(),
                "total", total,
                "checked_in", checked,
                "rate", total == 0 ? "0%" : Math.round((checked * 1000.0 / total)) / 10.0 + "%");
    }

    private Course course(String legacyKey) {
        return courses.findByLegacyKey("course:" + legacyKey)
                .orElseThrow(() -> new NotFoundException("Legacy course was not imported."));
    }

    private CheckinSession session(Course course, String sessionKey) {
        if (sessionKey != null && !sessionKey.isBlank()) {
            if (sessionKey.startsWith("java-")) {
                Long id = parseJavaSessionId(sessionKey);
                CheckinSession session = sessions.findById(id)
                        .orElseThrow(() -> new NotFoundException("Check-in session not found."));
                if (!session.getCourse().getId().equals(course.getId())) {
                    throw new NotFoundException("Check-in session does not belong to course.");
                }
                return session;
            }
            return sessions.findByLegacyKey("session:" + legacyCourseKey(course) + ":" + sessionKey)
                    .orElseThrow(() -> new NotFoundException("Legacy check-in session was not imported."));
        }
        return sessions.findByCourseIdOrderByStartsAtDesc(course.getId()).stream()
                .filter(item -> "ACTIVE".equals(item.getStatus()))
                .findFirst().orElseThrow(() -> new NotFoundException("No active check-in session."));
    }

    private Map<String, Object> session(CheckinSession session) {
        return Map.of(
                "id", legacySessionId(session),
                "name", session.getName(),
                "status", session.getStatus(),
                "created_at", session.getStartsAt().toString());
    }

    private String legacyCourseKey(Course course) {
        if (course.getLegacyKey() == null || !course.getLegacyKey().startsWith("course:")) {
            throw new NotFoundException("Course has no legacy compatibility mapping.");
        }
        return course.getLegacyKey().substring("course:".length());
    }

    private String legacySessionId(CheckinSession session) {
        String key = session.getLegacyKey();
        return key == null ? "java-" + session.getId() : key.substring(key.lastIndexOf(':') + 1);
    }

    private Long parseJavaSessionId(String value) {
        try {
            return Long.parseLong(value.substring("java-".length()));
        } catch (NumberFormatException exception) {
            throw new ResponseStatusException(BAD_REQUEST, "Invalid session identifier.");
        }
    }

    private void verifyImage(MultipartFile image) {
        if (image.isEmpty()) {
            throw new ResponseStatusException(BAD_REQUEST, "An image is required.");
        }
        if (image.getSize() > properties.maxImageBytes()) {
            throw new ResponseStatusException(PAYLOAD_TOO_LARGE, "Image is too large.");
        }
        String type = image.getContentType();
        if (!MediaType.IMAGE_JPEG_VALUE.equals(type) && !MediaType.IMAGE_PNG_VALUE.equals(type)) {
            throw new ResponseStatusException(BAD_REQUEST, "Only JPEG and PNG images are accepted.");
        }
    }

    private String requestId(HttpServletRequest request) {
        String requestId = request.getHeader("X-Request-ID");
        return requestId == null || requestId.isBlank() || requestId.length() > 128
                ? java.util.UUID.randomUUID().toString() : requestId;
    }
}
