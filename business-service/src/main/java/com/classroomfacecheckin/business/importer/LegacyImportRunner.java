package com.classroomfacecheckin.business.importer;

import com.classroomfacecheckin.business.domain.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
@ConditionalOnProperty(prefix = "legacy-import", name = "enabled", havingValue = "true")
public class LegacyImportRunner implements ApplicationRunner {
    private final ObjectMapper objectMapper; private final ClassroomRepository classrooms; private final StudentRepository students;
    private final StudentPhotoRepository photos; private final CourseRepository courses; private final EnrollmentRepository enrollments; private final CheckinSessionRepository sessions;
    @Value("${legacy-import.root:../data}") private String rootValue;
    @Value("${legacy-import.dry-run:true}") private boolean dryRun;
    public LegacyImportRunner(ObjectMapper objectMapper, ClassroomRepository classrooms, StudentRepository students, StudentPhotoRepository photos, CourseRepository courses, EnrollmentRepository enrollments, CheckinSessionRepository sessions) {
        this.objectMapper = objectMapper; this.classrooms = classrooms; this.students = students; this.photos = photos; this.courses = courses; this.enrollments = enrollments; this.sessions = sessions;
    }
    @Override @Transactional public void run(ApplicationArguments args) throws Exception {
        ImportReport report = importData(Path.of(rootValue), dryRun);
        System.out.println(report.render());
    }
    @Transactional public ImportReport importData(Path suppliedRoot, boolean simulate) {
        Path root = suppliedRoot.toAbsolutePath().normalize();
        ImportReport report = new ImportReport(simulate, root);
        if (!Files.isDirectory(root) || Files.isSymbolicLink(root)) { report.unresolved("Legacy data root is not a readable directory: " + root); return report; }
        Map<String, Classroom> classroomByName = new LinkedHashMap<>();
        loadClasses(root, classroomByName, report, simulate);
        Map<String, Student> studentByName = loadStudents(root, classroomByName, report, simulate);
        loadCourses(root, classroomByName, studentByName, report, simulate);
        return report;
    }
    private void loadClasses(Path root, Map<String, Classroom> result, ImportReport report, boolean simulate) {
        JsonNode classes = read(root.resolve("classes.json"), report);
        if (classes == null) return;
        if (!classes.isArray()) { report.unresolved("classes.json must be a JSON array."); return; }
        for (JsonNode value : classes) if (value.isTextual()) ensureClass(value.asText(), result, report, simulate);
        else report.unresolved("classes.json contains a non-string entry.");
    }
    private Map<String, Student> loadStudents(Path root, Map<String, Classroom> classroomByName, ImportReport report, boolean simulate) {
        Map<String, Student> result = new LinkedHashMap<>(); JsonNode index = read(root.resolve("students_index.json"), report);
        if (index == null) return result;
        if (!index.isObject()) { report.unresolved("students_index.json must be a JSON object."); return result; }
        Iterator<Map.Entry<String, JsonNode>> entries = index.fields();
        while (entries.hasNext()) {
            Map.Entry<String, JsonNode> entry = entries.next(); String name = entry.getKey().trim(); JsonNode metadata = entry.getValue();
            if (name.isEmpty() || !metadata.isObject()) { report.unresolved("Invalid student index entry: " + entry.getKey()); continue; }
            String className = text(metadata, "class"); Classroom classroom = className.isBlank() ? null : ensureClass(className, classroomByName, report, simulate);
            Student student = students.findByLegacyKey("student:" + name).orElse(null);
            if (student == null) {
                student = new Student(legacyCode("STUDENT", name), textOr(metadata, "name", name), classroom, text(metadata, "phone"));
                student.setLegacyKey("student:" + name); report.created("students");
                if (!simulate) student = students.save(student);
            } else report.existing("students");
            result.put(name, student);
            importGlobalPhoto(root, name, student, report, simulate);
        }
        return result;
    }
    private void loadCourses(Path root, Map<String, Classroom> classroomByName, Map<String, Student> studentByName, ImportReport report, boolean simulate) {
        Path coursesRoot = root.resolve("courses");
        if (!Files.isDirectory(coursesRoot) || Files.isSymbolicLink(coursesRoot)) return;
        try (var paths = Files.list(coursesRoot)) {
            for (Path directory : paths.filter(Files::isDirectory).filter(path -> !Files.isSymbolicLink(path)).sorted().toList()) {
                String directoryName = directory.getFileName().toString(); JsonNode info = readOptional(directory.resolve("meeting_info.json"), report);
                String courseName = info == null ? directoryName : textOr(info, "name", directoryName);
                Course course = courses.findByLegacyKey("course:" + directoryName).orElse(null);
                if (course == null) { course = new Course(legacyCode("COURSE", directoryName), courseName, info == null ? "" : text(info, "description")); course.setLegacyKey("course:" + directoryName); report.created("courses"); if (!simulate) course = courses.save(course); } else report.existing("courses");
                JsonNode classNames = info == null ? null : info.get("classes");
                if (classNames != null && classNames.isArray()) {
                    for (JsonNode className : classNames) if (className.isTextual()) {
                        Classroom classroom = ensureClass(className.asText(), classroomByName, report, simulate);
                        if (classroom != null) course.getClassrooms().add(classroom);
                    }
                }
                if (!simulate) courses.save(course);
                enrollIndexedStudents(root, course, directoryName, studentByName, report, simulate);
                loadSessions(directory, directoryName, course, report, simulate);
            }
        } catch (IOException exception) { report.unresolved("Cannot list legacy courses directory: " + exception.getMessage()); }
    }
    private void enrollIndexedStudents(Path root, Course course, String courseName, Map<String, Student> studentsByName, ImportReport report, boolean simulate) {
        Path indexPath = root.resolve("students_index.json");
        JsonNode index = readOptional(indexPath, report);
        if (index == null || !index.isObject()) return;
        Iterator<Map.Entry<String, JsonNode>> entries = index.fields();
        while (entries.hasNext()) {
            Map.Entry<String, JsonNode> entry = entries.next();
            Student student = studentsByName.get(entry.getKey());
            JsonNode courseNames = entry.getValue().get("courses");
            if (student == null || courseNames == null || !courseNames.isArray()) continue;
            boolean enrolled = false;
            for (JsonNode name : courseNames) if (name.isTextual() && courseName.equals(name.asText())) { enrolled = true; break; }
            if (!enrolled) continue;
            if (simulate) { report.created("enrollments"); continue; }
            if (enrollments.findByCourseIdAndStudentId(course.getId(), student.getId()).isPresent()) { report.existing("enrollments"); continue; }
            report.created("enrollments");
            enrollments.save(new Enrollment(course, student));
        }
    }
    private void loadSessions(Path directory, String courseKey, Course course, ImportReport report, boolean simulate) {
        JsonNode data = readOptional(directory.resolve("sessions.json"), report); if (data == null || !data.isObject()) return;
        String active = text(data, "active"); JsonNode list = data.get("sessions"); if (list == null || !list.isArray()) return;
        for (JsonNode item : list) {
            String id = text(item, "id"); String name = textOr(item, "name", "Legacy session " + id);
            if (id.isBlank()) { report.unresolved("Session without an id in " + courseKey); continue; }
            if (sessions.findByLegacyKey("session:" + courseKey + ":" + id).isPresent()) { report.existing("sessions"); continue; }
            CheckinSession session = CheckinSession.imported(course, name, instant(text(item, "created_at")), id.equals(active));
            session.setLegacyKey("session:" + courseKey + ":" + id); report.created("sessions"); if (!simulate) sessions.save(session);
        }
    }
    private Classroom ensureClass(String rawName, Map<String, Classroom> values, ImportReport report, boolean simulate) {
        String name = rawName.trim(); if (name.isEmpty()) { report.unresolved("Blank classroom name."); return null; }
        Classroom existing = values.get(name); if (existing != null) return existing;
        existing = classrooms.findByLegacyKey("class:" + name).orElse(null);
        if (existing == null) { existing = new Classroom(legacyCode("CLASS", name), name, null); existing.setLegacyKey("class:" + name); report.created("classrooms"); if (!simulate) existing = classrooms.save(existing); } else report.existing("classrooms");
        values.put(name, existing); return existing;
    }
    private void importGlobalPhoto(Path root, String name, Student student, ImportReport report, boolean simulate) {
        Path photosRoot = root.resolve("students").resolve("photos");
        if (!Files.isDirectory(photosRoot)) return;
        for (String extension : List.of(".jpg", ".jpeg", ".png", ".bmp")) {
            Path photo = photosRoot.resolve(name + extension).normalize();
            if (photo.startsWith(photosRoot) && Files.isRegularFile(photo) && !Files.isSymbolicLink(photo)) {
                String uri = "legacy://students/photos/" + photo.getFileName();
                if (!simulate && photos.findByStudentIdAndStorageUri(student.getId(), uri).isPresent()) report.existing("photoMetadata");
                else { report.created("photoMetadata"); if (!simulate) photos.save(new StudentPhoto(student, uri, null, true)); }
                return;
            }
        }
    }
    private JsonNode read(Path path, ImportReport report) { if (!Files.isRegularFile(path) || Files.isSymbolicLink(path)) { report.unresolved("Missing or unsafe legacy file: " + path.getFileName()); return null; } return readOptional(path, report); }
    private JsonNode readOptional(Path path, ImportReport report) { if (!Files.isRegularFile(path) || Files.isSymbolicLink(path)) return null; try { return objectMapper.readTree(path.toFile()); } catch (IOException exception) { report.unresolved("Cannot parse " + path.getFileName() + ": " + exception.getMessage()); return null; } }
    private static String text(JsonNode node, String field) { JsonNode value = node.get(field); return value != null && value.isTextual() ? value.asText().trim() : ""; }
    private static String textOr(JsonNode node, String field, String fallback) { String value = text(node, field); return value.isBlank() ? fallback : value; }
    private static Instant instant(String value) { try { return value.isBlank() ? Instant.now() : Instant.parse(value); } catch (DateTimeParseException ignored) { return Instant.now(); } }
    private static String legacyCode(String prefix, String value) { try { byte[] hash = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)); StringBuilder result = new StringBuilder(prefix).append("-"); for (int i = 0; i < 8; i++) result.append(String.format("%02x", hash[i])); return result.toString(); } catch (Exception exception) { throw new IllegalStateException("Cannot generate legacy identifier.", exception); } }
    public static final class ImportReport {
        private final boolean dryRun; private final Path root; private final Map<String, Integer> created = new LinkedHashMap<>(); private final Map<String, Integer> existing = new LinkedHashMap<>(); private final List<String> unresolved = new ArrayList<>();
        ImportReport(boolean dryRun, Path root) { this.dryRun = dryRun; this.root = root; }
        void created(String type) { created.merge(type, 1, Integer::sum); } void existing(String type) { existing.merge(type, 1, Integer::sum); } void unresolved(String detail) { unresolved.add(detail); }
        public String render() { return "Legacy import " + (dryRun ? "dry-run" : "completed") + " root=" + root + " created=" + created + " existing=" + existing + " unresolved=" + unresolved.size() + (unresolved.isEmpty() ? "" : System.lineSeparator() + String.join(System.lineSeparator(), unresolved)); }
    }
}
