package com.classroomfacecheckin.business.importer;

import com.classroomfacecheckin.business.domain.CheckinSessionRepository;
import com.classroomfacecheckin.business.domain.ClassroomRepository;
import com.classroomfacecheckin.business.domain.CourseRepository;
import com.classroomfacecheckin.business.domain.StudentRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "legacy-verification", name = "enabled", havingValue = "true")
public class LegacyMigrationVerifier implements ApplicationRunner {
    private final ObjectMapper objectMapper;
    private final ClassroomRepository classrooms;
    private final StudentRepository students;
    private final CourseRepository courses;
    private final CheckinSessionRepository sessions;

    @Value("${legacy-verification.root:../data}")
    private String rootValue;

    public LegacyMigrationVerifier(
            ObjectMapper objectMapper,
            ClassroomRepository classrooms,
            StudentRepository students,
            CourseRepository courses,
            CheckinSessionRepository sessions) {
        this.objectMapper = objectMapper;
        this.classrooms = classrooms;
        this.students = students;
        this.courses = courses;
        this.sessions = sessions;
    }

    @Override
    public void run(ApplicationArguments args) {
        System.out.println(verify(Path.of(rootValue)).render());
    }

    public VerificationReport verify(Path suppliedRoot) {
        Path root = suppliedRoot.toAbsolutePath().normalize();
        SourceCounts source = scan(root);
        return new VerificationReport(
                root,
                source,
                classrooms.countByLegacyKeyStartingWith("class:"),
                students.countByLegacyKeyStartingWith("student:"),
                courses.countByLegacyKeyStartingWith("course:"),
                sessions.countByLegacyKeyStartingWith("session:"));
    }

    private SourceCounts scan(Path root) {
        SourceCounts counts = new SourceCounts();
        if (!Files.isDirectory(root) || Files.isSymbolicLink(root)) {
            counts.unmappable.add("Legacy data root is not a readable directory: " + root);
            return counts;
        }
        JsonNode classes = read(root.resolve("classes.json"), counts);
        if (classes != null) {
            if (!classes.isArray()) counts.unmappable.add("classes.json must be a JSON array.");
            else for (JsonNode value : classes) addClass(value, counts, "classes.json");
        }
        JsonNode students = read(root.resolve("students_index.json"), counts);
        if (students != null) {
            if (!students.isObject()) counts.unmappable.add("students_index.json must be a JSON object.");
            else {
                students.fields().forEachRemaining(entry -> {
                    if (!entry.getKey().isBlank() && entry.getValue().isObject()) {
                        counts.students++;
                        addClass(entry.getValue().get("class"), counts, "students_index.json");
                    } else counts.unmappable.add("Invalid student index entry: " + entry.getKey());
                });
            }
        }
        Path coursesRoot = root.resolve("courses");
        if (!Files.isDirectory(coursesRoot) || Files.isSymbolicLink(coursesRoot)) return counts;
        try (var entries = Files.list(coursesRoot)) {
            for (Path course : entries.filter(Files::isDirectory).filter(path -> !Files.isSymbolicLink(path)).toList()) {
                counts.courses++;
                JsonNode info = readOptional(course.resolve("meeting_info.json"), counts);
                if (info != null && info.isObject() && info.path("classes").isArray()) {
                    for (JsonNode classroom : info.path("classes")) addClass(classroom, counts, course.getFileName().toString());
                }
                JsonNode sessionFile = readOptional(course.resolve("sessions.json"), counts);
                if (sessionFile != null && sessionFile.path("sessions").isArray()) {
                    for (JsonNode session : sessionFile.path("sessions")) {
                        if (session.isObject() && session.path("id").isTextual() && !session.path("id").asText().isBlank()) counts.sessions++;
                        else counts.unmappable.add("Invalid session in " + course.getFileName());
                    }
                }
                JsonNode attendance = readOptional(course.resolve("attendance.json"), counts);
                if (attendance != null) {
                    if (attendance.isArray()) counts.attendance += attendance.size();
                    else counts.unmappable.add("attendance.json must be a JSON array in " + course.getFileName());
                }
            }
        } catch (IOException exception) {
            counts.unmappable.add("Cannot list legacy courses directory: " + exception.getMessage());
        }
        return counts;
    }

    private void addClass(JsonNode node, SourceCounts counts, String location) {
        if (node != null && node.isTextual() && !node.asText().isBlank()) counts.classrooms.add(node.asText().trim());
        else counts.unmappable.add("Invalid classroom reference in " + location);
    }

    private JsonNode read(Path path, SourceCounts counts) {
        if (!Files.isRegularFile(path) || Files.isSymbolicLink(path)) {
            counts.unmappable.add("Missing or unsafe legacy file: " + path.getFileName());
            return null;
        }
        return readOptional(path, counts);
    }

    private JsonNode readOptional(Path path, SourceCounts counts) {
        if (!Files.isRegularFile(path) || Files.isSymbolicLink(path)) return null;
        try {
            return objectMapper.readTree(path.toFile());
        } catch (IOException exception) {
            counts.unmappable.add("Cannot parse " + path.getFileName() + ": " + exception.getMessage());
            return null;
        }
    }

    public record VerificationReport(
            Path root,
            SourceCounts source,
            long importedClassrooms,
            long importedStudents,
            long importedCourses,
            long importedSessions) {
        public String render() {
            return """
                    Legacy migration verification root=%s
                    classrooms source=%d imported=%d status=%s
                    students source=%d imported=%d status=%s
                    courses source=%d imported=%d status=%s
                    sessions source=%d imported=%d status=%s
                    attendance source=%d imported=UNSUPPORTED status=NOT_MIGRATED
                    unmappable_records=%d%s
                    """.formatted(
                    root,
                    source.classrooms.size(), importedClassrooms, status(source.classrooms.size(), importedClassrooms),
                    source.students, importedStudents, status(source.students, importedStudents),
                    source.courses, importedCourses, status(source.courses, importedCourses),
                    source.sessions, importedSessions, status(source.sessions, importedSessions),
                    source.attendance,
                    source.unmappable.size(),
                    source.unmappable.isEmpty() ? "" : System.lineSeparator() + String.join(System.lineSeparator(), source.unmappable));
        }

        private static String status(long source, long imported) {
            return source == imported ? "MATCH" : "MISMATCH";
        }
    }

    public static final class SourceCounts {
        private final Set<String> classrooms = new LinkedHashSet<>();
        private long students;
        private long courses;
        private long sessions;
        private long attendance;
        private final List<String> unmappable = new java.util.ArrayList<>();
    }
}
